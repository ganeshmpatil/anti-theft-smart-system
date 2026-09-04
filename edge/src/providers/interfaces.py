"""Abstract interfaces for hardware providers.

All hardware interactions go through these interfaces. Production providers
talk to real hardware (USB cameras, GPIO, sysfs). Simulation providers
return mock data or read from video files. The application code never
knows the difference.
"""

from abc import ABC, abstractmethod
from typing import Callable, Optional

import numpy as np


class ICameraProvider(ABC):
    """Captures frames from a camera source."""

    @abstractmethod
    def open(self) -> bool:
        """Open the camera. Returns True if successful."""

    @abstractmethod
    def read_frame(self) -> Optional[np.ndarray]:
        """Read a frame at inference resolution (640x480). Returns None on failure."""

    @abstractmethod
    def read_hires_frame(self) -> Optional[np.ndarray]:
        """Read a high-resolution frame (1280x720) for alert snapshots."""

    @abstractmethod
    def is_alive(self) -> bool:
        """Check if the camera is still producing frames."""

    @abstractmethod
    def release(self) -> None:
        """Release the camera resource."""

    @property
    @abstractmethod
    def camera_id(self) -> str:
        """Identifier for this camera (e.g., 'cam_front', 'cam_rear')."""


class ITamperProvider(ABC):
    """Detects physical tampering (device moved/tilted)."""

    @abstractmethod
    def is_tampered(self) -> bool:
        """Check if tamper has been detected since last call."""

    @abstractmethod
    def on_tamper(self, callback: Callable[[], None]) -> None:
        """Register a callback to be invoked on tamper detection."""


class IThermalProvider(ABC):
    """Reads CPU temperature and determines throttle state."""

    @abstractmethod
    def get_cpu_temp(self) -> float:
        """Return current CPU temperature in Celsius."""

    def get_throttle_state(self) -> str:
        """Return throttle state based on temperature thresholds."""
        temp = self.get_cpu_temp()
        if temp >= 85:
            return "critical"
        if temp >= 75:
            return "throttled"
        return "normal"


class IPowerProvider(ABC):
    """Monitors power source and battery status."""

    @abstractmethod
    def get_battery_pct(self) -> int:
        """Return battery percentage (0-100)."""

    @abstractmethod
    def get_power_source(self) -> str:
        """Return 'mains' or 'battery'."""

    def is_power_cut(self) -> bool:
        """Check if running on battery (mains power lost)."""
        return self.get_power_source() == "battery"


class IWatchdogProvider(ABC):
    """Hardware watchdog and USB device health monitoring."""

    @abstractmethod
    def ping(self) -> None:
        """Ping the hardware watchdog to prevent system reboot."""

    @abstractmethod
    def reset_usb_port(self, port: str) -> bool:
        """Reset a USB port. Returns True if successful."""
