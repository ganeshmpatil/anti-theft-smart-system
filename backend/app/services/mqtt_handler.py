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
from app.models.database import Alert, Device, DeviceFarmer, User
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
        # Live feed: device_uid -> list of asyncio.Queue
        self._live_subscribers: dict[str, list] = {}
        self._live_lock = threading.Lock()

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
            client.subscribe("farm/+/device/+/live_frame", qos=0)
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
            elif msg_type == "live_frame":
                self._handle_live_frame(device_uid, msg.payload)

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

        db: Session = SessionLocal()
        try:
            device = db.query(Device).filter(Device.device_uid == device_uid).first()
            if not device:
                return

            # Find the most recent alert that has an image_ref but no stored image yet
            latest_alert = (
                db.query(Alert)
                .filter(Alert.device_id == device.id)
                .order_by(Alert.created_at.desc())
                .first()
            )
            if not latest_alert:
                return

            # Use the image_ref from the alert as the storage key
            image_ref = latest_alert.image_path
            if not image_ref:
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                image_ref = f"alert_{timestamp}.jpg"

            object_name = f"{device_uid}/{image_ref}" if "/" not in image_ref else image_ref

            # Store in MinIO
            self._storage.upload_image(object_name, payload)

            # Update alert's image_path to the stored object name
            latest_alert.image_path = object_name
            db.commit()
            logger.info("Image stored: %s (%d bytes)", object_name, len(payload))

        finally:
            db.close()

    def _handle_heartbeat(self, device_uid: str, payload: bytes):
        """Process device heartbeat — update health metrics.

        Auto-registers unknown devices when a heartbeat arrives from a new device_uid.
        """
        try:
            data = json.loads(payload.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

        db: Session = SessionLocal()
        try:
            device = db.query(Device).filter(Device.device_uid == device_uid).first()
            if not device:
                # Auto-register: edge device came online, create Device row
                device = Device(
                    device_uid=device_uid,
                    status="online",
                )
                db.add(device)
                db.flush()
                logger.info("Auto-registered new device: %s (id=%d)", device_uid, device.id)

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
        """Send push notification to ALL farmers linked to the device."""
        confidence = data.get("detection", {}).get("confidence", 0)
        event_type = data.get("event_type", "intrusion_detected")

        farm = device.farm
        farm_name = farm.name if farm else device.device_uid

        if event_type == "tamper_detected":
            title = "TAMPER ALERT"
            body = f"Device {device.device_uid} at {farm_name} has been tampered with!"
        else:
            title = "INTRUSION ALERT"
            body = (f"Person detected at {farm_name} "
                    f"({data.get('direction', 'unknown')} camera, "
                    f"confidence: {confidence:.0%})")

        # Find all linked farmers and notify each one
        now = datetime.now(timezone.utc)
        links = db.query(DeviceFarmer).filter(DeviceFarmer.device_id == device.id).all()
        for link in links:
            # Only notify if monitoring is enabled for this farmer-device link
            if not link.monitoring_enabled:
                continue
            # Skip if alerts are suspended
            if link.suspended_until and link.suspended_until > now:
                logger.info("Skipping notification for user %d — suspended until %s", link.user_id, link.suspended_until)
                continue
            farmer = db.query(User).filter(User.id == link.user_id).first()
            if not farmer or not farmer.fcm_token:
                continue

            push_data = {
                "alert_id": str(alert.id),
                "device_uid": device.device_uid,
                "type": "intrusion",
            }
            if alert.image_path:
                push_data["image_url"] = self._storage.get_presigned_url(alert.image_path)
            send_push_notification(
                fcm_token=farmer.fcm_token,
                title=title,
                body=body,
                data=push_data,
            )

    # --- Live feed subscriber management ---

    def subscribe_live_feed(self, device_uid: str):
        """Create an asyncio.Queue for a new WebSocket subscriber. Returns the queue."""
        import asyncio
        queue = asyncio.Queue(maxsize=10)
        with self._live_lock:
            if device_uid not in self._live_subscribers:
                self._live_subscribers[device_uid] = []
            self._live_subscribers[device_uid].append(queue)
        logger.info("Live feed subscriber added for %s (total=%d)",
                     device_uid, len(self._live_subscribers[device_uid]))
        return queue

    def unsubscribe_live_feed(self, device_uid: str, queue):
        """Remove a subscriber queue."""
        with self._live_lock:
            if device_uid in self._live_subscribers:
                try:
                    self._live_subscribers[device_uid].remove(queue)
                except ValueError:
                    pass
                if not self._live_subscribers[device_uid]:
                    del self._live_subscribers[device_uid]
        logger.info("Live feed subscriber removed for %s", device_uid)

    def _handle_live_frame(self, device_uid: str, payload: bytes):
        """Push live frame to all WebSocket subscribers for this device."""
        with self._live_lock:
            subscribers = self._live_subscribers.get(device_uid, [])
            if not subscribers:
                return
            dead = []
            for queue in subscribers:
                try:
                    queue.put_nowait(payload)
                except Exception:
                    # Queue full or closed — mark for removal
                    dead.append(queue)
            for q in dead:
                try:
                    subscribers.remove(q)
                except ValueError:
                    pass
            if not subscribers:
                del self._live_subscribers[device_uid]

    def _notify_device_offline(self, db: Session, device: Device):
        """Notify all linked farmers that a device went offline unexpectedly."""
        farm = device.farm
        farm_name = farm.name if farm else device.device_uid

        links = db.query(DeviceFarmer).filter(DeviceFarmer.device_id == device.id).all()
        for link in links:
            farmer = db.query(User).filter(User.id == link.user_id).first()
            if not farmer or not farmer.fcm_token:
                continue

            send_push_notification(
                fcm_token=farmer.fcm_token,
                title="Device Offline",
                body=f"Device {device.device_uid} at {farm_name} is unreachable. Check power and connectivity.",
                data={"device_uid": device.device_uid, "event": "device_offline"},
            )
