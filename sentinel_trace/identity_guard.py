"""Zero-trust decision-only transfer authorization, independent of user job title."""
from dataclasses import dataclass
from collections import defaultdict, deque
from threading import RLock

@dataclass(frozen=True)
class TransferDecision:
    action: str
    reason: str
    cumulative_bytes: int

class IdentityTransferGuard:
    def __init__(self, window_seconds=3600, normal_limit=5*1024*1024, elevated_limit=10*1024*1024):
        if min(window_seconds, normal_limit, elevated_limit) <= 0 or elevated_limit < normal_limit:
            raise ValueError('invalid configuration')
        self.window = window_seconds
        self.normal_limit = normal_limit
        self.elevated_limit = elevated_limit
        self.events = defaultdict(deque)
        self.lock = RLock()

    def evaluate(self, *, tenant, user, device, bytes_out, timestamp, authenticated,
                 phishing_resistant_mfa, device_compliant, destination_approved,
                 data_approved, explicit_grant=False, unusual_session=False):
        if not tenant or not user or not device or type(bytes_out) is not int or bytes_out < 0:
            raise ValueError('invalid event')
        key = (tenant, user, device)
        with self.lock:
            q = self.events[key]
            if q and timestamp < q[-1][0]:
                raise ValueError('out-of-order timestamp')
            while q and q[0][0] <= timestamp - self.window:
                q.popleft()
            q.append((timestamp, bytes_out))
            total = sum(n for _, n in q)
            if not authenticated or not phishing_resistant_mfa or not device_compliant:
                return TransferDecision('deny', 'identity-or-device-not-verified', total)
            if not destination_approved or not data_approved:
                return TransferDecision('deny', 'destination-or-data-not-approved', total)
            if unusual_session:
                return TransferDecision('step_up', 'session-anomaly', total)
            if total >= self.elevated_limit:
                return TransferDecision('step_up', 'large-cumulative-transfer', total)
            if total >= self.normal_limit and not explicit_grant:
                return TransferDecision('step_up', 'elevated-transfer-needs-approval', total)
            return TransferDecision('allow', 'policy-satisfied', total)
