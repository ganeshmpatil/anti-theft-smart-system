"""CPU thermal monitoring providers."""

import logging

from .interfaces import IThermalProvider

logger = logging.getLogger(__name__)


class SysfsThermalProvider(IThermalProvider):
    """Production provider: reads CPU temperature from sysfs thermal zone."""

    def __init__(self, thermal_zone: int = 0):
        self._path = f"/sys/class/thermal/thermal_zone{thermal_zone}/temp"

    def get_cpu_temp(self) -> float:
        try:
            with open(self._path) as f:
                millidegrees = int(f.read().strip())
            return millidegrees / 1000.0
        except (FileNotFoundError, ValueError):
            logger.warning("Could not read thermal zone, returning default 50C")
            return 50.0


class MockThermalProvider(IThermalProvider):
    """Simulation provider: returns a configurable temperature."""

    def __init__(self, initial_temp: float = 55.0):
        self._temp = initial_temp

    def set_temp(self, temp: float):
        """Set mock temperature (called from debug API)."""
        self._temp = temp
        logger.info("Mock CPU temp set to %.1fC", temp)

    def get_cpu_temp(self) -> float:
        return self._temp
