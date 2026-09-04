"""Handles commands received from the mobile app via MQTT."""

import logging
import threading

logger = logging.getLogger(__name__)


class CommandHandler:
    """Processes arm/disarm/snapshot/reboot commands."""

    def __init__(self):
        self._armed = threading.Event()
        self._armed.set()  # armed by default
        self._snapshot_requested = threading.Event()
        self._reboot_requested = threading.Event()

    def handle(self, action: str, params: dict):
        """Process an incoming command.

        Args:
            action: command name (arm, disarm, snapshot, reboot, config_update)
            params: command parameters
        """
        logger.info("Command received: action=%s params=%s", action, params)

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

        elif action == "config_update":
            logger.info("Config update received: %s", params)
            # Config updates are handled by the surveillance loop
            # by re-reading the config. For now, just log it.

        else:
            logger.warning("Unknown command: %s", action)

    @property
    def is_armed(self) -> bool:
        return self._armed.is_set()

    @property
    def snapshot_requested(self) -> bool:
        """Check and clear the snapshot flag."""
        if self._snapshot_requested.is_set():
            self._snapshot_requested.clear()
            return True
        return False

    @property
    def reboot_requested(self) -> bool:
        return self._reboot_requested.is_set()

    def wait_for_arm(self, timeout: float = None) -> bool:
        """Block until the system is armed. Returns True if armed."""
        return self._armed.wait(timeout=timeout)
