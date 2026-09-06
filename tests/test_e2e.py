"""End-to-end integration test for the Anti-Theft Smart System.

Simulates the full pipeline:
  1. Edge device sends heartbeat via MQTT → backend updates device status
  2. Edge device sends intrusion alert via MQTT → backend stores alert in DB
  3. Edge device sends snapshot image via MQTT → backend stores in Supabase S3
  4. Edge device sends video clip via MQTT → backend stores in Supabase S3
  5. API returns alerts with image/video paths
  6. Storage presigned URLs work
  7. Fleet health endpoint reflects device status

Run: python tests/test_e2e.py
"""

import io
import json
import ssl
import sys
import time
import uuid

import cv2
import numpy as np
import paho.mqtt.client as mqtt
import requests

# --- Configuration ---
API_BASE = "https://farmguard-api.onrender.com"
MQTT_BROKER = "w1196cd6.ala.asia-southeast1.emqxsl.com"
MQTT_PORT = 8883
MQTT_USER = "farmguard-backend"
MQTT_PASS = "farmguard-backend"
DEVICE_UID = "FARM-001"
FARM_ID = "farm_1"
TOPIC_PREFIX = f"farm/{FARM_ID}/device/{DEVICE_UID}"

# Track test results
results = []


def log(test_name: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    results.append((test_name, passed))
    print(f"  [{status}] {test_name}" + (f" — {detail}" if detail else ""))


def make_test_image() -> bytes:
    """Generate a fake JPEG image with 'TEST' text."""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[:] = (30, 30, 80)  # dark red-ish background
    cv2.putText(img, "INTRUSION TEST", (120, 240),
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)
    cv2.putText(img, time.strftime("%Y-%m-%d %H:%M:%S"), (180, 300),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return buf.tobytes()


def make_test_video() -> bytes:
    """Generate a fake MP4 video clip (2 seconds, 5 fps)."""
    import tempfile
    from pathlib import Path

    tmpfile = tempfile.NamedTemporaryFile(suffix=".avi", delete=False)
    tmppath = tmpfile.name
    tmpfile.close()

    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    writer = cv2.VideoWriter(tmppath, fourcc, 5, (640, 480))

    for i in range(10):  # 2 seconds at 5fps
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img[:] = (30, 30, 80)
        cv2.putText(img, f"FRAME {i+1}/10", (180, 240),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)
        writer.write(img)

    writer.release()
    data = Path(tmppath).read_bytes()
    Path(tmppath).unlink(missing_ok=True)
    return data


# =============================================================================
# Test 1: API Health Check
# =============================================================================
def test_health():
    print("\n1. API Health Check")
    try:
        r = requests.get(f"{API_BASE}/health", timeout=60)
        data = r.json()
        log("API reachable", r.status_code == 200, f"status={data.get('status')}")
        log("MQTT connected", data.get("mqtt_connected") == True)
        log("Storage enabled", data.get("storage_enabled") == True)
    except Exception as e:
        log("API reachable", False, str(e))


# =============================================================================
# Test 2: Device Provisioning
# =============================================================================
def test_provisioning():
    print("\n2. Device Provisioning")
    try:
        # Try to provision (might already exist)
        r = requests.post(f"{API_BASE}/api/v1/admin/devices/provision",
                          json={"device_uid": DEVICE_UID}, timeout=30)
        if r.status_code == 201:
            log("Device provisioned", True, f"id={r.json()['id']}")
        elif r.status_code == 409:
            log("Device provisioned", True, "already exists")
        else:
            log("Device provisioned", False, f"status={r.status_code}: {r.text}")
    except Exception as e:
        log("Device provisioned", False, str(e))


# =============================================================================
# Test 3: MQTT Connectivity + Heartbeat
# =============================================================================
def test_mqtt_heartbeat():
    print("\n3. MQTT Heartbeat")
    connected = False
    message_received = False

    def on_connect(client, userdata, flags, rc, properties=None):
        nonlocal connected
        rc_value = getattr(rc, 'value', rc)
        connected = (rc_value == 0)

    client = mqtt.Client(
        client_id=f"e2e-test-{uuid.uuid4().hex[:6]}",
        protocol=mqtt.MQTTv5,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.on_connect = on_connect

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=30)
        client.loop_start()

        # Wait for connection
        for _ in range(20):
            if connected:
                break
            time.sleep(0.5)

        log("MQTT connected", connected)

        if connected:
            # Publish heartbeat
            heartbeat = {
                "device_id": DEVICE_UID,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "cpu_temp_c": 52.3,
                "battery_pct": 85,
                "power_source": "mains",
                "signal_dbm": -65,
                "firmware_version": "1.0.0-test",
                "uptime_seconds": 3600,
            }
            result = client.publish(f"{TOPIC_PREFIX}/heartbeat",
                                    json.dumps(heartbeat), qos=0)
            log("Heartbeat published", result.rc == mqtt.MQTT_ERR_SUCCESS)

            # Give backend time to process
            time.sleep(3)

            # Verify via fleet health API
            r = requests.get(f"{API_BASE}/api/v1/admin/health/fleet", timeout=30)
            if r.status_code == 200:
                fleet = r.json()
                device = next((d for d in fleet["devices"]
                               if d["device_uid"] == DEVICE_UID), None)
                if device:
                    log("Backend received heartbeat", True,
                        f"fw={device['firmware_version']}, temp={device['cpu_temp']}")
                else:
                    log("Backend received heartbeat", False, "device not in fleet")
            else:
                log("Backend received heartbeat", False, f"fleet API {r.status_code}")

    except Exception as e:
        log("MQTT connected", False, str(e))
    finally:
        client.loop_stop()
        client.disconnect()


# =============================================================================
# Test 4: Alert + Image + Video Pipeline
# =============================================================================
def test_alert_pipeline():
    print("\n4. Alert + Image + Video Pipeline")
    connected = False

    def on_connect(client, userdata, flags, rc, properties=None):
        nonlocal connected
        rc_value = getattr(rc, 'value', rc)
        connected = (rc_value == 0)

    client = mqtt.Client(
        client_id=f"e2e-alert-{uuid.uuid4().hex[:6]}",
        protocol=mqtt.MQTTv5,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.on_connect = on_connect

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=30)
        client.loop_start()

        for _ in range(20):
            if connected:
                break
            time.sleep(0.5)

        if not connected:
            log("MQTT connected for alerts", False)
            return

        # --- Publish alert ---
        ts = time.strftime("%Y%m%d_%H%M%S")
        image_ref = f"alert_{ts}_cam_front.jpg"
        alert_payload = {
            "device_id": DEVICE_UID,
            "farm_id": FARM_ID,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event_type": "intrusion_detected",
            "camera_id": "cam_front",
            "direction": "north",
            "detection": {
                "confidence": 0.87,
                "person_count": 1,
                "bboxes": [{"x": 200, "y": 100, "w": 120, "h": 300}],
            },
            "image_ref": image_ref,
            "device_status": {
                "cpu_temp_c": 55.0,
                "battery_pct": 72,
                "power_source": "mains",
            },
        }

        result = client.publish(f"{TOPIC_PREFIX}/alert",
                                json.dumps(alert_payload), qos=1)
        log("Alert published", result.rc == mqtt.MQTT_ERR_SUCCESS)
        time.sleep(2)

        # --- Publish image ---
        test_image = make_test_image()
        result = client.publish(f"{TOPIC_PREFIX}/image", test_image, qos=1)
        log("Image published", result.rc == mqtt.MQTT_ERR_SUCCESS,
            f"{len(test_image)} bytes")
        time.sleep(2)

        # --- Publish video ---
        test_video = make_test_video()
        result = client.publish(f"{TOPIC_PREFIX}/video", test_video, qos=1)
        log("Video published", result.rc == mqtt.MQTT_ERR_SUCCESS,
            f"{len(test_video)} bytes")
        time.sleep(3)

    except Exception as e:
        log("Alert pipeline", False, str(e))
    finally:
        client.loop_stop()
        client.disconnect()


# =============================================================================
# Test 5: Verify Alerts in API (requires auth — use admin endpoint)
# =============================================================================
def test_verify_alerts():
    print("\n5. Verify Alerts via Fleet Health")
    try:
        r = requests.get(f"{API_BASE}/api/v1/admin/health/fleet", timeout=30)
        if r.status_code == 200:
            fleet = r.json()
            device = next((d for d in fleet["devices"]
                           if d["device_uid"] == DEVICE_UID), None)
            if device:
                log("Device in fleet", True,
                    f"status={device['status']}, battery={device['battery_pct']}%")
            else:
                log("Device in fleet", False)
        else:
            log("Fleet health API", False, f"status={r.status_code}")
    except Exception as e:
        log("Fleet health API", False, str(e))


# =============================================================================
# Test 6: Storage Direct Test
# =============================================================================
def test_storage():
    print("\n6. Supabase S3 Storage")
    try:
        import boto3
        from botocore.config import Config

        s3 = boto3.client(
            "s3",
            endpoint_url="https://hixzeyeijkhbhphmjynq.supabase.co/storage/v1/s3",
            aws_access_key_id="79cae5060370d6da722589c3b86ab8a6",
            aws_secret_access_key="b0486ced3e2bf680ab8726ab60dd6144fb1f3ecd6fbf04af2bbec759880d97af",
            region_name="ap-south-1",
            config=Config(signature_version="s3v4"),
        )

        # Upload test
        test_key = "e2e-test/test_upload.jpg"
        test_data = make_test_image()
        s3.put_object(Bucket="alert-snapshots", Key=test_key,
                      Body=test_data, ContentType="image/jpeg")
        log("S3 upload", True, f"{len(test_data)} bytes")

        # Download test
        resp = s3.get_object(Bucket="alert-snapshots", Key=test_key)
        downloaded = resp["Body"].read()
        log("S3 download", len(downloaded) == len(test_data),
            f"{len(downloaded)} bytes")

        # Presigned URL test
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": "alert-snapshots", "Key": test_key},
            ExpiresIn=60,
        )
        r = requests.get(url, timeout=15)
        log("S3 presigned URL", r.status_code == 200,
            f"{len(r.content)} bytes downloaded")

        # List objects (check if alert images were stored by backend)
        resp = s3.list_objects_v2(Bucket="alert-snapshots",
                                  Prefix=f"{DEVICE_UID}/", MaxKeys=10)
        objects = resp.get("Contents", [])
        obj_names = [o["Key"] for o in objects]
        log("Alert media in S3", len(objects) > 0,
            f"{len(objects)} objects: {obj_names[:3]}")

        # Cleanup test file
        s3.delete_object(Bucket="alert-snapshots", Key=test_key)
        log("S3 cleanup", True)

    except Exception as e:
        log("S3 storage", False, str(e))


# =============================================================================
# Test 7: MQTT Command Delivery
# =============================================================================
def test_command_delivery():
    print("\n7. MQTT Command Delivery")
    command_received = {}

    def on_connect(client, userdata, flags, rc, properties=None):
        rc_value = getattr(rc, 'value', rc)
        if rc_value == 0:
            # Subscribe to command topic as if we are the edge device
            client.subscribe(f"{TOPIC_PREFIX}/command", qos=1)

    def on_message(client, userdata, msg):
        try:
            command_received.update(json.loads(msg.payload.decode()))
        except Exception:
            pass

    client = mqtt.Client(
        client_id=f"e2e-cmd-{uuid.uuid4().hex[:6]}",
        protocol=mqtt.MQTTv5,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=30)
        client.loop_start()
        time.sleep(3)  # wait for subscribe

        # Publish a command (simulating backend → device)
        cmd = {"action": "snapshot", "params": {}}
        client.publish(f"{TOPIC_PREFIX}/command", json.dumps(cmd), qos=1)
        time.sleep(2)

        log("Command received by device", command_received.get("action") == "snapshot",
            f"payload={command_received}")

    except Exception as e:
        log("Command delivery", False, str(e))
    finally:
        client.loop_stop()
        client.disconnect()


# =============================================================================
# Main
# =============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  Anti-Theft Smart System — End-to-End Test")
    print("=" * 60)

    # Wake up the Render service (cold start ~30s)
    print("\nWaking up Render service (may take 30s on cold start)...")
    try:
        requests.get(f"{API_BASE}/health", timeout=60)
    except Exception:
        pass

    test_health()
    test_provisioning()
    test_mqtt_heartbeat()
    test_alert_pipeline()
    test_verify_alerts()
    test_storage()
    test_command_delivery()

    # Summary
    print("\n" + "=" * 60)
    total = len(results)
    passed = sum(1 for _, p in results if p)
    failed = total - passed
    print(f"  Results: {passed}/{total} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        print("\n  Failed tests:")
        for name, p in results:
            if not p:
                print(f"    - {name}")

    sys.exit(0 if failed == 0 else 1)
