# Technical Architecture — Anti-Theft Smart System

## Table of Contents

- [1. Architecture Principles](#1-architecture-principles)
- [2. System Topology](#2-system-topology)
- [3. Edge Layer — Orange Pi](#3-edge-layer--orange-pi)
- [4. Communication Layer — MQTT](#4-communication-layer--mqtt)
- [5. Backend Layer — Cloud](#5-backend-layer--cloud)
- [6. Mobile Layer — Android App](#6-mobile-layer--android-app)
- [7. AI/ML Pipeline](#7-aiml-pipeline)
- [8. Database Design](#8-database-design)
- [9. API Specification](#9-api-specification)
- [10. Network Architecture](#10-network-architecture)
- [11. Reliability Engineering](#11-reliability-engineering)
- [12. Security Architecture](#12-security-architecture)
- [13. Deployment Architecture](#13-deployment-architecture)
- [14. Monitoring and Observability](#14-monitoring-and-observability)
- [15. OTA Update Mechanism](#15-ota-update-mechanism)
- [16. Performance Budgets](#16-performance-budgets)
- [17. Technology Decisions](#17-technology-decisions)

---

## 1. Architecture Principles

| Principle | Rationale |
|---|---|
| **Edge-first processing** | All detection runs on-device. Cloud is for relay and storage only. System works even if internet is down. |
| **Minimal bandwidth** | Rural 4G is slow and expensive. Transmit only alert metadata + compressed JPEG. Never stream video. |
| **Fail-safe defaults** | If any component fails, the system must degrade gracefully, not silently die. Every failure triggers a notification. |
| **No single point of failure** | Power backup, offline alert queue, watchdog auto-recovery, redundant detection stages. |
| **Simplicity over sophistication** | Python everywhere. Minimal dependencies. A farmer or local technician should be able to set it up. |
| **Cost-conscious at every layer** | Open-source stack. Self-hosted where possible. No per-API-call billing. |

---

## 2. System Topology

### 2.1 Three-Tier Architecture

```
    ┌─────────────────────────────────────────────────────────────────┐
    │                                                                 │
    │   TIER 1: EDGE (Per Farm)                                      │
    │   ════════════════════════                                      │
    │                                                                 │
    │   Orange Pi Zero 3 (2GB)                                       │
    │   ┌───────────────────────────────────────────────────────┐    │
    │   │                                                       │    │
    │   │   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────────┐ │    │
    │   │   │ camera  │ │ camera  │ │ detector│ │ mqtt      │ │    │
    │   │   │ manager │ │ manager │ │ engine  │ │ client    │─┼──┐ │
    │   │   │ (cam1)  │ │ (cam2)  │ │ (YOLO)  │ │ (paho)   │ │  │ │
    │   │   └────┬────┘ └────┬────┘ └────┬────┘ └───────────┘ │  │ │
    │   │        │           │           │                     │  │ │
    │   │   ┌────▼───────────▼───────────▼──────────────────┐  │  │ │
    │   │   │         surveillance daemon (main.py)         │  │  │ │
    │   │   └───────────────────────────────────────────────┘  │  │ │
    │   │                                                       │  │ │
    │   │   ┌────────────┐ ┌────────────┐ ┌──────────────────┐ │  │ │
    │   │   │ watchdog   │ │ thermal    │ │ connectivity     │ │  │ │
    │   │   │ manager    │ │ manager    │ │ manager          │ │  │ │
    │   │   └────────────┘ └────────────┘ └──────────────────┘ │  │ │
    │   └───────────────────────────────────────────────────────┘  │ │
    │                                                              │ │
    └──────────────────────────────────────────────────────────────┘ │
                                                                     │
                    4G LTE ── MQTT over TLS (port 8883) ─────────────┘
                                                                     │
    ┌────────────────────────────────────────────────────────────────┐│
    │                                                                ││
    │   TIER 2: CLOUD (Shared Infrastructure)                       ││
    │   ═════════════════════════════════════                        ││
    │                                                                ││
    │   VPS: 2 vCPU, 4GB RAM, 80GB SSD                             ││
    │   ┌────────────────────────────────────────────────────────┐  ││
    │   │                                                        │  ││
    │   │   ┌──────────┐  ┌──────────┐  ┌──────────┐           │  ││
    │   │   │  EMQX    │◀─┤ FastAPI  │──▶│PostgreSQL│           │◀─┘│
    │   │   │  MQTT    │  │ API      │  │ Database │           │   │
    │   │   │  Broker  │  │ Server   │  │          │           │   │
    │   │   └──────────┘  └────┬─────┘  └──────────┘           │   │
    │   │                      │                                │   │
    │   │              ┌───────┴───────┐                        │   │
    │   │              │               │                        │   │
    │   │         ┌────▼─────┐  ┌──────▼─────┐                 │   │
    │   │         │ Firebase │  │   MinIO    │                 │   │
    │   │         │ FCM      │  │   Object   │                 │   │
    │   │         │          │  │   Storage  │                 │   │
    │   │         └────┬─────┘  └────────────┘                 │   │
    │   │              │                                        │   │
    │   └──────────────┼────────────────────────────────────────┘   │
    │                  │                                            │
    └──────────────────┼────────────────────────────────────────────┘
                       │
                       │  FCM Push
                       │
    ┌──────────────────▼────────────────────────────────────────────┐
    │                                                               │
    │   TIER 3: MOBILE (Per Farmer)                                │
    │   ═══════════════════════════                                 │
    │                                                               │
    │   Android App (Flutter)                                      │
    │   ┌───────────────────────────────────────────────────────┐  │
    │   │                                                       │  │
    │   │  ┌──────────┐  ┌──────────┐  ┌──────────┐           │  │
    │   │  │Dashboard │  │ Alert    │  │ Settings │           │  │
    │   │  │ Screen   │  │ Screen   │  │ Screen   │           │  │
    │   │  └──────────┘  └──────────┘  └──────────┘           │  │
    │   │                                                       │  │
    │   │  ┌──────────┐  ┌──────────┐  ┌──────────┐           │  │
    │   │  │ API      │  │ FCM      │  │ Local    │           │  │
    │   │  │ Service  │  │ Service  │  │ Storage  │           │  │
    │   │  └──────────┘  └──────────┘  └──────────┘           │  │
    │   │                                                       │  │
    │   └───────────────────────────────────────────────────────┘  │
    │                                                               │
    └───────────────────────────────────────────────────────────────┘
```

### 2.2 Deployment Diagram

```
    ┌─────── Farm Site ───────┐     ┌────── Cloud ──────┐     ┌── Mobile ──┐
    │                         │     │                    │     │            │
    │  ┌───────────────────┐  │     │  ┌──────────────┐ │     │  ┌──────┐ │
    │  │   Orange Pi       │  │     │  │  Docker Host │ │     │  │ App  │ │
    │  │                   │  │     │  │              │ │     │  │      │ │
    │  │  ┌─────────────┐  │  │     │  │  ┌────────┐ │ │     │  └──────┘ │
    │  │  │surveillance │  │  │     │  │  │ emqx   │ │ │     │            │
    │  │  │  .service   │  │──┼─4G──┼──│  │ :1883  │ │ │     │            │
    │  │  └─────────────┘  │  │     │  │  │ :8883  │ │ │     │            │
    │  │                   │  │     │  │  └────────┘ │ │     │            │
    │  │  ┌─────┐ ┌─────┐ │  │     │  │  ┌────────┐ │ │     │            │
    │  │  │cam1 │ │cam2 │ │  │     │  │  │fastapi │ │ │     │            │
    │  │  └─────┘ └─────┘ │  │     │  │  │ :8000  │─┼─┼─────│            │
    │  │                   │  │     │  │  └────────┘ │ │     │            │
    │  │  ┌─────┐ ┌─────┐ │  │     │  │  ┌────────┐ │ │     │            │
    │  │  │4G   │ │UPS  │ │  │     │  │  │postgres│ │ │     │            │
    │  │  │dongl│ │     │ │  │     │  │  │ :5432  │ │ │     │            │
    │  │  └─────┘ └─────┘ │  │     │  │  └────────┘ │ │     │            │
    │  └───────────────────┘  │     │  │  ┌────────┐ │ │     │            │
    │                         │     │  │  │ minio  │ │ │     │            │
    │                         │     │  │  │ :9000  │ │ │     │            │
    │                         │     │  │  └────────┘ │ │     │            │
    │                         │     │  └──────────────┘ │     │            │
    └─────────────────────────┘     └────────────────────┘     └────────────┘
```

---

## 3. Edge Layer — Orange Pi

### 3.1 Software Architecture

```
    ┌──────────────────────────────────────────────────────────────────┐
    │                     ARMBIAN (Debian 12)                          │
    │                     Read-Only rootfs (overlayfs)                 │
    │                                                                  │
    │   ┌──────────────────────────────────────────────────────────┐  │
    │   │                  systemd service manager                  │  │
    │   │                                                          │  │
    │   │   surveillance.service    watchdog.service                │  │
    │   │   (main daemon)          (hardware watchdog ping)        │  │
    │   │                                                          │  │
    │   └──────────────────────────┬───────────────────────────────┘  │
    │                              │                                   │
    │   ┌──────────────────────────▼───────────────────────────────┐  │
    │   │                                                          │  │
    │   │              SURVEILLANCE DAEMON (Python 3.11)           │  │
    │   │                                                          │  │
    │   │   ┌────────────────────────────────────────────────┐     │  │
    │   │   │              APPLICATION LAYER                  │     │  │
    │   │   │                                                │     │  │
    │   │   │  main.py ─── Entry point, lifecycle manager    │     │  │
    │   │   │     │                                          │     │  │
    │   │   │     ├── surveillance_loop.py                   │     │  │
    │   │   │     │    Orchestrates camera → detect → alert  │     │  │
    │   │   │     │                                          │     │  │
    │   │   │     ├── alert_manager.py                       │     │  │
    │   │   │     │    Temporal filter, cooldown, queuing    │     │  │
    │   │   │     │                                          │     │  │
    │   │   │     └── command_handler.py                     │     │  │
    │   │   │          Process arm/disarm/snapshot commands   │     │  │
    │   │   └────────────────────────────────────────────────┘     │  │
    │   │                                                          │  │
    │   │   ┌────────────────────────────────────────────────┐     │  │
    │   │   │              DETECTION LAYER                    │     │  │
    │   │   │                                                │     │  │
    │   │   │  camera.py ──── Frame capture, resolution mgmt │     │  │
    │   │   │  motion_detector.py ─ Frame diff, contour area │     │  │
    │   │   │  human_detector.py ── YOLOv5n ONNX inference   │     │  │
    │   │   │  exclusion_zones.py ─ Mask regions to ignore   │     │  │
    │   │   └────────────────────────────────────────────────┘     │  │
    │   │                                                          │  │
    │   │   ┌────────────────────────────────────────────────┐     │  │
    │   │   │              INFRASTRUCTURE LAYER              │     │  │
    │   │   │                                                │     │  │
    │   │   │  mqtt_client.py ──── Publish alerts, subscribe │     │  │
    │   │   │  connectivity.py ─── 4G health, dongle reset   │     │  │
    │   │   │  thermal_manager.py ─ CPU temp, fan control    │     │  │
    │   │   │  power_monitor.py ── Mains detect, UPS status  │     │  │
    │   │   │  usb_watchdog.py ─── Camera liveness, USB reset│     │  │
    │   │   │  ota_updater.py ──── Pull updates from server  │     │  │
    │   │   └────────────────────────────────────────────────┘     │  │
    │   │                                                          │  │
    │   │   ┌────────────────────────────────────────────────┐     │  │
    │   │   │              CONFIGURATION                     │     │  │
    │   │   │                                                │     │  │
    │   │   │  device_config.yaml ─ Device ID, farm ID,      │     │  │
    │   │   │                       MQTT broker, thresholds,  │     │  │
    │   │   │                       scan interval, schedule   │     │  │
    │   │   └────────────────────────────────────────────────┘     │  │
    │   │                                                          │  │
    │   └──────────────────────────────────────────────────────────┘  │
    │                                                                  │
    │   ┌──────────────────────────────────────────────────────────┐  │
    │   │              OS / HARDWARE INTERFACE                      │  │
    │   │                                                          │  │
    │   │  /dev/video0 (Camera 1)     /dev/video2 (Camera 2)      │  │
    │   │  /dev/watchdog (HW WDT)     /sys/class/thermal (temp)   │  │
    │   │  /sys/bus/usb (reset)       /dev/ttyUSB0 (4G modem AT)  │  │
    │   │  GPIO (tamper switch)       /tmp (tmpfs — runtime data) │  │
    │   └──────────────────────────────────────────────────────────┘  │
    │                                                                  │
    └──────────────────────────────────────────────────────────────────┘
```

### 3.2 Process Lifecycle

```
    BOOT
     │
     ▼
    systemd starts surveillance.service
     │
     ▼
    main.py initializes
     │
     ├── Load device_config.yaml
     ├── Initialize MQTT client (connect to broker)
     ├── Open Camera 1 (/dev/video0)
     ├── Open Camera 2 (/dev/video2)
     ├── Load YOLOv5n model into memory (ONNX Runtime)
     ├── Start thermal monitor thread
     ├── Start USB watchdog thread
     ├── Start connectivity monitor thread
     ├── Publish MQTT: status = "online"
     │
     ▼
    ┌─── SURVEILLANCE LOOP (runs until disarmed) ◀───────────────┐
    │                                                             │
    │   Check schedule → within active hours?                    │
    │        │                                                    │
    │       NO ──▶ sleep(60s), re-check                          │
    │        │                                                    │
    │       YES                                                   │
    │        │                                                    │
    │        ▼                                                    │
    │   Grab frame from Camera 1                                 │
    │        │                                                    │
    │        ▼                                                    │
    │   Motion detected? ── NO ──▶ skip                          │
    │        │                        │                           │
    │       YES                       │                           │
    │        │                        │                           │
    │        ▼                        │                           │
    │   Apply exclusion zone mask     │                           │
    │        │                        │                           │
    │        ▼                        │                           │
    │   Run YOLOv5n (person?)         │                           │
    │        │                        │                           │
    │       YES ──▶ increment         │                           │
    │        │      consecutive       │                           │
    │        │      counter           │                           │
    │        │         │              │                           │
    │        │    count >= 3?         │                           │
    │        │      │     │          │                           │
    │        │     YES    NO         │                           │
    │        │      │     └──────────┤                           │
    │        │      ▼                │                           │
    │        │  TRIGGER ALERT        │                           │
    │        │  • capture hi-res     │                           │
    │        │  • publish MQTT       │                           │
    │        │  • start cooldown     │                           │
    │        │                       │                           │
    │        ▼                       │                           │
    │   Grab frame from Camera 2 ◀──┘                           │
    │        │                                                    │
    │        ▼                                                    │
    │   (same motion → YOLO → alert pipeline)                    │
    │        │                                                    │
    │        ▼                                                    │
    │   Ping hardware watchdog (/dev/watchdog)                   │
    │   Notify systemd watchdog (sd_notify)                      │
    │   Report heartbeat (every 60s)                             │
    │        │                                                    │
    └────────┘                                                    │
                                                                  │
    MQTT command received: "disarm" ─────────────────────────────┘
     │
     ▼
    Publish MQTT: status = "disarmed"
    Enter idle mode (heartbeat only)
    Wait for "arm" command to re-enter surveillance loop
```

### 3.3 Thread Architecture

```
    ┌──────────────────────────────────────────────────────┐
    │                   MAIN PROCESS (PID 1)               │
    │                                                      │
    │   Thread 1: SURVEILLANCE LOOP (main thread)          │
    │   ├── Camera capture                                 │
    │   ├── Motion detection                               │
    │   ├── YOLO inference                                 │
    │   └── Alert triggering                               │
    │                                                      │
    │   Thread 2: MQTT CLIENT                              │
    │   ├── Maintain broker connection                     │
    │   ├── Publish alerts/heartbeats                      │
    │   ├── Subscribe to commands                          │
    │   └── Handle reconnection                            │
    │                                                      │
    │   Thread 3: THERMAL MONITOR (daemon thread)          │
    │   ├── Read /sys/class/thermal every 10s              │
    │   ├── Adjust scan rate if CPU > 75C                  │
    │   └── Emergency pause if CPU > 85C                   │
    │                                                      │
    │   Thread 4: USB WATCHDOG (daemon thread)             │
    │   ├── Verify camera file descriptors every 15s       │
    │   ├── Check frame freshness (stale = frozen)         │
    │   └── Reset USB port via sysfs if camera hangs       │
    │                                                      │
    │   Thread 5: CONNECTIVITY MONITOR (daemon thread)     │
    │   ├── Ping 8.8.8.8 every 30s                        │
    │   ├── Check MQTT broker reachability                 │
    │   ├── Reset 4G dongle if 3 consecutive failures      │
    │   └── Manage offline alert queue                     │
    │                                                      │
    └──────────────────────────────────────────────────────┘

    Shared State (thread-safe):
    ├── alert_queue: collections.deque (maxlen=100)
    ├── device_state: threading.Event (armed/disarmed)
    ├── thermal_throttle: threading.Event (normal/throttled)
    └── camera_lock: threading.Lock (serialize USB access)
```

### 3.4 Memory Layout (2GB RAM Budget)

```
    ┌──────────────────────────────────────────┐
    │              2048 MB Total                │
    │                                          │
    │  ┌────────────────────────────────┐      │
    │  │ OS + systemd + kernel         │ 280MB │
    │  ├────────────────────────────────┤      │
    │  │ Python interpreter + libs     │ 120MB │
    │  ├────────────────────────────────┤      │
    │  │ OpenCV (loaded modules)       │  80MB │
    │  ├────────────────────────────────┤      │
    │  │ ONNX Runtime                  │  60MB │
    │  ├────────────────────────────────┤      │
    │  │ YOLOv5n model weights         │ 100MB │
    │  ├────────────────────────────────┤      │
    │  │ Frame buffers (2 cameras)     │ 120MB │
    │  │ (VGA + hi-res + processing)   │       │
    │  ├────────────────────────────────┤      │
    │  │ MQTT client + alert queue     │  30MB │
    │  ├────────────────────────────────┤      │
    │  │ tmpfs (/tmp runtime data)     │ 100MB │
    │  ├────────────────────────────────┤      │
    │  │ ┈┈┈┈┈ FREE / BUFFER ┈┈┈┈┈┈┈  │ ~350MB│  ← Headroom for spikes
    │  │ (kernel page cache, malloc)   │       │
    │  └────────────────────────────────┘      │
    │                                          │
    │  Peak usage: ~1650 MB                    │
    │  Safety margin: ~400 MB                  │
    └──────────────────────────────────────────┘

    SWAP: Disabled (SD card wear + latency)
    OOM Policy: systemd OOMPolicy=kill, Restart=always
```

### 3.5 Filesystem Layout

```
    / (rootfs — READ ONLY via overlayfs)
    ├── /opt/surveillance/
    │   ├── src/                    # Application code
    │   ├── models/yolov5n.onnx     # ML model (3.9MB)
    │   ├── config/device_config.yaml
    │   └── venv/                   # Python virtual environment
    │
    ├── /etc/systemd/system/
    │   ├── surveillance.service
    │   └── surveillance-watchdog.service
    │
    └── /tmp/ (tmpfs — RAM disk, writable)
        ├── alerts/                 # Pending alert images
        ├── frames/                 # Current frame temp files
        ├── surveillance.log        # Rotating log (max 10MB)
        └── surveillance.pid        # Process lock file

    No writes to SD card during normal operation.
    /tmp is wiped on every reboot (by design).
```

---

## 4. Communication Layer — MQTT

### 4.1 Why MQTT

```
    Protocol Comparison for IoT on Cellular

    ┌────────────┬──────────┬──────────┬──────────┬────────────┐
    │ Factor     │   MQTT   │   HTTP   │WebSocket │   CoAP     │
    ├────────────┼──────────┼──────────┼──────────┼────────────┤
    │ Header     │  2-5     │  500+    │  2-6     │  4         │
    │ overhead   │  bytes   │  bytes   │  bytes   │  bytes     │
    ├────────────┼──────────┼──────────┼──────────┼────────────┤
    │ Persistent │  YES     │  NO      │  YES     │  NO        │
    │ connection │          │  (new    │          │  (UDP)     │
    │            │          │  per req)│          │            │
    ├────────────┼──────────┼──────────┼──────────┼────────────┤
    │ QoS levels │  0,1,2   │  N/A     │  N/A     │  CON/NON   │
    ├────────────┼──────────┼──────────┼──────────┼────────────┤
    │ Bi-direct  │  YES     │  NO      │  YES     │  YES       │
    │ (pub/sub)  │  native  │  (poll)  │          │  (observe) │
    ├────────────┼──────────┼──────────┼──────────┼────────────┤
    │ LWT (Last  │  YES     │  NO      │  NO      │  NO        │
    │ Will)      │          │          │          │            │
    ├────────────┼──────────┼──────────┼──────────┼────────────┤
    │ Power      │  LOW     │  HIGH    │  MEDIUM  │  LOWEST    │
    │ usage      │          │          │          │            │
    ├────────────┼──────────┼──────────┼──────────┼────────────┤
    │ Maturity   │  HIGH    │  HIGH    │  HIGH    │  MEDIUM    │
    │ (IoT)      │          │          │          │            │
    └────────────┴──────────┴──────────┴──────────┴────────────┘

    Winner for this use case: MQTT
    ─ Lowest overhead on cellular
    ─ Built-in QoS guarantees delivery
    ─ Last Will Testament detects device offline
    ─ Bi-directional (alerts out, commands in) on single connection
    ─ Massive ecosystem (paho-mqtt, EMQX, Mosquitto)
```

### 4.2 MQTT Broker Configuration (EMQX)

```
    ┌──────────────────────────────────────────────────────┐
    │                    EMQX Broker                        │
    │                                                      │
    │   Listeners:                                         │
    │   ├── TCP  :1883  (internal, backend only)           │
    │   └── TLS  :8883  (external, edge devices)           │
    │                                                      │
    │   Authentication:                                    │
    │   ├── Edge devices: client certificate (mTLS)        │
    │   └── Backend: username/password (internal network)  │
    │                                                      │
    │   ACL Rules:                                         │
    │   ├── Device can PUBLISH to:                         │
    │   │   farm/+/device/{own_id}/alert                   │
    │   │   farm/+/device/{own_id}/image                   │
    │   │   farm/+/device/{own_id}/heartbeat               │
    │   │   farm/+/device/{own_id}/status                  │
    │   │                                                  │
    │   ├── Device can SUBSCRIBE to:                       │
    │   │   farm/+/device/{own_id}/command                 │
    │   │   farm/+/device/{own_id}/config                  │
    │   │                                                  │
    │   └── Backend can PUBLISH/SUBSCRIBE to:              │
    │       farm/#  (all topics)                           │
    │                                                      │
    │   Last Will Testament (per device):                  │
    │   ├── Topic: farm/{id}/device/{id}/status             │
    │   ├── Payload: {"status": "offline_unexpected"}      │
    │   ├── QoS: 1                                         │
    │   └── Retain: true                                   │
    │                                                      │
    │   Session:                                           │
    │   ├── Clean session: false (persistent subscriptions)│
    │   ├── Keep alive: 60 seconds                         │
    │   └── Max message size: 256KB (enough for JPEG)      │
    │                                                      │
    └──────────────────────────────────────────────────────┘
```

### 4.3 Message QoS Strategy

```
    ┌─────────────────┬─────┬────────────────────────────────────┐
    │ Topic           │ QoS │ Rationale                          │
    ├─────────────────┼─────┼────────────────────────────────────┤
    │ .../alert       │  1  │ Must be delivered at least once.   │
    │                 │     │ Duplicate alerts are acceptable.   │
    ├─────────────────┼─────┼────────────────────────────────────┤
    │ .../image       │  1  │ Must arrive. Farmer needs to see   │
    │                 │     │ the snapshot to decide action.      │
    ├─────────────────┼─────┼────────────────────────────────────┤
    │ .../heartbeat   │  0  │ Best effort. Missing a heartbeat   │
    │                 │     │ is detected by absence, not by      │
    │                 │     │ guaranteed delivery.                │
    ├─────────────────┼─────┼────────────────────────────────────┤
    │ .../command     │  1  │ Must be delivered. Arm/disarm is    │
    │                 │     │ critical. Idempotent commands.      │
    ├─────────────────┼─────┼────────────────────────────────────┤
    │ .../status      │  1  │ Retained message. Last known state │
    │                 │     │ must be available for new clients.  │
    ├─────────────────┼─────┼────────────────────────────────────┤
    │ .../config      │  1  │ Config changes must reach device.  │
    │                 │     │ Retained so device gets latest on   │
    │                 │     │ reconnect.                          │
    └─────────────────┴─────┴────────────────────────────────────┘
```

### 4.4 Offline Queue Behavior

```
    NORMAL OPERATION:
    ┌────────┐     ┌────────────┐     ┌────────┐
    │ Detect │────▶│ MQTT Pub   │────▶│ Broker │
    └────────┘     └────────────┘     └────────┘

    CONNECTIVITY LOST:
    ┌────────┐     ┌────────────┐     ┌────────────────┐
    │ Detect │────▶│ MQTT Pub   │──X──│ Broker         │
    └────────┘     │ (fails)    │     │ (unreachable)  │
                   └─────┬──────┘     └────────────────┘
                         │
                         ▼
                   ┌────────────────┐
                   │ Local Queue    │
                   │ (deque in RAM) │
                   │ max: 100 alerts│
                   │ FIFO eviction  │
                   └────────────────┘

    CONNECTIVITY RESTORED:
                   ┌────────────────┐
                   │ Local Queue    │
                   │ [alert1]       │──┐
                   │ [alert2]       │  │  Drain queue
                   │ [alert3]       │  │  oldest first
                   └────────────────┘  │
                                       ▼
                   ┌────────────┐     ┌────────┐
                   │ MQTT Pub   │────▶│ Broker │
                   │ (resumed)  │     │        │
                   └────────────┘     └────────┘
```

---

## 5. Backend Layer — Cloud

### 5.1 Application Architecture

```
    ┌──────────────────────────────────────────────────────────────┐
    │                    FastAPI Application                        │
    │                                                              │
    │   ┌──────────────────────────────────────────────────────┐  │
    │   │                    API LAYER                          │  │
    │   │                                                      │  │
    │   │  POST /api/v1/auth/login         → JWT token         │  │
    │   │  POST /api/v1/auth/register      → Create account    │  │
    │   │                                                      │  │
    │   │  GET  /api/v1/devices            → List user devices │  │
    │   │  POST /api/v1/devices/register   → Register device   │  │
    │   │  GET  /api/v1/devices/{id}/status→ Device health     │  │
    │   │                                                      │  │
    │   │  GET  /api/v1/alerts             → Alert history     │  │
    │   │  GET  /api/v1/alerts/{id}        → Alert detail      │  │
    │   │  GET  /api/v1/alerts/{id}/image  → Alert snapshot    │  │
    │   │                                                      │  │
    │   │  POST /api/v1/commands/arm       → Arm device        │  │
    │   │  POST /api/v1/commands/disarm    → Disarm device     │  │
    │   │  POST /api/v1/commands/snapshot  → Request snapshot  │  │
    │   │  POST /api/v1/commands/reboot    → Reboot device     │  │
    │   │                                                      │  │
    │   │  PUT  /api/v1/settings/schedule  → Update schedule   │  │
    │   │  PUT  /api/v1/settings/zones     → Update exclusions │  │
    │   │  PUT  /api/v1/settings/threshold → Update sensitivity│  │
    │   └──────────────────────────────────────────────────────┘  │
    │                                                              │
    │   ┌──────────────────────────────────────────────────────┐  │
    │   │                  SERVICE LAYER                        │  │
    │   │                                                      │  │
    │   │  mqtt_handler.py                                     │  │
    │   │  ├── Subscribe to farm/+/device/+/alert              │  │
    │   │  ├── Subscribe to farm/+/device/+/image              │  │
    │   │  ├── Subscribe to farm/+/device/+/heartbeat          │  │
    │   │  ├── Subscribe to farm/+/device/+/status             │  │
    │   │  ├── on_alert() → store + trigger notification       │  │
    │   │  ├── on_image() → store in MinIO                     │  │
    │   │  ├── on_heartbeat() → update device health           │  │
    │   │  └── on_status() → update device state               │  │
    │   │                                                      │  │
    │   │  notification_service.py                             │  │
    │   │  ├── send_push() → Firebase FCM                      │  │
    │   │  └── build_payload() → title, body, image URL        │  │
    │   │                                                      │  │
    │   │  storage_service.py                                  │  │
    │   │  ├── upload_image() → MinIO bucket                   │  │
    │   │  └── get_presigned_url() → temporary download URL    │  │
    │   │                                                      │  │
    │   │  device_monitor.py                                   │  │
    │   │  ├── check_heartbeats() → runs every 120s            │  │
    │   │  └── if no heartbeat for 5 min → push "device offline│  │
    │   └──────────────────────────────────────────────────────┘  │
    │                                                              │
    │   ┌──────────────────────────────────────────────────────┐  │
    │   │                  DATA LAYER                           │  │
    │   │                                                      │  │
    │   │  SQLAlchemy ORM + Alembic Migrations                 │  │
    │   │  PostgreSQL 16                                       │  │
    │   │                                                      │  │
    │   │  MinIO (S3-compatible)                               │  │
    │   │  Bucket: alert-snapshots                             │  │
    │   │  Retention: 90 days auto-delete                      │  │
    │   └──────────────────────────────────────────────────────┘  │
    │                                                              │
    └──────────────────────────────────────────────────────────────┘
```

### 5.2 Backend Process Flow

```
    ┌─────────────────────────────────────────────────────────────┐
    │               FastAPI Application Startup                    │
    │                                                             │
    │   1. Load environment config (.env)                         │
    │   2. Initialize PostgreSQL connection pool                  │
    │   3. Run Alembic migrations (auto)                          │
    │   4. Initialize MinIO client                                │
    │   5. Connect MQTT client to EMQX broker                    │
    │   6. Subscribe to all device topics                         │
    │   7. Start heartbeat monitor background task               │
    │   8. Start Uvicorn ASGI server on :8000                    │
    └──────────────────────────────┬──────────────────────────────┘
                                   │
                                   ▼
    ┌──────────────────────────────────────────────────────────────┐
    │                                                              │
    │   EVENT LOOP (concurrent)                                   │
    │                                                              │
    │   ┌──────────────┐    ┌──────────────┐                      │
    │   │ HTTP Handler │    │ MQTT Handler │                      │
    │   │              │    │              │                      │
    │   │ Mobile app   │    │ Edge device  │                      │
    │   │ requests     │    │ messages     │                      │
    │   │ (REST API)   │    │ (pub/sub)    │                      │
    │   └──────┬───────┘    └──────┬───────┘                      │
    │          │                   │                               │
    │          ▼                   ▼                               │
    │   ┌────────────────────────────────────┐                    │
    │   │         SERVICE LAYER              │                    │
    │   │                                    │                    │
    │   │  ┌─ Alert received from device:    │                    │
    │   │  │  1. Validate payload            │                    │
    │   │  │  2. Store alert in PostgreSQL   │                    │
    │   │  │  3. Store image in MinIO        │                    │
    │   │  │  4. Lookup user FCM token       │                    │
    │   │  │  5. Send push notification      │                    │
    │   │  │                                 │                    │
    │   │  ├─ Command from mobile app:       │                    │
    │   │  │  1. Authenticate JWT            │                    │
    │   │  │  2. Authorize (user owns device)│                    │
    │   │  │  3. Publish MQTT command         │                    │
    │   │  │  4. Return acknowledgment       │                    │
    │   │  │                                 │                    │
    │   │  └─ Heartbeat check (periodic):    │                    │
    │   │     1. Query last_heartbeat per dev│                    │
    │   │     2. If stale > 5 min            │                    │
    │   │     3. Push "device offline" notif │                    │
    │   └────────────────────────────────────┘                    │
    │                                                              │
    └──────────────────────────────────────────────────────────────┘
```

---

## 6. Mobile Layer — Android App

### 6.1 Architecture (Flutter)

```
    ┌──────────────────────────────────────────────────────────┐
    │                  FLUTTER APPLICATION                      │
    │                                                          │
    │   ┌──────────────────────────────────────────────────┐  │
    │   │                PRESENTATION LAYER                 │  │
    │   │                                                  │  │
    │   │  Screens:                                        │  │
    │   │  ├── SplashScreen          (app init)            │  │
    │   │  ├── LoginScreen           (auth)                │  │
    │   │  ├── DashboardScreen       (status + controls)   │  │
    │   │  ├── AlertDetailScreen     (snapshot + metadata)  │  │
    │   │  ├── AlertHistoryScreen    (timeline + filters)   │  │
    │   │  └── SettingsScreen        (schedule, zones, etc) │  │
    │   │                                                  │  │
    │   │  State Management: Provider / Riverpod           │  │
    │   └──────────────────────────┬───────────────────────┘  │
    │                              │                           │
    │   ┌──────────────────────────▼───────────────────────┐  │
    │   │                 DOMAIN LAYER                      │  │
    │   │                                                  │  │
    │   │  Models:                                         │  │
    │   │  ├── Device      (id, farm, status, battery)     │  │
    │   │  ├── Alert       (id, timestamp, confidence,     │  │
    │   │  │                camera, image_url)              │  │
    │   │  ├── User        (id, email, fcm_token)          │  │
    │   │  └── DeviceConfig(schedule, zones, threshold)    │  │
    │   │                                                  │  │
    │   │  Repositories (interfaces):                      │  │
    │   │  ├── AuthRepository                              │  │
    │   │  ├── DeviceRepository                            │  │
    │   │  ├── AlertRepository                             │  │
    │   │  └── SettingsRepository                          │  │
    │   └──────────────────────────┬───────────────────────┘  │
    │                              │                           │
    │   ┌──────────────────────────▼───────────────────────┐  │
    │   │                  DATA LAYER                       │  │
    │   │                                                  │  │
    │   │  Services:                                       │  │
    │   │  ├── ApiService          (Dio HTTP client)       │  │
    │   │  │   └── Base URL: https://api.example.com       │  │
    │   │  ├── FcmService          (Firebase Messaging)    │  │
    │   │  │   ├── onMessage       (foreground alerts)     │  │
    │   │  │   ├── onBackgroundMsg  (background alerts)    │  │
    │   │  │   └── requestPermission                       │  │
    │   │  ├── AuthService         (JWT token management)  │  │
    │   │  │   └── SecureStorage   (flutter_secure_storage)│  │
    │   │  └── LocalStorageService (SQLite for offline)     │  │
    │   └──────────────────────────────────────────────────┘  │
    │                                                          │
    └──────────────────────────────────────────────────────────┘
```

### 6.2 Notification Handling

```
    ┌───────────────────────────────────────────────────────────────┐
    │                 FCM NOTIFICATION FLOW                          │
    │                                                               │
    │   APP STATE        ACTION                                     │
    │   ─────────        ──────                                     │
    │                                                               │
    │   Foreground  ──▶  Show in-app banner with snapshot           │
    │                    Play alert sound                            │
    │                    Vibrate device                              │
    │                    Auto-navigate to AlertDetail on tap         │
    │                                                               │
    │   Background  ──▶  System notification tray                   │
    │                    Show title + body + thumbnail               │
    │                    Play alert sound                            │
    │                    Tap opens app → AlertDetail                 │
    │                                                               │
    │   Killed      ──▶  System notification tray                   │
    │                    High-priority notification                  │
    │                    Tap cold-starts app → AlertDetail           │
    │                                                               │
    │   DND Mode    ──▶  Override DND (critical notification        │
    │                    channel on Android — requires user          │
    │                    to grant "override DND" permission)         │
    └───────────────────────────────────────────────────────────────┘
```

---

## 7. AI/ML Pipeline

### 7.1 Model Architecture

```
    ┌──────────────────────────────────────────────────────────┐
    │                    YOLOv5n (Nano)                         │
    │                                                          │
    │   Input: 320 x 320 x 3 (RGB)                            │
    │                                                          │
    │   ┌──────────────┐                                      │
    │   │  BACKBONE     │   CSPDarknet (depth=0.33, width=0.25)│
    │   │  (Feature     │   Extracts spatial features at        │
    │   │   Extraction) │   multiple scales                     │
    │   └──────┬───────┘                                      │
    │          │                                               │
    │   ┌──────▼───────┐                                      │
    │   │  NECK         │   PANet (Path Aggregation Network)   │
    │   │  (Feature     │   Fuses multi-scale features         │
    │   │   Fusion)     │                                      │
    │   └──────┬───────┘                                      │
    │          │                                               │
    │   ┌──────▼───────┐                                      │
    │   │  HEAD         │   Detect layer                       │
    │   │  (Detection)  │   80 COCO classes                    │
    │   │               │   We filter: class 0 (person) only   │
    │   └──────┬───────┘                                      │
    │          │                                               │
    │   Output: [x, y, w, h, confidence, class_scores]        │
    │                                                          │
    │   Model size:  3.9 MB (ONNX)                            │
    │   Parameters:  1.9M                                      │
    │   GFLOPs:      4.5                                       │
    │   mAP@0.5:     28.0 (COCO val)                          │
    └──────────────────────────────────────────────────────────┘
```

### 7.2 Inference Pipeline Detail

```
    RAW FRAME (640x480, BGR, uint8)
         │
         ▼
    ┌─────────────────────────────────┐
    │  PRE-PROCESSING                 │
    │                                 │
    │  1. Resize: 640x480 → 320x320  │  (letterbox padding)
    │  2. Color:  BGR → RGB          │
    │  3. Type:   uint8 → float32    │
    │  4. Scale:  [0,255] → [0,1]    │
    │  5. Dims:   HWC → NCHW         │  (batch=1)
    │                                 │
    │  Output: tensor [1,3,320,320]  │
    │  Time: ~5ms                     │
    └────────────┬────────────────────┘
                 │
                 ▼
    ┌─────────────────────────────────┐
    │  ONNX RUNTIME INFERENCE        │
    │                                 │
    │  Provider: CPUExecutionProvider │
    │  Threads:  2 (half of 4 cores) │
    │  Model:    yolov5n.onnx        │
    │                                 │
    │  Output: [N, 85] detections    │
    │  (x, y, w, h, obj_conf,       │
    │   80 class probabilities)      │
    │                                 │
    │  Time: ~280ms                   │
    └────────────┬────────────────────┘
                 │
                 ▼
    ┌─────────────────────────────────┐
    │  POST-PROCESSING               │
    │                                 │
    │  1. Filter: class=0 (person)   │
    │  2. Threshold: conf > 0.6      │
    │  3. NMS: IoU threshold 0.45    │
    │     (remove overlapping boxes) │
    │  4. Scale boxes back to        │
    │     original 640x480 coords    │
    │                                 │
    │  Output: List[Detection]       │
    │  Time: ~3ms                     │
    └────────────┬────────────────────┘
                 │
                 ▼
    ┌─────────────────────────────────┐
    │  EXCLUSION ZONE FILTER         │
    │                                 │
    │  Check if detection bbox       │
    │  center falls within any       │
    │  user-defined exclusion zone   │
    │  (scarecrow, clothesline)      │
    │                                 │
    │  If inside zone → discard      │
    │  Time: ~1ms                     │
    └────────────┬────────────────────┘
                 │
                 ▼
    Result: List[ValidDetection] or empty

    TOTAL INFERENCE TIME: ~290ms per frame
```

### 7.3 Model Update Path

```
    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
    │  Training    │     │  Export      │     │  Deploy      │
    │  Server      │────▶│              │────▶│              │
    │  (offline)   │     │  .pt → .onnx │     │  OTA to edge │
    │              │     │              │     │              │
    │  Fine-tune   │     │  Quantize    │     │  Validate    │
    │  on farm     │     │  INT8        │     │  on device   │
    │  specific    │     │  (optional)  │     │  before swap │
    │  data        │     │              │     │              │
    └──────────────┘     └──────────────┘     └──────────────┘

    Model A/B swap:
    1. Download new model to /tmp/yolov5n_new.onnx
    2. Run validation inference on 10 test frames
    3. If accuracy acceptable → replace active model
    4. If fails → keep existing model, report to server
```

---

## 8. Database Design

### 8.1 Entity Relationship Diagram

```
    ┌────────────────┐       ┌────────────────┐
    │     users      │       │    farms       │
    ├────────────────┤       ├────────────────┤
    │ id          PK │──┐    │ id          PK │──┐
    │ email          │  │    │ name           │  │
    │ password_hash  │  │    │ location       │  │
    │ fcm_token      │  │    │ owner_id    FK │──┘ (users.id)
    │ created_at     │  │    │ created_at     │
    │ updated_at     │  │    │ updated_at     │
    └────────────────┘  │    └────────────────┘
                        │           │
                        │           │ 1:N
                        │           ▼
                        │    ┌────────────────┐
                        │    │   devices      │
                        │    ├────────────────┤
                        │    │ id          PK │──────────────┐
                        │    │ device_uid     │ (unique)     │
                        │    │ farm_id     FK │              │
                        │    │ status         │ (armed/      │
                        │    │                │  disarmed/   │
                        │    │                │  offline)    │
                        │    │ last_heartbeat │              │
                        │    │ battery_pct    │              │
                        │    │ cpu_temp       │              │
                        │    │ signal_dbm     │              │
                        │    │ firmware_ver   │              │
                        │    │ config_json    │ (schedule,   │
                        │    │                │  threshold,  │
                        │    │                │  zones)      │
                        │    │ created_at     │              │
                        │    │ updated_at     │              │
                        │    └────────────────┘              │
                        │                                    │
                        │                          1:N       │
                        │                                    ▼
                        │                         ┌────────────────┐
                        │                         │    alerts      │
                        │                         ├────────────────┤
                        │                         │ id          PK │
                        │                         │ device_id   FK │
                        │                         │ event_type     │
                        │                         │ camera_id      │
                        │                         │ confidence     │
                        │                         │ person_count   │
                        │                         │ bbox_json      │
                        │                         │ direction      │
                        │                         │ image_path     │ (MinIO key)
                        │                         │ acknowledged   │ (boolean)
                        │                         │ created_at     │
                        │                         └────────────────┘
                        │
                        │                         ┌────────────────┐
                        │                         │ command_log    │
                        │                         ├────────────────┤
                        │                         │ id          PK │
                        └─────────────────────────│ user_id     FK │
                                                  │ device_id   FK │
                                                  │ command        │
                                                  │ payload_json   │
                                                  │ status         │ (sent/acked/
                                                  │                │  failed)
                                                  │ created_at     │
                                                  └────────────────┘
```

### 8.2 Indexes

```
    alerts:
      - idx_alerts_device_created    ON (device_id, created_at DESC)
      - idx_alerts_created           ON (created_at DESC)

    devices:
      - idx_devices_uid              ON (device_uid) UNIQUE
      - idx_devices_farm             ON (farm_id)
      - idx_devices_heartbeat        ON (last_heartbeat)

    command_log:
      - idx_cmdlog_device_created    ON (device_id, created_at DESC)
```

### 8.3 Data Retention

```
    ┌──────────────┬───────────┬────────────────────────────┐
    │ Data         │ Retention │ Policy                     │
    ├──────────────┼───────────┼────────────────────────────┤
    │ Alerts       │ 180 days  │ pg_cron daily cleanup      │
    │ Snapshots    │  90 days  │ MinIO lifecycle policy      │
    │ Heartbeats   │   7 days  │ Aggregated, then purged    │
    │ Command logs │  90 days  │ pg_cron daily cleanup      │
    │ User data    │ Permanent │ Until account deletion     │
    └──────────────┴───────────┴────────────────────────────┘
```

---

## 9. API Specification

### 9.1 Authentication

```
    POST /api/v1/auth/login
    ─────────────────────────────────────────────

    Request:
    {
        "email": "farmer@example.com",
        "password": "********"
    }

    Response (200):
    {
        "access_token": "eyJhbGciOiJIUzI1NiIs...",
        "token_type": "bearer",
        "expires_in": 86400
    }

    All subsequent requests:
    Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### 9.2 Core Endpoints

```
    ┌────────┬──────────────────────────────┬───────────────────────────┐
    │ Method │ Endpoint                     │ Description               │
    ├────────┼──────────────────────────────┼───────────────────────────┤
    │ POST   │ /api/v1/auth/register        │ Create farmer account     │
    │ POST   │ /api/v1/auth/login           │ Get JWT token             │
    │ POST   │ /api/v1/auth/fcm-token       │ Update FCM token          │
    ├────────┼──────────────────────────────┼───────────────────────────┤
    │ GET    │ /api/v1/farms                │ List farmer's farms       │
    │ POST   │ /api/v1/farms                │ Register new farm         │
    ├────────┼──────────────────────────────┼───────────────────────────┤
    │ GET    │ /api/v1/devices              │ List devices (all farms)  │
    │ POST   │ /api/v1/devices              │ Register new device       │
    │ GET    │ /api/v1/devices/{id}         │ Device details + health   │
    │ DELETE │ /api/v1/devices/{id}         │ Unregister device         │
    ├────────┼──────────────────────────────┼───────────────────────────┤
    │ GET    │ /api/v1/alerts               │ List alerts (paginated)   │
    │        │   ?device_id=&from=&to=      │ Filter by device, date    │
    │ GET    │ /api/v1/alerts/{id}          │ Single alert detail       │
    │ GET    │ /api/v1/alerts/{id}/image    │ Redirect to presigned URL │
    │ PATCH  │ /api/v1/alerts/{id}/ack      │ Acknowledge alert         │
    ├────────┼──────────────────────────────┼───────────────────────────┤
    │ POST   │ /api/v1/commands             │ Send command to device    │
    │        │   {device_id, action, params}│ arm/disarm/snapshot/reboot│
    ├────────┼──────────────────────────────┼───────────────────────────┤
    │ GET    │ /api/v1/settings/{device_id} │ Get device config         │
    │ PUT    │ /api/v1/settings/{device_id} │ Update device config      │
    │        │   {schedule, zones, threshold│ Pushed via MQTT           │
    └────────┴──────────────────────────────┴───────────────────────────┘
```

### 9.3 Alert Response Schema

```json
    {
        "id": 1042,
        "device_id": "FARM-MH-001",
        "farm_name": "Ganesh Farm, Nashik",
        "event_type": "intrusion_detected",
        "camera_id": "cam_front",
        "direction": "north",
        "confidence": 0.87,
        "person_count": 1,
        "bounding_boxes": [
            {"x": 120, "y": 80, "w": 220, "h": 330}
        ],
        "image_url": "https://api.example.com/api/v1/alerts/1042/image",
        "device_status": {
            "battery_pct": 72,
            "cpu_temp_c": 58,
            "signal_dbm": -67
        },
        "acknowledged": false,
        "created_at": "2026-09-04T22:15:03.412Z"
    }
```

---

## 10. Network Architecture

### 10.1 Network Topology

```
    ┌─────────────────────────────────────────────────────────────────┐
    │                                                                 │
    │   EDGE DEVICE                                                  │
    │   ┌────────────────────────┐                                   │
    │   │  Orange Pi              │                                   │
    │   │  ┌──────────────────┐  │                                   │
    │   │  │ eth_usb0         │  │   USB 4G Dongle                   │
    │   │  │ (RNDIS interface)│──┼──▶ SIM (Jio/Airtel)              │
    │   │  │ DHCP from dongle │  │   NAT IP (carrier-grade NAT)     │
    │   │  └──────────────────┘  │                                   │
    │   │                        │                                   │
    │   │  ┌──────────────────┐  │                                   │
    │   │  │ wg0 (WireGuard)  │──┼──▶ VPN tunnel to cloud VPS       │
    │   │  │ 10.10.0.x/24     │  │   (for remote SSH access)        │
    │   │  └──────────────────┘  │                                   │
    │   └────────────────────────┘                                   │
    │                                                                 │
    └───────────────────────────────┬─────────────────────────────────┘
                                    │
                       4G LTE (Carrier Network)
                       Carrier-Grade NAT
                       (no inbound connections possible)
                                    │
                                    ▼
    ┌───────────────────────────────────────────────────────────────────┐
    │                                                                   │
    │   CLOUD VPS (Public IP: x.x.x.x)                                │
    │                                                                   │
    │   ┌───────────────────────────────────────────────────────────┐  │
    │   │  Firewall (iptables / ufw)                                │  │
    │   │                                                           │  │
    │   │  ALLOW:                                                   │  │
    │   │  ├── TCP :8883  ← MQTT TLS (edge devices)                │  │
    │   │  ├── TCP :443   ← HTTPS (mobile app API)                 │  │
    │   │  ├── UDP :51820 ← WireGuard VPN (edge devices)           │  │
    │   │  └── TCP :22    ← SSH (admin only, key auth)             │  │
    │   │                                                           │  │
    │   │  INTERNAL ONLY (127.0.0.1 / docker network):             │  │
    │   │  ├── TCP :1883  ← MQTT plain (backend ↔ EMQX)           │  │
    │   │  ├── TCP :8000  ← FastAPI (behind Nginx)                 │  │
    │   │  ├── TCP :5432  ← PostgreSQL                             │  │
    │   │  └── TCP :9000  ← MinIO                                  │  │
    │   └───────────────────────────────────────────────────────────┘  │
    │                                                                   │
    │   ┌───────────────────────────────────────────────────────────┐  │
    │   │  WireGuard Server                                         │  │
    │   │  Interface: wg0 (10.10.0.1/24)                           │  │
    │   │                                                           │  │
    │   │  Peers:                                                   │  │
    │   │  ├── FARM-MH-001: 10.10.0.2                              │  │
    │   │  ├── FARM-MH-002: 10.10.0.3                              │  │
    │   │  └── ...                                                  │  │
    │   │                                                           │  │
    │   │  Purpose: SSH into edge devices for debugging/OTA         │  │
    │   │  Bandwidth: minimal (management traffic only)             │  │
    │   └───────────────────────────────────────────────────────────┘  │
    │                                                                   │
    └───────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTPS (:443)
                                    ▼
    ┌───────────────────────────────────────────────────────────────────┐
    │   MOBILE APP                                                      │
    │   ├── REST API calls → https://api.example.com/api/v1/...        │
    │   └── FCM push ← Firebase (Google infrastructure)                │
    └───────────────────────────────────────────────────────────────────┘
```

### 10.2 Bandwidth Budget

```
    ┌──────────────────────────────────────────────────────────────┐
    │              MONTHLY BANDWIDTH ESTIMATE                      │
    │                                                              │
    │  Heartbeats:                                                │
    │  ├── Size: ~200 bytes × 1/minute × 43,200 min/month         │
    │  └── Total: ~8.6 MB/month                                   │
    │                                                              │
    │  Alert (intrusion):                                         │
    │  ├── Metadata: ~500 bytes                                   │
    │  ├── Snapshot: ~80 KB (compressed JPEG)                     │
    │  ├── Assuming 5 real alerts/day × 30 days = 150 alerts      │
    │  └── Total: ~12 MB/month                                    │
    │                                                              │
    │  Commands (arm/disarm):                                     │
    │  ├── ~200 bytes × 2/day × 30 = negligible                  │
    │  └── Total: <0.1 MB/month                                   │
    │                                                              │
    │  MQTT overhead (keep-alive, TLS):                           │
    │  └── Total: ~5 MB/month                                     │
    │                                                              │
    │  WireGuard VPN (keep-alive):                                │
    │  └── Total: ~3 MB/month                                     │
    │                                                              │
    │  ══════════════════════════════                              │
    │  GRAND TOTAL: ~29 MB/month                                  │
    │  With safety margin (2x): ~60 MB/month                      │
    │  Well within 1 GB data plan                                  │
    └──────────────────────────────────────────────────────────────┘
```

---

## 11. Reliability Engineering

### 11.1 Failure Recovery Matrix

```
    ┌───────────────────┬─────────────────┬──────────────────────────┐
    │ Failure           │ Detection       │ Recovery                 │
    ├───────────────────┼─────────────────┼──────────────────────────┤
    │                   │                 │                          │
    │ Daemon crash      │ systemd         │ Restart=always           │
    │                   │ WatchdogSec=30  │ RestartSec=5             │
    │                   │                 │ StartLimitBurst=5        │
    │                   │                 │                          │
    │ Daemon hang       │ Hardware WDT    │ Board reboot after 60s   │
    │ (infinite loop)   │ /dev/watchdog   │ no ping                  │
    │                   │                 │                          │
    │ Camera 1 freeze   │ USB watchdog    │ Reset USB port, reopen   │
    │                   │ (no new frame   │ camera. If fails 3x,     │
    │                   │  for 30s)       │ continue with camera 2   │
    │                   │                 │ only + alert admin        │
    │                   │                 │                          │
    │ Camera 2 freeze   │ Same            │ Same (continue cam 1)    │
    │                   │                 │                          │
    │ Both cameras dead │ USB watchdog    │ Full USB bus reset.      │
    │                   │                 │ If persists, reboot.     │
    │                   │                 │ Alert: "cameras offline" │
    │                   │                 │                          │
    │ 4G dongle hang    │ Ping watchdog   │ USB reset dongle.        │
    │                   │ (3 failed pings)│ Wait 30s for re-register │
    │                   │                 │ Queue alerts locally     │
    │                   │                 │                          │
    │ Cellular outage   │ Ping watchdog   │ Queue alerts (100 max)   │
    │ (tower down)      │                 │ Flush on reconnect       │
    │                   │                 │ Farmer gets "offline"    │
    │                   │                 │ notification from cloud  │
    │                   │                 │                          │
    │ Power cut         │ UPS switchover  │ Continue on battery.     │
    │                   │ (instant)       │ Alert: "on battery"      │
    │                   │                 │ Reduce scan rate to      │
    │                   │                 │ conserve power            │
    │                   │                 │                          │
    │ CPU overheat      │ Thermal monitor │ > 75C: reduce scan rate  │
    │                   │ (10s interval)  │ > 85C: pause inference,  │
    │                   │                 │   motion-only mode       │
    │                   │                 │ > 90C: alert + shutdown  │
    │                   │                 │                          │
    │ SD card corrupt   │ Read-only rootfs│ overlayfs protects base. │
    │                   │ prevents this   │ /tmp is tmpfs (RAM).     │
    │                   │                 │ No writes to SD card.    │
    │                   │                 │                          │
    │ Physical tamper   │ Tamper switch   │ Instant alert via MQTT   │
    │ (device moved)    │ (GPIO interrupt)│ even before cameras can  │
    │                   │                 │ capture anything         │
    │                   │                 │                          │
    │ MQTT broker down  │ paho-mqtt       │ Auto-reconnect with      │
    │                   │ on_disconnect   │ exponential backoff      │
    │                   │                 │ (1s, 2s, 4s, 8s, max 60s)│
    │                   │                 │                          │
    │ Cloud VPS down    │ N/A (edge is    │ Edge continues detection │
    │                   │ autonomous)     │ Alerts queued locally    │
    │                   │                 │ No notification until    │
    │                   │                 │ cloud recovers           │
    └───────────────────┴─────────────────┴──────────────────────────┘
```

### 11.2 Graceful Degradation Modes

```
    FULL CAPABILITY (Normal)
    ├── 2 cameras active
    ├── Motion + YOLO detection
    ├── MQTT connected
    ├── Alerts sent in real-time
    │
    ▼ Camera 1 fails
    DEGRADED — SINGLE CAMERA
    ├── 1 camera active (180 coverage)
    ├── Detection continues
    ├── Alert sent: "Camera 1 offline"
    │
    ▼ Network fails
    DEGRADED — OFFLINE
    ├── 1 camera active
    ├── Detection continues
    ├── Alerts queued locally (RAM)
    ├── Cloud notifies farmer: "Device offline"
    │
    ▼ CPU overheat
    DEGRADED — MOTION ONLY
    ├── 1 camera active
    ├── Motion detection only (no YOLO)
    ├── Higher false positive rate
    ├── Alert sent: "Reduced detection mode"
    │
    ▼ Both cameras fail
    MINIMAL — TAMPER ONLY
    ├── No visual detection
    ├── Tamper switch still active
    ├── Heartbeat still running
    ├── Alert sent: "All cameras offline"
    │
    ▼ Complete hardware failure
    DEAD
    ├── Cloud detects missing heartbeat (5 min)
    └── Farmer notified: "Device unreachable"
```

---

## 12. Security Architecture

### 12.1 Security Layers

```
    ┌─────────────────────────────────────────────────────────┐
    │                    SECURITY LAYERS                       │
    │                                                         │
    │   LAYER 1: TRANSPORT SECURITY                          │
    │   ┌─────────────────────────────────────────────────┐  │
    │   │  MQTT: TLS 1.3 (port 8883)                      │  │
    │   │  ├── Server certificate (Let's Encrypt)         │  │
    │   │  ├── Client certificate (per device, mTLS)      │  │
    │   │  └── Cipher: TLS_AES_256_GCM_SHA384             │  │
    │   │                                                  │  │
    │   │  API: HTTPS (TLS 1.3 via Nginx)                  │  │
    │   │  VPN: WireGuard (ChaCha20-Poly1305)              │  │
    │   └─────────────────────────────────────────────────┘  │
    │                                                         │
    │   LAYER 2: AUTHENTICATION                              │
    │   ┌─────────────────────────────────────────────────┐  │
    │   │  Edge → Broker:  mTLS client certificate        │  │
    │   │  App → API:      JWT (HS256, 24h expiry)        │  │
    │   │  Admin → VPS:    SSH key only (no password)     │  │
    │   │  SIM card:       PIN locked                     │  │
    │   └─────────────────────────────────────────────────┘  │
    │                                                         │
    │   LAYER 3: AUTHORIZATION                               │
    │   ┌─────────────────────────────────────────────────┐  │
    │   │  MQTT ACL:  Device can only pub/sub own topics  │  │
    │   │  API RBAC:  User can only access own farm data  │  │
    │   │  Ownership: device → farm → user chain verified │  │
    │   └─────────────────────────────────────────────────┘  │
    │                                                         │
    │   LAYER 4: DATA INTEGRITY                              │
    │   ┌─────────────────────────────────────────────────┐  │
    │   │  Alert payload: timestamp + nonce (anti-replay) │  │
    │   │  Image: SHA256 hash in alert metadata           │  │
    │   │  Config: version counter (reject stale configs) │  │
    │   └─────────────────────────────────────────────────┘  │
    │                                                         │
    │   LAYER 5: PHYSICAL SECURITY                           │
    │   ┌─────────────────────────────────────────────────┐  │
    │   │  Tamper switch (reed/tilt sensor)                │  │
    │   │  12ft mount height (out of casual reach)        │  │
    │   │  Concealed cables (inside pole)                  │  │
    │   │  No external ports exposed                      │  │
    │   └─────────────────────────────────────────────────┘  │
    │                                                         │
    └─────────────────────────────────────────────────────────┘
```

### 12.2 Certificate Management

```
    DEVICE PROVISIONING (one-time, during installation):

    1. Generate key pair on device:
       openssl genrsa -out device.key 2048

    2. Create CSR:
       openssl req -new -key device.key -out device.csr \
         -subj "/CN=FARM-MH-001/O=AntiTheft"

    3. Sign with CA (on provisioning laptop):
       openssl x509 -req -in device.csr \
         -CA ca.crt -CAkey ca.key \
         -out device.crt -days 3650

    4. Install on device:
       /opt/surveillance/certs/
       ├── ca.crt          (CA certificate — verify broker)
       ├── device.crt      (device certificate — identify self)
       └── device.key      (private key — never leaves device)

    5. Register public cert fingerprint in EMQX ACL database

    Certificate rotation: OTA push new cert before expiry
    Revocation: Remove from EMQX ACL + push "decommission" command
```

---

## 13. Deployment Architecture

### 13.1 Cloud Deployment (Docker Compose)

```
    docker-compose.yml
    ┌──────────────────────────────────────────────────────┐
    │                                                      │
    │   ┌──────────┐  ┌──────────┐  ┌──────────┐         │
    │   │  nginx   │  │ fastapi  │  │ emqx     │         │
    │   │  :443    │─▶│ :8000    │  │ :1883    │         │
    │   │  :80     │  │          │  │ :8883    │         │
    │   │ (TLS     │  │ (2 workers│  │ :18083   │         │
    │   │  term)   │  │  uvicorn) │  │ (dashboard)│        │
    │   └──────────┘  └────┬─────┘  └──────────┘         │
    │                      │                               │
    │   ┌──────────────────▼──────────────────────────┐   │
    │   │              docker network                  │   │
    │   │              (bridge: atss_net)               │   │
    │   └──────────────────┬──────────────────────────┘   │
    │                      │                               │
    │   ┌──────────┐  ┌────▼─────┐                        │
    │   │ postgres │  │  minio   │                        │
    │   │ :5432    │  │  :9000   │                        │
    │   │          │  │  :9001   │                        │
    │   │ vol:     │  │ (console)│                        │
    │   │  pgdata  │  │  vol:    │                        │
    │   │          │  │  mdata   │                        │
    │   └──────────┘  └──────────┘                        │
    │                                                      │
    │   Volumes:                                           │
    │   ├── pgdata     (PostgreSQL data)                  │
    │   ├── mdata      (MinIO object data)                │
    │   ├── emqx_data  (EMQX persistence)                 │
    │   └── certs      (TLS certificates)                 │
    │                                                      │
    └──────────────────────────────────────────────────────┘
```

### 13.2 Edge Deployment (Setup Script)

```
    setup.sh — Run once on fresh Armbian installation:

    ┌──────────────────────────────────────────────────┐
    │  1. System update (apt update && apt upgrade)    │
    │  2. Install Python 3.11, pip, venv               │
    │  3. Install OpenCV dependencies (libopencv)      │
    │  4. Install system packages (usbutils, v4l-utils)│
    │  5. Create /opt/surveillance directory            │
    │  6. Set up Python venv + install requirements    │
    │  7. Download YOLOv5n ONNX model                  │
    │  8. Copy device_config.yaml (with unique IDs)    │
    │  9. Install TLS certificates                     │
    │ 10. Install systemd service files                │
    │ 11. Configure read-only rootfs (overlayfs)       │
    │ 12. Configure hardware watchdog                  │
    │ 13. Set up WireGuard VPN tunnel                  │
    │ 14. Enable and start surveillance.service        │
    │ 15. Verify: cameras detected, MQTT connected     │
    └──────────────────────────────────────────────────┘
```

---

## 14. Monitoring and Observability

### 14.1 Health Metrics

```
    EDGE DEVICE → CLOUD (via heartbeat every 60s)
    ┌──────────────────────────────────────────┐
    │  {                                        │
    │    "device_id": "FARM-MH-001",           │
    │    "timestamp": "2026-09-04T22:15:00Z",  │
    │    "uptime_seconds": 604800,             │
    │    "cpu_temp_c": 58,                     │
    │    "cpu_usage_pct": 35,                  │
    │    "memory_used_mb": 1420,               │
    │    "memory_total_mb": 2048,              │
    │    "battery_pct": 72,                    │
    │    "power_source": "mains",             │
    │    "signal_dbm": -67,                    │
    │    "camera_1_status": "active",          │
    │    "camera_2_status": "active",          │
    │    "inference_avg_ms": 295,              │
    │    "scan_cycle_ms": 710,                 │
    │    "alerts_today": 3,                    │
    │    "alerts_queued": 0,                   │
    │    "firmware_version": "1.2.0",          │
    │    "model_version": "yolov5n-v1"         │
    │  }                                        │
    └──────────────────────────────────────────┘
```

### 14.2 Cloud Monitoring Dashboard

```
    ┌──────────────────────────────────────────────────────────────┐
    │  ADMIN DASHBOARD (EMQX Console + Custom)                     │
    │                                                              │
    │  ┌─── Device Fleet ──────────────────────────────────────┐  │
    │  │                                                        │  │
    │  │  Total: 47    Online: 44    Offline: 2    Warning: 1  │  │
    │  │                                                        │  │
    │  │  FARM-MH-001  ● Online   58C  72%bat  -67dBm  v1.2.0 │  │
    │  │  FARM-MH-002  ● Online   52C  91%bat  -72dBm  v1.2.0 │  │
    │  │  FARM-PU-003  ○ Offline  --   --      --       v1.1.0 │  │
    │  │  FARM-KA-004  ▲ Warning  81C  45%bat  -89dBm  v1.2.0 │  │
    │  │  ...                                                   │  │
    │  └────────────────────────────────────────────────────────┘  │
    │                                                              │
    │  ┌─── Alerts Today ──────────────────────────────────────┐  │
    │  │  Total: 127   True Positive: 89   False Positive: 38  │  │
    │  │  FP Rate: 29.9%                                       │  │
    │  └────────────────────────────────────────────────────────┘  │
    │                                                              │
    │  ┌─── System Health ─────────────────────────────────────┐  │
    │  │  MQTT Connections: 44     Messages/min: 52            │  │
    │  │  API Requests/min: 12    DB Size: 2.1 GB              │  │
    │  │  MinIO Used: 8.4 GB      FCM Sent Today: 89           │  │
    │  └────────────────────────────────────────────────────────┘  │
    │                                                              │
    └──────────────────────────────────────────────────────────────┘
```

---

## 15. OTA Update Mechanism

### 15.1 Update Flow

```
    ADMIN                    CLOUD                     EDGE DEVICE
    ─────                    ─────                     ───────────
      │                        │                           │
      │  Upload new package    │                           │
      │  (tar.gz: code +      │                           │
      │   model + config)     │                           │
      ├───────────────────────▶│                           │
      │                        │                           │
      │  Select target devices │                           │
      ├───────────────────────▶│                           │
      │                        │                           │
      │                        ├── MQTT: config ──────────▶│
      │                        │   {action: "update",      │
      │                        │    url: "https://...",     │
      │                        │    checksum: "sha256:..."} │
      │                        │                           │
      │                        │                    ┌──────┤
      │                        │                    │ 1. Download package
      │                        │                    │ 2. Verify checksum
      │                        │                    │ 3. Extract to /tmp/update
      │                        │                    │ 4. Run pre-update checks
      │                        │                    │ 5. Stop surveillance
      │                        │                    │ 6. Remount rootfs rw
      │                        │                    │ 7. Apply update
      │                        │                    │ 8. Remount rootfs ro
      │                        │                    │ 9. Restart surveillance
      │                        │                    │ 10. Run post-update verify
      │                        │                    └──────┤
      │                        │                           │
      │                        │◀── MQTT: status ──────────┤
      │                        │   {update: "success",      │
      │                        │    version: "1.3.0"}       │
      │                        │                           │
      │                        │   OR                       │
      │                        │                           │
      │                        │◀── MQTT: status ──────────┤
      │                        │   {update: "rollback",     │
      │                        │    error: "verify failed"} │
      │                        │                           │

    ROLLBACK: If post-update verification fails,
    restore from /opt/surveillance.bak/ (created before update)
```

---

## 16. Performance Budgets

### 16.1 Latency Budget (Detection to Notification)

```
    ┌──────────────────────────────────────────────────────────────┐
    │                                                              │
    │   LATENCY BREAKDOWN (worst case)                            │
    │                                                              │
    │   Motion detection (OpenCV)         :     5 ms              │
    │   YOLO inference (frame 1)          :   300 ms              │
    │   YOLO inference (frame 2)          :   300 ms              │
    │   YOLO inference (frame 3)          :   300 ms              │
    │   ── Temporal validation ───────────: ~1000 ms (3 frames)   │
    │                                                              │
    │   High-res capture + JPEG compress  :    50 ms              │
    │   MQTT publish (alert + image)      :    20 ms              │
    │   ── Edge total ────────────────────: ~1070 ms              │
    │                                                              │
    │   4G network latency                :   200 ms              │
    │   MQTT broker routing               :    10 ms              │
    │   ── Network total ─────────────────:   210 ms              │
    │                                                              │
    │   FastAPI processing + DB write     :    50 ms              │
    │   MinIO image upload                :   100 ms              │
    │   Firebase FCM API call             :   200 ms              │
    │   ── Cloud total ───────────────────:   350 ms              │
    │                                                              │
    │   FCM delivery to device            :   500 ms              │
    │   ── Mobile total ──────────────────:   500 ms              │
    │                                                              │
    │   ══════════════════════════════════════════                 │
    │   TOTAL END-TO-END (worst case)     : ~2130 ms              │
    │   TARGET                            : <5000 ms              │
    │   STATUS                            : WITHIN BUDGET         │
    │                                                              │
    └──────────────────────────────────────────────────────────────┘
```

### 16.2 Resource Budgets

```
    ┌──────────────────────────────────────────────┐
    │  CPU BUDGET (4 cores @ 1.5 GHz)              │
    │                                              │
    │  Surveillance loop:        2 cores (50%)     │
    │  Watchdog threads:         0.2 cores (5%)    │
    │  MQTT client:              0.1 cores (2.5%)  │
    │  OS + systemd:             0.5 cores (12.5%) │
    │  Headroom:                 1.2 cores (30%)   │
    │                                              │
    │  MEMORY BUDGET (2048 MB)                     │
    │                                              │
    │  OS + kernel:              280 MB (13.7%)    │
    │  Application:              890 MB (43.5%)    │
    │  tmpfs (/tmp):             100 MB (4.9%)     │
    │  Headroom:                 778 MB (38.0%)    │
    │                                              │
    │  STORAGE BUDGET (16 GB SD)                   │
    │                                              │
    │  Armbian OS:               3 GB              │
    │  Application + venv:       1 GB              │
    │  ML model:                 4 MB              │
    │  Certificates:             10 KB             │
    │  Free:                     ~12 GB            │
    │                                              │
    └──────────────────────────────────────────────┘
```

---

## 17. Technology Decisions

### 17.1 Decision Log

```
    ┌────┬──────────────┬──────────────┬──────────────┬──────────────────┐
    │ #  │ Decision     │ Chosen       │ Alternatives │ Rationale        │
    │    │              │              │ Considered   │                  │
    ├────┼──────────────┼──────────────┼──────────────┼──────────────────┤
    │ 1  │ SBC          │ Orange Pi    │ Raspberry Pi │ 40% cheaper,     │
    │    │              │ Zero 3 (2GB) │ Zero 2W,     │ H618 is adequate │
    │    │              │              │ ESP32-CAM    │ for YOLO nano    │
    ├────┼──────────────┼──────────────┼──────────────┼──────────────────┤
    │ 2  │ ML Model     │ YOLOv5n     │ MobileNet-   │ Best speed/acc   │
    │    │              │ (ONNX)       │ SSD, YOLOv8n │ balance. 3.9MB.  │
    │    │              │              │ TFLite       │ ONNX portable.   │
    ├────┼──────────────┼──────────────┼──────────────┼──────────────────┤
    │ 3  │ Runtime      │ ONNX Runtime │ TFLite,      │ Cross-platform,  │
    │    │              │ (CPU)        │ NCNN,        │ well-maintained, │
    │    │              │              │ OpenVINO     │ ARM optimized    │
    ├────┼──────────────┼──────────────┼──────────────┼──────────────────┤
    │ 4  │ Protocol     │ MQTT (EMQX)  │ HTTP, WS,   │ Lowest overhead, │
    │    │              │              │ CoAP, gRPC   │ QoS, LWT, mature │
    ├────┼──────────────┼──────────────┼──────────────┼──────────────────┤
    │ 5  │ Backend      │ FastAPI      │ Flask, Node, │ Async, same lang │
    │    │              │ (Python)     │ Go, Spring   │ as edge, fast dev│
    ├────┼──────────────┼──────────────┼──────────────┼──────────────────┤
    │ 6  │ Database     │ PostgreSQL   │ MySQL,       │ Robust, JSON     │
    │    │              │              │ SQLite,      │ support, mature  │
    │    │              │              │ MongoDB      │                  │
    ├────┼──────────────┼──────────────┼──────────────┼──────────────────┤
    │ 7  │ Object Store │ MinIO        │ S3, GCS,     │ Self-hosted,     │
    │    │              │ (self-hosted)│ local disk   │ S3-compatible,   │
    │    │              │              │              │ no vendor lock   │
    ├────┼──────────────┼──────────────┼──────────────┼──────────────────┤
    │ 8  │ Push Notif   │ Firebase FCM │ OneSignal,   │ Free tier ample, │
    │    │              │              │ custom APNS, │ reliable, native │
    │    │              │              │ Pushy        │ Android support  │
    ├────┼──────────────┼──────────────┼──────────────┼──────────────────┤
    │ 9  │ Mobile       │ Flutter      │ React Native,│ Single codebase, │
    │    │              │              │ Kotlin,      │ fast dev, future │
    │    │              │              │ PWA          │ iOS ready        │
    ├────┼──────────────┼──────────────┼──────────────┼──────────────────┤
    │ 10 │ Edge OS      │ Armbian      │ Ubuntu,      │ Best Orange Pi   │
    │    │              │ (Debian 12)  │ DietPi,      │ support, stable, │
    │    │              │              │ OrangePi OS  │ overlayfs ready  │
    ├────┼──────────────┼──────────────┼──────────────┼──────────────────┤
    │ 11 │ VPN          │ WireGuard    │ OpenVPN,     │ Fastest, lowest  │
    │    │              │              │ Tailscale,   │ overhead, kernel │
    │    │              │              │ ZeroTier     │ built-in         │
    ├────┼──────────────┼──────────────┼──────────────┼──────────────────┤
    │ 12 │ 360 Coverage │ 2x wide-    │ Servo+cam,   │ No moving parts, │
    │    │              │ angle cams   │ fisheye,     │ no mech failure, │
    │    │              │ (170 FOV)   │ 360 USB cam  │ reliable in dust │
    ├────┼──────────────┼──────────────┼──────────────┼──────────────────┤
    │ 13 │ Night Vision │ IR LED +     │ Thermal cam, │ Cheapest viable  │
    │    │              │ NoIR camera  │ starlight    │ option. Proven.  │
    │    │              │              │ sensor       │                  │
    └────┴──────────────┴──────────────┴──────────────┴──────────────────┘
```

### 17.2 Dependency Matrix

```
    EDGE DEVICE (Python 3.11)
    ├── opencv-python-headless    4.9.x     (camera, motion detection)
    ├── onnxruntime               1.17.x    (YOLO inference)
    ├── paho-mqtt                 2.1.x     (MQTT client)
    ├── numpy                     1.26.x    (array operations)
    ├── Pillow                    10.x      (JPEG compression)
    ├── PyYAML                    6.x       (config file parsing)
    └── sdnotify                  0.3.x     (systemd watchdog notify)

    BACKEND (Python 3.11)
    ├── fastapi                   0.111.x   (API framework)
    ├── uvicorn[standard]         0.30.x    (ASGI server)
    ├── sqlalchemy                2.0.x     (ORM)
    ├── alembic                   1.13.x    (DB migrations)
    ├── asyncpg                   0.29.x    (async PostgreSQL driver)
    ├── paho-mqtt                 2.1.x     (MQTT client)
    ├── firebase-admin            6.5.x     (FCM push notifications)
    ├── minio                     7.2.x     (object storage client)
    ├── python-jose[cryptography] 3.3.x     (JWT tokens)
    ├── passlib[bcrypt]           1.7.x     (password hashing)
    └── pydantic                  2.7.x     (data validation)

    MOBILE (Flutter 3.22)
    ├── dio                       5.4.x     (HTTP client)
    ├── firebase_messaging        14.x      (FCM)
    ├── flutter_secure_storage    9.x       (token storage)
    ├── provider / riverpod       2.5.x     (state management)
    ├── cached_network_image      3.3.x     (image caching)
    ├── intl                      0.19.x    (date formatting)
    └── go_router                 13.x      (navigation)
```

---

*This document is the authoritative technical reference for the Anti-Theft Smart System. All implementation decisions should align with the architecture defined here. Deviations require a documented decision record.*
