"""Sentinel Trusted Identity Seal policy: server-verified evidence only.

The authentication service must verify WebAuthn and device-bound proofs before
setting these booleans. This module never creates or validates a passkey itself.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class IdentityEvidence:
    account_id: str
    session_id: str
    registered_key_id: str
    webauthn_verified: bool
    device_proof_verified: bool
    session_active: bool
    risk_score: int
    sensitive_action: bool = False
    fresh_user_verification: bool = False

@dataclass(frozen=True)
class IdentityDecision:
    action: str
    notify: bool
    reason: str

def decide(e: IdentityEvidence) -> IdentityDecision:
    if not all((e.account_id, e.session_id, e.registered_key_id)):
        raise ValueError("missing identity identifiers")
    if not isinstance(e.risk_score, int) or isinstance(e.risk_score, bool) or not 0 <= e.risk_score <= 100:
        raise ValueError("risk_score must be integer 0..100")
    if not e.session_active or not e.webauthn_verified or not e.device_proof_verified:
        return IdentityDecision("deny", True, "identity-proof-invalid")
    if e.risk_score >= 85:
        return IdentityDecision("revoke", True, "critical-session-risk")
    if e.risk_score >= 60:
        return IdentityDecision("investigate", False, "silent-risk-investigation")
    if e.sensitive_action and not e.fresh_user_verification:
        return IdentityDecision("step_up", False, "fresh-proof-required")
    return IdentityDecision("allow", False, "trusted-session")
