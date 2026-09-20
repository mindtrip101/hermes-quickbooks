from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Tenant:
    tenant_id: str
    display_name: str
    environment: str
    credentials_ref: str
    allowed_agents: frozenset[str]


def load_tenants(path: Path) -> tuple[str, dict[str, Tenant]]:
    raw = yaml.safe_load(path.read_text()) or {}
    default = str(raw.get("default_tenant") or "company_a")
    tenants: dict[str, Tenant] = {}
    for tenant_id, spec in (raw.get("tenants") or {}).items():
        spec = spec or {}
        tenants[str(tenant_id)] = Tenant(
            tenant_id=str(tenant_id),
            display_name=str(spec.get("display_name") or tenant_id),
            environment=str(spec.get("environment") or "sandbox").lower(),
            credentials_ref=str(spec.get("credentials_ref") or tenant_id),
            allowed_agents=frozenset(str(a) for a in (spec.get("allowed_agents") or [])),
        )
    return default, tenants
