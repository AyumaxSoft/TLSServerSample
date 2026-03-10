# TLSServerSample

ObjectDelivererV2 の `TLSClient` と通信できる、Python 製の `TLSTCPIPServer` サンプルです。

このサンプルは以下を提供します。

- OpenSSL を使った CA/サーバー証明書作成
- OpenSSL を使った mTLS 用クライアント証明書作成
- ObjectDeliverer の `PacketRuleSizeBody` 互換のパケット処理
- 受信データをそのまま返す Echo back サーバー

## 1. 前提

- macOS / Linux / Windows(WSL) のいずれか
- `python3` (3.9 以降推奨)
- `openssl` コマンド

確認:

```bash
python3 --version
openssl version
```

## 2. ファイル構成

- `server.py`: TLS + SizeBody + Echo back サーバー本体
- `scripts/create_ca_and_server_cert.sh`: CA とサーバー証明書を作成
- `scripts/create_client_cert.sh`: mTLS 用クライアント証明書を作成
- `certs/`: 証明書出力先

## 3. 証明書作成

### 3-1. CA + サーバー証明書を作る

```bash
cd /TLSServerSample
./scripts/create_ca_and_server_cert.sh ./certs localhost localhost 127.0.0.1
```

引数:

1. 出力先ディレクトリ (省略時 `./certs`)
2. サーバー証明書の CN (省略時 `localhost`)
3. SAN の DNS 名 (省略時 `localhost`)
4. SAN の IP (省略時 `127.0.0.1`)

生成物(例):

- `./certs/ca.crt.pem`
- `./certs/ca.key.pem`
- `./certs/server.crt.pem`
- `./certs/server.key.pem`
- `./certs/server.fullchain.pem`

### 3-2. mTLS 用クライアント証明書を作る

```bash
cd /TLSServerSample
./scripts/create_client_cert.sh ./certs od-client
```

引数:

1. 出力先ディレクトリ (省略時 `./certs`)
2. クライアント名/CN (省略時 `od-client`)
3. CA証明書パス (省略時 `./certs/ca.crt.pem`)
4. CA秘密鍵パス (省略時 `./certs/ca.key.pem`)

生成物(例):

- `./certs/od-client.crt.pem`
- `./certs/od-client.key.pem`

## 4. サーバー起動

### 4-1. mTLS 必須で起動 (推奨)

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

### 4-2. mTLS 無しで起動

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

## 5. ObjectDeliverer TLSClient 側の設定ポイント

ObjectDeliverer 側で TLSClient を使う際、以下を合わせてください。

1. 接続先
- Host: サーバー証明書の SAN/CN と一致する値を指定
- Port: `server.py` の `--port`

2. TLS サーバー検証
- `Trusted CA Certificate`: `./certs/ca.crt.pem` を指定
- 証明書検証を有効化して利用

3. mTLS (サーバー側 `--client-auth required` の場合)
- Client Certificate: `./certs/od-client.crt.pem`
- Client Private Key: `./certs/od-client.key.pem`

4. PacketRule
- `PacketRuleSizeBody` を選択
- `SizeLength`: `4` (またはサーバー起動値に一致)
- `SizeBufferEndian`: `Big` (またはサーバー起動値に一致)

## 6. PacketRuleSizeBody 互換仕様

このサーバーのフレーミングは ObjectDeliverer の `PacketRuleSizeBody` と同じです。

- 先頭 `SizeLength` バイト: Body サイズ(符号なし)
- 続く N バイト: Body 本体
- Endian: `big` / `little`

例 (`SizeLength=4`, `big`, Body=`\x01\x02\x03`):

- 送信: `00 00 00 03 01 02 03`
- 受信後の返信(Echo): `00 00 00 03 01 02 03`

## 7. `server.py` 主なオプション

- `--client-auth`: `none | optional | required` (既定: `required`)
- `--size-length`: `1 | 2 | 3 | 4` (既定: `4`)
- `--size-endian`: `big | little` (既定: `big`)
- `--max-body-size`: 1パケットの最大 Body サイズ (既定: 8MiB)
- `--min-tls-version`: `1.2 | 1.3` (既定: `1.2`)

ヘルプ:

```bash
python3 server.py --help
```

## 8. 動作確認 (OpenSSL)

### 8-1. mTLS 必須サーバーに接続

```bash
openssl s_client \
  -connect 127.0.0.1:8765 \
  -CAfile ./certs/ca.crt.pem \
  -cert ./certs/od-client.crt.pem \
  -key ./certs/od-client.key.pem
```

### 8-2. よくあるエラー

- `TLS handshake failed`
  - `--ca-cert` とクライアント証明書の発行元 CA が一致しているか確認
  - クライアント証明書/鍵の組み合わせが正しいか確認
- `certificate verify failed`
  - ObjectDeliverer 側の接続先 Host と証明書 SAN/CN の不一致を確認
  - `Trusted CA Certificate` に `ca.crt.pem` を設定したか確認
- `body too large`
  - `--max-body-size` を見直す

## 9. セキュリティ注意

- `ca.key.pem` は秘密情報です。公開しないでください。
- 本番用途では、運用ポリシーに沿った証明書管理・ローテーションを実施してください。
