"""Gateway telemetry counters (AUD-012)."""

from __future__ import annotations

import threading
from collections import defaultdict

_lock = threading.Lock()
_metrics: dict[str, int] = defaultdict(int)
_deny_by_code: dict[str, int] = defaultdict(int)


def inc(name: str, n: int = 1) -> None:
    with _lock:
        _metrics[name] += n


def inc_deny(code: str) -> None:
    with _lock:
        _metrics["resolver_deny_total"] += 1
        _deny_by_code[code] += 1


def snapshot() -> dict:
    with _lock:
        return {
            "counters": dict(_metrics),
            "deny_by_code": dict(_deny_by_code),
        }
