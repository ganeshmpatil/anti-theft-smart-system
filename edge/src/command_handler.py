"""Handles commands received from the mobile app via MQTT."""

import logging
import threading

from .ota_updater import OTAUpdater

logger = logging.getLogger(__name__)


class CommandHandler:
    """Processes arm/disarm/snapshot/reboot/live_feed/ota_update commands."""

    def __init__(self, current_version: str = "0.0.0"):
        self._armed = threading.Event()
        self._armed.set()  # armed by default
        self._snapshot_requested = threading.Event()
        self._reboot_requested = threading.Event()
        self._live_feed_active = threading.Event()
        self._live_feed_duration = 30  # seconds
        self._live_feed_fps = 3
        self._live_feed_camera = "cam_front"
        self._lock = threading.Lock()
        self._ota = OTAUpdater(current_version=current_version)

    def handle(self, action: str, params: dict):
        """Process an incoming command.

        Args:
            action: command name (arm, disarm, snapshot, reboot, config_update)
            params: command parameters
        """
        logger.info("Command received: action=%s", action)

        if action == "arm":
            self._armed.set()
            logger.info("Surveillance ARMED")

        elif action == "disarm":
            self._armed.clear()
            logger.info("Surveillance DISARMED")

        elif action == "snapshot":
            self._snapshot_requested.set()
            logger.info("Snapshot requested")

        elif action == "reboot":
            self._reboot_requested.set()
            logger.warning("Reboot requested")

        elif action == "live_feed_start":
            self._live_feed_duration = params.get("duration", 30)
            self._live_feed_fps = params.get("fps", 3)
            self._live_feed_camera = params.get("camera_id", "cam_front")
            self._live_feed_active.set()
            logger.info("Live feed requested: %ds at %dfps from %s",
                        self._live_feed_duration, self._live_feed_fps, self._live_feed_camera)

        elif action == "live_feed_stop":
            self._live_feed_active.clear()
            logger.info("Live feed stopped by command")

        elif action == "ota_update":
            self._ota.handle_update_command(params)

        elif action == "config_update":
            logger.info("Config update received")

        else:
            logger.warning("Unknown command: %s", action)

    @property
    def is_armed(self) -> bool:
        return self._armed.is_set()

    def consume_snapshot_request(self) -> bool:
        """Atomically check and clear the snapshot flag. Thread-safe."""
        with self._lock:
            if self._snapshot_requested.is_set():
                self._snapshot_requested.clear()
                return True
            return False

    @property
    def snapshot_requested(self) -> bool:
        """Check and clear the snapshot flag. Use consume_snapshot_request() for thread safety."""
        return self.consume_snapshot_request()

    @property
    def reboot_requested(self) -> bool:
        return self._reboot_requested.is_set()

    @property
    def live_feed_active(self) -> bool:
        return self._live_feed_active.is_set()

    @property
    def live_feed_duration(self) -> int:
        return self._live_feed_duration

    @property
    def live_feed_fps(self) -> int:
        return self._live_feed_fps

    @property
    def live_feed_camera(self) -> str:
        return self._live_feed_camera

    def stop_live_feed(self):
        self._live_feed_active.clear()

    def wait_for_arm(self, timeout: float = None) -> bool:
        """Block until the system is armed. Returns True if armed."""
        return self._armed.wait(timeout=timeout)
