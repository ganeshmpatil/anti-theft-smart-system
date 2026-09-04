"""MQTT handler — subscribes to edge device topics and processes messages.

Runs as a background thread alongside the FastAPI server.
Handles: alerts, images, heartbeats, status updates.
"""

import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import SessionLocal
from app.models.database import Alert, Device
from app.services.notification import send_push_notification
from app.services.storage import StorageService

logger = logging.getLogger(__name__)


class MQTTHandler:
    """Consumes MQTT messages from edge devices and processes them."""

    def __init__(self, storage: StorageService):
        self._storage = storage
        client_id = f"atss-backend-{uuid.uuid4().hex[:8]}"
        self._client = mqtt.Client(
            client_id=client_id,
            protocol=mqtt.MQTTv5,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._running = False

        if settings.mqtt_username:
            self._client.username_pw_set(settings.mqtt_username, settings.mqtt_password)

    def start(self):
        """Connect to MQTT broker and start processing messages."""
        self._running = True
        try:
            self._client.connect(settings.mqtt_broker, settings.mqtt_port, keepalive=60)
            self._client.loop_start()
            logger.info("MQTT handler connected to %s:%d", settings.mqtt_broker, settings.mqtt_port)
        except Exception:
            logger.exception("Failed to connect MQTT handler")

    def stop(self):
        """Disconnect from MQTT broker."""
        self._running = False
        self._client.loop_stop()
        self._client.disconnect()
        logger.info("MQTT handler stopped")

    def publish_command(self, farm_id: str, device_uid: str,
                        action: str, params: dict = None) -> bool:
        """Publish a command to an edge device."""
        topic = f"farm/{farm_id}/device/{device_uid}/command"
        payload = json.dumps({"action": action, "params": params or {}})
        try:
            result = self._client.publish(topic, payload, qos=1)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception:
            logger.exception("Failed to publish command to %s", topic)
            return False

    def publish_config(self, farm_id: str, device_uid: str, config: dict) -> bool:
        """Publish config update to an edge device."""
        topic = f"farm/{farm_id}/device/{device_uid}/config"
        payload = json.dumps(config)
        try:
            result = self._client.publish(topic, payload, qos=1, retain=True)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception:
            logger.exception("Failed to publish config to %s", topic)
            return False

    @property
    def is_connected(self) -> bool:
        return self._client.is_connected()

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        # MQTTv5 rc may be a ReasonCode object; compare via .value or check is_failure
        rc_value = getattr(rc, 'value', rc)
        if rc_value == 0:
            logger.info("MQTT handler connected — subscribing to topics")
            client.subscribe("farm/+/device/+/alert", qos=1)
            client.subscribe("farm/+/device/+/image", qos=1)
            client.subscribe("farm/+/device/+/heartbeat", qos=0)
            client.subscribe("farm/+/device/+/status", qos=1)
        else:
            logger.error("MQTT handler connection failed (rc=%s)", rc)

    def _on_message(self, client, userdata, msg):
        """Route incoming messages to the appropriate handler."""
        try:
            topic = msg.topic
            parts = topic.split("/")
            # topic format: farm/{farm_id}/device/{device_uid}/{message_type}
            if len(parts) != 5:
                return

            farm_id = parts[1]
            device_uid = parts[3]
            msg_type = parts[4]

            if msg_type == "alert":
                self._handle_alert(device_uid, msg.payload)
            elif msg_type == "image":
                self._handle_image(device_uid, msg.payload)
            elif msg_type == "heartbeat":
                self._handle_heartbeat(device_uid, msg.payload)
            elif msg_type == "status":
                self._handle_status(device_uid, msg.payload)

        except Exception:
            logger.exception("Error processing MQTT message on %s", msg.topic)

    def _handle_alert(self, device_uid: str, payload: bytes):
        """Process intrusion/tamper alert from edge device."""
        try:
            data = json.loads(payload.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.error("Invalid alert payload from %s", device_uid)
            return

        logger.warning("ALERT from %s: %s (conf=%.2f)",
                        device_uid, data.get("event_type"),
                        data.get("detection", {}).get("confidence", 0))

        db: Session = SessionLocal()
        try:
            device = db.query(Device).filter(Device.device_uid == device_uid).first()
            if not device:
                logger.warning("Alert from unknown device: %s", device_uid)
                return

            # Store alert in database
            detection = data.get("detection", {})
            alert = Alert(
                device_id=device.id,
                event_type=data.get("event_type", "unknown"),
                camera_id=data.get("camera_id", ""),
                confidence=detection.get("confidence", 0.0),
                person_count=detection.get("person_count", 0),
                bbox_json=json.dumps(detection.get("bboxes", [])),
                direction=data.get("direction", ""),
                image_path=data.get("image_ref", ""),
            )
            db.add(alert)
            db.commit()
            db.refresh(alert)

            logger.info("Alert stored: id=%d device=%s", alert.id, device_uid)

            # Send push notification to farm owner
            self._notify_owner(db, device, alert, data)

        finally:
            db.close()

    def _handle_image(self, device_uid: str, payload: bytes):
        """Process alert snapshot image from edge device."""
        if not payload:
            return

        # Store in MinIO
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        object_name = f"{device_uid}/alert_{timestamp}.jpg"
        self._storage.upload_image(object_name, payload)

        # Update the most recent alert's image_path
        db: Session = SessionLocal()
        try:
            device = db.query(Device).filter(Device.device_uid == device_uid).first()
            if device:
                latest_alert = (
                    db.query(Alert)
                    .filter(Alert.device_id == device.id)
                    .order_by(Alert.created_at.desc())
                    .first()
                )
                if latest_alert:
                    latest_alert.image_path = object_name
                    db.commit()
        finally:
            db.close()

    def _handle_heartbeat(self, device_uid: str, payload: bytes):
        """Process device heartbeat — update health metrics."""
        try:
            data = json.loads(payload.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

        db: Session = SessionLocal()
        try:
            device = db.query(Device).filter(Device.device_uid == device_uid).first()
            if not device:
                return

            device.last_heartbeat = datetime.now(timezone.utc)
            device.battery_pct = data.get("battery_pct", -1)
            device.cpu_temp = data.get("cpu_temp_c", 0.0)
            device.signal_dbm = data.get("signal_dbm", 0)
            device.firmware_version = data.get("firmware_version", "")
            db.commit()

        finally:
            db.close()

    def _handle_status(self, device_uid: str, payload: bytes):
        """Process device status change (online/offline/armed/disarmed)."""
        try:
            data = json.loads(payload.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

        new_status = data.get("status", "")
        logger.info("Device %s status: %s", device_uid, new_status)

        db: Session = SessionLocal()
        try:
            device = db.query(Device).filter(Device.device_uid == device_uid).first()
            if device:
                device.status = new_status
                device.last_heartbeat = datetime.now(timezone.utc)
                db.commit()

                # If device went offline unexpectedly, notify owner
                if new_status == "offline_unexpected":
                    self._notify_device_offline(db, device)
        finally:
            db.close()

    def _notify_owner(self, db: Session, device: Device, alert: Alert, data: dict):
        """Send push notification to the farm owner."""
        farm = device.farm
        if not farm:
            return
        owner = farm.owner
        if not owner or not owner.fcm_token:
            return

        confidence = data.get("detection", {}).get("confidence", 0)
        event_type = data.get("event_type", "intrusion_detected")

        if event_type == "tamper_detected":
            title = "TAMPER ALERT"
            body = f"Device {device.device_uid} at {farm.name} has been tampered with!"
        else:
            title = "INTRUSION ALERT"
            body = (f"Person detected at {farm.name} "
                    f"({data.get('direction', 'unknown')} camera, "
                    f"confidence: {confidence:.0%})")

        send_push_notification(
            fcm_token=owner.fcm_token,
            title=title,
            body=body,
            data={"alert_id": str(alert.id), "device_uid": device.device_uid},
        )

    def _notify_device_offline(self, db: Session, device: Device):
        """Notify owner that a device went offline unexpectedly."""
        farm = device.farm
        if not farm:
            return
        owner = farm.owner
        if not owner or not owner.fcm_token:
            return

        send_push_notification(
            fcm_token=owner.fcm_token,
            title="Device Offline",
            body=f"Device {device.device_uid} at {farm.name} is unreachable. Check power and connectivity.",
            data={"device_uid": device.device_uid, "event": "device_offline"},
        )
