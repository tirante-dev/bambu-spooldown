"""Hand-rolled Prometheus exposition; a client library is not worth a dep."""

import threading
from collections.abc import Callable


class Metrics:
    """Thread-safe counters plus live gauges rendered on scrape."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, Callable[[], float | None]] = {}

    def inc(self, name: str, amount: float = 1.0) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0.0) + amount

    def gauge(self, name: str, fn: Callable[[], float | None]) -> None:
        self._gauges[name] = fn

    def render(self) -> str:
        lines = []
        with self._lock:
            counters = dict(self._counters)
        for name, value in sorted(counters.items()):
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")
        for name, fn in sorted(self._gauges.items()):
            try:
                gauge_value = fn()
            except Exception:
                gauge_value = None
            if gauge_value is None:
                continue
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {gauge_value}")
        return "\n".join(lines) + "\n"
