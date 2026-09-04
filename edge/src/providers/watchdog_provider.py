"""Hardware watchdog and USB health providers."""

import logging
import os

from .interfaces import IWatchdogProvider

logger = logging.getLogger(__name__)


class HardwareWatchdogProvider(IWatchdogProvider):
    """Production provider: pings /dev/watchdog and resets USB ports via sysfs."""

    def __init__(self):
        self._wdt_fd = None

    def open(self):
        try:
            self._wdt_fd = os.open("/dev/watchdog", os.O_WRONLY)
            logger.info("Hardware watchdog opened")
        except OSError:
            logger.warning("Hardware watchdog not available — skipping")

    def ping(self) -> None:
        if self._wdt_fd is not None:
            try:
                os.write(self._wdt_fd, b"1")
            except OSError:
                logger.error("Failed to ping hardware watchdog")

    def reset_usb_port(self, port: str) -> bool:
        """Reset a USB port by unbinding and rebinding its sysfs driver.

        port: sysfs USB device path, e.g., '1-1' or '1-1.2'
        """
        unbind_path = "/sys/bus/usb/drivers/usb/unbind"
        bind_path = "/sys/bus/usb/drivers/usb/bind"
        try:
            with open(unbind_path, "w") as f:
                f.write(port)
            import time
            time.sleep(1)
            with open(bind_path, "w") as f:
                f.write(port)
            logger.info("USB port %s reset successfully", port)
            return True
        except OSError:
            logger.error("Failed to reset USB port %s", port)
            return False

    def close(self):
        if self._wdt_fd is not None:
            # Write 'V' (magic close) to prevent immediate reboot
            os.write(self._wdt_fd, b"V")
            os.close(self._wdt_fd)
            self._wdt_fd = None


class MockWatchdogProvider(IWatchdogProvider):
    """Simulation provider: logs pings, does not interact with hardware."""

    def __init__(self):
        self._ping_count = 0

    def ping(self) -> None:
        self._ping_count += 1

    def reset_usb_port(self, port: str) -> bool:
        logger.info("Mock USB reset on port %s (ping count: %d)", port, self._ping_count)
        return True
