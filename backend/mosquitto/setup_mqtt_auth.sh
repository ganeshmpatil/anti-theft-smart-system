#!/bin/bash
# Generate MQTT credentials for backend and edge devices.
# Run this ONCE before first deployment.
#
# Usage: ./setup_mqtt_auth.sh [num_devices]
#
# Generates:
#   mosquitto/passwd          — Mosquitto password file
#   mosquitto/credentials/    — Per-device credential files for provisioning

set -euo pipefail

NUM_DEVICES="${1:-10}"
PASSWD_FILE="$(dirname "$0")/passwd"
CREDS_DIR="$(dirname "$0")/credentials"

mkdir -p "$CREDS_DIR"

# Generate backend MQTT user
BACKEND_PASS=$(openssl rand -hex 16)
echo "backend_svc:${BACKEND_PASS}" > "$PASSWD_FILE"

echo "MQTT_USERNAME=backend_svc" > "$CREDS_DIR/backend.env"
echo "MQTT_PASSWORD=${BACKEND_PASS}" >> "$CREDS_DIR/backend.env"
echo "[backend] credentials saved to $CREDS_DIR/backend.env"

# Generate per-device MQTT users
for i in $(seq 1 "$NUM_DEVICES"); do
    DEVICE_ID=$(printf "FARM-%03d" "$i")
    DEVICE_PASS=$(openssl rand -hex 16)
    echo "${DEVICE_ID}:${DEVICE_PASS}" >> "$PASSWD_FILE"

    cat > "$CREDS_DIR/${DEVICE_ID}.env" <<EOF
MQTT_USERNAME=${DEVICE_ID}
MQTT_PASSWORD=${DEVICE_PASS}
EOF
    echo "[${DEVICE_ID}] credentials saved to $CREDS_DIR/${DEVICE_ID}.env"
done

# Hash the password file using mosquitto_passwd
# If mosquitto_passwd is available locally, hash in place.
# Otherwise, the docker container will hash on first start.
if command -v mosquitto_passwd &>/dev/null; then
    mosquitto_passwd -U "$PASSWD_FILE"
    echo "Password file hashed with mosquitto_passwd"
else
    echo "WARNING: mosquitto_passwd not found locally."
    echo "Run inside the container: docker exec mosquitto mosquitto_passwd -U /mosquitto/config/passwd"
    echo "Then restart: docker restart mosquitto"
fi

echo ""
echo "Done. Generated credentials for backend + ${NUM_DEVICES} devices."
echo "Copy each FARM-XXX.env to the corresponding Pi during provisioning."
echo "Add backend credentials to your backend .env file."
