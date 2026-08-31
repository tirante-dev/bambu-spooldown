"""Per-tray filament usage for a finished job.

Two evidence sources, tried in order:

1. The sliced 3MF's `Metadata/slice_info.config`, fetched from the printer
   over FTPS. Only LAN-sent prints are stored where FTPS can see them.
2. The Bambu cloud task API, when a cloud token is configured. Cloud prints
   never appear on the printer's FTPS share.
"""

import logging
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
from urllib.parse import urlencode

from spooldown.http import request_json

log = logging.getLogger(__name__)

CLOUD_TASKS_URL = "https://api.bambulab.com/v1/user-service/my/tasks"


def parse_slice_info(threemf: bytes, plate_index: int) -> dict[int, float]:
    """Reads used grams per filament id from a 3MF's slice_info.config.

    Returns {filament_id: used_g} for the given 1-based plate index.
    """
    with zipfile.ZipFile(BytesIO(threemf)) as z:
        root = ET.fromstring(z.read("Metadata/slice_info.config"))
    for plate in root.iter("plate"):
        idx = None
        for meta in plate.iter("metadata"):
            if meta.get("key") == "index":
                idx = int(meta.get("value", "0"))
        if idx != plate_index:
            continue
        return {int(f.get("id", "0")): float(f.get("used_g", "0")) for f in plate.iter("filament")}
    raise ValueError(f"plate {plate_index} not found in slice_info.config")


def plate_index_from_gcode_path(gcode_file: str) -> int:
    """Extracts the plate number from a path like /data/Metadata/plate_1.gcode."""
    stem = gcode_file.rsplit("/", 1)[-1]
    if stem.startswith("plate_") and stem.endswith(".gcode"):
        try:
            return int(stem[len("plate_") : -len(".gcode")])
        except ValueError:
            pass
    return 1


def per_tray_usage(filament_grams: dict[int, float], mapping: list[int]) -> dict[int, float]:
    """Attributes per-filament grams onto global tray indices via the job mapping.

    `mapping[i]` is the tray for filament id i+1; -1 marks an unused slot.
    """
    out: dict[int, float] = {}
    for fid, grams in filament_grams.items():
        if grams <= 0:
            continue
        pos = fid - 1
        if pos < 0 or pos >= len(mapping) or mapping[pos] < 0:
            log.warning("filament id %d has no tray mapping; dropping %.2fg", fid, grams)
            continue
        tray = mapping[pos]
        out[tray] = out.get(tray, 0.0) + grams
    return out


def cloud_task_usage(token: str, serial: str, task_id: str) -> dict[int, float] | None:
    """Fetches per-tray grams for a cloud task; None when the task is not found.

    The task's amsDetailMapping carries per-filament weight and target tray.
    Tasks without it (single filament) fall back to the task's total weight,
    which the caller attributes via the job mapping.
    """
    query = urlencode({"deviceId": serial, "limit": 40})
    data = request_json(
        f"{CLOUD_TASKS_URL}?{query}",
        headers={"Authorization": f"Bearer {token}"},
    )
    for task in data.get("hits", []):
        if str(task.get("id")) != task_id:
            continue
        detail = task.get("amsDetailMapping") or []
        out: dict[int, float] = {}
        for entry in detail:
            grams = float(entry.get("weight", 0))
            tray = int(entry.get("ams", -1))
            if grams > 0 and tray >= 0:
                out[tray] = out.get(tray, 0.0) + grams
        if out:
            return out
        total = float(task.get("weight", 0))
        return {-1: total} if total > 0 else None
    return None
