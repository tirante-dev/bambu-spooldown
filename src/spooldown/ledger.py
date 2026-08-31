"""Processed-job ledger.

A job must decrement spools exactly once. The ledger persists processed task
ids across restarts; without it, a reconnect that replays a FINISH transition
would double-count.
"""

import json
import logging
import os

log = logging.getLogger(__name__)

MAX_ENTRIES = 500


class Ledger:
    """Append-only set of processed job keys, persisted as a JSON list."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._keys: list[str] = []
        try:
            with open(path, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, list):
                self._keys = [str(k) for k in loaded]
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            log.warning("ledger at %s unreadable; starting empty", path)

    def seen(self, key: str) -> bool:
        return key in self._keys

    def record(self, key: str) -> None:
        self._keys.append(key)
        self._keys = self._keys[-MAX_ENTRIES:]
        tmp = f"{self._path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._keys, f)
        os.replace(tmp, self._path)
