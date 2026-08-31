"""Push notifications for trays that need a human, via an ntfy topic URL.

A notification fires when the set of unmapped trays changes to something
non-empty, not on every evaluation, so a tray that stays unmapped nags once
per insertion rather than every minute.
"""

import logging
import urllib.request

from spooldown.http import USER_AGENT
from spooldown.mapper import Unmapped

log = logging.getLogger(__name__)


class Notifier:
    def __init__(self, ntfy_url: str | None, map_url: str | None) -> None:
        self._url = ntfy_url
        self._map_url = map_url
        self._last_signature: tuple[tuple[int, str], ...] = ()

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
