"""Cumulative server-side transfer decisions across sessions and vendors."""
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import RLock

@dataclass(frozen=True)
class TransferEvent:
    tenant: str
    principal: str
    session: str
    timestamp: int
    bytes_out: int
    file_count: int
    identity_verified: bool
    device_verified: bool
    destination_approved: bool
    data_approved: bool
    vendor_access: bool = False
    vendor_grant_valid: bool = False

@dataclass(frozen=True)
class Verdict:
    action: str
    reason: str
    cumulative_bytes: int
    cumulative_files: int

class ContinuousGuard:
    def __init__(self, window_seconds=3600, byte_limit=5*1024*1024,
                 file_limit=200, vendor_byte_limit=1024*1024):
        if min(window_seconds, byte_limit, file_limit, vendor_byte_limit) <= 0:
            raise ValueError('limits must be positive')
        self.window, self.byte_limit = window_seconds, byte_limit
        self.file_limit, self.vendor_byte_limit = file_limit, vendor_byte_limit
        self._history = defaultdict(deque)
        self._lock = RLock()

    def evaluate(self, e: TransferEvent) -> Verdict:
        if not e.tenant or not e.principal or not e.session:
            raise ValueError('missing tenant, principal, or session')
        if any(type(v) is not int or v < 0 for v in (e.timestamp, e.bytes_out, e.file_count)):
            raise ValueError('invalid telemetry')
        key = (e.tenant, e.principal)
        with self._lock:
            q = self._history[key]
            if q and e.timestamp < q[-1][0]:
                raise ValueError('out-of-order telemetry')
            while q and q[0][0] <= e.timestamp - self.window:
                q.popleft()
            q.append((e.timestamp, e.bytes_out, e.file_count))
            total_bytes = sum(item[1] for item in q)
            total_files = sum(item[2] for item in q)
            if not e.identity_verified or not e.device_verified:
                action, reason = 'DENY', 'identity-or-device-unverified'
            elif not e.destination_approved or not e.data_approved:
                action, reason = 'DENY', 'transfer-not-authorized'
            elif e.vendor_access and not e.vendor_grant_valid:
                action, reason = 'DENY', 'vendor-grant-missing'
            elif e.vendor_access and total_bytes >= self.vendor_byte_limit:
                action, reason = 'HOLD', 'vendor-egress-threshold'
            elif total_bytes >= self.byte_limit or total_files >= self.file_limit:
                action, reason = 'HOLD', 'cumulative-transfer-threshold'
            else:
                action, reason = 'ALLOW', 'verified-within-budget'
            return Verdict(action, reason, total_bytes, total_files)
