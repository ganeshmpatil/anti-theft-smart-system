"""Stage 1: Motion detection using frame differencing.

Runs on every frame. Costs ~5ms. Filters out 90% of static frames
so that the expensive YOLO inference only runs when there's actual movement.
"""

import cv2
import numpy as np


class MotionDetector:
    """Detects motion by computing absolute frame difference."""

    def __init__(self, min_contour_area: int = 3000, blur_kernel: int = 21):
        self._min_area = min_contour_area
        self._blur_kernel = (blur_kernel, blur_kernel)
        self._prev_gray: np.ndarray | None = None

    def detect(self, frame: np.ndarray) -> tuple[bool, int]:
        """Check if significant motion exists in the frame.

        Args:
            frame: BGR image (640x480)

        Returns:
            (motion_detected: bool, motion_area: int)
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, self._blur_kernel, 0)

        if self._prev_gray is None:
            self._prev_gray = gray
            return False, 0

        delta = cv2.absdiff(self._prev_gray, gray)
        self._prev_gray = gray

        thresh = cv2.threshold(delta, 30, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        total_area = 0
        for c in contours:
            area = cv2.contourArea(c)
            if area > self._min_area:
                total_area += area

        return total_area > 0, total_area

    def reset(self):
        """Reset the previous frame reference (e.g., after camera switch)."""
        self._prev_gray = None
