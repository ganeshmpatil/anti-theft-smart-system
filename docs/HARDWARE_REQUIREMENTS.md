# Hardware Requirements — Anti-Theft Smart System

## Table of Contents

- [1. Bill of Materials (BOM)](#1-bill-of-materials-bom)
- [2. Core Compute Unit](#2-core-compute-unit)
- [3. Camera Module](#3-camera-module)
- [4. Night Vision — IR Illumination](#4-night-vision--ir-illumination)
- [5. Connectivity — 4G LTE Dongle](#5-connectivity--4g-lte-dongle)
- [6. USB Hub](#6-usb-hub)
- [7. Power System](#7-power-system)
- [8. Tamper Detection](#8-tamper-detection)
- [9. Thermal Management](#9-thermal-management)
- [10. Enclosure](#10-enclosure)
- [11. Mounting Hardware](#11-mounting-hardware)
- [12. Cables and Connectors](#12-cables-and-connectors)
- [13. Software Requirements on Hardware](#13-software-requirements-on-hardware)
- [14. GPIO Pin Assignments](#14-gpio-pin-assignments)
- [15. Power Budget](#15-power-budget)
- [16. Assembly Checklist](#16-assembly-checklist)
- [17. Recommended Suppliers (India)](#17-recommended-suppliers-india)
- [18. Hardware Alternatives](#18-hardware-alternatives)

---

## 1. Bill of Materials (BOM)

| # | Component | Specification | Qty | Est. Cost (INR) | Notes |
|---|-----------|---------------|-----|-----------------|-------|
| 1 | Single Board Computer | Orange Pi Zero 3 (2GB RAM) | 1 | 2,200 | Quad-core Cortex-A53 |
| 2 | MicroSD Card | 16GB Class 10 (A1 rated) | 1 | 250 | Read-only rootfs to prevent wear |
| 3 | USB Camera (Wide-Angle) | NoIR USB UVC, 170° FOV | 2 | 1,200 | No IR filter — essential for night vision |
| 4 | IR LED Ring | 850nm wavelength, 3W | 2 | 400 | One per camera |
| 5 | 4G USB Dongle | LTE Cat 4, RNDIS mode | 1 | 600 | Jio/Airtel SIM compatible |
| 6 | SIM Card | 4G LTE data plan (1GB/month) | 1 | 150/month | Only alert snapshots transmitted |
| 7 | Powered USB Hub | 4-port, externally powered | 1 | 200 | Must be powered — Pi cannot supply enough current |
| 8 | 5V/3A USB-C Adapter | Mains power supply | 1 | 200 | Quality adapter with surge protection |
| 9 | Surge Protector | Single-outlet, MOV based | 1 | 150 | Protects against rural power spikes |
| 10 | Power Bank (UPS) | 10000mAh, pass-through charging | 1 | 500 | Must support simultaneous charge + discharge |
| 11 | Tamper Switch | Tilt/vibration sensor (SW-420 or spring type) | 1 | 30 | Connected to GPIO |
| 12 | Cooling Fan | 40mm, 5V DC | 1 | 80 | Prevents thermal throttling |
| 13 | Enclosure | ABS weatherproof box, ventilated | 1 | 250 | IP54 or better, with fan cutout |
| 14 | Mounting Pole | 12ft steel/PVC pipe, 1.5" diameter | 1 | 250 | Keeps unit above reach, provides 360° view |
| 15 | Pole Bracket | U-clamp or flange bracket | 1 | 100 | Secures enclosure to pole top |
| 16 | Cable Glands | PG7/PG9 waterproof | 3 | 50 | For USB, power, and sensor cable entry |
| 17 | Cables & Connectors | USB extensions, jumper wires, zip ties | - | 300 | See Section 12 |
| | | | | **~6,710** | **Total one-time hardware cost** |

**Recurring cost:** SIM data ~INR 150/month + Cloud VPS ~INR 10-50/month (shared across farms)

---

## 2. Core Compute Unit

### Orange Pi Zero 3 (2GB RAM)

| Parameter | Specification |
|-----------|---------------|
| SoC | Allwinner H618 (Quad-core ARM Cortex-A53 @ 1.5GHz) |
| RAM | 2GB LPDDR4 |
| Storage | MicroSD slot (no eMMC on Zero 3) |
| USB | 1x USB 3.0 Type-A + 1x USB 2.0 Type-A |
| GPIO | 26-pin header (compatible with RPi-style pinout) |
| Network | Onboard Wi-Fi 5 + Bluetooth 5.0 (unused — 4G dongle used instead) |
| Power Input | USB-C, 5V/2A minimum (3A recommended) |
| Dimensions | 65mm x 30mm |
| Operating Temp | 0°C to 70°C (SoC rated) |
| OS | Armbian (Debian 12 Bookworm) |

### Why Orange Pi Zero 3?

- Cheapest SBC with USB 3.0 (needed for dual cameras)
- Quad-core A53 handles YOLO nano inference at ~200ms/frame
- 2GB RAM sufficient for OS + Python daemon + ONNX Runtime + OpenCV buffers
- Active community, Armbian support, long-term availability
- GPIO header for tamper switch and power detection

### MicroSD Card Requirements

| Parameter | Specification |
|-----------|---------------|
| Capacity | 16GB minimum |
| Speed Class | Class 10 / A1 rated |
| Filesystem | ext4 with read-only rootfs (overlayfs) |
| Write Endurance | >10,000 P/E cycles |

> **Critical:** The rootfs MUST be mounted read-only to prevent SD card corruption from continuous writes. Use overlayfs to redirect writes to tmpfs. This extends card lifespan from months to years in 24/7 operation.

---

## 3. Camera Module

### USB Wide-Angle NoIR Camera (x2)

| Parameter | Specification |
|-----------|---------------|
| Type | USB 2.0 UVC compliant (plug-and-play on Linux) |
| Sensor | NoIR (No Infrared filter) |
| Lens | Wide-angle, 170° horizontal FOV |
| Resolution — Inference | 640x480 (VGA) @ 15 FPS |
| Resolution — Snapshot | 1280x720 (HD) for alert images |
| Focus | Fixed focus (no autofocus — avoids hunting delays) |
| Night Vision | Enabled via external IR LED rings (sensor sees IR without filter) |
| Connector | USB 2.0 Type-A |
| Cable Length | 50cm–100cm (shorter = less interference) |

### Why NoIR Cameras?

Standard cameras have an IR-cut filter that blocks infrared light. NoIR cameras remove this filter, allowing the sensor to capture IR light from the LED illuminators. This enables night vision without any mechanical IR-cut switcher.

**Daytime trade-off:** Images appear slightly washed-out/pinkish in daylight (excess IR), but this has zero impact on YOLO human detection accuracy.

### Camera Placement

```
                     NORTH
                       │
                170° FOV
              ┌────────┼────────┐
             /         │         \
            /          │          \
           /           │           \
          /   CAMERA 1 │            \
WEST ────/─────────────┼─────────────\──── EAST
          \            │  CAMERA 2  /
           \           │           /
            \          │          /
             \─────────┼─────────/
                       │
                     SOUTH

Total coverage: 340° (20° overlap zone)
Mounting: Back-to-back on pole top, facing opposite directions
```

### Camera Selection Criteria

- **MUST** be UVC compliant (no proprietary drivers)
- **MUST** be NoIR variant (no IR filter)
- **MUST** support 640x480 @ 15fps minimum
- **MUST** have fixed focus lens
- **SHOULD** have 150°+ FOV (170° preferred)
- **SHOULD NOT** have built-in microphone (unnecessary power draw)

---

## 4. Night Vision — IR Illumination

### IR LED Ring (x2)

| Parameter | Specification |
|-----------|---------------|
| Wavelength | 850nm (near-infrared, faintly visible red glow) |
| Power | 3W per ring |
| LED Count | 24–36 LEDs per ring |
| Illumination Range | 10–15 meters |
| Beam Angle | 60°–90° (matches camera FOV center) |
| Power Supply | 12V DC (powered from 5V via boost converter) or 5V direct variants |
| Mounting | Concentric around camera lens |
| Light Sensor | Built-in CDS photoresistor (auto on at dusk, off at dawn) |

### Why 850nm?

| Wavelength | Visibility | Range | Use Case |
|------------|-----------|-------|----------|
| 850nm | Faint red glow visible | 10–15m | Good balance — acceptable for farms |
| 940nm | Completely invisible | 5–8m | Covert — shorter range, less efficient |

850nm is chosen because:
- 40% more efficient than 940nm (more light per watt)
- Farm environment — no need for covert operation
- Faint red glow may itself deter intruders
- Better detection range (15m vs 8m)

### Night Vision Test Checklist

- [ ] Camera captures clear image at 10m in complete darkness with IR LEDs on
- [ ] YOLO detects person standing at 10m in IR-lit scene
- [ ] IR LEDs auto-activate when ambient light drops below threshold
- [ ] No IR reflection/glare from enclosure window

---

## 5. Connectivity — 4G LTE Dongle

### USB 4G LTE Modem

| Parameter | Specification |
|-----------|---------------|
| Standard | 4G LTE Cat 4 (150 Mbps down / 50 Mbps up) |
| Mode | RNDIS (USB ethernet — no driver installation needed) |
| SIM Slot | Nano-SIM or Micro-SIM |
| Antenna | Internal (external antenna port preferred for rural areas) |
| Bands | Band 3 (1800MHz), Band 5 (850MHz), Band 40 (2300MHz) — covers Jio/Airtel/BSNL |
| Power | Powered via USB from hub |
| LED Indicators | Network registration, signal strength |

### SIM Card & Data Plan

| Parameter | Specification |
|-----------|---------------|
| Carrier | Jio / Airtel / BSNL (whichever has best coverage at farm) |
| Plan Type | Data-only, minimum 1GB/month |
| Expected Usage | 300–500 MB/month under normal alert volume |
| SIM Security | PIN lock enabled to prevent theft/reuse |
| APN | Auto-configured by carrier |

### Data Usage Breakdown

| Event | Size | Frequency | Monthly Estimate |
|-------|------|-----------|-----------------|
| Alert payload (JSON) | ~500 bytes | 5–20/day | ~300 KB |
| Alert snapshot (JPEG) | ~80–150 KB | 5–20/day | ~45 MB |
| Heartbeat (JSON) | ~200 bytes | 1/minute | ~8.6 MB |
| MQTT overhead | ~50 bytes/msg | All messages | ~5 MB |
| OTA updates (occasional) | ~50 MB | 1/month | ~50 MB |
| **Total** | | | **~110 MB/month** |

### Connectivity Failover

```
Connected (normal)    ──→  Publish alerts in real-time via MQTT
         │
    4G signal lost
         │
         ▼
Disconnected (offline) ──→  Queue alerts locally in tmpfs (max 100)
         │                   Continue surveillance normally
    4G signal restored        MQTT auto-reconnects
         │
         ▼
Reconnected           ──→  Flush queued alerts (FIFO)
                            Resume real-time publishing
```

---

## 6. USB Hub

### Powered USB Hub (4-Port)

| Parameter | Specification |
|-----------|---------------|
| Ports | 4x USB 2.0 Type-A |
| Power | Externally powered (5V/2A adapter or shared from main PSU) |
| Chipset | Any standard hub chipset (FE1.1s common) |

### Why a Powered Hub?

The Orange Pi Zero 3 has only 2 USB ports, and its internal USB power budget (~500mA per port) cannot reliably power:

- Camera 1 (~200mA)
- Camera 2 (~200mA)
- 4G Dongle (~400mA peak)

Total demand: ~800mA, exceeding the Pi's USB power delivery. A powered hub provides independent 5V power to each device.

### USB Port Assignment

| Hub Port | Device | Protocol |
|----------|--------|----------|
| Port 1 | Camera 1 (Front) | USB 2.0 UVC — `/dev/video0` |
| Port 2 | Camera 2 (Rear) | USB 2.0 UVC — `/dev/video2` |
| Port 3 | 4G USB Dongle | RNDIS ethernet — `usb0` |
| Port 4 | (Spare) | Future: IR LED controller, tamper sensor USB |

---

## 7. Power System

### Architecture

```
    230V AC Mains (Farm supply)
         │
         ▼
    ┌─────────────────────┐
    │  Surge Protector     │ ← MOV-based, protects against rural power spikes
    │  (Single outlet)     │
    └──────────┬──────────┘
               │
               ▼
    ┌─────────────────────┐
    │  5V / 3A USB-C      │ ← Quality adapter (not cheap charger)
    │  Power Adapter       │
    └──────────┬──────────┘
               │
               ▼
    ┌─────────────────────┐
    │  10000mAh Power Bank │ ← Must support pass-through charging
    │  (UPS Mode)          │
    │                      │
    │  Mains ON:  Pass-through power + trickle charge battery
    │  Mains OFF: Battery → Orange Pi (seamless switchover)
    └──────────┬──────────┘
               │
               ├──→ Orange Pi Zero 3 (USB-C, 5V/2A)
               │
               └──→ USB Hub → Cameras + 4G Dongle (5V/2A)
```

### Power Supply Specifications

| Component | Specification |
|-----------|---------------|
| Mains Adapter | 5V/3A USB-C, BIS certified, short-circuit protection |
| Surge Protector | MOV-based, 230V/6A, clamping voltage 275V |
| Power Bank | 10000mAh, supports pass-through/UPS mode |
| Power Bank Output | 5V/2A minimum (one port), USB-A output |

### Power Bank Selection Criteria

The power bank acts as a UPS. Not all power banks support true pass-through charging. Required features:

- **Pass-through charging:** Can charge and discharge simultaneously
- **Auto-power-on:** Resumes output automatically when mains power is restored after a complete drain
- **No auto-shutoff:** Does not turn off when load is below a threshold (some banks shutoff below 50mA)
- **10000mAh capacity:** Provides 4–8 hours of backup depending on load

### Backup Duration Calculation

| Scenario | Total Load | 10000mAh @ 5V = 50Wh | Duration |
|----------|-----------|----------------------|----------|
| Day (no IR) | 6.0W | 50Wh / 6.0W | ~8.3 hours |
| Night (IR on) | 7.0W | 50Wh / 7.0W | ~7.1 hours |
| Throttled (battery saver) | 3.5W | 50Wh / 3.5W | ~14.3 hours |

### Mains Power Detection (GPIO)

A simple voltage divider circuit detects whether mains power is present:

```
    5V from Adapter ──→ 10kΩ ──┬── 10kΩ ──→ GND
                               │
                               └──→ GPIO 27 (reads HIGH = mains on, LOW = mains off)
```

The software reads GPIO 27 to determine power source (`mains` vs `battery`) and adjusts scan rate accordingly to conserve battery during power cuts.

---

## 8. Tamper Detection

### Tilt/Vibration Sensor

| Parameter | Specification |
|-----------|---------------|
| Type | SW-420 vibration sensor module or spring-type tilt switch |
| Interface | Digital output — GPIO (HIGH = tamper event) |
| Sensitivity | Adjustable via onboard potentiometer (SW-420) |
| Power | 3.3V from Orange Pi GPIO header |
| GPIO Pin | GPIO 17 (configurable in `device_config.yaml`) |

### Wiring

```
    SW-420 Module
    ┌───────────┐
    │  VCC  ────│──→  Pin 1 (3.3V) on Orange Pi GPIO header
    │  GND  ────│──→  Pin 6 (GND)
    │  DO   ────│──→  Pin 11 (GPIO 17)
    └───────────┘
```

### Behavior

| Event | GPIO State | Software Action |
|-------|-----------|-----------------|
| Normal (device still) | LOW | No action |
| Tamper (device moved/shaken) | HIGH | Immediate MQTT alert → `tamper_detected` event |
| Sustained vibration (wind) | Debounced | Software debounces: only triggers if HIGH for >2 consecutive reads |

### Tamper Alert Priority

Tamper alerts bypass:
- Cooldown timer (always sent immediately)
- Motion detection pipeline (not camera-dependent)
- Schedule restrictions (24/7 tamper monitoring)

---

## 9. Thermal Management

### Cooling System

| Component | Specification |
|-----------|---------------|
| Fan | 40mm x 40mm, 5V DC, sleeve bearing |
| Airflow | Intake from bottom vents, exhaust through top |
| Control | Always-on (5V from USB hub or Pi header) |
| Thermal Zone | SoC thermal sensor at `/sys/class/thermal/thermal_zone0/temp` |

### Thermal Throttling Policy (Software-Controlled)

| CPU Temperature | State | Action |
|----------------|-------|--------|
| < 65°C | Normal | Full scan rate (~700ms per 360° cycle) |
| 65°C – 75°C | Throttled | Reduced scan rate (1 second delay between cycles) |
| > 75°C | Critical | Skip YOLO inference, motion-only mode, 5 second delay |
| > 85°C | Emergency | Would trigger OS thermal shutdown (should never reach) |

### Enclosure Ventilation Design

```
    TOP VIEW
    ┌────────────────────────┐
    │ ░░░░░ exhaust vents ░░░│ ← Hot air exits through top mesh
    │                        │
    │   ┌──────────────┐     │
    │   │   Fan (40mm)  │     │ ← Pulls air upward across SoC heatsink
    │   └──────────────┘     │
    │                        │
    │   [Orange Pi + Hub]    │
    │   [Power Bank]         │
    │                        │
    │ ░░░░░ intake vents ░░░░│ ← Cool air enters from bottom mesh
    └────────────────────────┘

    Mesh material: Fine nylon mesh (blocks insects, allows airflow)
```

### Operating Temperature Range

| Condition | Ambient Temp | SoC Temp (est.) | Status |
|-----------|-------------|-----------------|--------|
| Winter night (rural India) | 5°C | 35°C | Normal |
| Spring/autumn day | 25°C | 55°C | Normal |
| Summer day (shade) | 40°C | 65°C | Borderline — throttle |
| Summer day (direct sun) | 50°C | 75°C+ | Critical — mount in shade |

> **Important:** The enclosure must NOT be placed in direct sunlight. Mount on the north side of the pole or under a shade canopy in hot regions.

---

## 10. Enclosure

### Weatherproof Enclosure

| Parameter | Specification |
|-----------|---------------|
| Material | ABS plastic (UV-resistant) |
| Rating | IP54 minimum (dust-protected, splash-proof) |
| Dimensions | ~200mm x 150mm x 80mm (internal) |
| Color | White or light grey (reflects heat) |
| Ventilation | Bottom intake + top exhaust mesh vents |
| Cable Entry | 3x PG7/PG9 cable glands (power, USB cameras, sensor) |
| Camera Openings | 2x circular cutouts with clear acrylic/polycarbonate window |
| Fan Cutout | 40mm cutout on internal wall for fan mounting |

### Camera Window Requirements

- **Material:** Clear polycarbonate or acrylic (2mm thick)
- **Anti-glare:** Matte finish on exterior to reduce IR LED reflection
- **Seal:** Silicone gasket around window edges (waterproof)
- **Angle:** Flush or slightly recessed to prevent rain pooling

### Internal Layout

```
    FRONT VIEW (enclosure open)
    ┌──────────────────────────────┐
    │ ┌──────────┐  ┌──────────┐  │
    │ │ Camera 1  │  │ Camera 2  │  │ ← Cameras face opposite directions
    │ │ (window)  │  │ (window)  │  │    through side walls
    │ └──────────┘  └──────────┘  │
    │                              │
    │  ┌──────────────────────┐   │
    │  │  Orange Pi Zero 3     │   │ ← Mounted on standoffs
    │  └──────────────────────┘   │
    │                              │
    │  ┌──────────────────────┐   │
    │  │  USB Hub + 4G Dongle  │   │
    │  └──────────────────────┘   │
    │                              │
    │  ┌──────────────────────┐   │
    │  │  Power Bank (UPS)     │   │ ← Heaviest component at bottom
    │  └──────────────────────┘   │
    │                              │
    │  [Tamper sensor on wall]     │
    │  [Fan on internal partition] │
    └──────────────────────────────┘
```

---

## 11. Mounting Hardware

### Pole and Bracket

| Component | Specification |
|-----------|---------------|
| Pole | 12ft (3.6m) galvanized steel pipe or heavy-duty PVC, 1.5" diameter |
| Base | Concrete footing or ground sleeve (prevents tipping) |
| Bracket | U-clamp or flange plate at pole top for enclosure |
| Cable Routing | Inside the pole (prevents cable tampering/weather damage) |
| Height | 12ft recommended — above reach, wide camera view, avoids animals triggering |

### Mounting Diagram

```
                        ┌─────────┐
                        │Enclosure│ ← Enclosure bolted to bracket
                        │ + Cams  │
                        └────┬────┘
                             │
                        ┌────┴────┐
                        │ Bracket │ ← U-clamp or flange on pole top
                        └────┬────┘
                             │
                             │  12ft steel/PVC pole
                             │
                             │  (Power cable + USB routed inside)
                             │
                             │
                        ═════╧═════ ← Ground level
                        │ Concrete │
                        │ footing  │
                        └──────────┘

    Location: Near farm perimeter, at highest-risk entry point
    Direction: Camera 1 facing the main approach/gate
    Clearance: Minimum 2m from any tree/structure (avoids false triggers)
```

### Mounting Best Practices

1. **Height:** 12ft keeps the device out of arm's reach (deters theft) and provides a wider field of view
2. **Orientation:** Camera 1 (front) should face the most likely entry point (gate, road, field edge)
3. **Clearance:** Keep 2+ meters away from trees, walls, or clotheslines to reduce false positives
4. **Cable routing:** Route all cables inside the pole — external cables are vulnerable to animals and weather
5. **Grounding:** Ground the pole if metal (lightning protection in open fields)
6. **Shade:** If in a hot region, mount on the north side of existing structures or add a small sun shield above the enclosure

---

## 12. Cables and Connectors

| Cable | Specification | Length | Purpose |
|-------|---------------|--------|---------|
| USB-A to USB-A extension | USB 2.0, shielded | 1m x2 | Camera to hub (inside pole) |
| USB-C cable | 5V/3A rated | 0.5m | Power adapter to power bank |
| USB-A to USB-C | 5V/2A rated | 0.3m | Power bank to Orange Pi |
| Jumper wires (F-F) | 22AWG, Dupont connectors | 20cm x3 | GPIO: tamper sensor + mains detect |
| Cable glands | PG7 / PG9, IP68 | - x3 | Waterproof cable entry into enclosure |
| Zip ties | Nylon, UV-resistant | - x20 | Cable management inside pole and enclosure |
| Heat shrink tubing | Assorted sizes | - | Waterproofing exposed solder joints |
| Electrical tape | PVC insulation | 1 roll | General insulation |

---

## 13. Software Requirements on Hardware

### OS Installation

| Item | Detail |
|------|--------|
| OS Image | Armbian Bookworm (Debian 12) for Orange Pi Zero 3 |
| Kernel | Linux 6.x (mainline, shipped with Armbian) |
| Flash Tool | Etcher / dd to write image to MicroSD |
| First Boot | Expand filesystem, set timezone, disable GUI desktop |

### Required Software Packages

```bash
# System
sudo apt update && sudo apt install -y \
    python3.11 python3.11-venv python3-pip \
    v4l-utils \
    usbutils \
    network-manager \
    mosquitto-clients

# Python packages (in venv)
pip install \
    opencv-python-headless==4.9.0.80 \
    onnxruntime==1.17.3 \
    paho-mqtt==2.1.0 \
    numpy==1.26.4 \
    Pillow==10.3.0 \
    PyYAML==6.0.1
```

### YOLO Model

| Item | Detail |
|------|--------|
| Model | YOLOv5n (nano) — smallest YOLOv5 variant |
| Format | ONNX (Open Neural Network Exchange) |
| Size | ~4 MB |
| Input | 320x320 RGB, float16 |
| Output | Bounding boxes + class + confidence |
| Inference Time | ~180–200ms on Cortex-A53 (CPU only, no GPU) |
| Download | Run `edge/download_model.sh` or export from PyTorch |

### Systemd Service

The surveillance daemon runs as a systemd service for automatic start, restart, and watchdog:

```ini
# /etc/systemd/system/atss.service
[Unit]
Description=Anti-Theft Smart System Edge Daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=atss
WorkingDirectory=/opt/atss/edge
ExecStart=/opt/atss/edge/venv/bin/python -m src.main --config config/device_config.yaml
Restart=always
RestartSec=5
WatchdogSec=60
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

---

## 14. GPIO Pin Assignments

Orange Pi Zero 3 — 26-pin GPIO header:

| Pin # | GPIO # | Function | Connected To |
|-------|--------|----------|-------------|
| 1 | — | 3.3V Power | Tamper sensor VCC |
| 6 | — | Ground | Tamper sensor GND, mains detect GND |
| 11 | GPIO 17 | Digital Input | Tamper switch (SW-420 DO pin) |
| 13 | GPIO 27 | Digital Input | Mains power detect (voltage divider) |
| 9 | — | Ground | (Spare) |

### GPIO Setup (One-time)

```bash
# Export GPIO pins
echo 17 > /sys/class/gpio/export
echo 27 > /sys/class/gpio/export

# Set as inputs
echo in > /sys/class/gpio/gpio17/direction
echo in > /sys/class/gpio/gpio27/direction
```

> Add these to `/etc/rc.local` or a udev rule for persistence across reboots.

---

## 15. Power Budget

### Component Power Consumption

| Component | Active Power | Idle Power | Peak Power |
|-----------|-------------|------------|------------|
| Orange Pi Zero 3 (CPU) | 3.5W | 1.5W | 5.0W |
| USB Camera x2 | 1.0W | 0.0W | 1.2W |
| 4G USB Dongle | 1.0W | 0.1W | 2.0W (transmit burst) |
| USB Hub (overhead) | 0.5W | 0.3W | 0.5W |
| IR LED Ring x2 (night only) | 1.0W | 0.0W | 1.5W |
| Cooling Fan | 0.3W | 0.3W | 0.3W |
| Tamper Sensor | 0.01W | 0.01W | 0.01W |
| **Total (Day)** | **6.3W** | **2.2W** | **9.0W** |
| **Total (Night)** | **7.3W** | **2.2W** | **10.5W** |

### Power Source Sizing

| Power Source | Capacity | Day Runtime | Night Runtime |
|-------------|----------|-------------|---------------|
| 5V/3A Mains Adapter | Unlimited | Continuous | Continuous |
| 10000mAh Power Bank | 50Wh | ~8 hours | ~7 hours |
| 20000mAh Power Bank | 100Wh | ~16 hours | ~14 hours |

### Battery-Saver Mode (Software)

When on battery power, the software automatically:
- Reduces scan frequency (1 second delay between cycles)
- Skips YOLO on low-confidence motion events
- Reduces heartbeat frequency (every 5 minutes instead of every minute)
- Estimated power savings: ~40% (extends runtime to 12+ hours on 10000mAh)

---

## 16. Assembly Checklist

### Pre-Assembly

- [ ] Flash Armbian to MicroSD card
- [ ] Boot Orange Pi, expand filesystem, set timezone, create `atss` user
- [ ] Install Python 3.11, pip, venv, v4l-utils
- [ ] Connect to Wi-Fi temporarily for initial setup
- [ ] Clone/copy edge software to `/opt/atss/edge/`
- [ ] Create Python venv, install requirements
- [ ] Download YOLOv5n ONNX model via `download_model.sh`
- [ ] Test cameras individually: `v4l2-ctl --list-devices`
- [ ] Test 4G dongle: `nmcli device status` → verify `usb0` interface
- [ ] Test MQTT connectivity: `mosquitto_pub -h <broker> -t test -m hello`

### Hardware Assembly

- [ ] Mount Orange Pi on standoffs inside enclosure
- [ ] Connect powered USB hub to Orange Pi USB 3.0 port
- [ ] Connect Camera 1 to hub port 1 → verify `/dev/video0`
- [ ] Connect Camera 2 to hub port 2 → verify `/dev/video2`
- [ ] Connect 4G dongle to hub port 3 → verify `usb0` and internet
- [ ] Wire tamper sensor: VCC→3.3V, GND→GND, DO→GPIO17
- [ ] Wire mains detect: voltage divider → GPIO27
- [ ] Mount cameras in enclosure with IR LED rings
- [ ] Mount fan on internal partition (airflow: bottom→top)
- [ ] Place power bank at bottom of enclosure
- [ ] Route all cables, secure with zip ties
- [ ] Seal cable glands with silicone
- [ ] Close enclosure, verify IP54 seal

### Field Installation

- [ ] Install pole at perimeter with concrete base
- [ ] Route power cable inside pole from ground to top
- [ ] Mount enclosure on pole bracket
- [ ] Connect mains power through surge protector
- [ ] Verify system boots and connects to MQTT
- [ ] Verify Camera 1 faces the primary entry point
- [ ] Verify Camera 2 covers the opposite direction
- [ ] Test night vision: confirm IR LEDs illuminate and camera captures in darkness
- [ ] Test tamper alert: shake the pole → verify MQTT alert received
- [ ] Walk in front of cameras → verify intrusion alert
- [ ] Verify push notification received on farmer's phone
- [ ] Set monitoring schedule if desired
- [ ] Mark as armed in the mobile app

---

## 17. Recommended Suppliers (India)

| Component | Supplier Options | Platform |
|-----------|-----------------|----------|
| Orange Pi Zero 3 | Official Orange Pi store, Robu.in | AliExpress, Robu.in |
| USB Wide-Angle NoIR Camera | Arducam, ELP camera modules | Amazon.in, AliExpress |
| IR LED Ring (850nm) | Generic CCTV IR boards | Amazon.in, Electronics shops |
| 4G USB Dongle | Jio Dongle, ZTE MF833V, Huawei E3372 | Amazon.in, Jio Store |
| Powered USB Hub | Any branded 4-port powered hub | Amazon.in |
| 10000mAh Power Bank | Mi, Ambrane, Syska (with pass-through) | Amazon.in, Flipkart |
| SW-420 Vibration Sensor | Generic module | Amazon.in, Robu.in |
| 40mm Fan | Noctua NF-A4x10 (premium) or generic 5V | Amazon.in |
| ABS Enclosure | Junction box / CCTV enclosure | Amazon.in, local electrical shop |
| 12ft Pole | GI pipe 1.5" or PVC conduit | Local hardware store |
| Cable Glands | PG7/PG9 nylon glands | Amazon.in, Robu.in |
| MicroSD 16GB | SanDisk Industrial / Samsung EVO | Amazon.in |

---

## 18. Hardware Alternatives

### SBC Alternatives

| Board | RAM | USB | Price (INR) | Pros | Cons |
|-------|-----|-----|-------------|------|------|
| **Orange Pi Zero 3 (chosen)** | 2GB | USB 3.0 + 2.0 | 2,200 | Cheapest with USB 3.0, good Armbian support | Limited GPIO docs |
| Raspberry Pi Zero 2 W | 512MB | 1x micro-USB | 1,800 | Huge community | Only 512MB RAM, 1 USB port |
| Orange Pi 3B | 4GB | 2x USB 3.0 | 3,500 | More RAM, more USB | Overkill for this use case |
| Raspberry Pi 4B (2GB) | 2GB | 2x USB 3.0 + 2x USB 2.0 | 3,800 | Best community support | Expensive, high power draw |
| Radxa Zero 3W | 2GB | 1x USB 3.0 | 2,500 | Compact | Single USB port |

### Camera Alternatives

| Camera | FOV | Interface | Price (INR) | Notes |
|--------|-----|-----------|-------------|-------|
| **ELP 170° NoIR USB (chosen)** | 170° | USB 2.0 | 600 | Best value wide-angle NoIR |
| Arducam OV5647 NoIR | 160° | CSI (RPi only) | 500 | Not USB — requires CSI port |
| Logitech C270 (modified) | 60° | USB 2.0 | 800 | IR filter must be removed manually |
| RPi Camera Module 3 NoIR | 120° | CSI | 2,500 | Expensive, CSI only |

### Connectivity Alternatives

| Option | Cost (INR) | Monthly | Notes |
|--------|-----------|---------|-------|
| **4G USB Dongle (chosen)** | 600 | 150 | Best balance of cost, coverage, reliability |
| SIM800L (2G) | 300 | 50 | Very slow, 2G being phased out |
| ESP32 + SIM7600 | 1,500 | 150 | Custom PCB needed, more complex |
| LoRa gateway | 2,000 | 0 | No internet — only local mesh |
| Farm Wi-Fi (if available) | 0 | 0 | Rarely available in rural farms |
