#!/bin/bash
# Generate self-signed TLS certificates for development/VPS deployment.
# For production with a domain, use Let's Encrypt via Caddy instead.
#
# Usage: ./generate_self_signed.sh [server_ip_or_hostname]
#
# Generates:
#   certs/ca.crt, ca.key          — Certificate Authority
#   certs/server.crt, server.key  — Server certificate (for Caddy + Mosquitto)

set -euo pipefail

CERT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVER_CN="${1:-$(hostname -I | awk '{print $1}')}"
DAYS=365

echo "Generating certificates for: ${SERVER_CN}"
echo "Output directory: ${CERT_DIR}"

# CA key and cert
openssl genrsa -out "$CERT_DIR/ca.key" 2048
openssl req -new -x509 -days "$DAYS" -key "$CERT_DIR/ca.key" \
    -out "$CERT_DIR/ca.crt" \
    -subj "/CN=FarmGuard CA/O=FarmGuard/C=IN"

# Server key and CSR
openssl genrsa -out "$CERT_DIR/server.key" 2048
openssl req -new -key "$CERT_DIR/server.key" \
    -out "$CERT_DIR/server.csr" \
    -subj "/CN=${SERVER_CN}/O=FarmGuard/C=IN"

# Sign server cert with CA (include IP SAN)
cat > "$CERT_DIR/server_ext.cnf" <<EOF
[v3_req]
subjectAltName = @alt_names
[alt_names]
IP.1 = ${SERVER_CN}
DNS.1 = localhost
EOF

openssl x509 -req -in "$CERT_DIR/server.csr" \
    -CA "$CERT_DIR/ca.crt" -CAkey "$CERT_DIR/ca.key" -CAcreateserial \
    -out "$CERT_DIR/server.crt" -days "$DAYS" \
    -extfile "$CERT_DIR/server_ext.cnf" -extensions v3_req

# Cleanup intermediate files
rm -f "$CERT_DIR/server.csr" "$CERT_DIR/server_ext.cnf" "$CERT_DIR/ca.srl"

echo ""
echo "Certificates generated:"
echo "  CA:     ${CERT_DIR}/ca.crt"
echo "  Server: ${CERT_DIR}/server.crt + server.key"
echo ""
echo "Copy ca.crt to each Pi for MQTT TLS verification:"
echo "  scp ${CERT_DIR}/ca.crt pi@<pi-ip>:/opt/surveillance/certs/"
