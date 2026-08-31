"""Spoolman REST client and tray -> spool resolution."""

import json
import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)


class Spoolman:
    """Thin client for the two Spoolman calls this service needs."""

    def __init__(self, base_url: str) -> None:
        self._client = httpx.Client(base_url=f"{base_url}/api/v1", timeout=30)

    def spools(self) -> list[dict[str, Any]]:
        resp = self._client.get("/spool")
        resp.raise_for_status()
        out = resp.json()
        assert isinstance(out, list)
        return out

    def use_weight(self, spool_id: int, grams: float) -> None:
        resp = self._client.put(f"/spool/{spool_id}/use", json={"use_weight": round(grams, 2)})
        resp.raise_for_status()


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
