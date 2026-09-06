# Raspberry Pi 3 Model B — Setup Guide

**Target**: Raspberry Pi 3 Model B, Raspbian OS Lite, CSI Camera Module (5MP)

---

## Prerequisites

- Raspberry Pi 3 Model B with Raspbian OS Lite installed
- Pi connected to the same network (WiFi or Ethernet)
- SSH access to the Pi
- CSI camera module (5MP, ribbon cable) — can be connected later

---

## Step 1: SSH into the Pi

```bash
ssh pi@<PI_IP_ADDRESS>
# Default password: raspberry (change it if not already done)
```

Verify the Pi model and OS:

```bash
cat /proc/device-tree/model && echo
cat /etc/os-release | head -3
uname -m   # Should show "armv7l" for Pi 3
```

---

## Step 2: System Update

```bash
sudo apt update && sudo apt upgrade -y
```

---

## Step 3: Enable CSI Camera

The 5MP CSI camera module connects via the ribbon cable to the CSI port (between the HDMI and audio jack).

```bash
# Enable camera interface (0 = enable)
sudo raspi-config nonint do_camera 0

# Load V4L2 driver on boot so camera appears as /dev/video0
echo "bcm2835-v4l2" | sudo tee /etc/modules-load.d/camera.conf

# Reboot to apply
sudo reboot
```

After reboot (and once camera is physically connected), verify:

```bash
ls /dev/video0          # Should exist
vcgencmd get_camera     # Should show: supported=1 detected=1
```

---

## Step 4: Install System Dependencies

```bash
sudo apt install -y \
    python3-pip \
    python3-venv \
    python3-opencv \
    libopencv-dev \
    libatlas-base-dev \
    git
```

- `python3-opencv` — OpenCV with V4L2 support (pre-built for ARM)
- `libatlas-base-dev` — required by numpy on ARMv7
- `git` — to clone the repo

---

## Step 5: Create Install Directory

```bash
sudo mkdir -p /opt/surveillance
sudo chown $USER:$USER /opt/surveillance
cd /opt/surveillance
```

---

## Step 6: Clone Repository and Copy Edge Code

```bash
git clone https://github.com/ganeshmpatil/anti-theft-smart-system.git /opt/surveillance/repo

# Copy edge files to install location
cp -r repo/edge/src /opt/surveillance/
cp -r repo/edge/config /opt/surveillance/
cp -r repo/edge/models /opt/surveillance/
cp repo/edge/requirements.txt /opt/surveillance/
```

---

## Step 7: Create Python Virtual Environment and Install Dependencies

```bash
cd /opt/surveillance

python3 -m venv --system-site-packages venv
# --system-site-packages allows using the system OpenCV (python3-opencv)

# Upgrade pip
./venv/bin/pip install --upgrade pip

# Install base requirements
./venv/bin/pip install -r requirements.txt

# Install TFLite runtime for Pi 3 (ARMv7 32-bit)
./venv/bin/pip install tflite-runtime
```

Note: `tflite-runtime` is the inference engine for Pi 3. ONNX Runtime does NOT support ARMv7 32-bit.

---

## Step 8: Create MQTT Credentials in EMQX Cloud

1. Go to https://cloud-intl.emqx.com/console
2. Open the `farmguard` deployment
3. Navigate to **Access Control > Authentication**
4. Click **Add**
5. Create:
   - Username: `FARM-001`
   - Password: (choose a strong password, note it down)

---

## Step 9: Configure the Device

```bash
cd /opt/surveillance

# Copy production config as the active config
cp config/production_config.yaml config/device_config.yaml
```

Edit `config/device_config.yaml`:

```bash
nano config/device_config.yaml
```

Update these fields:

```yaml
device:
  device_id: "FARM-001"
  farm_id: "farm_1"

camera:
  production:
    cam1_source: "/dev/video0"    # CSI camera
    cam2_source: ""               # Leave empty — single camera for now

mqtt:
  broker: "w1196cd6.ala.asia-southeast1.emqxsl.com"
  port: 8883
  username: "FARM-001"
  password: "<PASSWORD_FROM_STEP_8>"
  tls_enabled: true
  ca_cert: ""

detection:
  backend: "tflite"
  model_path: "models/yolov5n.tflite"
  input_size: 320

schedule:
  enabled: false                  # Disable schedule for initial testing
```

---

## Step 10: Test Run (Manual)

Run the daemon manually to verify everything works:

```bash
cd /opt/surveillance
./venv/bin/python -m src.main --config config/device_config.yaml --debug
```

Expected output:
```
Anti-Theft Smart System -- Edge Daemon
Mode: production
Device: FARM-001 | Farm: farm_1
Camera cam_front opened at /dev/video0
TFLite model loaded: models/yolov5n.tflite
MQTT connected to w1196cd6.ala.asia-southeast1.emqxsl.com:8883
Starting surveillance loop...
```

Press `Ctrl+C` to stop after verifying.

---

## Step 11: Provision Device on Backend

The backend rejects heartbeats from unknown devices. Register FARM-001:

```bash
# Run from your laptop (not the Pi)
curl -X POST https://farmguard-api.onrender.com/api/v1/admin/devices/provision \
  -H "Content-Type: application/json" \
  -d '{"device_uid": "FARM-001"}'
```

---

## Step 12: Install systemd Service

```bash
# Copy the service file
sudo cp /opt/surveillance/repo/edge/systemd/surveillance.service \
    /etc/systemd/system/atss-surveillance.service

# Copy journald log rotation config
sudo cp /opt/surveillance/repo/edge/systemd/journald-atss.conf \
    /etc/systemd/journald.conf.d/atss.conf
sudo mkdir -p /etc/systemd/journald.conf.d

# Reload systemd
sudo systemctl daemon-reload

# Enable (start on boot) and start
sudo systemctl enable atss-surveillance
sudo systemctl start atss-surveillance

# Check status
sudo systemctl status atss-surveillance
```

---

## Step 13: Verify End-to-End

1. Check Pi service is running:
```bash
sudo journalctl -u atss-surveillance -f
```

2. Check backend received the heartbeat:
```bash
curl -s https://farmguard-api.onrender.com/api/v1/admin/health/fleet | python3 -m json.tool
```

FARM-001 should appear with status "online".

3. Walk in front of the camera — you should receive a push notification on the mobile app (if FCM is set up).

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `/dev/video0` not found | Check ribbon cable, run `sudo raspi-config` > Interface > Camera > Enable, reboot |
| `vcgencmd get_camera` shows `detected=0` | Camera not seated properly — reseat the ribbon cable |
| TFLite import error | `./venv/bin/pip install tflite-runtime` |
| MQTT connection failed | Check EMQX credentials, verify port 8883, check `tls_enabled: true` |
| Out of memory | Reduce `input_size` to 160, or add swap: `sudo dphys-swapfile swapoff && sudo sed -i 's/CONF_SWAPSIZE=.*/CONF_SWAPSIZE=512/' /etc/dphys-swapfile && sudo dphys-swapfile setup && sudo dphys-swapfile swapon` |
| Service keeps restarting | Check logs: `sudo journalctl -u atss-surveillance -n 50` |
| Camera gives green/pink tint | Known Pi CSI issue — add `awb_mode=auto` or try: `v4l2-ctl --set-ctrl=auto_exposure=0` |

---

## Write Version File

```bash
echo "1.0.0" | sudo tee /opt/surveillance/VERSION
```

This is used by the OTA updater to skip updates if already on the latest version.

---

## Summary

| Component | Value |
|---|---|
| Install path | `/opt/surveillance/` |
| Config file | `/opt/surveillance/config/device_config.yaml` |
| Service name | `atss-surveillance` |
| Model | YOLOv5n TFLite (11MB, ~500ms inference) |
| MQTT broker | EMQX Cloud (TLS, port 8883) |
| Logs | `sudo journalctl -u atss-surveillance -f` |
