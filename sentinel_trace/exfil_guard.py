"""Per-identity egress budgets for authorized telemetry; returns decisions only."""
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import RLock

@dataclass(frozen=True)
class Decision:
    blocked: bool
    observed_bytes: int
    threshold_bytes: int
    reason: str

class EgressGuard:
    def __init__(self, threshold_bytes=5 * 1024 * 1024, window_seconds=60):
        if threshold_bytes <= 0 or window_seconds <= 0:
            raise ValueError('threshold and window must be positive')
        self.threshold_bytes = threshold_bytes
        self.window_seconds = window_seconds
        self._events = defaultdict(deque)
        self._lock = RLock()

    def evaluate(self, identity: str, byte_count: int, timestamp: float, authorized_source: bool) -> Decision:
        if not authorized_source or not identity:
            raise ValueError('authorized source and identity required')
        if type(byte_count) is not int or byte_count < 0:
            raise ValueError('byte_count must be nonnegative integer')
        with self._lock:
            q = self._events[identity]
            if q and timestamp < q[-1][0]:
                raise ValueError('out-of-order event')
            while q and q[0][0] <= timestamp - self.window_seconds:
                q.popleft()
            q.append((timestamp, byte_count))
            total = sum(n for _, n in q)
            return Decision(total >= self.threshold_bytes, total, self.threshold_bytes,
                            'egress-budget-exceeded' if total >= self.threshold_bytes else 'within-budget')
