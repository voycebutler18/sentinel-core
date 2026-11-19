"""BAIFI Sentinel: passive, authorized threat-origin enrichment.
No secrets, external scans, VPN bypass, or third-party probing.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
from ipaddress import ip_address
import json
import os
from typing import Any

@dataclass(frozen=True)
class Finding:
    agent: str
    observation: str
    confidence: str
    evidence: dict[str, Any]

def classify_address(value: str) -> Finding:
    ip = ip_address(value)
    scope = "public" if ip.is_global else "non-public"
    return Finding("network_origin", "Observed connection endpoint", "observed",
                   {"ip": str(ip), "scope": scope, "version": ip.version})

def vpn_intelligence(value: str, known_exits: set[str] | None = None) -> Finding:
    ip = str(ip_address(value))
    matched = ip in (known_exits or set())
    return Finding("vpn_proxy", "Known exit-node match" if matched else "VPN status unresolved",
                   "indicator-match" if matched else "unknown",
                   {"observed_ip": ip, "matched": matched,
                    "note": "Exit-node match does not identify the originating person"})

def correlate(event: dict[str, Any], known_exits: set[str] | None = None) -> dict[str, Any]:
    """Only process telemetry from a system the operator is authorized to monitor."""
    if not event.get("authorized_source"):
        raise ValueError("authorized_source must be true")
    source = event["source_ip"]
    observed_at = event.get("observed_at") or datetime.now(timezone.utc).isoformat()
    raw = json.dumps(event, sort_keys=True, separators=(",", ":"), default=str)
    findings = [classify_address(source), vpn_intelligence(source, known_exits)]
    return {
        "schema": "baifi.sentinel.trace.v1",
        "observed_at": observed_at,
        "event_sha256": sha256(raw.encode()).hexdigest(),
        "findings": [asdict(f) for f in findings],
        "attribution": "unresolved",
        "limitations": ["IP identifies observed endpoint, not necessarily actor",
                        "No VPN ingress or physical location inferred"],
    }

def main() -> None:
    """Read a single JSON event on stdin; optionally load a local exit-node file."""
    import sys
    event = json.load(sys.stdin)
    exits_path = os.environ.get("BAIFI_EXIT_NODE_FILE")
    exits: set[str] = set()
    if exits_path:
        with open(exits_path, encoding="utf-8") as handle:
            exits = {line.strip() for line in handle if line.strip() and not line.startswith("#")}
    print(json.dumps(correlate(event, exits), indent=2))

if __name__ == "__main__":
    main()
