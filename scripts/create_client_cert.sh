#!/usr/bin/env bash
set -euo pipefail

OUTPUT_DIR="${1:-./certs}"
CLIENT_NAME="${2:-od-client}"
CA_CERT="${3:-$OUTPUT_DIR/ca.crt.pem}"
CA_KEY="${4:-$OUTPUT_DIR/ca.key.pem}"

mkdir -p "$OUTPUT_DIR"

if [[ ! -f "$CA_CERT" ]]; then
  echo "CA cert not found: $CA_CERT" >&2
  exit 1
fi

if [[ ! -f "$CA_KEY" ]]; then
  echo "CA key not found: $CA_KEY" >&2
  exit 1
fi

CLIENT_KEY="$OUTPUT_DIR/${CLIENT_NAME}.key.pem"
CLIENT_CSR="$OUTPUT_DIR/${CLIENT_NAME}.csr.pem"
CLIENT_CERT="$OUTPUT_DIR/${CLIENT_NAME}.crt.pem"
CLIENT_EXT="$OUTPUT_DIR/${CLIENT_NAME}.ext"

openssl genrsa -out "$CLIENT_KEY" 2048
openssl req -new -key "$CLIENT_KEY" \
  -subj "/CN=${CLIENT_NAME}" \
  -out "$CLIENT_CSR"

cat > "$CLIENT_EXT" <<EOF
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=clientAuth
EOF

openssl x509 -req -in "$CLIENT_CSR" -CA "$CA_CERT" -CAkey "$CA_KEY" -CAcreateserial \
  -out "$CLIENT_CERT" -days 825 -sha256 -extfile "$CLIENT_EXT"

chmod 600 "$CLIENT_KEY"

cat <<EOF
Generated:
- Client cert: $CLIENT_CERT
- Client key:  $CLIENT_KEY

You can use this client certificate/key for mTLS in TLSServerSample.
You can also use it when ObjectDeliverer TLSClient sends a client certificate.
EOF
