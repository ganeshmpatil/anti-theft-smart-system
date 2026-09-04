"""Tamper detection providers."""

import logging
import threading
from typing import Callable, Optional

from .interfaces import ITamperProvider

logger = logging.getLogger(__name__)


class GPIOTamperProvider(ITamperProvider):
    """Production provider: reads tamper switch state from GPIO pin."""

    def __init__(self, gpio_pin: int = 17):
        self._gpio_pin = gpio_pin
        self._tampered = False
        self._callback: Optional[Callable[[], None]] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start monitoring GPIO pin for tamper events."""
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def _monitor_loop(self):
        try:
            gpio_path = f"/sys/class/gpio/gpio{self._gpio_pin}/value"
            while self._running:
                try:
                    with open(gpio_path) as f:
                        val = f.read().strip()
                    if val == "1" and not self._tampered:
                        self._tampered = True
                        logger.warning("Tamper detected on GPIO %d", self._gpio_pin)
                        if self._callback:
                            self._callback()
                except FileNotFoundError:
                    pass
                threading.Event().wait(0.5)
        except Exception:
            logger.exception("GPIO tamper monitor error")

    def stop(self):
        self._running = False

    def is_tampered(self) -> bool:
        was_tampered = self._tampered
        self._tampered = False
        return was_tampered

    def on_tamper(self, callback: Callable[[], None]) -> None:
        self._callback = callback


class MockTamperProvider(ITamperProvider):
    """Simulation provider: tamper can be triggered programmatically."""

    def __init__(self):
        self._tampered = False
        self._callback: Optional[Callable[[], None]] = None

    def trigger_tamper(self):
        """Simulate a tamper event (called from debug API or keyboard)."""
        self._tampered = True
        logger.warning("Mock tamper triggered")
        if self._callback:
            self._callback()

    def is_tampered(self) -> bool:
        was_tampered = self._tampered
        self._tampered = False
        return was_tampered

    def on_tamper(self, callback: Callable[[], None]) -> None:
        self._callback = callback
