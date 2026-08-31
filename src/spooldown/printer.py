"""Printer transport: local MQTT report stream and FTPS file fetch."""

import ftplib
import json
import logging
import socket
import ssl
import time
from collections.abc import Callable
from io import BytesIO
from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

log = logging.getLogger(__name__)


class ImplicitFTPS(ftplib.FTP_TLS):
    """FTPS with implicit TLS on 990 and data-channel session reuse.

    The printer's server rejects data connections that do not resume the
    control connection's TLS session ("522 session reuse required").
    """

    def __init__(self) -> None:
        super().__init__()
        self.ctx = ssl._create_unverified_context()

    def connect(
        self, host: str = "", port: int = 990, timeout: float = 30, source_address: Any = None
    ) -> str:
        self.host, self.port, self.timeout = host, port, timeout
        raw = socket.create_connection((host, port), timeout)
        self.af = raw.family
        self.sock = self.ctx.wrap_socket(raw, server_hostname=host)
        self.file = self.sock.makefile("r", encoding=self.encoding)
        self.welcome = self.getresp()
        return self.welcome

    def ntransfercmd(self, cmd: str, rest: Any = None) -> tuple[socket.socket, int | None]:
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        assert isinstance(self.sock, ssl.SSLSocket)
        conn = self.ctx.wrap_socket(conn, server_hostname=self.host, session=self.sock.session)
        return conn, size


def fetch_file(host: str, access_code: str, path: str) -> bytes:
    """Downloads one file from the printer's FTPS share."""
    f = ImplicitFTPS()
    f.connect(host)
    try:
        f.login("bblp", access_code)
        f.prot_p()
        buf = BytesIO()
        f.retrbinary(f"RETR {path}", buf.write)
        return buf.getvalue()
    finally:
        try:
            f.quit()
        except (OSError, ftplib.all_errors):  # type: ignore[misc]
            f.close()


def find_threemf(host: str, access_code: str, subtask_name: str) -> bytes | None:
    """Fetches the cached 3MF for a LAN print, trying the known cache paths."""
    candidates = [
        f"/cache/{subtask_name}.3mf",
        f"/{subtask_name}.3mf",
        f"/model/{subtask_name}.3mf",
    ]
    for path in candidates:
        try:
            return fetch_file(host, access_code, path)
        except ftplib.all_errors:
            continue
        except OSError:
            continue
    return None


class ReportStream:
    """Maintains the MQTT subscription to the printer's report topic.

    paho reconnects on its own; on every (re)connect a `pushall` is requested
    so the tracker starts from a full state snapshot rather than deltas.
    """

    def __init__(
        self,
        host: str,
        serial: str,
        access_code: str,
        on_payload: Callable[[dict[str, Any]], None],
    ) -> None:
        self._serial = serial
        self._on_payload = on_payload
        self.last_message_at = 0.0
        self._client = mqtt.Client(CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv311)
        self._client.tls_set(cert_reqs=ssl.CERT_NONE)
        self._client.tls_insecure_set(True)
        self._client.username_pw_set("bblp", access_code)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.reconnect_delay_set(min_delay=1, max_delay=60)
        self._host = host

    def start(self) -> None:
        self._client.connect_async(self._host, 8883, keepalive=60)
        self._client.loop_start()

    def stop(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    def _on_connect(self, client: mqtt.Client, *args: Any, **kwargs: Any) -> None:
        log.info("mqtt connected to %s", self._host)
        client.subscribe(f"device/{self._serial}/report")
        client.publish(
            f"device/{self._serial}/request",
            json.dumps({"pushing": {"sequence_id": "0", "command": "pushall"}}),
        )

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        self.last_message_at = time.monotonic()
        try:
            payload = json.loads(msg.payload)
        except ValueError:
            return
        if isinstance(payload, dict):
            self._on_payload(payload)
