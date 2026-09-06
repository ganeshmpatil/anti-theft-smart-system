"""Factory to create the correct providers based on configuration mode."""

import logging
from typing import NamedTuple

from .interfaces import (
    ICameraProvider,
    IPowerProvider,
    ITamperProvider,
    IThermalProvider,
    IWatchdogProvider,
)
from .camera_provider import USBCameraProvider, VideoFileProvider, WebcamSplitProvider
from .tamper_provider import GPIOTamperProvider, MockTamperProvider
from .thermal_provider import SysfsThermalProvider, MockThermalProvider
from .power_provider import SystemPowerProvider, MockPowerProvider
from .watchdog_provider import HardwareWatchdogProvider, MockWatchdogProvider

logger = logging.getLogger(__name__)


class Providers(NamedTuple):
    cam1: ICameraProvider
    cam2: ICameraProvider
    tamper: ITamperProvider
    thermal: IThermalProvider
    power: IPowerProvider
    watchdog: IWatchdogProvider


def create_providers(config: dict) -> Providers:
    """Create all hardware providers based on the config mode.

    Modes:
      - 'simulation': video files + all mock providers
      - 'webcam': laptop webcam split + mock providers
      - 'production': USB cameras + real hardware providers
    """
    mode = config.get("mode", "simulation")
    cam_config = config.get("camera", {}).get(mode, {})
    sim_config = config.get("simulation", {})

    logger.info("Creating providers in '%s' mode", mode)

    if mode == "simulation":
        cam1 = VideoFileProvider(
            video_path=cam_config.get("cam1_source", "test_videos/intrusion/person_walk_day.mp4"),
            camera_id="cam_front",
            loop=cam_config.get("loop_video", True),
            playback_speed=cam_config.get("playback_speed", 1.0),
        )
        cam2 = VideoFileProvider(
            video_path=cam_config.get("cam2_source", "test_videos/false_positives/empty_field_day.mp4"),
            camera_id="cam_rear",
            loop=cam_config.get("loop_video", True),
            playback_speed=cam_config.get("playback_speed", 1.0),
        )
        tamper = MockTamperProvider()
        thermal = MockThermalProvider(sim_config.get("mock_cpu_temp", 55.0))
        power = MockPowerProvider(
            battery_pct=sim_config.get("mock_battery_pct", 72),
            power_source=sim_config.get("mock_power_source", "mains"),
        )
        watchdog = MockWatchdogProvider()

    elif mode == "webcam":
        device_index = cam_config.get("cam1_source", 0)
        split_mode = cam_config.get("split_mode", True)
        if split_mode:
            cam1 = WebcamSplitProvider(device_index, "cam_front", half="left")
            cam2 = WebcamSplitProvider(device_index, "cam_rear", half="right")
        else:
            # Full-frame mode: use entire webcam as cam_front, cam_rear is a dummy
            from .camera_provider import WebcamFullProvider
            cam1 = WebcamFullProvider(device_index, "cam_front")
            cam2 = WebcamFullProvider(device_index, "cam_rear")
        tamper = MockTamperProvider()
        thermal = MockThermalProvider(sim_config.get("mock_cpu_temp", 55.0))
        power = MockPowerProvider(
            battery_pct=sim_config.get("mock_battery_pct", 72),
            power_source=sim_config.get("mock_power_source", "mains"),
        )
        watchdog = MockWatchdogProvider()

    elif mode == "production":
        cam1 = USBCameraProvider(
            device_path=cam_config.get("cam1_source", "/dev/video0"),
            camera_id="cam_front",
        )
        cam2 = USBCameraProvider(
            device_path=cam_config.get("cam2_source", "/dev/video2"),
            camera_id="cam_rear",
        )
        tamper = GPIOTamperProvider(gpio_pin=config.get("gpio", {}).get("tamper_pin", 17))
        thermal = SysfsThermalProvider()
        power = SystemPowerProvider()
        watchdog = HardwareWatchdogProvider()

    else:
        raise ValueError(f"Unknown mode: {mode}")

    return Providers(
        cam1=cam1,
        cam2=cam2,
        tamper=tamper,
        thermal=thermal,
        power=power,
        watchdog=watchdog,
    )
