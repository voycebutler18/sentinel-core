"""Incident-review decisions with scoped approvals; no live enforcement integration."""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import hmac
import secrets

@dataclass(frozen=True)
class Incident:
    incident_id: str
    tenant: str
    principal: str
    operation: str
    resource: str
    destination: str
    reason: str

@dataclass(frozen=True)
class Approval:
    incident_id: str
    tenant: str
    principal: str
    operation: str
    resource: str
    destination: str
    expires_at: datetime
    approved_by: str
    token_hash: str

def create_approval(incident: Incident, reviewer: str, reviewer_authorized: bool,
                    reviewer_step_up_verified: bool, now: datetime,
                    lifetime_seconds: int = 120) -> tuple[Approval, str]:
    if not incident.incident_id or not incident.tenant or not reviewer:
        raise ValueError('missing identifiers')
    if not reviewer_authorized or not reviewer_step_up_verified:
        raise PermissionError('reviewer must be authorized and strongly verified')
    if not 0 < lifetime_seconds <= 300:
        raise ValueError('approval lifetime out of range')
    if now.tzinfo is None:
        raise ValueError('timezone-aware timestamp required')
    token = secrets.token_urlsafe(32)
    approval = Approval(incident.incident_id, incident.tenant, incident.principal,
                        incident.operation, incident.resource, incident.destination,
                        now + timedelta(seconds=lifetime_seconds), reviewer,
                        sha256(token.encode()).hexdigest())
    return approval, token

def validate_approval(approval: Approval, incident: Incident, token: str, now: datetime) -> bool:
    if now.tzinfo is None:
        raise ValueError('timezone-aware timestamp required')
    return (now < approval.expires_at and
            (approval.incident_id, approval.tenant, approval.principal, approval.operation,
             approval.resource, approval.destination) ==
            (incident.incident_id, incident.tenant, incident.principal, incident.operation,
             incident.resource, incident.destination) and
            hmac.compare_digest(approval.token_hash, sha256(token.encode()).hexdigest()))
