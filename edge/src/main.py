"""Entry point for the Anti-Theft Smart System edge daemon.

Usage:
    python -m src.main                           # default config
    python -m src.main --config path/to/config.yaml
    python -m src.main --mode simulation         # override mode
"""

import argparse
import logging
import signal
import sys
from pathlib import Path

import yaml

from .alert_manager import AlertManager
from .command_handler import CommandHandler
from .detection.exclusion_zones import ExclusionZoneFilter
from .detection.human_detector import HumanDetector
from .mqtt_client import MQTTClient
from .providers import create_providers
from .surveillance_loop import SurveillanceLoop

logger = logging.getLogger("atss")


def setup_logging(debug: bool = False):
    level = logging.DEBUG if debug else logging.INFO
    fmt = "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s"
    logging.basicConfig(level=level, format=fmt, datefmt="%Y-%m-%d %H:%M:%S")


def load_config(config_path: str) -> dict:
    path = Path(config_path)
    if not path.exists():
        logger.error("Config file not found: %s", config_path)
        sys.exit(1)
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="Anti-Theft Smart System Edge Daemon")
    parser.add_argument("--config", default="config/device_config.yaml",
                        help="Path to config file")
    parser.add_argument("--mode", choices=["simulation", "webcam", "production"],
                        help="Override mode from config")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    setup_logging(args.debug)
    logger.info("=" * 60)
    logger.info("  Anti-Theft Smart System — Edge Daemon")
    logger.info("=" * 60)

    # Load config
    config = load_config(args.config)
    if args.mode:
        config["mode"] = args.mode
    mode = config.get("mode", "simulation")
    logger.info("Mode: %s", mode)

    device_cfg = config.get("device", {})
    device_id = device_cfg.get("device_id", "FARM-SIM-001")
    farm_id = device_cfg.get("farm_id", "farm_test")
    logger.info("Device: %s | Farm: %s", device_id, farm_id)

    # Create hardware providers
    providers = create_providers(config)
    logger.info("Providers created")

    # Open cameras
    if not providers.cam1.open():
        logger.error("Failed to open camera 1 — exiting")
        sys.exit(1)
    if not providers.cam2.open():
        logger.warning("Failed to open camera 2 — running single camera mode")

    # Load YOLO model
    det_cfg = config.get("detection", {})
    model_path = det_cfg.get("model_path", "models/yolov5n.onnx")
    confidence = det_cfg.get("confidence_threshold", 0.6)
    backend = det_cfg.get("backend", "onnx")
    input_size = det_cfg.get("input_size", 0)
    detector = HumanDetector(model_path=model_path, confidence_threshold=confidence,
                             backend=backend, input_size=input_size)
    if not detector.load():
        logger.error("Failed to load YOLO model at %s (backend=%s) — exiting", model_path, backend)
        sys.exit(1)
    logger.info("YOLO model loaded: %s (backend=%s, input=%d, threshold=%.2f)",
                model_path, backend, detector._input_size, confidence)

    # Initialize MQTT client
    mqtt_cfg = config.get("mqtt", {})
    mqtt_client = MQTTClient(
        broker=mqtt_cfg.get("broker", "localhost"),
        port=mqtt_cfg.get("port", 1883),
        device_id=device_id,
        farm_id=farm_id,
        username=mqtt_cfg.get("username", ""),
        password=mqtt_cfg.get("password", ""),
        tls_enabled=mqtt_cfg.get("tls_enabled", False),
        ca_cert=mqtt_cfg.get("ca_cert", ""),
        client_cert=mqtt_cfg.get("client_cert", ""),
        client_key=mqtt_cfg.get("client_key", ""),
    )

    mqtt_connected = mqtt_client.connect()
    if mqtt_connected:
        logger.info("MQTT connected to %s:%d", mqtt_cfg.get("broker"), mqtt_cfg.get("port"))
    else:
        logger.warning("MQTT connection failed — will retry in background")

    # Initialize alert manager
    det_cfg = config.get("detection", {})
    alert_manager = AlertManager(
        device_id=device_id,
        farm_id=farm_id,
        temporal_frames=det_cfg.get("temporal_frames", 3),
        cooldown_seconds=det_cfg.get("cooldown_seconds", 300),
        capture_window_seconds=det_cfg.get("capture_window_seconds", 3.0),
    )

    # Start tamper monitoring (GPIO polling thread in production mode)
    if hasattr(providers.tamper, "start"):
        providers.tamper.start()
        logger.info("Tamper monitor started")

    # Initialize command handler
    command_handler = CommandHandler()
    mqtt_client.on_command(command_handler.handle)

    # Initialize exclusion zone filter
    exclusion_filter = ExclusionZoneFilter()
    zones_cfg = config.get("exclusion_zones", {})
    for cam_id, zones in zones_cfg.items():
        exclusion_filter.set_zones(cam_id, zones)

    # Build and run surveillance loop
    loop = SurveillanceLoop(
        cam1=providers.cam1,
        cam2=providers.cam2,
        tamper=providers.tamper,
        thermal=providers.thermal,
        power=providers.power,
        watchdog=providers.watchdog,
        detector=detector,
        mqtt_client=mqtt_client,
        alert_manager=alert_manager,
        command_handler=command_handler,
        exclusion_filter=exclusion_filter,
        config=config,
    )

    # Handle SIGTERM/SIGINT gracefully
    def signal_handler(sig, frame):
        logger.info("Signal %s received — shutting down", sig)
        loop.stop()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    logger.info("Starting surveillance loop...")
    try:
        loop.run()
    finally:
        # Cleanup — always runs even if loop.run() raises
        logger.info("Shutting down...")
        if hasattr(providers.tamper, "stop"):
            providers.tamper.stop()
        providers.cam1.release()
        providers.cam2.release()
        mqtt_client.disconnect()
        logger.info("Edge daemon stopped")


if __name__ == "__main__":
    main()
