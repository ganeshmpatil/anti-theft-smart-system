"""Alert manager with temporal filtering, cooldown, and offline queue."""

import io
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


class AlertManager:
    """Manages temporal filtering, cooldown, and alert queuing.

    An alert is only triggered when a person is detected in N consecutive
    frames (temporal filter). After an alert, further alerts from the same
    camera are suppressed for a cooldown period.
    """

    def __init__(self, device_id: str, farm_id: str,
                 temporal_frames: int = 3, cooldown_seconds: int = 300,
                 max_queue_size: int = 100):
        self._device_id = device_id
        self._farm_id = farm_id
        self._temporal_frames = temporal_frames
        self._cooldown_seconds = cooldown_seconds

        # Per-camera consecutive detection counters
        self._consecutive: dict[str, int] = {}
        # Per-camera last alert timestamp
        self._last_alert_time: dict[str, float] = {}
        # Offline alert queue
        self._queue: deque[Alert] = deque(maxlen=max_queue_size)

        self._alerts_today = 0
        self._last_reset_day = datetime.now(timezone.utc).date()

    def process_detections(self, camera_id: str, detections: list[Detection],
                           frame: np.ndarray,
                           device_status: dict) -> Alert | None:
        """Process detection results and determine if an alert should fire.

        Args:
            camera_id: Which camera produced this detection
            detections: List of person detections from YOLO
            frame: The current frame (for snapshot capture)
            device_status: Current device health metrics

        Returns:
            Alert object if triggered, None otherwise
        """
        self._maybe_reset_daily_count()

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

        # Temporal filter passed + cooldown clear -> TRIGGER ALERT
        self._last_alert_time[camera_id] = time.monotonic()
        self._consecutive[camera_id] = 0
        self._alerts_today += 1

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

    def queue_alert(self, alert: Alert):
        """Add alert to offline queue when MQTT is unavailable."""
        self._queue.append(alert)
        logger.info("Alert queued (queue size: %d)", len(self._queue))

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
