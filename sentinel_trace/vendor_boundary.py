"""Tenant-owned boundary policy for third-party application operations.

Only trusted, instrumented company-side telemetry should populate these events.
This is a decision engine, not a network interceptor.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class BoundaryEvent:
    tenant: str
    vendor_id: str
    principal_id: str
    operation: str
    resource_class: str
    destination: str
    grant_active: bool
    trusted_telemetry: bool

@dataclass(frozen=True)
class VendorGrant:
    tenant: str
    vendor_id: str
    operations: frozenset[str]
    resource_classes: frozenset[str]
    destinations: frozenset[str]

@dataclass(frozen=True)
class BoundaryDecision:
    action: str
    reason: str

def evaluate_boundary(event: BoundaryEvent, grant: VendorGrant) -> BoundaryDecision:
    if not all((event.tenant, event.vendor_id, event.principal_id, event.operation,
                event.resource_class, event.destination)):
        raise ValueError('missing boundary event identifiers')
    if not event.trusted_telemetry:
        return BoundaryDecision('DENY', 'untrusted-event-source')
    if not event.grant_active or event.tenant != grant.tenant or event.vendor_id != grant.vendor_id:
        return BoundaryDecision('DENY', 'grant-not-valid-for-tenant-vendor')
    if event.operation not in grant.operations:
        return BoundaryDecision('DENY', 'operation-not-authorized')
    if event.resource_class not in grant.resource_classes:
        return BoundaryDecision('DENY', 'resource-not-authorized')
    if event.destination not in grant.destinations:
        return BoundaryDecision('DENY', 'destination-not-authorized')
    return BoundaryDecision('ALLOW', 'within-vendor-grant')
