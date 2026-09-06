# Edge Layer — Knowledge Transfer Document

This document explains every source file in the `edge/` directory, what it does, its key classes/functions, and how files relate to each other.

---

## Table of Contents

1. [Entry Point](#1-entry-point)
2. [Core Loop](#2-core-loop)
3. [Detection Pipeline](#3-detection-pipeline)
4. [Communication](#4-communication)
5. [Alert Management](#5-alert-management)
6. [Video Recording](#6-video-recording)
7. [OTA Updates](#7-ota-updates)
8. [Hardware Providers](#8-hardware-providers)
9. [Configuration](#9-configuration)
10. [Data Flow Diagram](#10-data-flow-diagram)

---

## 1. Entry Point

### `src/main.py`

The application entry point. Responsible for:

- **Loading configuration** from `config/device_config.yaml` (or override via `--config` CLI arg)
- **Initializing all subsystems** in order: providers (via factory), MQTT client, human detector, alert manager, video recorder, surveillance loop
- **Reading the VERSION file** from `edge/VERSION` and passing it to `CommandHandler` for OTA version comparison
- **Signal handling** — traps `SIGINT`/`SIGTERM` for graceful shutdown (closes watchdog, disconnects MQTT, releases cameras)
- **Starting the surveillance loop** — calls `loop.run()` which blocks until shutdown

Key flow:
```
main() → load config → ProviderFactory.create() → MQTTClient() → HumanDetector() → AlertManager() → VideoRecorder() → SurveillanceLoop() → loop.run()
```

---

## 2. Core Loop

### `src/surveillance_loop.py`

The main processing loop that ties together cameras, detection, alerting, and communication. This is the **central orchestrator** of the edge system.

**Class: `SurveillanceLoop`**

- **`run()`** — Infinite loop that:
  1. Captures a frame from the current camera (alternates between cameras for 360° coverage)
  2. Pushes the frame to `VideoRecorder` ring buffer
  3. Runs the detection pipeline: motion gate → YOLO inference → temporal validation
  4. On confirmed intrusion: triggers alert (snapshot + MQTT publish), triggers video recording
  5. Pings the hardware watchdog every cycle
  6. Sends periodic heartbeats via MQTT (CPU temp, battery, uptime)
  7. Checks if a video clip is ready to collect and publish
  8. Sleeps to maintain target cycle time (~700ms for dual-camera scan)

- **`_handle_detection(frame, detections)`** — Called when YOLO finds people. Increments the consecutive-detection counter. After 3 consecutive detections (~1 second), confirms intrusion and triggers `AlertManager.trigger()`.

- **`_maybe_collect_video()`** — Checks `VideoRecorder.should_collect()` each cycle. When post-event recording is done, collects the encoded MP4 clip and publishes it via MQTT.

- **`_send_heartbeat()`** — Periodically publishes device telemetry (CPU temp, battery %, power source, firmware version, uptime) to `{topic_prefix}/heartbeat`.

---

## 3. Detection Pipeline

Detection is a two-stage pipeline: fast motion gate → slower YOLO inference. This saves ~90% of compute by skipping static frames.

### `src/detection/motion_detector.py`

**Class: `MotionDetector`**

A lightweight frame-differencing motion gate (~5ms per frame).

- **`detect(frame) → bool`** — Computes absolute difference between current and previous frame (grayscale), applies Gaussian blur, thresholds, and counts non-zero pixels. Returns `True` if motion area exceeds the configured threshold (default: 0.5% of frame area).
- Maintains the previous frame internally. First frame always returns `False`.
- Purpose: filter out 90%+ of static frames so YOLO only runs when something moves.

### `src/detection/human_detector.py`

**Class: `HumanDetector`**

YOLOv5n object detection with dual backend support.

- **`__init__(model_path, conf_threshold=0.6)`** — Auto-selects inference backend:
  - `.onnx` file → ONNX Runtime (Orange Pi, x86 dev machines)
  - `.tflite` file → TFLite Runtime (Raspberry Pi 3 ARMv7, where ONNX isn't available)
- **`detect(frame) → list[Detection]`** — Preprocesses frame (resize to 640×640, normalize), runs inference, applies NMS (non-max suppression), filters for person class (class 0) above confidence threshold.
- **`Detection`** dataclass: `bbox` (x, y, w, h), `confidence`, `class_id`
- Inference time: ~300ms on Orange Pi Zero 3, ~500ms on Pi 3 with TFLite.

### `src/detection/exclusion_zones.py`

**Class: `ExclusionZoneFilter`**

Filters out detections that fall within user-defined exclusion zones (e.g., a road visible from the camera where pedestrians are expected).

- **`__init__(zones: list[dict])`** — Each zone is a polygon defined by a list of (x, y) points in normalized coordinates (0.0–1.0).
- **`filter(detections, frame_shape) → list[Detection]`** — Removes detections whose center point falls inside any exclusion zone. Uses OpenCV's `pointPolygonTest`.
- Zones are configured in `device_config.yaml` under `detection.exclusion_zones`.

---

## 4. Communication

### `src/mqtt_client.py`

**Class: `MQTTClient`**

Handles all MQTT communication with the backend via EMQX Cloud.

- **`__init__(config)`** — Sets up paho-mqtt client with:
  - TLS encryption (port 8883). If `ca_cert` is specified, uses that file; otherwise falls back to system CA trust store (`ssl.PROTOCOL_TLS_CLIENT`) — required for EMQX Cloud which uses DigiCert.
  - Username/password authentication
  - Auto-reconnect with exponential backoff
  - Subscribes to `{topic_prefix}/command` on connect for receiving backend commands

- **`publish_alert(alert_payload: dict)`** — Publishes JSON alert to `{topic_prefix}/alert` (QoS 1)
- **`publish_image(image_data: bytes)`** — Publishes raw JPEG bytes to `{topic_prefix}/image` (QoS 1)
- **`publish_video(video_data: bytes)`** — Publishes raw MP4 bytes to `{topic_prefix}/video` (QoS 1)
- **`publish_heartbeat(telemetry: dict)`** — Publishes device status to `{topic_prefix}/heartbeat` (QoS 0)
- **`is_connected`** — Property for checking connection status

- **Command handling**: On message received on `/command` topic, delegates to `CommandHandler.handle()`.

Topic structure: `farm/{farm_id}/device/{device_uid}/{message_type}`

### `src/command_handler.py`

**Class: `CommandHandler`**

Processes commands received from the backend via MQTT.

- **`handle(action: str, params: dict)`** — Dispatches based on `action`:
  - `snapshot` — Triggers an immediate snapshot capture and publish
  - `reboot` — Initiates system reboot (`sudo reboot`)
  - `update_config` — Hot-reloads detection parameters (confidence threshold, exclusion zones)
  - `ota_update` — Delegates to `OTAUpdater` for firmware updates

- Integrates `OTAUpdater` instance, initialized with the current firmware version from `edge/VERSION`.

---

## 5. Alert Management

### `src/alert_manager.py`

**Class: `AlertManager`**

Manages alert lifecycle: temporal filtering, best-frame selection, cooldown, and offline queuing.

- **Temporal validation**: Requires N consecutive detections (default: 3) within a time window to confirm an intrusion. Prevents false positives from single-frame glitches.

- **Capture window**: After initial detection trigger, keeps collecting frames for a short window (e.g., 1 second) and selects the frame with the highest detection confidence as the alert snapshot. This ensures the best possible image quality.

- **Cooldown**: After sending an alert, enforces a cooldown period (default: 5 minutes) before another alert can be sent for the same camera. Prevents alert flooding.

- **Offline queue**: If MQTT is disconnected when an alert triggers, the alert (JSON + snapshot) is persisted to disk (`/tmp/farmguard_queue/`). On reconnection, queued alerts are replayed in order.

- **`trigger(frame, detections)`** — Main entry point called by the surveillance loop on confirmed intrusion. Builds alert payload (device ID, timestamp, camera ID, detection details, image reference), encodes the best frame as JPEG, and publishes both via MQTT (or queues if offline).

---

## 6. Video Recording

### `src/video_recorder.py`

**Class: `VideoRecorder`**

Ring-buffer-based video clip recorder that captures context around intrusion events (5s before + 5s after).

- **Ring buffer**: A `collections.deque` with `maxlen = pre_seconds * fps` continuously stores recent frames. This gives "time travel" — when an intrusion is detected, we already have the last 5 seconds of footage.

- **`push_frame(frame)`** — Called every cycle by the surveillance loop. During normal operation, adds frames to the ring buffer (throttled to target FPS, default 5). During post-event recording, adds to the post-event list instead.

- **`trigger()`** — Called on confirmed intrusion. Snapshots the current ring buffer contents as pre-event frames and starts collecting post-event frames.

- **`should_collect() → bool`** — Returns `True` when post-event recording has collected enough frames (post_seconds × fps).

- **`collect() → VideoClip | None`** — Encodes all pre+post frames into an MP4 file using OpenCV's `VideoWriter`. Returns a `VideoClip` dataclass with the raw bytes. The file is written to a temp path, read into memory, then deleted.

- **`VideoClip`** dataclass: `data: bytes`, `duration: float`, `frame_count: int`

Output: ~200–400 KB per 10-second clip at 5 FPS, 640×480 resolution.

---

## 7. OTA Updates

### `src/ota_updater.py`

**Class: `OTAUpdater`**

Handles over-the-air firmware updates received as MQTT commands from the backend.

- **`handle_update_command(params)`** — Entry point called by `CommandHandler`. Params include `url` (download URL for tar.gz), `version` (target version), and `sha256` (expected hash). Skips if target version matches current version. Runs the actual update in a background thread to avoid blocking the surveillance loop.

- **Update process**:
  1. Downloads the tar.gz archive from the provided URL
  2. Verifies SHA-256 checksum against the expected hash
  3. **Security**: Validates all paths in the tarball — rejects entries containing `..` or absolute paths to prevent path traversal attacks
  4. Extracts to `/opt/surveillance/` (the installation directory)
  5. Restarts the systemd service (`sudo systemctl restart surveillance`)

- **`current_version`** — Read from `edge/VERSION` file at startup

---

## 8. Hardware Providers

The provider layer abstracts all hardware interactions behind interfaces, enabling the system to run in simulation, webcam dev, or production mode without code changes.

### `src/providers/interfaces.py`

Defines abstract base classes (ABCs) for all hardware:

| Interface | Purpose | Key Methods |
|---|---|---|
| `ICameraProvider` | Camera capture | `open()`, `read() → (bool, frame)`, `release()`, `camera_id` |
| `ITamperProvider` | Physical tamper detection | `is_tampered() → bool`, `start()`, `stop()` |
| `IThermalProvider` | CPU temperature monitoring | `read_temp() → float` |
| `IPowerProvider` | Power source detection | `is_on_mains() → bool`, `battery_pct() → int` |
| `IWatchdogProvider` | Hardware watchdog timer | `ping()`, `reset_usb_port(port) → bool` |

### `src/providers/factory.py`

**Class: `ProviderFactory`**

Factory that creates the correct provider implementations based on the `mode` field in `device_config.yaml`:

| Mode | Use Case | Providers Created |
|---|---|---|
| `production` | Deployed on Orange Pi / Pi | Real hardware providers (USB cameras, GPIO, sysfs, /dev/watchdog) |
| `webcam` | Developer laptop testing | WebcamProvider + MockThermal/Power/Tamper/Watchdog |
| `simulation` | CI/automated testing | VideoFileProvider + all mocks |

- **`create(config) → ProviderSet`** — Returns a named tuple of all provider instances, ready for injection into the surveillance loop.

### `src/providers/camera_provider.py`

Multiple camera implementations:

| Class | Description |
|---|---|
| `USBCameraProvider` | Production: opens USB cameras via V4L2 (`/dev/videoN`). Supports resolution config. |
| `VideoFileProvider` | Simulation: reads from a video file on loop. For CI testing. |
| `WebcamFullProvider` | Dev: uses laptop webcam as a single full-frame camera. |
| `WebcamSplitProvider` | Dev: splits laptop webcam frame into left/right halves to simulate dual cameras. |

All implement `ICameraProvider`. The surveillance loop doesn't know which implementation it's using.

### `src/providers/thermal_provider.py`

| Class | Description |
|---|---|
| `SysfsThermalProvider` | Reads CPU temperature from `/sys/class/thermal/thermal_zone0/temp`. Returns value in °C (sysfs reports millidegrees). |
| `MockThermalProvider` | Returns a configurable fixed temperature (default: 45°C). |

### `src/providers/power_provider.py`

| Class | Description |
|---|---|
| `SystemPowerProvider` | Reads GPIO pin to detect mains power vs battery. Returns battery percentage estimate based on voltage divider ADC reading (if available) or a default. |
| `MockPowerProvider` | Returns mains=True, battery=100%. |

### `src/providers/tamper_provider.py`

| Class | Description |
|---|---|
| `GPIOTamperProvider` | Monitors a GPIO pin connected to a tamper switch (e.g., enclosure lid sensor). Runs a polling thread that checks the pin state periodically. Sets `is_tampered()` flag when triggered. |
| `MockTamperProvider` | Always returns `is_tampered() = False`. |

### `src/providers/watchdog_provider.py`

| Class | Description |
|---|---|
| `HardwareWatchdogProvider` | Opens `/dev/watchdog` and writes keepalive bytes each cycle. If the process hangs or crashes, the hardware watchdog reboots the device. Also supports USB port reset via sysfs unbind/rebind (for recovering stuck cameras). Sends magic close byte `'V'` on graceful shutdown to prevent reboot. |
| `MockWatchdogProvider` | Counts pings silently. No hardware interaction. |

### `src/providers/__init__.py`

Package-level exports — re-exports all provider classes and `ProviderFactory` for clean imports.

---

## 9. Configuration

### `config/device_config.yaml`

Central configuration file. Key sections:

```yaml
mode: "webcam"              # production | webcam | simulation

device:
  uid: "FARM-001"
  farm_id: "farm_1"

cameras:                     # List of camera configs
  - id: "cam_front"
    source: 0               # /dev/video0 or video file path
    resolution: [640, 480]

mqtt:
  broker: "w1196cd6.ala.asia-southeast1.emqxsl.com"
  port: 8883
  tls_enabled: true
  ca_cert: ""               # Empty = use system CA
  username: "farmguard-edge"
  password: "..."

detection:
  model_path: "models/yolov5n.onnx"   # or .tflite
  confidence_threshold: 0.6
  consecutive_frames: 3      # Temporal validation count
  cooldown_seconds: 300      # 5-minute cooldown
  exclusion_zones: []        # Polygon zones to ignore

video:
  pre_seconds: 5
  post_seconds: 5
  fps: 5

heartbeat:
  interval_seconds: 60
```

### `config/production_config.yaml`

Production-specific overrides for deployment on actual hardware. Inherits defaults from `device_config.yaml` structure but with production MQTT broker, camera paths, etc.

---

## 10. Data Flow Diagram

```
Camera Frame Capture (USBCameraProvider / WebcamProvider)
         │
         ▼
   ┌─────────────┐
   │ VideoRecorder│──── push_frame() ──→ Ring Buffer (5s @ 5fps)
   │              │
   └─────────────┘
         │
         ▼
   ┌─────────────┐
   │MotionDetector│──── Frame diff → motion? ──→ No → skip YOLO
   │              │                              (saves ~90% compute)
   └─────────────┘
         │ Yes
         ▼
   ┌─────────────┐
   │HumanDetector │──── YOLOv5n inference (~300ms)
   │  (ONNX/TFL)  │
   └─────────────┘
         │ Person detected?
         ▼
   ┌──────────────┐
   │ExclusionZones │──── Filter detections in ignored areas
   └──────────────┘
         │
         ▼
   ┌─────────────┐
   │ AlertManager │──── 3 consecutive detections? → Confirmed intrusion
   │              │     Best-frame selection → JPEG encode
   │              │     Cooldown check (5 min)
   └─────────────┘
         │ Confirmed
         ├──────────────────────────────┐
         ▼                              ▼
   ┌──────────┐                 ┌─────────────┐
   │MQTTClient │                │VideoRecorder │
   │           │                │  .trigger()  │
   │ alert JSON│                │              │
   │ image JPEG│                │ 5s post-event│
   │           │                │ recording... │
   └──────────┘                └─────────────┘
         │                              │
         │                    collect() after 5s
         │                              │
         │                              ▼
         │                     ┌──────────┐
         └─────────────────────│MQTTClient │
                               │ video MP4 │
                               └──────────┘
         │
         ▼
   EMQX Cloud (MQTT Broker)
         │
         ▼
   FastAPI Backend → PostgreSQL + Supabase S3
         │
         ▼
   Firebase FCM → Flutter Mobile App
```

### Heartbeat Flow (parallel)

```
SurveillanceLoop (every 60s)
         │
         ├── ThermalProvider.read_temp()
         ├── PowerProvider.is_on_mains() / battery_pct()
         │
         ▼
   MQTTClient.publish_heartbeat()
         │
         ▼
   Backend → fleet health dashboard
```

### Command Flow (async)

```
Backend / Admin API
         │
         ▼
   MQTT: {topic_prefix}/command
         │
         ▼
   MQTTClient.on_message()
         │
         ▼
   CommandHandler.handle()
         │
         ├── "snapshot"    → immediate capture + publish
         ├── "reboot"      → sudo reboot
         ├── "update_config" → hot-reload detection params
         └── "ota_update"  → OTAUpdater (background thread)
                                │
                                ├── Download tar.gz
                                ├── Verify SHA-256
                                ├── Extract to /opt/surveillance/
                                └── Restart systemd service
```

---

## File Summary Table

| File | Lines | Purpose |
|---|---|---|
| `src/main.py` | ~80 | Entry point, init, signal handling |
| `src/surveillance_loop.py` | ~200 | Main processing loop, orchestrator |
| `src/detection/motion_detector.py` | ~40 | Frame-diff motion gate |
| `src/detection/human_detector.py` | ~150 | YOLOv5n inference (ONNX + TFLite) |
| `src/detection/exclusion_zones.py` | ~50 | Polygon-based detection filtering |
| `src/alert_manager.py` | ~180 | Temporal validation, capture window, cooldown, offline queue |
| `src/video_recorder.py` | ~100 | Ring buffer pre/post event video clips |
| `src/mqtt_client.py` | ~150 | MQTT pub/sub, TLS, auto-reconnect |
| `src/command_handler.py` | ~60 | Backend command dispatch |
| `src/ota_updater.py` | ~100 | OTA firmware updates |
| `src/providers/interfaces.py` | ~60 | Abstract hardware interfaces |
| `src/providers/factory.py` | ~80 | Provider creation by mode |
| `src/providers/camera_provider.py` | ~150 | 4 camera implementations |
| `src/providers/thermal_provider.py` | ~40 | CPU temp reading |
| `src/providers/power_provider.py` | ~50 | Power source detection |
| `src/providers/tamper_provider.py` | ~60 | Tamper switch monitoring |
| `src/providers/watchdog_provider.py` | ~70 | Hardware watchdog + USB reset |
