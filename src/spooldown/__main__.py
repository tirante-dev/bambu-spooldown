"""Service entrypoint: wires the report stream to the usage pipeline."""

import logging
import os
import signal
import threading
import time
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from spooldown import usage
from spooldown.cloud import FileTokenStore, K8sSecretStore, TokenManager, TokenStore
from spooldown.config import Config
from spooldown.ledger import Ledger
from spooldown.printer import ReportStream, find_threemf
from spooldown.spoolman import Spoolman, resolve_tray
from spooldown.tracker import Job, Tracker

log = logging.getLogger("spooldown")

STALE_AFTER_SECONDS = 300


class Service:
    """Consumes finished jobs and decrements the mapped Spoolman spools."""

    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._spoolman = Spoolman(cfg.spoolman_url)
        self._ledger = Ledger(cfg.ledger_path)
        store: TokenStore = (
            K8sSecretStore(cfg.token_secret_name)
            if cfg.token_secret_name
            else FileTokenStore(cfg.token_state_path)
        )
        self.tokens = TokenManager(store, cfg.cloud_token, cfg.cloud_refresh_token)
        self._tracker = Tracker(self.on_job_done)
        self.stream = ReportStream(
            cfg.printer_host, cfg.printer_serial, cfg.access_code, self._tracker.handle
        )

    def on_job_done(self, job: Job, fraction: float) -> None:
        key = (
            job.task_id
            if job.task_id not in ("", "0")
            else f"{job.subtask_name}@{int(time.time())}"
        )
        if self._ledger.seen(key):
            log.info("job %s already processed; skipping", key)
            return
        if fraction <= 0:
            log.info("job %s ended at 0%%; nothing to record", key)
            return
        if fraction < 1.0 and not self._cfg.partial_on_cancel:
            log.info("job %s incomplete and PARTIAL_ON_CANCEL=false; skipping", key)
            return
        try:
            per_tray = self._usage_for(job)
        except Exception:
            log.exception("job %s: usage lookup failed", key)
            return
        if not per_tray:
            log.warning("job %s: no usage evidence available; nothing recorded", key)
            return
        self._apply(job, per_tray, fraction)
        self._ledger.record(key)

    def _usage_for(self, job: Job) -> dict[int, float]:
        if job.print_type != "cloud":
            threemf = find_threemf(self._cfg.printer_host, self._cfg.access_code, job.subtask_name)
            if threemf is not None:
                grams = usage.parse_slice_info(
                    threemf, usage.plate_index_from_gcode_path(job.gcode_file)
                )
                return usage.per_tray_usage(grams, job.mapping)
            log.warning("job %s: 3MF not found on printer", job.task_id)
        token = self.tokens.access()
        if token:
            try:
                per_tray = usage.cloud_task_usage(token, self._cfg.printer_serial, job.task_id)
            except urllib.error.HTTPError as e:
                if e.code not in (401, 403) or not self.tokens.refresh():
                    raise
                fresh = self.tokens.access()
                assert fresh is not None
                per_tray = usage.cloud_task_usage(fresh, self._cfg.printer_serial, job.task_id)
            if per_tray is not None:
                # A -1 key is an unattributed total; place it via the job mapping.
                if -1 in per_tray and len(job.mapping) == 1 and job.mapping[0] >= 0:
                    per_tray[job.mapping[0]] = per_tray.pop(-1)
                per_tray.pop(-1, None)
                return per_tray
            log.warning("job %s: not found in cloud task list", job.task_id)
        return {}

    def _apply(self, job: Job, per_tray: dict[int, float], fraction: float) -> None:
        spools = self._spoolman.spools()
        for tray, grams in sorted(per_tray.items()):
            spool_id = resolve_tray(spools, tray, job.tray_uuids.get(tray), self._cfg.printer_name)
            if spool_id is None:
                continue
            used = grams * fraction
            self._spoolman.use_weight(spool_id, used)
            log.info(
                "job %s: tray A%d -> spool %d, used %.2fg (fraction %.2f)",
                job.task_id,
                tray,
                spool_id,
                used,
                fraction,
            )


def refresh_loop(service: Service) -> None:
    """Rotates the cloud token pair well before the ~90 day access expiry."""

    def run() -> None:
        while True:
            if service.tokens.should_refresh_proactively():
                service.tokens.refresh()
            time.sleep(6 * 3600)

    threading.Thread(target=run, daemon=True).start()


def serve_health(service: Service, port: int) -> None:
    """Liveness endpoint: unhealthy when the report stream has gone quiet."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            age = time.monotonic() - service.stream.last_message_at
            healthy = service.stream.last_message_at > 0 and age < STALE_AFTER_SECONDS
            self.send_response(200 if healthy else 503)
            self.end_headers()
            self.wfile.write(b"ok" if healthy else b"stale")

        def log_message(self, fmt: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    cfg = Config.from_env()
    service = Service(cfg)
    serve_health(service, cfg.health_port)
    refresh_loop(service)
    service.stream.start()
    log.info(
        "spooldown watching printer %s for Spoolman at %s", cfg.printer_serial, cfg.spoolman_url
    )
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    stop.wait()
    service.stream.stop()


if __name__ == "__main__":
    main()
