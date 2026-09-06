"""Alert manager with temporal filtering, capture window, cooldown, and offline queue."""

import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

import cv2
import numpy as np

from .detection.human_detector import Detection

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    """An intrusion alert ready to be published."""
    device_id: str
    farm_id: str
    timestamp: str
    camera_id: str
    direction: str
    confidence: float
    person_count: int
    bboxes: list[dict]
    image_jpeg: bytes
    device_status: dict


@dataclass
class _CaptureCandidate:
    """A scored frame candidate during the capture window."""
    frame: np.ndarray
    detections: list[Detection]
    score: float
    device_status: dict


@dataclass
class _CaptureWindow:
    """Active capture window — collecting the best possible snapshot."""
    start_time: float
    frame_width: int
    frame_height: int
    best: _CaptureCandidate | None = None
    frames_collected: int = 0


class AlertManager:
    """Manages temporal filtering, best-frame capture, cooldown, and alert queuing.

    Detection flow per camera:
      1. Consecutive detections reach temporal_frames threshold → intrusion confirmed
      2. Enter a "capture window" — keep scanning for capture_window_seconds
      3. Score each frame: how centered is the person? how big? how confident?
      4. When window expires OR a "good enough" frame is found → fire the alert
      5. Cooldown prevents duplicate alerts for cooldown_seconds
    """

    def __init__(self, device_id: str, farm_id: str,
                 temporal_frames: int = 3, cooldown_seconds: int = 300,
                 capture_window_seconds: float = 3.0,
                 max_queue_size: int = 100):
        self._device_id = device_id
        self._farm_id = farm_id
        self._temporal_frames = temporal_frames
        self._cooldown_seconds = cooldown_seconds
        self._capture_window_seconds = capture_window_seconds

        # Per-camera state
        self._consecutive: dict[str, int] = {}
        self._last_alert_time: dict[str, float] = {}
        self._capture_windows: dict[str, _CaptureWindow] = {}

        # Offline alert queue
        self._queue: deque[Alert] = deque(maxlen=max_queue_size)

        self._alerts_today = 0
        self._last_reset_day = datetime.now(timezone.utc).date()

    def process_detections(self, camera_id: str, detections: list[Detection],
                           frame: np.ndarray,
                           device_status: dict) -> Alert | None:
        """Process detection results for one frame.

        This method is called every scan cycle. It manages three states:
          - Counting consecutive detections (temporal filter)
          - Capture window active (collecting best frame)
          - Cooldown (suppressing alerts)

        Returns an Alert only when the capture window produces the best snapshot.
        """
        self._maybe_reset_daily_count()

        # --- If a capture window is active, handle it first ---
        if camera_id in self._capture_windows:
            return self._process_capture_window(camera_id, detections, frame, device_status)

        if not detections:
            self._consecutive[camera_id] = 0
            return None

        # Increment consecutive counter
        count = self._consecutive.get(camera_id, 0) + 1
        self._consecutive[camera_id] = count

        if count < self._temporal_frames:
            logger.debug("%s: person detected (%d/%d consecutive)",
                         camera_id, count, self._temporal_frames)
            return None

        # Check cooldown
        last_time = self._last_alert_time.get(camera_id, 0)
        if (time.monotonic() - last_time) < self._cooldown_seconds:
            logger.debug("%s: alert suppressed (cooldown active)", camera_id)
            return None

        # --- Temporal filter passed → open capture window ---
        frame_h, frame_w = frame.shape[:2]
        window = _CaptureWindow(
            start_time=time.monotonic(),
            frame_width=frame_w,
            frame_height=frame_h,
        )
        self._capture_windows[camera_id] = window
        self._consecutive[camera_id] = 0

        logger.info("%s: intrusion confirmed — capture window opened (%.1fs)",
                     camera_id, self._capture_window_seconds)

        # Score this first frame too (it may be the only one we get)
        self._score_and_update(window, detections, frame, device_status)

        return None  # don't fire yet — wait for better frame

    def _process_capture_window(self, camera_id: str, detections: list[Detection],
                                frame: np.ndarray,
                                device_status: dict) -> Alert | None:
        """Handle a frame during an active capture window."""
        window = self._capture_windows[camera_id]
        elapsed = time.monotonic() - window.start_time

        # Score this frame if it has detections
        if detections:
            self._score_and_update(window, detections, frame, device_status)

        # Check if we should close the window
        should_close = False
        reason = ""

        if elapsed >= self._capture_window_seconds:
            should_close = True
            reason = f"window expired ({elapsed:.1f}s)"
        elif window.best and window.best.score >= 0.75:
            # Good enough — person is well-centered with high confidence
            should_close = True
            reason = f"good frame found (score={window.best.score:.2f})"

        if not should_close:
            return None

        # --- Close window and fire alert ---
        del self._capture_windows[camera_id]
        self._last_alert_time[camera_id] = time.monotonic()
        self._alerts_today += 1

        if window.best is None:
            # Person disappeared during window — still fire with whatever we have
            logger.warning("%s: capture window closed with no good frame — "
                           "firing with trigger frame", camera_id)
            # Use current frame as fallback
            best_det = max(detections, key=lambda d: d.confidence) if detections else None
            if best_det is None:
                return None
            return self._build_alert(camera_id, [best_det], frame, device_status)

        logger.info("%s: capture window closed (%s) — %d frames scored, best=%.2f",
                     camera_id, reason, window.frames_collected, window.best.score)

        return self._build_alert(
            camera_id,
            window.best.detections,
            window.best.frame,
            window.best.device_status,
        )

    def _score_and_update(self, window: _CaptureWindow,
                          detections: list[Detection],
                          frame: np.ndarray,
                          device_status: dict):
        """Score a frame and update the capture window's best candidate."""
        window.frames_collected += 1
        score = self._score_frame(detections, window.frame_width, window.frame_height)

        if window.best is None or score > window.best.score:
            window.best = _CaptureCandidate(
                frame=frame.copy(),
                detections=list(detections),
                score=score,
                device_status=device_status,
            )
            logger.debug("Capture window: new best frame (score=%.2f, #%d)",
                         score, window.frames_collected)

    def _score_frame(self, detections: list[Detection],
                     frame_w: int, frame_h: int) -> float:
        """Score how good a frame is for the alert snapshot.

        Scoring criteria (0.0 to 1.0):
          - Centeredness (40%): bbox center close to frame center
          - Containment (30%): bbox fully inside frame, not clipped at edges
          - Size (15%): larger bbox = person closer = better image
          - Confidence (15%): YOLO confidence
        """
        if not detections:
            return 0.0

        # Use the highest-confidence detection for scoring
        det = max(detections, key=lambda d: d.confidence)
        bbox_cx = det.x + det.w / 2
        bbox_cy = det.y + det.h / 2
        frame_cx = frame_w / 2
        frame_cy = frame_h / 2

        # Centeredness: 1.0 = dead center, 0.0 = at frame edge
        dx = abs(bbox_cx - frame_cx) / frame_cx  # 0..1 (0=center, 1=edge)
        dy = abs(bbox_cy - frame_cy) / frame_cy
        center_score = max(0.0, 1.0 - (dx * 0.7 + dy * 0.3))  # weight horizontal more

        # Containment: how much of bbox is inside frame (not clipped)
        visible_x1 = max(0, det.x)
        visible_y1 = max(0, det.y)
        visible_x2 = min(frame_w, det.x + det.w)
        visible_y2 = min(frame_h, det.y + det.h)
        visible_area = max(0, visible_x2 - visible_x1) * max(0, visible_y2 - visible_y1)
        full_area = max(1, det.w * det.h)
        containment_score = min(1.0, visible_area / full_area)

        # Penalize if bbox touches frame edges (strong clipping indicator)
        edge_penalty = 1.0
        margin = int(frame_w * 0.05)  # 5% margin
        if det.x < margin:
            edge_penalty *= 0.4
        if det.x + det.w > frame_w - margin:
            edge_penalty *= 0.4
        if det.y < margin:
            edge_penalty *= 0.7
        if det.y + det.h > frame_h - margin:
            edge_penalty *= 0.8  # bottom edge is less problematic (feet may be cut)
        containment_score *= edge_penalty

        # Size: bbox area relative to frame area (bigger = better, capped at 0.5)
        size_ratio = (det.w * det.h) / (frame_w * frame_h)
        size_score = min(1.0, size_ratio / 0.5)  # 50% of frame = max score

        # Confidence
        conf_score = min(1.0, det.confidence)

        # Weighted combination
        score = (center_score * 0.40 +
                 containment_score * 0.30 +
                 size_score * 0.15 +
                 conf_score * 0.15)

        return score

    def _build_alert(self, camera_id: str, detections: list[Detection],
                     frame: np.ndarray, device_status: dict) -> Alert:
        """Build an Alert object from the best frame."""
        best = max(detections, key=lambda d: d.confidence)
        direction = self._camera_to_direction(camera_id)
        image_jpeg = self._encode_jpeg(frame, detections)

        alert = Alert(
            device_id=self._device_id,
            farm_id=self._farm_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            camera_id=camera_id,
            direction=direction,
            confidence=round(best.confidence, 2),
            person_count=len(detections),
            bboxes=[{"x": d.x, "y": d.y, "w": d.w, "h": d.h} for d in detections],
            image_jpeg=image_jpeg,
            device_status=device_status,
        )

        logger.warning("INTRUSION ALERT: %s | %s | conf=%.2f | count=%d",
                        camera_id, direction, best.confidence, len(detections))
        return alert

    @property
    def has_active_capture(self) -> bool:
        """True if any camera has an active capture window."""
        return len(self._capture_windows) > 0

    def queue_alert(self, alert: Alert):
        """Add alert to offline queue when MQTT is unavailable."""
        if len(self._queue) == self._queue.maxlen:
            logger.warning("Alert queue full (%d) — oldest alert will be dropped",
                           self._queue.maxlen)
        self._queue.append(alert)
        logger.info("Alert queued (queue size: %d)", len(self._queue))

    def queue_raw_payload(self, payload: str):
        """Queue a raw JSON payload (e.g., tamper alert) for later delivery."""
        raw_alert = Alert(
            device_id=self._device_id, farm_id=self._farm_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            camera_id="", direction="", confidence=0.0, person_count=0,
            bboxes=[], image_jpeg=b"", device_status={},
        )
        raw_alert._raw_payload = payload
        self.queue_alert(raw_alert)

    def drain_queue(self) -> list[Alert]:
        """Return all queued alerts and clear the queue."""
        alerts = list(self._queue)
        self._queue.clear()
        return alerts

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    @property
    def alerts_today(self) -> int:
        return self._alerts_today

    def _encode_jpeg(self, frame: np.ndarray,
                     detections: list[Detection]) -> bytes:
        """Draw bounding boxes on frame and encode as JPEG."""
        annotated = frame.copy()
        for det in detections:
            color = (0, 0, 255)  # red
            cv2.rectangle(annotated, (det.x, det.y),
                          (det.x + det.w, det.y + det.h), color, 2)
            label = f"person {det.confidence:.0%}"
            cv2.putText(annotated, label, (det.x, det.y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return buf.tobytes()

    def to_payload(self, alert: Alert) -> str:
        """Convert alert to JSON payload (excluding image binary)."""
        return json.dumps({
            "device_id": alert.device_id,
            "farm_id": alert.farm_id,
            "timestamp": alert.timestamp,
            "event_type": "intrusion_detected",
            "camera_id": alert.camera_id,
            "direction": alert.direction,
            "detection": {
                "confidence": alert.confidence,
                "person_count": alert.person_count,
                "bboxes": alert.bboxes,
            },
            "image_ref": f"alert_{alert.timestamp.replace(':', '').replace('-', '')}_{alert.camera_id}.jpg",
            "device_status": alert.device_status,
        })

    @staticmethod
    def _camera_to_direction(camera_id: str) -> str:
        return {"cam_front": "north", "cam_rear": "south"}.get(camera_id, "unknown")

    def _maybe_reset_daily_count(self):
        today = datetime.now(timezone.utc).date()
        if today != self._last_reset_day:
            self._alerts_today = 0
            self._last_reset_day = today
