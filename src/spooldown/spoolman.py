"""Spoolman REST client and tray -> spool resolution."""

import json
import logging
from typing import Any

from spooldown.http import request_json

log = logging.getLogger(__name__)


class Spoolman:
    """Thin client for the two Spoolman calls this service needs."""

    def __init__(self, base_url: str) -> None:
        self._base = f"{base_url}/api/v1"

    def spools(self) -> list[dict[str, Any]]:
        out = request_json(f"{self._base}/spool")
        assert isinstance(out, list)
        return out

    def use_weight(self, spool_id: int, grams: float) -> None:
        request_json(
            f"{self._base}/spool/{spool_id}/use",
            method="PUT",
            body={"use_weight": round(grams, 2)},
        )


def spool_tag(spool: dict[str, Any]) -> str | None:
    """Reads the RFID tag extra, which Spoolman stores JSON-encoded ('"ABC"')."""
    raw = spool.get("extra", {}).get("tag")
    if not isinstance(raw, str):
        return None
    try:
        val = json.loads(raw)
    except ValueError:
        val = raw
    return val if isinstance(val, str) and val else None


ZERO_UUID = "0" * 32


def resolve_tray(
    spools: list[dict[str, Any]],
    tray: int,
    tray_uuid: str | None,
    printer_name: str,
) -> int | None:
    """Resolves a global tray index to a Spoolman spool id.

    RFID trays match on the tag extra. Third-party trays (all-zeros uuid) match
    on the location convention `<printer name> - A<tray>`, which the AMS
    inventory bridge writes for RFID spools and the user sets by hand for
    third-party ones.
    """
    if tray_uuid and tray_uuid != ZERO_UUID:
        for spool in spools:
            if spool_tag(spool) == tray_uuid:
                return int(spool["id"])
        log.warning("no spool carries tag %s for tray %d", tray_uuid, tray)
    location = f"{printer_name} - A{tray}"
    for spool in spools:
        if spool.get("location") == location and not spool.get("archived"):
            return int(spool["id"])
    log.warning("no spool at location %r for tray %d", location, tray)
    return None
