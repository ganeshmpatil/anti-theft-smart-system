"""Stage 1: Motion detection using frame differencing.

Runs on every frame. Costs ~5ms. Filters out 90% of static frames
so that the expensive YOLO inference only runs when there's actual movement.
"""

import cv2
import numpy as np


class MotionDetector:
    """Detects motion by computing absolute frame difference.

    Uses a slowly-updating reference frame instead of the immediately
    previous frame so that gradual motion (e.g. a person walking slowly)
    still accumulates a visible pixel delta.
    """

    def __init__(self, min_contour_area: int = 3000, blur_kernel: int = 21,
                 pixel_threshold: int = 20, ref_update_interval: int = 100):
        self._min_area = min_contour_area
        self._blur_kernel = (blur_kernel, blur_kernel)
        self._pixel_threshold = pixel_threshold
        self._ref_update_interval = ref_update_interval
        self._ref_gray: np.ndarray | None = None
        self._frame_count = 0

    def detect(self, frame: np.ndarray) -> tuple[bool, int]:
        """Check if significant motion exists in the frame.

        Args:
            frame: BGR image (640x480)

        Returns:
            (motion_detected: bool, motion_area: int)
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, self._blur_kernel, 0)

        if self._ref_gray is None:
            self._ref_gray = gray
            return False, 0

        delta = cv2.absdiff(self._ref_gray, gray)

        # Update reference frame periodically (not every frame)
        self._frame_count += 1
        if self._frame_count >= self._ref_update_interval:
            self._ref_gray = gray
            self._frame_count = 0

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
        self._frame_count = 0
