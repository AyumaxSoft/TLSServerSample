#!/usr/bin/env python3
import argparse
import logging
import signal
import socket
import ssl
import threading
from typing import Optional


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ObjectDeliverer PacketRuleSizeBody互換 TLS Echo Server"
    )
    parser.add_argument("--host", default="0.0.0.0", help="bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="bind port (default: 8765)")
    parser.add_argument("--cert", required=True, help="server certificate PEM path")
    parser.add_argument("--key", required=True, help="server private key PEM path")
    parser.add_argument(
        "--ca-cert",
        default=None,
        help="CA certificate PEM path (required when --client-auth optional/required)",
    )
    parser.add_argument(
        "--client-auth",
        choices=["none", "optional", "required"],
        default="required",
        help="mTLS client auth mode (default: required)",
    )
    parser.add_argument(
        "--size-length",
        type=int,
        choices=[1, 2, 3, 4],
        default=4,
        help="PacketRuleSizeBody size header bytes (default: 4)",
    )
    parser.add_argument(
        "--size-endian",
        choices=["big", "little"],
        default="big",
        help="PacketRuleSizeBody size header endian (default: big)",
    )
    parser.add_argument(
        "--max-body-size",
        type=int,
        default=8 * 1024 * 1024,
        help="max accepted body bytes (default: 8388608)",
    )
    parser.add_argument(
        "--min-tls-version",
        choices=["1.2", "1.3"],
        default="1.2",
        help="minimum TLS version (default: 1.2)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="log level (default: INFO)",
    )
    return parser.parse_args()


def recv_exact(conn: ssl.SSLSocket, size: int) -> Optional[bytes]:
    data = bytearray()
    while len(data) < size:
        chunk = conn.recv(size - len(data))
        if not chunk:
            return None
        data.extend(chunk)
    return bytes(data)


def build_ssl_context(args: argparse.Namespace) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=args.cert, keyfile=args.key)

    if args.min_tls_version == "1.2":
        context.minimum_version = ssl.TLSVersion.TLSv1_2
    else:
        context.minimum_version = ssl.TLSVersion.TLSv1_3

    if args.client_auth in ("optional", "required"):
        if not args.ca_cert:
            raise ValueError("--client-auth optional/required の場合は --ca-cert が必要です")
        context.load_verify_locations(cafile=args.ca_cert)
        context.verify_mode = (
            ssl.CERT_REQUIRED if args.client_auth == "required" else ssl.CERT_OPTIONAL
        )
    else:
        context.verify_mode = ssl.CERT_NONE

    return context


def handle_client(
    conn: ssl.SSLSocket,
    addr: tuple,
    size_length: int,
    size_endian: str,
    max_body_size: int,
) -> None:
    peer = f"{addr[0]}:{addr[1]}"
    try:
        peer_cert = conn.getpeercert()
        if peer_cert:
            logging.info("client connected: %s cert subject=%s", peer, peer_cert.get("subject"))
        else:
            logging.info("client connected: %s cert=none", peer)

        while True:
            size_buf = recv_exact(conn, size_length)
            if size_buf is None:
                logging.info("client disconnected: %s", peer)
                break

            body_size = int.from_bytes(size_buf, byteorder=size_endian, signed=False)
            if body_size > max_body_size:
                logging.warning(
                    "body too large from %s: %d > %d", peer, body_size, max_body_size
                )
                break

            body = recv_exact(conn, body_size)
            if body is None:
                logging.info("client disconnected before body completed: %s", peer)
                break

            conn.sendall(size_buf + body)
            logging.debug("echoed %d bytes to %s", body_size, peer)

    except ssl.SSLError as e:
        logging.warning("ssl error from %s: %s", peer, e)
    except (ConnectionError, OSError) as e:
        logging.warning("connection error from %s: %s", peer, e)
    finally:
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        conn.close()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    context = build_ssl_context(args)

    stop_event = threading.Event()

    def on_signal(signum, _frame):
        logging.info("received signal %s, shutting down", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((args.host, args.port))
        sock.listen(128)
        sock.settimeout(1.0)

        logging.info(
            "TLS echo server started: %s:%d size_length=%d endian=%s client_auth=%s",
            args.host,
            args.port,
            args.size_length,
            args.size_endian,
            args.client_auth,
        )

        while not stop_event.is_set():
            try:
                client_sock, addr = sock.accept()
            except socket.timeout:
                continue
            except OSError as e:
                if stop_event.is_set():
                    break
                logging.error("accept failed: %s", e)
                continue

            try:
                conn = context.wrap_socket(client_sock, server_side=True)
            except ssl.SSLError as e:
                logging.warning("TLS handshake failed from %s:%s: %s", addr[0], addr[1], e)
                client_sock.close()
                continue

            thread = threading.Thread(
                target=handle_client,
                args=(conn, addr, args.size_length, args.size_endian, args.max_body_size),
                daemon=True,
            )
            thread.start()

    logging.info("server stopped")


if __name__ == "__main__":
    main()
