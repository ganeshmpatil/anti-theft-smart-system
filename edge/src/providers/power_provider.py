"""Power monitoring providers."""

import logging

from .interfaces import IPowerProvider

logger = logging.getLogger(__name__)


class SystemPowerProvider(IPowerProvider):
    """Production provider: checks power source and battery status.

    On Orange Pi with a UPS power bank, we detect mains loss by checking
    if the USB power input voltage drops (via ADC or a simple GPIO pin
    connected to the mains adapter's 5V output through a voltage divider).
    """

    def __init__(self, mains_detect_gpio: int = 27):
        self._gpio_pin = mains_detect_gpio
        self._gpio_path = f"/sys/class/gpio/gpio{mains_detect_gpio}/value"

    def get_battery_pct(self) -> int:
        # Most USB power banks don't expose battery level via USB.
        # Without I2C battery gauge, return -1 (unknown).
        return -1

    def get_power_source(self) -> str:
        try:
            with open(self._gpio_path) as f:
                val = f.read().strip()
            return "mains" if val == "1" else "battery"
        except FileNotFoundError:
            return "mains"


class MockPowerProvider(IPowerProvider):
    """Simulation provider: returns configurable power state."""

    def __init__(self, battery_pct: int = 72, power_source: str = "mains"):
        self._battery_pct = battery_pct
        self._power_source = power_source

    def set_battery_pct(self, pct: int):
        self._battery_pct = pct

    def set_power_source(self, source: str):
        self._power_source = source
        logger.info("Mock power source set to %s", source)

    def get_battery_pct(self) -> int:
        return self._battery_pct

    def get_power_source(self) -> str:
        return self._power_source
