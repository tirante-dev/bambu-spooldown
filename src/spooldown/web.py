"""Health, and the /map page for trays the mapper could not settle."""

import html
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from spooldown.__main__ import Service

STALE_AFTER_SECONDS = 300

PAGE = """<!doctype html>
<title>spooldown</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body {{
  font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 34rem; padding: 0 1rem;
}}
fieldset {{ margin-bottom: 1.5rem; border-radius: 8px; }}
button {{ padding: .5rem 1.5rem; font-size: 1rem; }}
.swatch {{
  display: inline-block; width: .9em; height: .9em;
  border: 1px solid #888; border-radius: 3px; vertical-align: -0.1em;
}}
</style>
<h1>Spool mapping</h1>
{body}
"""


def render_map(service: "Service") -> str:
    unmapped = service.mapper.unmapped
    if not unmapped:
        return PAGE.format(body="<p>Every occupied tray is mapped. Nothing to do.</p>")
    spools = service.spoolman.spools()
    by_id = {int(s["id"]): s for s in spools}
    sections = []
    for u in sorted(unmapped.values(), key=lambda u: u.tray):
        ids = u.candidate_ids or [int(s["id"]) for s in spools if not s.get("archived")]
        options = []
        for sid in ids:
            s = by_id.get(sid)
            if s is None:
                continue
            f = s["filament"]
            label = html.escape(
                f"#{sid} {f.get('material', '')} {f.get('name', '')} "
                f"({s.get('remaining_weight', '?')}g left)"
            )
            sw = html.escape(f.get("color_hex") or "ffffff")
            options.append(
                f'<label><input type="radio" name="spool" value="{sid}" required> '
                f'<span class="swatch" style="background:#{sw}"></span> {label}</label><br>'
            )
        sections.append(
            f"<form method='post'><fieldset>"
            f"<legend>Tray A{u.tray}: {html.escape(u.material)}"
            f"{' (no matching spool found; pick any)' if not u.candidate_ids else ''}</legend>"
            f"<input type='hidden' name='tray' value='{u.tray}'>"
            f"{''.join(options) or '<p>No spools exist yet; create one in Spoolman first.</p>'}"
            f"<button>Map</button></fieldset></form>"
        )
    return PAGE.format(body="".join(sections))


def serve(service: "Service", port: int) -> None:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path.startswith("/map"):
                self._send(200, render_map(service).encode())
                return
            age = time.monotonic() - service.stream.last_message_at
            healthy = service.stream.last_message_at > 0 and age < STALE_AFTER_SECONDS
            self._send(200 if healthy else 503, b"ok" if healthy else b"stale", "text/plain")

        def do_POST(self) -> None:
            if not self.path.startswith("/map"):
                self._send(404, b"not found", "text/plain")
                return
            length = int(self.headers.get("Content-Length", "0"))
            form = urllib.parse.parse_qs(self.rfile.read(length).decode())
            try:
                tray = int(form["tray"][0])
                spool = int(form["spool"][0])
            except (KeyError, ValueError, IndexError):
                self._send(400, b"tray and spool are required", "text/plain")
                return
            service.mapper.assign(tray, spool)
            self.send_response(303)
            self.send_header("Location", "/map")
            self.end_headers()

        def log_message(self, fmt: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
