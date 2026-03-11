#!/usr/bin/env bash
set -euo pipefail

OUTPUT_DIR="${1:-./certs}"
SERVER_CN="${2:-localhost}"
SERVER_SAN_DNS="${3:-localhost}"
SERVER_SAN_IP="${4:-127.0.0.1}"

mkdir -p "$OUTPUT_DIR"

CA_KEY="$OUTPUT_DIR/ca.key.pem"
CA_CERT="$OUTPUT_DIR/ca.crt.pem"
SERVER_KEY="$OUTPUT_DIR/server.key.pem"
SERVER_CSR="$OUTPUT_DIR/server.csr.pem"
SERVER_CERT="$OUTPUT_DIR/server.crt.pem"
SERVER_CHAIN="$OUTPUT_DIR/server.fullchain.pem"
SERVER_EXT="$OUTPUT_DIR/server.ext"

openssl genrsa -out "$CA_KEY" 4096
openssl req -x509 -new -nodes -key "$CA_KEY" -sha256 -days 3650 \
  -subj "/CN=TLSServerSample-CA" \
  -addext "basicConstraints=critical,CA:TRUE,pathlen:1" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -addext "subjectKeyIdentifier=hash" \
  -out "$CA_CERT"

openssl genrsa -out "$SERVER_KEY" 2048
openssl req -new -key "$SERVER_KEY" \
  -subj "/CN=${SERVER_CN}" \
  -out "$SERVER_CSR"

cat > "$SERVER_EXT" <<EOF
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer
subjectAltName=DNS:${SERVER_SAN_DNS},IP:${SERVER_SAN_IP}
EOF

openssl x509 -req -in "$SERVER_CSR" -CA "$CA_CERT" -CAkey "$CA_KEY" -CAcreateserial \
  -out "$SERVER_CERT" -days 825 -sha256 -extfile "$SERVER_EXT"

cat "$SERVER_CERT" "$CA_CERT" > "$SERVER_CHAIN"

chmod 600 "$CA_KEY" "$SERVER_KEY"

cat <<EOF
Generated:
- CA cert:      $CA_CERT
- CA key:       $CA_KEY
- Server cert:  $SERVER_CERT
- Server key:   $SERVER_KEY
- Full chain:   $SERVER_CHAIN

For ObjectDeliverer TLSClient (server verification), set the CA cert to $CA_CERT.
EOF
