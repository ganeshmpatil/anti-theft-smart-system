"""Video clip recorder for alert evidence.

Maintains a rolling ring buffer of recent frames. When an intrusion is
confirmed, captures pre-event + post-event frames and encodes them as
an MP4 video clip.

Typical clip: 5s pre-event + 5s post-event = 10s total at 5 FPS = 50 frames.
"""

import logging
import tempfile
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Recording parameters
PRE_EVENT_SECONDS = 5
POST_EVENT_SECONDS = 5
CLIP_FPS = 5
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
MAX_BUFFER_FRAMES = PRE_EVENT_SECONDS * CLIP_FPS  # 25 frames


@dataclass
class VideoClip:
    """A recorded video clip."""
    data: bytes
    duration_seconds: float
    frame_count: int


class VideoRecorder:
    """Ring-buffer based video clip recorder."""

    def __init__(self, pre_seconds: int = PRE_EVENT_SECONDS,
                 post_seconds: int = POST_EVENT_SECONDS,
                 fps: int = CLIP_FPS):
        self._pre_seconds = pre_seconds
        self._post_seconds = post_seconds
        self._fps = fps
        self._buffer_size = pre_seconds * fps

        # Ring buffer of (timestamp, frame) tuples
        self._buffer: deque[tuple[float, np.ndarray]] = deque(maxlen=self._buffer_size)
        self._lock = threading.Lock()

        # Recording state
        self._recording = False
        self._record_start: float = 0
        self._post_frames: list[np.ndarray] = []
        self._pre_frames: list[np.ndarray] = []
        self._last_push: float = 0

    def push_frame(self, frame: np.ndarray):
        """Push a frame into the ring buffer. Call this every scan cycle.

        Throttles to target FPS to avoid filling buffer too fast.
        """
        now = time.monotonic()
        min_interval = 1.0 / self._fps
        if (now - self._last_push) < min_interval:
            return
        self._last_push = now

        # Resize to standard clip resolution
        if frame.shape[1] != FRAME_WIDTH or frame.shape[0] != FRAME_HEIGHT:
            frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))

        with self._lock:
            if self._recording:
                self._post_frames.append(frame.copy())
            else:
                self._buffer.append((now, frame.copy()))

    def trigger(self):
        """Called when intrusion is confirmed. Snapshots the pre-event buffer
        and starts collecting post-event frames.

        Returns immediately. Call `collect()` after post_seconds to get the clip.
        """
        with self._lock:
            if self._recording:
                return  # already recording
            self._recording = True
            self._record_start = time.monotonic()
            self._pre_frames = [f for _, f in self._buffer]
            self._post_frames = []
            self._buffer.clear()

        logger.info("Video recording triggered: %d pre-event frames captured",
                     len(self._pre_frames))

    def is_recording(self) -> bool:
        return self._recording

    def should_collect(self) -> bool:
        """True if post-event recording period has elapsed."""
        if not self._recording:
            return False
        return (time.monotonic() - self._record_start) >= self._post_seconds

    def collect(self) -> VideoClip | None:
        """Encode the pre+post frames into an MP4 clip. Returns None on failure.

        Must be called after `should_collect()` returns True.
        """
        with self._lock:
            pre = self._pre_frames
            post = self._post_frames
            self._pre_frames = []
            self._post_frames = []
            self._recording = False

        all_frames = pre + post
        if not all_frames:
            logger.warning("No frames to encode for video clip")
            return None

        logger.info("Encoding video clip: %d frames (%d pre + %d post)",
                     len(all_frames), len(pre), len(post))

        return self._encode_mp4(all_frames)

    def _encode_mp4(self, frames: list[np.ndarray]) -> VideoClip | None:
        """Encode frames to MP4 using OpenCV's VideoWriter."""
        tmpfile = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmppath = tmpfile.name
        tmpfile.close()

        try:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(tmppath, fourcc, self._fps,
                                     (FRAME_WIDTH, FRAME_HEIGHT))
            if not writer.isOpened():
                # Fallback to XVID if mp4v not available
                fourcc = cv2.VideoWriter_fourcc(*"XVID")
                tmppath = tmppath.replace(".mp4", ".avi")
                writer = cv2.VideoWriter(tmppath, fourcc, self._fps,
                                         (FRAME_WIDTH, FRAME_HEIGHT))

            if not writer.isOpened():
                logger.error("Failed to open VideoWriter")
                return None

            for frame in frames:
                if frame.shape[1] != FRAME_WIDTH or frame.shape[0] != FRAME_HEIGHT:
                    frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))
                writer.write(frame)

            writer.release()

            # Read the encoded file
            video_data = Path(tmppath).read_bytes()
            duration = len(frames) / self._fps

            logger.info("Video clip encoded: %d frames, %.1fs, %.1f KB",
                         len(frames), duration, len(video_data) / 1024)

            return VideoClip(
                data=video_data,
                duration_seconds=duration,
                frame_count=len(frames),
            )
        except Exception:
            logger.exception("Failed to encode video clip")
            return None
        finally:
            try:
                Path(tmppath).unlink(missing_ok=True)
            except Exception:
                pass
