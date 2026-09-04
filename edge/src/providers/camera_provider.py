"""Camera providers for production and simulation modes."""

import logging
import time
from typing import Optional

import cv2
import numpy as np

from .interfaces import ICameraProvider

logger = logging.getLogger(__name__)

INFER_WIDTH = 640
INFER_HEIGHT = 480
HIRES_WIDTH = 1280
HIRES_HEIGHT = 720


class USBCameraProvider(ICameraProvider):
    """Production provider: reads from a USB camera device (e.g., /dev/video0)."""

    def __init__(self, device_path: str, camera_id: str):
        self._device_path = device_path
        self._camera_id = camera_id
        self._cap: Optional[cv2.VideoCapture] = None
        self._last_frame_time: float = 0

    @property
    def camera_id(self) -> str:
        return self._camera_id

    def open(self) -> bool:
        try:
            self._cap = cv2.VideoCapture(self._device_path, cv2.CAP_V4L2)
            if not self._cap.isOpened():
                logger.error("Failed to open camera %s at %s", self._camera_id, self._device_path)
                return False
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, INFER_WIDTH)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, INFER_HEIGHT)
            self._cap.set(cv2.CAP_PROP_FPS, 15)
            self._last_frame_time = time.monotonic()
            logger.info("Camera %s opened at %s", self._camera_id, self._device_path)
            return True
        except Exception:
            logger.exception("Error opening camera %s", self._camera_id)
            return False

    def read_frame(self) -> Optional[np.ndarray]:
        if self._cap is None or not self._cap.isOpened():
            return None
        ret, frame = self._cap.read()
        if not ret or frame is None:
            return None
        self._last_frame_time = time.monotonic()
        if frame.shape[1] != INFER_WIDTH or frame.shape[0] != INFER_HEIGHT:
            frame = cv2.resize(frame, (INFER_WIDTH, INFER_HEIGHT))
        return frame

    def read_hires_frame(self) -> Optional[np.ndarray]:
        if self._cap is None or not self._cap.isOpened():
            return None
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, HIRES_WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HIRES_HEIGHT)
        ret, frame = self._cap.read()
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, INFER_WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, INFER_HEIGHT)
        if not ret or frame is None:
            return None
        self._last_frame_time = time.monotonic()
        return frame

    def is_alive(self) -> bool:
        if self._cap is None or not self._cap.isOpened():
            return False
        return (time.monotonic() - self._last_frame_time) < 30

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("Camera %s released", self._camera_id)


class VideoFileProvider(ICameraProvider):
    """Simulation provider: reads from a video file, optionally looping."""

    def __init__(self, video_path: str, camera_id: str, loop: bool = True,
                 playback_speed: float = 1.0):
        self._video_path = video_path
        self._camera_id = camera_id
        self._loop = loop
        self._playback_speed = playback_speed
        self._cap: Optional[cv2.VideoCapture] = None
        self._fps: float = 30.0
        self._last_grab_time: float = 0

    @property
    def camera_id(self) -> str:
        return self._camera_id

    def open(self) -> bool:
        try:
            self._cap = cv2.VideoCapture(self._video_path)
            if not self._cap.isOpened():
                logger.error("Failed to open video file %s for %s", self._video_path, self._camera_id)
                return False
            self._fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
            logger.info("Video %s opened for %s (fps=%.1f, loop=%s)",
                        self._video_path, self._camera_id, self._fps, self._loop)
            return True
        except Exception:
            logger.exception("Error opening video %s", self._video_path)
            return False

    def _enforce_playback_speed(self):
        """Throttle frame reads to simulate real-time playback."""
        if self._last_grab_time > 0 and self._playback_speed > 0:
            interval = 1.0 / (self._fps * self._playback_speed)
            elapsed = time.monotonic() - self._last_grab_time
            if elapsed < interval:
                time.sleep(interval - elapsed)
        self._last_grab_time = time.monotonic()

    def read_frame(self) -> Optional[np.ndarray]:
        if self._cap is None or not self._cap.isOpened():
            return None
        self._enforce_playback_speed()
        ret, frame = self._cap.read()
        if not ret or frame is None:
            if self._loop:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self._cap.read()
                if not ret or frame is None:
                    return None
            else:
                return None
        if frame.shape[1] != INFER_WIDTH or frame.shape[0] != INFER_HEIGHT:
            frame = cv2.resize(frame, (INFER_WIDTH, INFER_HEIGHT))
        return frame

    def read_hires_frame(self) -> Optional[np.ndarray]:
        frame = self.read_frame()
        if frame is None:
            return None
        return cv2.resize(frame, (HIRES_WIDTH, HIRES_HEIGHT))

    def is_alive(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("Video source %s released", self._camera_id)


class WebcamSplitProvider(ICameraProvider):
    """Simulation provider: splits a single laptop webcam into two virtual cameras.

    cam_front gets the left half, cam_rear gets the right half.
    """

    def __init__(self, device_index: int, camera_id: str, half: str = "left"):
        self._device_index = device_index
        self._camera_id = camera_id
        self._half = half  # "left" or "right"
        self._cap: Optional[cv2.VideoCapture] = None

    # Class-level shared capture to avoid opening webcam twice
    _shared_caps: dict[int, cv2.VideoCapture] = {}
    _shared_ref_count: dict[int, int] = {}
    _shared_frame: dict[int, tuple[float, Optional[np.ndarray]]] = {}  # device -> (timestamp, frame)

    @property
    def camera_id(self) -> str:
        return self._camera_id

    def open(self) -> bool:
        try:
            if self._device_index not in WebcamSplitProvider._shared_caps:
                cap = cv2.VideoCapture(self._device_index)
                if not cap.isOpened():
                    logger.error("Failed to open webcam %d for %s", self._device_index, self._camera_id)
                    return False
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, INFER_WIDTH * 2)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, INFER_HEIGHT)
                WebcamSplitProvider._shared_caps[self._device_index] = cap
                WebcamSplitProvider._shared_ref_count[self._device_index] = 0
            self._cap = WebcamSplitProvider._shared_caps[self._device_index]
            WebcamSplitProvider._shared_ref_count[self._device_index] += 1
            logger.info("Webcam split (%s half) opened for %s", self._half, self._camera_id)
            return True
        except Exception:
            logger.exception("Error opening webcam for %s", self._camera_id)
            return False

    def _split_frame(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        mid = w // 2
        if self._half == "left":
            return frame[:, :mid]
        return frame[:, mid:]

    def _read_shared_frame(self) -> Optional[np.ndarray]:
        """Read from webcam only once per frame period; return cached frame otherwise."""
        if self._cap is None or not self._cap.isOpened():
            return None
        now = time.monotonic()
        cached = WebcamSplitProvider._shared_frame.get(self._device_index)
        # Re-read if no cache or cache is older than 5ms (same loop cycle uses cache)
        if cached is None or (now - cached[0]) > 0.005:
            ret, frame = self._cap.read()
            if not ret or frame is None:
                return None
            WebcamSplitProvider._shared_frame[self._device_index] = (now, frame)
            return frame
        return cached[1]

    def read_frame(self) -> Optional[np.ndarray]:
        frame = self._read_shared_frame()
        if frame is None:
            return None
        cropped = self._split_frame(frame)
        return cv2.resize(cropped, (INFER_WIDTH, INFER_HEIGHT))

    def read_hires_frame(self) -> Optional[np.ndarray]:
        frame = self.read_frame()
        if frame is None:
            return None
        return cv2.resize(frame, (HIRES_WIDTH, HIRES_HEIGHT))

    def is_alive(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def release(self) -> None:
        if self._cap is not None and self._device_index in WebcamSplitProvider._shared_ref_count:
            WebcamSplitProvider._shared_ref_count[self._device_index] -= 1
            if WebcamSplitProvider._shared_ref_count[self._device_index] <= 0:
                self._cap.release()
                del WebcamSplitProvider._shared_caps[self._device_index]
                del WebcamSplitProvider._shared_ref_count[self._device_index]
            self._cap = None
            logger.info("Webcam split %s released for %s", self._half, self._camera_id)
