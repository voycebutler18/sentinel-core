"""BAIFI portal pre-authentication controls.

Policy only: integrate with server-side rate limiter, WebAuthn verifier,
security event bus, and isolated decoy endpoints before deployment.
Never log or return submitted customer codes.
"""
from dataclasses import dataclass
import hashlib
import hmac

@dataclass(frozen=True)
class LoginAttempt:
    company_id: str
    submitted_code: str
    expected_code_digest: str
    verified_device: bool
    verified_passkey: bool
    active_company: bool
    attempts_last_5min: int
    decoy_endpoint_touched: bool = False

@dataclass(frozen=True)
class LoginDecision:
    action: str
    reason: str
    notify_security: bool

def evaluate_login(a: LoginAttempt) -> LoginDecision:
    if not a.company_id or not a.expected_code_digest:
        return LoginDecision('DENY', 'invalid-company-context', True)
    if a.decoy_endpoint_touched:
        return LoginDecision('DENY', 'decoy-interaction', True)
    if a.attempts_last_5min < 0 or a.attempts_last_5min >= 5:
        return LoginDecision('DENY', 'rate-limit', a.attempts_last_5min >= 5)
    if not a.active_company:
        return LoginDecision('DENY', 'inactive-company', True)
    # Hash comparison is a policy prototype; real production codes require
    # high-entropy random values and a server-side pepper/HMAC or keyed lookup.
    digest = hashlib.sha256(a.submitted_code.encode()).hexdigest()
    if not hmac.compare_digest(digest, a.expected_code_digest):
        return LoginDecision('DENY', 'invalid-credential', False)
    if not a.verified_device or not a.verified_passkey:
        return LoginDecision('STEP_UP', 'device-or-passkey-verification-required', True)
    return LoginDecision('ALLOW', 'verified-company-session', False)
