"""Push notifications for trays that need a human, via an ntfy topic URL.

A notification fires when the set of unmapped trays changes to something
non-empty, not on every evaluation, so a tray that stays unmapped nags once
per insertion rather than every minute.
"""

import logging
import time
import urllib.request

from spooldown.http import USER_AGENT
from spooldown.mapper import Unmapped

log = logging.getLogger(__name__)


RENEWAL_REMINDER_INTERVAL_SECONDS = 7 * 24 * 3600


class Notifier:
    def __init__(self, ntfy_url: str | None, map_url: str | None) -> None:
        self._url = ntfy_url
        self._map_url = map_url
        self._last_signature: tuple[tuple[int, str], ...] = ()
        self._last_renewal_notice = 0.0

    def send(self, title: str, body: str, click: str | None = None) -> bool:
        if not self._url:
            return False
        req = urllib.request.Request(self._url, data=body.encode(), method="POST")
        req.add_header("User-Agent", USER_AGENT)
        req.add_header("Title", title)
        if click:
            req.add_header("Click", click)
        try:
            with urllib.request.urlopen(req, timeout=15):
                pass
        except OSError as e:
            log.warning("ntfy notification failed: %s", e)
            return False
        return True

    def token_renewal_due(self, age_days: float) -> None:
        """Weekly nudge once the cloud token pair is near its ~90 day expiry."""
        now = time.monotonic()
        if now - self._last_renewal_notice < RENEWAL_REMINDER_INTERVAL_SECONDS:
            return
        if self.send(
            "Bambu cloud token expiring",
            f"The token pair is {age_days:.0f} days old and refresh is not "
            "available for email-code logins. Re-run the login flow from the "
            "bambu-spooldown README and re-seal the pair.",
            "https://github.com/tirante-dev/bambu-spooldown#getting-a-cloud-token",
        ):
            self._last_renewal_notice = now

    def observe(self, unmapped: dict[int, Unmapped]) -> None:
        signature = tuple(sorted((u.tray, u.material) for u in unmapped.values()))
        if signature == self._last_signature:
            return
        self._last_signature = signature
        if not unmapped or not self._url:
            return
        lines = [
            f"A{u.tray}: {u.material}"
            + (f" ({len(u.candidate_ids)} candidates)" if u.candidate_ids else " (no match)")
            for u in sorted(unmapped.values(), key=lambda u: u.tray)
        ]
        req = urllib.request.Request(self._url, data="\n".join(lines).encode(), method="POST")
        req.add_header("User-Agent", USER_AGENT)
        req.add_header("Title", "Spool needs mapping")
        req.add_header("Tags", "thread")
        req.add_header("Priority", "default")
        if self._map_url:
            req.add_header("Click", self._map_url)
            req.add_header("Actions", f"view, Map now, {self._map_url}")
        try:
            with urllib.request.urlopen(req, timeout=15):
                pass
            log.info("notified about %d unmapped tray(s)", len(unmapped))
        except OSError as e:
            log.warning("ntfy notification failed: %s", e)
