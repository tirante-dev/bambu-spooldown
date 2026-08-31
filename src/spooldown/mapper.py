"""Third-party tray to Spoolman spool mapping.

RFID trays identify themselves; third-party trays only report the material
and color the user configured on the printer. When exactly one active
untagged spool matches, the location is set automatically; otherwise the
tray is surfaced as unmapped for the notifier and the /map page.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from spooldown.spoolman import ZERO_UUID, Spoolman, spool_tag

log = logging.getLogger(__name__)

COLOR_DISTANCE_LIMIT = 60.0


@dataclass
class Unmapped:
    """One third-party tray with no confidently matching spool."""

    tray: int
    material: str
    color: str
    candidate_ids: list[int] = field(default_factory=list)


def _color_distance(a: str, b: str) -> float | None:
    try:
        ar, ag, ab_ = (int(a[i : i + 2], 16) for i in (0, 2, 4))
        br, bg, bb = (int(b[i : i + 2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        return None
    return float(((ar - br) ** 2 + (ag - bg) ** 2 + (ab_ - bb) ** 2) ** 0.5)


def _material_matches(tray_type: str, material: str) -> bool:
    return bool(tray_type) and tray_type.lower() in material.lower()


class Mapper:
    """Evaluates the AMS inventory against Spoolman and auto-maps when safe."""

    def __init__(self, spoolman: Spoolman, printer_name: str) -> None:
        self._spoolman = spoolman
        self._printer_name = printer_name
        self.unmapped: dict[int, Unmapped] = {}

    def location(self, tray: int) -> str:
        return f"{self._printer_name} - A{tray}"

    def evaluate(self, trays: dict[int, dict[str, str]]) -> None:
        """One pass over the current AMS state. Cheap; called periodically."""
        if not self._printer_name:
            return
        spools = self._spoolman.spools()
        seen: dict[int, Unmapped] = {}
        for tray, info in sorted(trays.items()):
            if not info.get("type") or info.get("uuid", "") != ZERO_UUID:
                continue
            result = self._evaluate_tray(tray, info, spools)
            if result is not None:
                seen[tray] = result
        self.unmapped = seen

    def _evaluate_tray(
        self, tray: int, info: dict[str, str], spools: list[dict[str, Any]]
    ) -> Unmapped | None:
        location = self.location(tray)
        material, color = info["type"], info.get("color", "")[:6]
        occupant = next(
            (s for s in spools if s.get("location") == location and not s.get("archived")), None
        )
        if occupant is not None:
            if _material_matches(material, occupant["filament"].get("material", "")):
                return None
            # The tray's contents changed under a stale mapping; surface it
            # rather than silently charging the wrong spool.
            log.warning(
                "tray A%d holds %s but mapped spool %d is %s",
                tray,
                material,
                occupant["id"],
                occupant["filament"].get("material"),
            )
            return Unmapped(tray, material, color, [])

        other_slots = {
            s.get("location")
            for s in spools
            if (s.get("location") or "").startswith(f"{self._printer_name} - A")
        }
        candidates = [
            s
            for s in spools
            if not s.get("archived")
            and spool_tag(s) is None
            and _material_matches(material, s["filament"].get("material", ""))
            and (not s.get("location") or s.get("location") not in other_slots)
        ]
        if len(candidates) > 1 and color:
            near = [
                s
                for s in candidates
                if (d := _color_distance(color, s["filament"].get("color_hex") or "")) is not None
                and d <= COLOR_DISTANCE_LIMIT
            ]
            if len(near) == 1:
                candidates = near
        if len(candidates) == 1:
            spool_id = int(candidates[0]["id"])
            self._spoolman.set_location(spool_id, location)
            log.info("auto-mapped tray A%d -> spool %d (%s)", tray, spool_id, material)
            return None
        return Unmapped(tray, material, color, [int(s["id"]) for s in candidates])

    def assign(self, tray: int, spool_id: int) -> None:
        """Manual mapping from the /map page."""
        self._spoolman.set_location(spool_id, self.location(tray))
        self.unmapped.pop(tray, None)
        log.info("manually mapped tray A%d -> spool %d", tray, spool_id)
