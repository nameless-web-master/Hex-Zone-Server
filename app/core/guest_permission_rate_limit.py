"""Rolling-window rate limit for public guest arrival (per client key, e.g. IP)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

_lock = threading.Lock()
_buckets: dict[str, deque[float]] = defaultdict(deque)


def allow_request(key: str, *, max_events: int, window_seconds: float = 60.0) -> bool:
    """Return True if under limit; if at limit, return False (do not record this attempt)."""
    now = time.monotonic()
    with _lock:
        dq = _buckets[key]
        cutoff = now - window_seconds
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= max_events:
            return False
        dq.append(now)
        return True


def reset_for_tests() -> None:
    """Clear counters (pytest only)."""
    with _lock:
        _buckets.clear()
