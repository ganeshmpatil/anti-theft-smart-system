"""MQTT client for publishing alerts and subscribing to commands."""

import json
import logging
import threading
import time
from typing import Callable, Optional

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class MQTTClient:
    """Manages MQTT connection, publishing, and command subscription."""

    def __init__(self, broker: str, port: int, device_id: str, farm_id: str,
                 username: str = "", password: str = "",
                 tls_enabled: bool = False, ca_cert: str = "",
                 client_cert: str = "", client_key: str = ""):
        self._broker = broker
        self._port = port
        self._device_id = device_id
        self._farm_id = farm_id
        self._connected = False
        self._command_callback: Optional[Callable[[str, dict], None]] = None

        self._topic_prefix = f"farm/{farm_id}/device/{device_id}"

        self._client = mqtt.Client(
            client_id=device_id,
            protocol=mqtt.MQTTv5,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )

        if username:
            self._client.username_pw_set(username, password)

        if tls_enabled and ca_cert:
            self._client.tls_set(
                ca_certs=ca_cert,
                certfile=client_cert or None,
                keyfile=client_key or None,
            )

        # Last Will Testament: if we disconnect unexpectedly
        self._client.will_set(
            f"{self._topic_prefix}/status",
            payload=json.dumps({"status": "offline_unexpected", "device_id": device_id}),
            qos=1,
            retain=True,
        )

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    def connect(self) -> bool:
        """Connect to the MQTT broker. Returns True on success."""
        try:
            self._client.connect(self._broker, self._port, keepalive=60)
            self._client.loop_start()
            # Wait for connection (up to 10 seconds)
            for _ in range(20):
                if self._connected:
                    return True
                time.sleep(0.5)
            logger.error("MQTT connection timeout")
            return False
        except Exception:
            logger.exception("Failed to connect to MQTT broker %s:%d", self._broker, self._port)
            return False

    def disconnect(self):
        """Gracefully disconnect from broker."""
        self.publish_status("offline")
        self._client.loop_stop()
        self._client.disconnect()

    def publish_alert(self, payload_json: str, image_jpeg: bytes) -> bool:
        """Publish an intrusion alert (metadata + image)."""
        try:
            result = self._client.publish(
                f"{self._topic_prefix}/alert",
                payload=payload_json,
                qos=1,
            )
            self._client.publish(
                f"{self._topic_prefix}/image",
                payload=image_jpeg,
                qos=1,
            )
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception:
            logger.exception("Failed to publish alert")
            return False

    def publish_heartbeat(self, heartbeat: dict) -> bool:
        """Publish device heartbeat (QoS 0 — best effort)."""
        try:
            self._client.publish(
                f"{self._topic_prefix}/heartbeat",
                payload=json.dumps(heartbeat),
                qos=0,
            )
            return True
        except Exception:
            return False

    def publish_live_frame(self, frame_jpeg: bytes) -> bool:
        """Publish a live feed frame (QoS 0 — speed over reliability)."""
        try:
            self._client.publish(
                f"{self._topic_prefix}/live_frame",
                payload=frame_jpeg,
                qos=0,
            )
            return True
        except Exception:
            return False

    def publish_status(self, status: str) -> bool:
        """Publish device status (retained message)."""
        try:
            self._client.publish(
                f"{self._topic_prefix}/status",
                payload=json.dumps({"status": status, "device_id": self._device_id}),
                qos=1,
                retain=True,
            )
            return True
        except Exception:
            return False

    def on_command(self, callback: Callable[[str, dict], None]):
        """Register callback for incoming commands: callback(action, params)."""
        self._command_callback = callback

    @property
    def is_connected(self) -> bool:
        return self._connected

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        rc_value = getattr(rc, 'value', rc)
        if rc_value == 0:
            was_connected = self._connected
            self._connected = True
            if not was_connected:
                logger.info("MQTT connected to %s:%d", self._broker, self._port)
            else:
                logger.debug("MQTT reconnected to %s:%d", self._broker, self._port)
            # Subscribe to command and config topics
            client.subscribe(f"{self._topic_prefix}/command", qos=1)
            client.subscribe(f"{self._topic_prefix}/config", qos=1)
            self.publish_status("online")
        else:
            logger.error("MQTT connection failed with code %s", rc)

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        self._connected = False
        if rc != 0:
            logger.warning("MQTT unexpected disconnect (rc=%d), will auto-reconnect", rc)

    def _on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            logger.debug("MQTT message on %s: %s", topic, payload)

            if topic.endswith("/command") and self._command_callback:
                action = payload.get("action", "")
                params = payload.get("params", {})
                self._command_callback(action, params)

            elif topic.endswith("/config"):
                # Config updates handled as a special command
                if self._command_callback:
                    self._command_callback("config_update", payload)

        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.error("Invalid MQTT message payload on %s", msg.topic)
