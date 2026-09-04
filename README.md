# Anti-Theft Smart System

An AI-powered, low-cost surveillance system for agricultural farms. Uses edge AI on Orange Pi to detect human intrusion in 360 degrees and sends real-time push notifications to the farmer's Android app.

## Problem

Agricultural farms face theft of expensive equipment (motors, water pipes, lights). Farmers need an affordable, autonomous monitoring solution that works in remote locations with unreliable power and connectivity.

## Documentation

- **[System Overview](docs/SYSTEM_OVERVIEW.md)** — Business requirements, stakeholders, detection pipeline, data flow diagrams, mobile app wireframes, cost analysis, and scalability plan.
- **[Technical Architecture](docs/TECHNICAL_ARCHITECTURE.md)** — Three-tier topology, edge software architecture, MQTT protocol design, backend API specification, database schema, security layers, OTA updates, performance budgets, and technology decision log.

## Architecture Overview

```
  [Orange Pi Zero 3 + 2x Wide-Angle Cameras]
          │ (Edge AI - YOLOv5 nano)
          │
          │ MQTT over 4G LTE
          ▼
  [Cloud Backend - FastAPI + EMQX + PostgreSQL]
          │
          │ Firebase Cloud Messaging
          ▼
  [Android App - Flutter]
```

### Key Design Decisions

- **Edge inference** — All human detection runs on-device. No cloud GPU costs. Works offline.
- **Dual wide-angle cameras** — Two 170 FOV cameras mounted back-to-back for 340+ degree coverage. No moving parts, no servo failures.
- **Two-stage detection** — OpenCV motion detection first (5ms), YOLO only on motion frames (300ms). Saves 90% CPU.
- **MQTT protocol** — 10x less overhead than HTTP. Built for unreliable cellular networks.
- **Snapshots, not video** — One JPEG (~80KB) per alert vs 30fps video (~500KB/s). Saves 99% bandwidth.

## Hardware Bill of Materials (~INR 6,500)

| Component | Specification | Cost (INR) |
|---|---|---|
| SBC | Orange Pi Zero 3 (2GB RAM) | 2,200 |
| Cameras | 2x Wide-angle NoIR USB camera (170 FOV, UVC) | 1,200 |
| Night Vision | 2x IR LED ring (850nm) | 400 |
| Connectivity | 4G USB dongle | 600 |
| USB Hub | Powered 4-port | 200 |
| Power | 5V/3A adapter + surge protector | 350 |
| Backup Power | 10000mAh power bank (UPS) | 500 |
| Enclosure | Ventilated enclosure + 40mm fan | 350 |
| Mounting | 12ft pole + bracket + tamper switch | 400 |
| Misc | Wiring, cables, connectors | 300 |

**Recurring:** SIM data ~INR 150/month, Cloud VPS ~INR 500/month (shared across farms)

## Project Structure

```
anti-theft-smart-system/
├── edge/                   # Runs on Orange Pi
│   ├── config/             # Device configuration
│   ├── models/             # ML models (YOLOv5n ONNX)
│   ├── src/                # Python surveillance daemon
│   └── systemd/            # Auto-start service
├── backend/                # Cloud server
│   └── app/                # FastAPI application
│       ├── api/            # REST endpoints
│       ├── services/       # MQTT handler, FCM, storage
│       ├── models/         # Pydantic schemas
│       └── db/             # SQLAlchemy + Alembic
├── mobile/                 # Flutter Android app
│   └── lib/
│       ├── screens/        # Dashboard, alerts, settings
│       ├── services/       # API, FCM, auth
│       └── models/         # Data models
└── docs/                   # Hardware assembly, wiring, deployment
```

## Field Hardening

This system is designed for real-world farm conditions:

- **Night vision** — IR illumination for 24/7 detection
- **Power backup** — 10000mAh UPS survives 4-5 hour power cuts
- **Thermal management** — Ventilated enclosure + fan, software thermal throttling
- **USB watchdog** — Auto-detects frozen cameras, resets USB bus
- **Read-only rootfs** — Prevents SD card corruption from continuous writes
- **Remote recovery** — Hardware watchdog, reverse SSH tunnel, OTA updates
- **False positive reduction** — Temporal filtering, exclusion zones, confidence tuning, scheduling
- **Tamper detection** — Tilt/vibration switch triggers instant alert
- **Offline resilience** — Local alert queue, auto-flush when connectivity restores

## Getting Started

> Documentation for each component is in their respective directories.

- [Edge Device Setup](edge/README.md)
- [Backend Deployment](backend/README.md)
- [Mobile App Build](mobile/README.md)

## Tech Stack

| Layer | Technology |
|---|---|
| Edge OS | Armbian (Debian-based) |
| Edge Runtime | Python 3.11 |
| AI Model | YOLOv5n (ONNX Runtime) |
| Protocol | MQTT (EMQX broker) |
| Backend | FastAPI + PostgreSQL |
| Push Notifications | Firebase Cloud Messaging |
| Mobile | Flutter (Android) |
| Object Storage | MinIO (self-hosted) |

## License

MIT
