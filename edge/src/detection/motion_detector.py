"""Stage 1: Motion detection using frame differencing.

Runs on every frame. Costs ~5ms. Filters out 90% of static frames
so that the expensive YOLO inference only runs when there's actual movement.
"""

import time

import cv2
import numpy as np


class MotionDetector:
    """Detects motion by computing absolute frame difference.

    Uses exponential moving average for the reference frame so it adapts
    to gradual lighting changes (sunset, clouds) without periodic jumps.
    """

    def __init__(self, min_contour_area: int = 3000, blur_kernel: int = 11,
                 pixel_threshold: int = 20, ref_update_seconds: float = 10.0,
                 ema_alpha: float = 0.02):
        self._min_area = min_contour_area
        self._blur_kernel = (blur_kernel, blur_kernel)
        self._pixel_threshold = pixel_threshold
        self._ref_update_seconds = ref_update_seconds
        self._ema_alpha = ema_alpha
        self._ref_gray: np.ndarray | None = None
        self._last_ref_time: float = 0

    def detect(self, frame: np.ndarray) -> tuple[bool, int]:
        """Check if significant motion exists in the frame.

        Args:
            frame: BGR image

        Returns:
            (motion_detected: bool, motion_area: int)
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, self._blur_kernel, 0)

        if self._ref_gray is None:
            self._ref_gray = gray.astype(np.float32)
            self._last_ref_time = time.monotonic()
            return False, 0

        delta = cv2.absdiff(self._ref_gray.astype(np.uint8), gray)

        # EMA update: smooth reference adapts to gradual lighting changes
        now = time.monotonic()
        if (now - self._last_ref_time) >= self._ref_update_seconds:
            cv2.accumulateWeighted(gray, self._ref_gray, self._ema_alpha)
            self._last_ref_time = now

        thresh = cv2.threshold(delta, self._pixel_threshold, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        total_area = 0
        for c in contours:
            area = cv2.contourArea(c)
            if area > self._min_area:
                total_area += area

        return total_area > 0, total_area

    def reset(self):
        """Reset the reference frame (e.g., after camera switch)."""
        self._ref_gray = None
        self._last_ref_time = 0
