# TLSServerSample

A Python `TLSTCPIPServer` sample that can communicate with ObjectDelivererV2 `TLSClient`.

This sample provides:

- CA/server certificate generation with OpenSSL
- Client certificate generation for mTLS with OpenSSL
- Packet framing compatible with ObjectDeliverer `PacketRuleSizeBody`
- Echo-back behavior (returns exactly what it receives)

## 1. Prerequisites

- macOS / Linux / Windows (WSL)
- `python3` (3.9+ recommended)
- `openssl`

Check:

```bash
python3 --version
openssl version
```

## 2. File layout

- `server.py`: TLS + SizeBody + echo-back server
- `scripts/create_ca_and_server_cert.sh`: Generates CA and server certificates
- `scripts/create_client_cert.sh`: Generates a client certificate for mTLS
- `certs/`: Certificate output directory

## 3. Generate certificates

### 3-1. Generate CA + server certificate

```bash
cd /TLSServerSample
./scripts/create_ca_and_server_cert.sh ./certs localhost localhost 127.0.0.1
```

Arguments:

1. Output directory (default: `./certs`)
2. Server certificate CN (default: `localhost`)
3. SAN DNS name (default: `localhost`)
4. SAN IP address (default: `127.0.0.1`)

Generated files (example):

- `./certs/ca.crt.pem`
- `./certs/ca.key.pem`
- `./certs/server.crt.pem`
- `./certs/server.key.pem`
- `./certs/server.fullchain.pem`

### 3-2. Generate client certificate for mTLS

```bash
cd /TLSServerSample
./scripts/create_client_cert.sh ./certs od-client
```

Arguments:

1. Output directory (default: `./certs`)
2. Client name/CN (default: `od-client`)
3. CA certificate path (default: `./certs/ca.crt.pem`)
4. CA private key path (default: `./certs/ca.key.pem`)

Generated files (example):

- `./certs/od-client.crt.pem`
- `./certs/od-client.key.pem`

## 4. Start server

### 4-1. Start with mTLS required (recommended)

```bash
cd /TLSServerSample
python3 server.py \
  --host 0.0.0.0 \
  --port 8765 \
  --cert ./certs/server.crt.pem \
  --key ./certs/server.key.pem \
  --ca-cert ./certs/ca.crt.pem \
  --client-auth required \
  --size-length 4 \
  --size-endian big
```

### 4-2. Start without mTLS

```bash
cd /TLSServerSample
python3 server.py \
  --host 0.0.0.0 \
  --port 8765 \
  --cert ./certs/server.crt.pem \
  --key ./certs/server.key.pem \
  --client-auth none \
  --size-length 4 \
  --size-endian big
```

## 5. ObjectDeliverer TLSClient settings

When configuring ObjectDeliverer TLSClient, match these values:

1. Connection target
- Host: Must match server certificate SAN/CN
- Port: Must match `server.py --port`

2. TLS server verification
- Set `Trusted CA Certificate` to `./certs/ca.crt.pem`
- Keep certificate verification enabled

3. mTLS (when server uses `--client-auth required`)
- Client Certificate: `./certs/od-client.crt.pem`
- Client Private Key: `./certs/od-client.key.pem`

4. Packet rule
- Select `PacketRuleSizeBody`
- `SizeLength`: `4` (or match server value)
- `SizeBufferEndian`: `Big` (or match server value)

## 6. `PacketRuleSizeBody` compatibility

This server follows the same framing as ObjectDeliverer `PacketRuleSizeBody`:

- First `SizeLength` bytes: unsigned body size
- Next N bytes: body payload
- Endian: `big` or `little`

Example (`SizeLength=4`, `big`, body=`\x01\x02\x03`):

- Sent: `00 00 00 03 01 02 03`
- Echoed response: `00 00 00 03 01 02 03`

## 7. Main `server.py` options

- `--client-auth`: `none | optional | required` (default: `required`)
- `--size-length`: `1 | 2 | 3 | 4` (default: `4`)
- `--size-endian`: `big | little` (default: `big`)
- `--max-body-size`: Max body bytes per packet (default: 8 MiB)
- `--min-tls-version`: `1.2 | 1.3` (default: `1.2`)

Help:

```bash
python3 server.py --help
```

## 8. Connectivity check (OpenSSL)

### 8-1. Connect to server requiring mTLS

```bash
openssl s_client \
  -connect 127.0.0.1:8765 \
  -CAfile ./certs/ca.crt.pem \
  -cert ./certs/od-client.crt.pem \
  -key ./certs/od-client.key.pem
```

### 8-2. Common errors

- `TLS handshake failed`
  - Confirm `--ca-cert` matches the CA that issued the client certificate
  - Confirm client certificate/key pair is correct
- `certificate verify failed`
  - Confirm ObjectDeliverer host value matches cert SAN/CN
  - Confirm `Trusted CA Certificate` points to `ca.crt.pem`
- `body too large`
  - Increase `--max-body-size` if needed

## 9. Security notes

- `ca.key.pem` is sensitive. Do not expose it.
- For production, use proper certificate lifecycle management and rotation.
