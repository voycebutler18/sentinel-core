from dataclasses import dataclass
from typing import FrozenSet

@dataclass(frozen=True)
class SessionSignal:
    account_id: str
    session_id: str
    device_id: str
    device_bound: bool
    verified_device: bool
    authenticated: bool
    privileged_action: bool
    active_session_ids: FrozenSet[str]
    new_device: bool = False
    anomalous_behavior: bool = False
    source_ip_changed: bool = False

@dataclass(frozen=True)
class ShadowDecision:
    action: str
    reasons: tuple[str, ...]
    notify_owner: bool
    revoke_session: bool

def assess(signal: SessionSignal) -> ShadowDecision:
    if not signal.account_id or not signal.session_id or not signal.device_id:
        raise ValueError('missing identity/session/device identifier')
    if not signal.authenticated:
        return ShadowDecision('deny', ('unauthenticated',), True, True)
    if not signal.device_bound or not signal.verified_device:
        return ShadowDecision('deny', ('device-proof-missing',), True, True)
    reasons = []
    if signal.new_device: reasons.append('new-device')
    if signal.anomalous_behavior: reasons.append('behavior-anomaly')
    if signal.privileged_action and len(signal.active_session_ids - {signal.session_id}) > 0:
        reasons.append('concurrent-privileged-session')
    if reasons:
        return ShadowDecision('step_up', tuple(reasons), True, False)
    return ShadowDecision('allow', (), False, False)
