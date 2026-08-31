"""Print-job state tracking over the printer's MQTT report stream.

The printer publishes partial `print` payloads; a `pushall` request yields a
full snapshot. Payloads are deep-merged into one running state, and job
lifecycle events are derived from `gcode_state` transitions.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

ACTIVE_STATES = {"PREPARE", "SLICING", "RUNNING", "PAUSE"}
TERMINAL_STATES = {"FINISH", "FAILED", "IDLE"}


@dataclass
class Job:
    """A print job observed from its start, with the fields usage needs."""

    task_id: str
    subtask_name: str
    gcode_file: str
    print_type: str
    mapping: list[int] = field(default_factory=list)
    tray_uuids: dict[int, str] = field(default_factory=dict)
    percent: int = 0
    seen_start: bool = True


def _deep_merge(dst: dict[str, Any], src: dict[str, Any]) -> None:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v


class Tracker:
    """Merges report payloads and emits (job, completion_fraction) on job end.

    A job first observed in a terminal state (service restarted mid-print or
    stale retained state) is emitted with seen_start=False so the caller can
    decide whether the usage evidence is still trustworthy.
    """

    def __init__(self, on_done: Callable[[Job, float], None]) -> None:
        self._state: dict[str, Any] = {}
        self._job: Job | None = None
        self._on_done = on_done

    def handle(self, payload: dict[str, Any]) -> None:
        """Consumes one MQTT report payload."""
        p = payload.get("print")
        if not isinstance(p, dict):
            return
        prev_state = self._state.get("gcode_state")
        _deep_merge(self._state, p)
        cur_state = self._state.get("gcode_state")
        if cur_state is None:
            return

        if cur_state in ACTIVE_STATES:
            self._track_active(first_observation=prev_state is None)
        elif cur_state in TERMINAL_STATES and prev_state in ACTIVE_STATES:
            self._finish(str(cur_state))

    def _track_active(self, first_observation: bool) -> None:
        task_id = str(self._state.get("task_id", ""))
        if self._job is None or (task_id and task_id != self._job.task_id):
            self._job = Job(
                task_id=task_id,
                subtask_name=str(self._state.get("subtask_name", "")),
                gcode_file=str(self._state.get("gcode_file", "")),
                print_type=str(self._state.get("print_type", "")),
                seen_start=not first_observation,
            )
            log.info(
                "tracking job task_id=%s name=%r seen_start=%s",
                self._job.task_id,
                self._job.subtask_name,
                self._job.seen_start,
            )
        job = self._job
        mapping = self._state.get("mapping")
        if isinstance(mapping, list) and mapping:
            job.mapping = [int(t) for t in mapping]
        pct = self._state.get("mc_percent")
        if isinstance(pct, int):
            job.percent = pct
        job.tray_uuids.update(self._current_tray_uuids())

    def _finish(self, end_state: str) -> None:
        job = self._job
        self._job = None
        if job is None:
            return
        if end_state == "FINISH":
            fraction = 1.0
        elif end_state == "FAILED":
            fraction = job.percent / 100.0
        else:
            # IDLE without FINISH/FAILED is a user cancel on some firmwares.
            fraction = job.percent / 100.0
        log.info("job ended task_id=%s state=%s fraction=%.2f", job.task_id, end_state, fraction)
        self._on_done(job, fraction)

    def trays(self) -> dict[int, dict[str, str]]:
        """Global tray index -> {uuid, type, color} from the merged AMS snapshot.

        Global indices follow the print `mapping` convention: 4 trays per AMS
        unit, in unit order. The all-zeros uuid marks a third-party spool; an
        empty `type` marks an empty slot.
        """
        out: dict[int, dict[str, str]] = {}
        units = self._state.get("ams", {}).get("ams")
        if not isinstance(units, list):
            return out
        for unit in units:
            try:
                base = int(unit.get("id", 0)) * 4
                for tray in unit.get("tray", []):
                    out[base + int(tray["id"])] = {
                        "uuid": str(tray.get("tray_uuid", "")),
                        "type": str(tray.get("tray_type", "")),
                        "color": str(tray.get("tray_color", "")),
                    }
            except (TypeError, ValueError, KeyError):
                continue
        return out

    def _current_tray_uuids(self) -> dict[int, str]:
        return {i: t["uuid"] for i, t in self.trays().items()}
