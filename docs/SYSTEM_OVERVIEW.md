# System Overview — Anti-Theft Smart System

## Table of Contents

- [1. Business Context](#1-business-context)
- [2. Business Requirements](#2-business-requirements)
- [3. Stakeholders](#3-stakeholders)
- [4. System Architecture](#4-system-architecture)
- [5. Component Deep Dive](#5-component-deep-dive)
- [6. Detection Pipeline](#6-detection-pipeline)
- [7. Communication Flow](#7-communication-flow)
- [8. Data Flow Diagram](#8-data-flow-diagram)
- [9. Mobile Application](#9-mobile-application)
- [10. Power and Deployment](#10-power-and-deployment)
- [11. Field Hardening](#11-field-hardening)
- [12. Security Model](#12-security-model)
- [13. Cost Analysis](#13-cost-analysis)
- [14. Scalability](#14-scalability)
- [15. Constraints and Assumptions](#15-constraints-and-assumptions)

---

## 1. Business Context

### 1.1 Problem Statement

Agricultural farms across rural India suffer significant financial losses due to theft of high-value equipment — motors, submersible pumps, copper wiring, irrigation pipes, solar panels, and lighting systems. These thefts typically occur at night or during periods when the farmer is away from the field.

Existing solutions are either:

- **Too expensive** — Commercial CCTV systems cost INR 15,000–50,000 and require broadband internet
- **Too limited** — Simple alarm systems have no intelligence, trigger on animals/wind, cause alert fatigue
- **Too dependent** — Cloud-based camera systems rely on stable internet, which rural farms lack

### 1.2 Proposed Solution

A **self-contained, AI-powered surveillance unit** that:

- Operates autonomously at the farm with no internet dependency for detection
- Uses on-device AI to distinguish humans from animals, shadows, and environmental noise
- Provides 360-degree coverage using dual wide-angle cameras
- Alerts the farmer in real-time via push notification on their smartphone
- Costs under INR 7,000 per unit with minimal recurring expenses

### 1.3 Target Users

| User | Profile |
|---|---|
| **Primary** | Small to mid-size farmers (1–20 acres) with smartphone access |
| **Secondary** | Farm owners who employ laborers and visit periodically |
| **Tertiary** | Agricultural cooperatives managing shared equipment yards |

---

## 2. Business Requirements

### 2.1 Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | System shall detect human presence within 15 meters of the surveillance unit | Must Have |
| FR-02 | System shall provide 360-degree field of view coverage | Must Have |
| FR-03 | System shall operate in both daylight and complete darkness (night vision) | Must Have |
| FR-04 | System shall send push notification to farmer's mobile within 5 seconds of detection | Must Have |
| FR-05 | System shall capture and transmit a snapshot of the detected intrusion | Must Have |
| FR-06 | Farmer shall be able to arm/disarm surveillance remotely from mobile app | Must Have |
| FR-07 | System shall continue detecting intrusions during internet/cellular outages (offline mode) | Must Have |
| FR-08 | System shall queue alerts locally and transmit when connectivity restores | Must Have |
| FR-09 | Farmer shall view alert history with snapshots in the mobile app | Should Have |
| FR-10 | System shall distinguish between humans and common farm animals (reduce false positives) | Should Have |
| FR-11 | Farmer shall configure active surveillance hours (scheduling) | Should Have |
| FR-12 | Farmer shall define exclusion zones in the camera frame (ignore scarecrows, clotheslines) | Should Have |
| FR-13 | System shall send "device offline" alert if the unit stops responding | Should Have |
| FR-14 | Farmer shall request a live snapshot on-demand from the mobile app | Could Have |
| FR-15 | System shall detect physical tampering (device moved/tilted) and alert immediately | Could Have |

### 2.2 Non-Functional Requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-01 | Detection-to-notification latency | < 5 seconds end-to-end |
| NFR-02 | False positive rate | < 5% after tuning |
| NFR-03 | System uptime | 99.5% (including power cuts with UPS) |
| NFR-04 | Power backup duration | Minimum 4 hours on battery |
| NFR-05 | Operating temperature | 0 C to 50 C ambient |
| NFR-06 | Cellular data consumption | < 500 MB/month under normal alert volume |
| NFR-07 | Unit cost (hardware) | < INR 7,000 per unit |
| NFR-08 | Mobile app startup time | < 3 seconds |
| NFR-09 | Concurrent devices per server | 100+ farms on single VPS |
| NFR-10 | SD card lifespan | > 2 years (read-only rootfs) |

---

## 3. Stakeholders

```
                        ┌──────────────┐
                        │   Farmer     │
                        │  (End User)  │
                        └──────┬───────┘
                               │ Uses mobile app
                               │ Receives alerts
                               ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Device     │      │   System     │      │  Network     │
│   Installer  │      │   Admin      │      │  Operator    │
│              │      │              │      │  (Telecom)   │
│ Installs &   │      │ Manages      │      │ Provides 4G  │
│ configures   │      │ backend &    │      │ connectivity │
│ field unit   │      │ OTA updates  │      │              │
└──────────────┘      └──────────────┘      └──────────────┘
```

---

## 4. System Architecture

### 4.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│                          AGRICULTURAL FARM                               │
│                                                                         │
│    ┌─────────────────────────────────────────────────────────────┐      │
│    │              EDGE DEVICE (Orange Pi Zero 3)                 │      │
│    │                                                             │      │
│    │   ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌────────────┐ │      │
│    │   │ Camera 1 │  │ Camera 2 │  │ IR LEDs  │  │ Tamper     │ │      │
│    │   │ (Front)  │  │ (Rear)   │  │ (Night)  │  │ Switch     │ │      │
│    │   │ 170 FOV  │  │ 170 FOV  │  │ 850nm    │  │            │ │      │
│    │   └────┬─────┘  └────┬─────┘  └──────────┘  └────────────┘ │      │
│    │        │              │                                      │      │
│    │        ▼              ▼                                      │      │
│    │   ┌──────────────────────────────────────────────────────┐  │      │
│    │   │              SURVEILLANCE DAEMON (Python)             │  │      │
│    │   │                                                      │  │      │
│    │   │  ┌────────────┐  ┌────────────┐  ┌───────────────┐  │  │      │
│    │   │  │ Motion     │  │ YOLO v5n   │  │ Alert         │  │  │      │
│    │   │  │ Detector   │─▶│ Inference  │─▶│ Manager       │  │  │      │
│    │   │  │ (OpenCV)   │  │ (ONNX)     │  │               │  │  │      │
│    │   │  └────────────┘  └────────────┘  └───────┬───────┘  │  │      │
│    │   │                                          │          │  │      │
│    │   │  ┌────────────┐  ┌────────────┐  ┌───────▼───────┐  │  │      │
│    │   │  │ Thermal    │  │ USB        │  │ MQTT Client   │  │  │      │
│    │   │  │ Manager    │  │ Watchdog   │  │ (paho-mqtt)   │  │  │      │
│    │   │  └────────────┘  └────────────┘  └───────┬───────┘  │  │      │
│    │   │                                          │          │  │      │
│    │   └──────────────────────────────────────────┼──────────┘  │      │
│    │                                              │             │      │
│    │   ┌──────────┐   ┌───────────┐               │             │      │
│    │   │ Power    │   │ 4G USB    │───────────────┘             │      │
│    │   │ Bank UPS │   │ Dongle    │  MQTT over TLS              │      │
│    │   └──────────┘   └───────────┘                             │      │
│    └─────────────────────────────────────────────────────────────┘      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │  4G LTE (Cellular Network)
                                    │  MQTT over TLS (port 8883)
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│                           CLOUD BACKEND (VPS)                           │
│                                                                         │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                 │
│   │             │   │             │   │             │                 │
│   │  EMQX       │   │  FastAPI    │   │  PostgreSQL │                 │
│   │  MQTT       │──▶│  API        │──▶│  Database   │                 │
│   │  Broker     │   │  Server     │   │             │                 │
│   │             │   │             │   │             │                 │
│   └─────────────┘   └──────┬──────┘   └─────────────┘                 │
│                            │                                           │
│                     ┌──────┴──────┐                                    │
│                     │             │                                    │
│               ┌─────▼─────┐ ┌────▼──────┐                             │
│               │  Firebase  │ │  MinIO    │                             │
│               │  FCM       │ │  Object   │                             │
│               │  (Push)    │ │  Storage  │                             │
│               └─────┬──────┘ └───────────┘                             │
│                     │                                                   │
└─────────────────────┼───────────────────────────────────────────────────┘
                      │
                      │  Firebase Cloud Messaging
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│                      MOBILE APPLICATION (Android)                       │
│                                                                         │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                 │
│   │  Dashboard  │   │  Alert      │   │  Settings   │                 │
│   │  - Status   │   │  History    │   │  - Schedule │                 │
│   │  - Battery  │   │  - Images   │   │  - Zones    │                 │
│   │  - ARM/OFF  │   │  - Timeline │   │  - Tuning   │                 │
│   └─────────────┘   └─────────────┘   └─────────────┘                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 360-Degree Camera Placement

```
                         NORTH
                           │
                    170 FOV│
                  ┌────────┼────────┐
                 ╱         │         ╲
                ╱          │          ╲
               ╱           │           ╲
              ╱            │            ╲
             ╱    CAMERA 1 │             ╲
    WEST ───╱──────────────┼──────────────╲─── EAST
             ╲             │    CAMERA 2 ╱
              ╲            │            ╱
               ╲           │           ╱
                ╲          │          ╱
                 ╲─────────┼─────────╱
                           │
                         SOUTH

    Total Coverage: 340 degrees (20 degree overlap zone)
    Mounting: Back-to-back on 12ft pole
    No blind spots in the horizontal plane
```

---

## 5. Component Deep Dive

### 5.1 Edge Device — Orange Pi Zero 3 (2GB)

| Specification | Value |
|---|---|
| SoC | Allwinner H618 (Quad-core Cortex-A53) |
| RAM | 2GB LPDDR4 |
| Storage | MicroSD (16GB, read-only rootfs) |
| USB | 1x USB 3.0 + 1x USB 2.0 |
| GPIO | 26-pin header |
| Network | Onboard WiFi + Bluetooth (unused; 4G dongle for connectivity) |
| Power | 5V/2A via USB-C |
| OS | Armbian (Debian 12 Bookworm) |

### 5.2 Camera Specifications

| Specification | Value |
|---|---|
| Type | USB UVC compliant (plug-and-play on Linux) |
| Sensor | NoIR (No IR filter — enables night vision with IR LEDs) |
| Field of View | 170 degrees (wide-angle lens) |
| Resolution | 640x480 (VGA) for inference, 1280x720 for alert snapshots |
| Frame Rate | 15 FPS at VGA |
| Interface | USB 2.0 |
| Quantity | 2 per unit (front + rear, mounted back-to-back) |

### 5.3 Connectivity — 4G USB Dongle

| Specification | Value |
|---|---|
| Type | USB 4G LTE dongle (Jio/Airtel compatible) |
| Mode | RNDIS (presents as USB ethernet — no driver issues on Linux) |
| Data Plan | 1GB/month sufficient (only alert snapshots transmitted) |
| Fallback | Local alert queue on tmpfs, auto-flush on reconnect |

### 5.4 Power System

```
    ┌──────────────┐         ┌──────────────┐
    │  Mains 230V  │────────▶│  5V/3A USB   │──────┐
    │  (Farm line) │         │  Adapter +   │      │
    └──────────────┘         │  Surge Prot. │      │
                             └──────────────┘      │
                                                   ▼
                             ┌──────────────┐   ┌──────────────────┐
                             │  10000mAh    │──▶│  Orange Pi       │
                             │  Power Bank  │   │  + Cameras       │
                             │  (UPS Mode)  │   │  + 4G Dongle     │
                             │              │   │  + USB Hub        │
                             │  Pass-through│   └──────────────────┘
                             │  charging    │
                             └──────────────┘

    Normal:    Mains → Power Bank (pass-through) → Orange Pi
    Power Cut: Power Bank (battery) → Orange Pi (4-5 hours backup)
    Restored:  Mains → Power Bank (charges + passes through) → Orange Pi
```

---

## 6. Detection Pipeline

### 6.1 Two-Stage Detection Strategy

Running YOLO on every frame from both cameras continuously would overheat the CPU and waste resources. Instead, a two-stage approach is used:

```
    ┌───────────────────────────────────────────────────────────┐
    │                   STAGE 1: MOTION GATE                    │
    │                   (Runs on every frame)                   │
    │                                                           │
    │   Frame(t) ──▶ Grayscale ──▶ Gaussian Blur               │
    │                                   │                       │
    │   Frame(t-1) ──▶ Grayscale ──▶ Gaussian Blur              │
    │                                   │                       │
    │                        ┌──────────▼──────────┐            │
    │                        │  Absolute Frame     │            │
    │                        │  Difference          │            │
    │                        └──────────┬──────────┘            │
    │                                   │                       │
    │                        ┌──────────▼──────────┐            │
    │                        │  Threshold + Contour │            │
    │                        │  Area > 3000 px?     │            │
    │                        └──────────┬──────────┘            │
    │                                   │                       │
    │                         NO ◀──────┼──────▶ YES            │
    │                          │        │         │             │
    │                       (skip)      │     (proceed)         │
    │                                   │                       │
    │   Cost: ~5ms per frame                                    │
    │   Filters: 90% of frames (static scenes)                 │
    └───────────────────────────────────┼───────────────────────┘
                                        │
                                        ▼
    ┌───────────────────────────────────────────────────────────┐
    │                  STAGE 2: HUMAN DETECTION                 │
    │                 (Runs only on motion frames)              │
    │                                                           │
    │   Motion Frame ──▶ Resize 320x320 ──▶ Normalize          │
    │                                           │               │
    │                              ┌────────────▼────────────┐  │
    │                              │   YOLOv5n Inference     │  │
    │                              │   (ONNX Runtime)        │  │
    │                              │                         │  │
    │                              │   Filter: class=person  │  │
    │                              │   Threshold: conf > 0.6 │  │
    │                              └────────────┬────────────┘  │
    │                                           │               │
    │                             NO ◀──────────┼──────▶ YES    │
    │                              │            │          │    │
    │                           (discard)       │    (candidate) │
    │                                           │               │
    │   Cost: ~300ms per frame                                  │
    └───────────────────────────────┼───────────────────────────┘
                                    │
                                    ▼
    ┌───────────────────────────────────────────────────────────┐
    │               STAGE 3: TEMPORAL VALIDATION                │
    │              (Eliminates single-frame noise)              │
    │                                                           │
    │   Person detected in frame N?                             │
    │   Person detected in frame N+1?                           │
    │   Person detected in frame N+2?                           │
    │                                                           │
    │          3 consecutive detections?                         │
    │                    │                                      │
    │          NO ◀──────┼──────▶ YES                           │
    │           │        │         │                            │
    │       (false       │    INTRUSION                         │
    │        positive)   │    CONFIRMED                         │
    │                    │                                      │
    │   Time to confirm: ~1 second (3 frames)                   │
    │   Eliminates: shadows, swaying crops, birds               │
    └───────────────────────────────┼───────────────────────────┘
                                    │
                                    ▼
                          ┌─────────────────┐
                          │  TRIGGER ALERT  │
                          │                 │
                          │  1. High-res    │
                          │     snapshot    │
                          │  2. MQTT pub    │
                          │  3. Local log   │
                          │  4. Cooldown    │
                          │     (5 min)     │
                          └─────────────────┘
```

### 6.2 Dual Camera Scan Cycle

```
    TIME (ms)   ACTION
    ─────────   ──────────────────────────────────────
        0       Grab frame from Camera 1 (Front)
       20       Motion detection on Camera 1 frame
       25       Motion? → Run YOLO inference (~300ms)
      325       Result: person / no person
      350       Grab frame from Camera 2 (Rear)
      370       Motion detection on Camera 2 frame
      375       Motion? → Run YOLO inference (~300ms)
      675       Result: person / no person
      700       Loop back to Camera 1
    ─────────   ──────────────────────────────────────

    Full 360-degree scan: ~700ms per cycle
    Scans per minute: ~85
```

---

## 7. Communication Flow

### 7.1 MQTT Topic Structure

```
    farm/{farm_id}/device/{device_id}/
    ├── alert              Device → Cloud     Intrusion alert payload
    ├── image              Device → Cloud     Alert snapshot (JPEG binary)
    ├── heartbeat          Device → Cloud     Health status every 60s
    ├── status             Device → Cloud     Armed/disarmed state changes
    ├── command            Cloud → Device     Arm, disarm, snapshot, reboot
    └── config             Cloud → Device     Update scan interval, threshold
```

### 7.2 Alert Message Format

```json
{
    "device_id": "FARM-MH-001",
    "farm_id": "farm_ganesh_nashik",
    "timestamp": "2026-09-04T22:15:03.412Z",
    "event_type": "intrusion_detected",
    "camera_id": "cam_front",
    "detection": {
        "confidence": 0.87,
        "bbox": [120, 80, 340, 410],
        "person_count": 1
    },
    "direction": "north",
    "image_ref": "alert_20260904_221503_cam1.jpg",
    "device_status": {
        "battery_pct": 72,
        "cpu_temp_c": 58,
        "uptime_hrs": 168,
        "signal_strength": -67
    }
}
```

### 7.3 End-to-End Alert Sequence

```
    FARM (Edge)              CLOUD                    MOBILE APP
    ───────────              ─────                    ──────────
         │                      │                         │
         │  Motion detected     │                         │
         │  YOLO confirms       │                         │
         │  3-frame validated   │                         │
         │                      │                         │
         ├─── MQTT: alert ─────▶│                         │
         │    (QoS 1)           │                         │
         │                      │  Store in PostgreSQL    │
         ├─── MQTT: image ─────▶│  Store in MinIO         │
         │    (QoS 1)           │                         │
         │                      ├─── FCM Push ───────────▶│
         │                      │    Notification         │
         │                      │                         │  User sees alert
         │                      │                         │  with snapshot
         │                      │                         │
         │                      │◀── GET /alerts ─────────┤
         │                      │                         │  Opens app
         │                      ├─── Alert details ──────▶│  Views history
         │                      │                         │
         │                      │◀── POST /command ───────┤
         │                      │    {action: "disarm"}   │  Disarms system
         │◀── MQTT: command ────┤                         │
         │    {action: "disarm"}│                         │
         │                      │                         │
         │  Surveillance stops  │                         │
         │                      │                         │

    Total latency: < 5 seconds (detection to notification)
```

---

## 8. Data Flow Diagram

### 8.1 Level 0 — Context Diagram

```
    ┌───────────┐                                    ┌───────────┐
    │           │         Push Notifications          │           │
    │  Intruder │                              ┌─────▶  Farmer   │
    │           │                              │     │           │
    └─────┬─────┘                              │     └─────┬─────┘
          │                                    │           │
          │ Physical                           │           │ Arm/Disarm
          │ Presence                           │           │ View Alerts
          │                                    │           │
          ▼                                    │           ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                                                             │
    │              ANTI-THEFT SMART SYSTEM                        │
    │                                                             │
    │   Detect → Analyze → Alert → Notify → Display              │
    │                                                             │
    └─────────────────────────────────────────────────────────────┘
```

### 8.2 Level 1 — Process Decomposition

```
    ┌──────────┐     Frames      ┌──────────────┐
    │ Cameras  │────────────────▶│ P1: Motion   │
    └──────────┘                 │ Detection    │
                                 └──────┬───────┘
                                        │ Motion frames
                                        ▼
                                 ┌──────────────┐
                                 │ P2: Human    │
                                 │ Classification│
                                 └──────┬───────┘
                                        │ Confirmed detections
                                        ▼
                                 ┌──────────────┐     Alert + Image     ┌──────────┐
                                 │ P3: Alert    │──────────────────────▶│ D1: Alert│
                                 │ Processing   │                      │ Database │
                                 └──────┬───────┘                      └──────────┘
                                        │ Alert payload
                                        ▼
                                 ┌──────────────┐     Push              ┌──────────┐
                                 │ P4: Notify   │──────────────────────▶│ Farmer's │
                                 │ Farmer       │                      │ Phone    │
                                 └──────────────┘                      └──────────┘
                                        ▲
                                        │ Commands
                                 ┌──────┴───────┐
                                 │ P5: Process  │◀──── Arm/Disarm/Snapshot
                                 │ Commands     │
                                 └──────────────┘
```

---

## 9. Mobile Application

### 9.1 Screen Flow

```
    ┌─────────────────┐
    │   Splash +      │
    │   Login/PIN     │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
    │                 │     │                 │     │                 │
    │   DASHBOARD     │────▶│  ALERT DETAIL   │     │   SETTINGS      │
    │                 │     │                 │     │                 │
    │  - Farm status  │     │  - Snapshot     │     │  - Schedule     │
    │  - ARM / DISARM │     │  - Confidence   │     │  - Sensitivity  │
    │  - Battery %    │     │  - Direction    │     │  - Exclusion    │
    │  - Signal       │     │  - Timestamp    │     │    zones        │
    │  - Recent alerts│     │  - Dismiss      │     │  - Device info  │
    │                 │     │                 │     │  - Account      │
    └────────┬────────┘     └─────────────────┘     └─────────────────┘
             │
             ▼
    ┌─────────────────┐
    │  ALERT HISTORY  │
    │                 │
    │  - Date filter  │
    │  - Image grid   │
    │  - Export       │
    └─────────────────┘
```

### 9.2 Dashboard Wireframe

```
    ┌──────────────────────────────────────┐
    │  Anti-Theft Smart System     [gear]  │
    ├──────────────────────────────────────┤
    │                                      │
    │  Ganesh Farm, Nashik                 │
    │                                      │
    │  ┌────────────────────────────────┐  │
    │  │                                │  │
    │  │    Status: ARMED               │  │
    │  │    ● Surveillance Active       │  │
    │  │                                │  │
    │  │    Battery: 72%  [========--]  │  │
    │  │    Signal:  -67 dBm (Good)     │  │
    │  │    CPU Temp: 58 C              │  │
    │  │    Last Scan: 0.7s ago         │  │
    │  │                                │  │
    │  └────────────────────────────────┘  │
    │                                      │
    │  ┌──────────────┐ ┌──────────────┐  │
    │  │              │ │              │  │
    │  │   DISARM     │ │  SNAPSHOT    │  │
    │  │              │ │              │  │
    │  └──────────────┘ └──────────────┘  │
    │                                      │
    │  ─── Recent Alerts ─────────────── │
    │                                      │
    │  ! 10:15 PM  Person detected        │
    │    Camera: Front (North)             │
    │    Confidence: 87%        [View >]  │
    │  ─────────────────────────────────  │
    │  ! 09:42 PM  Person detected        │
    │    Camera: Rear (South)              │
    │    Confidence: 74%        [View >]  │
    │  ─────────────────────────────────  │
    │                                      │
    │  [View All Alerts]                   │
    │                                      │
    ├──────────────────────────────────────┤
    │  [Home]     [Alerts]    [Settings]  │
    └──────────────────────────────────────┘
```

### 9.3 Push Notification

```
    ┌──────────────────────────────────────┐
    │  Anti-Theft Smart System        now  │
    │                                      │
    │  INTRUSION ALERT                     │
    │  Person detected at Ganesh Farm      │
    │  Camera: Front | Confidence: 87%     │
    │  Tap to view snapshot                │
    └──────────────────────────────────────┘
```

---

## 10. Power and Deployment

### 10.1 Power Budget

| Component | Active Power | Idle Power |
|---|---|---|
| Orange Pi Zero 3 | 3.5W | 1.5W |
| USB Camera x2 | 1.0W | 0W |
| 4G USB Dongle | 1.0W | 0.1W |
| USB Hub | 0.5W | 0.3W |
| IR LEDs x2 (night) | 1.0W | 0W |
| **Total (Day)** | **6.0W** | **1.9W** |
| **Total (Night, IR on)** | **7.0W** | **1.9W** |

**Backup Duration:** 10000mAh at 5V = 50Wh. At 7W = **~7 hours**. At 6W = **~8 hours**.

### 10.2 Physical Mounting

```
                    ┌───┐ ← Weatherproof enclosure
                    │   │    (ventilated, fan inside)
                    │ Pi│
                    │   │
               ─────┤   ├─────
              │     │   │     │
         Camera 1   │   │   Camera 2
         (Front)    │   │   (Rear)
              │     │   │     │
               ─────┤   ├─────
                    │   │
                    │   │ ← 12ft steel/PVC pole
                    │   │
                    │   │
                    │   │
                    │   │
                    │   │ ← Power + 4G dongle cable
                    │   │    routed inside pole
                ════╧═══╧════ ← Ground / concrete base
```

---

## 11. Field Hardening

### 11.1 Failure Modes and Mitigations

| Failure Mode | Impact | Mitigation | Recovery |
|---|---|---|---|
| **Power cut** | System offline | 10000mAh UPS (7+ hours) | Auto-resume on power restore |
| **Camera freeze** | Blind spot | USB watchdog detects, resets USB bus | Auto within 10 seconds |
| **4G dropout** | Alerts not sent | Local queue in tmpfs (up to 100 alerts) | Auto-flush on reconnect |
| **SD card corrupt** | System dead | Read-only rootfs (overlayfs) | Survives power cycles |
| **CPU overheat** | Throttle/shutdown | Fan + thermal manager reduces scan rate | Auto-resume when cooled |
| **Physical tamper** | Device stolen | Tamper switch sends instant alert | Alert reaches farmer before theft completes |
| **Process crash** | No surveillance | systemd auto-restart + hardware watchdog | Auto within 5 seconds |
| **False positive flood** | Alert fatigue | Temporal filter + cooldown + scheduling | User tunes sensitivity in app |
| **Dongle hang** | No connectivity | Ping watchdog, USB reset every 3 failed pings | Auto within 30 seconds |

### 11.2 Watchdog Architecture

```
    ┌─────────────────────────────────────────────┐
    │              WATCHDOG LAYER                   │
    │                                              │
    │  ┌──────────────┐  Hardware watchdog (SoC)   │
    │  │ /dev/watchdog │  Must be pinged every 30s  │
    │  │              │  or board auto-reboots      │
    │  └──────┬───────┘                             │
    │         │                                     │
    │  ┌──────▼───────┐  systemd watchdog           │
    │  │ systemd      │  Restarts daemon if it      │
    │  │ WatchdogSec  │  stops sending sd_notify    │
    │  └──────┬───────┘                             │
    │         │                                     │
    │  ┌──────▼───────┐  Application-level          │
    │  │ App Watchdog │  Monitors camera, dongle,   │
    │  │              │  CPU temp, memory, disk      │
    │  └──────────────┘                             │
    └─────────────────────────────────────────────┘
```

---

## 12. Security Model

### 12.1 Threat Matrix

| Attack Vector | Threat | Countermeasure |
|---|---|---|
| Network sniffing | Intercept alerts/images | MQTT over TLS 1.3 (port 8883) |
| Device spoofing | Inject false alerts | Per-device client certificates |
| Physical theft | Steal the unit | 12ft mount + tamper switch + instant alert |
| SIM extraction | Use farmer's data | SIM PIN lock + APN authentication |
| API abuse | Unauthorized app access | JWT authentication + rate limiting |
| Replay attack | Re-send old commands | Timestamp + nonce in every message |
| Brute force | Guess app password | Account lockout after 5 attempts |

### 12.2 Authentication Flow

```
    Mobile App                 Backend                    Edge Device
    ──────────                 ───────                    ───────────
        │                        │                           │
        ├── Login (email+pass) ─▶│                           │
        │                        │  Verify credentials       │
        │◀── JWT token ──────────┤                           │
        │                        │                           │
        ├── API calls ──────────▶│                           │
        │   (Bearer token)       │                           │
        │                        │                           │
        │                        │◀── MQTT connect ──────────┤
        │                        │    (client certificate)   │
        │                        │                           │
        │                        │──── CONNACK ─────────────▶│
        │                        │    (authenticated)        │
        │                        │                           │
```

---

## 13. Cost Analysis

### 13.1 One-Time Cost Per Farm Unit

| Category | Items | Cost (INR) |
|---|---|---|
| Compute | Orange Pi Zero 3 (2GB) | 2,200 |
| Vision | 2x NoIR wide-angle USB cameras | 1,200 |
| Vision | 2x IR LED rings (850nm) | 400 |
| Network | 4G USB dongle | 600 |
| Peripherals | Powered USB hub | 200 |
| Power | 5V/3A adapter + surge protector | 350 |
| Power | 10000mAh power bank (UPS) | 500 |
| Enclosure | Ventilated box + 40mm fan | 350 |
| Mounting | 12ft pole + bracket + tamper switch | 400 |
| Misc | Cables, connectors, zip ties | 300 |
| **TOTAL** | | **6,500** |

### 13.2 Recurring Cost

| Item | Monthly (INR) | Notes |
|---|---|---|
| SIM data (1GB) | 150 | Only alert snapshots transmitted |
| Cloud VPS (shared) | 10-50 | 500/month shared across 10-50 farms |
| **TOTAL per farm** | **~200** | |

### 13.3 Comparison with Alternatives

| Solution | One-Time Cost | Monthly | Night Vision | AI Detection | Mobile Alert |
|---|---|---|---|---|---|
| Commercial CCTV | 15,000-50,000 | 500-1,500 | Yes | No | Limited |
| IP Camera + NVR | 8,000-25,000 | 300-800 | Yes | No | Yes |
| Security Guard | 0 | 10,000-15,000 | N/A | N/A | N/A |
| Simple Alarm | 2,000-5,000 | 0 | No | No | No |
| **This System** | **6,500** | **200** | **Yes** | **Yes** | **Yes** |

---

## 14. Scalability

### 14.1 Multi-Farm Architecture

```
    Farm 1 ──┐                               ┌── Farmer 1 (App)
    Farm 2 ──┤                               ├── Farmer 2 (App)
    Farm 3 ──┤── MQTT ──▶ [ Cloud VPS ] ──▶──┤── Farmer 3 (App)
    ...      │           Single instance     │   ...
    Farm N ──┘           handles 100+        └── Farmer N (App)
                         concurrent devices
```

### 14.2 Scaling Thresholds

| Farms | Infrastructure | Monthly Cost |
|---|---|---|
| 1-50 | Single VPS (2 vCPU, 4GB) | INR 500 |
| 50-200 | Single VPS (4 vCPU, 8GB) | INR 1,200 |
| 200-1000 | EMQX cluster + separate API server | INR 3,000 |
| 1000+ | Kubernetes + managed MQTT | Custom |

---

## 15. Constraints and Assumptions

### 15.1 Assumptions

- Farm has mains electricity (for motor, lights, pump operation)
- Farmer owns an Android smartphone with mobile data
- 4G cellular coverage exists at the farm location
- Farm has a defined perimeter with identifiable entry points
- Primary threat is nighttime theft by humans (not wildlife or natural disasters)

### 15.2 Constraints

- Edge device must operate within 2GB RAM
- Cellular data budget capped at 1GB/month per device
- No continuous video streaming (bandwidth limitation)
- Detection range limited to ~15 meters with wide-angle lens
- System requires initial on-site setup by installer or farmer

### 15.3 Out of Scope (v1.0)

- Live video streaming
- Facial recognition or person identification
- Integration with local police or emergency services
- Multi-camera (more than 2) per unit
- Solar-powered variant (planned for v2.0)
- iOS mobile application (planned for v2.0)
- Voice intercom / two-way audio
