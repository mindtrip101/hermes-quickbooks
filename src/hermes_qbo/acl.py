from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .api_surface import ACL_DOMAINS

DOMAINS = set(ACL_DOMAINS)


@dataclass(frozen=True)
class AgentAcl:
    agent_id: str
    read: bool | frozenset[str]
    draft: bool
    write: str | bool
    tenants: frozenset[str]

    def can_read(self, domain: str) -> bool:
        if self.read is True:
            return True
        if self.read is False:
            return False
        return domain in self.read or domain == "system"

    def can_draft(self) -> bool:
        return bool(self.draft)

    def write_mode(self) -> str:
        if self.write is True:
            return "allow"
        if self.write is False or self.write in {None, ""}:
            return "deny"
        return str(self.write)

    def can_access_tenant(self, tenant_id: str) -> bool:
        return tenant_id in self.tenants


def _parse_read(value: Any) -> bool | frozenset[str]:
    if value is True:
        return True
    if value is False or value is None:
        return False
    if isinstance(value, list):
        domains = frozenset(str(item) for item in value)
        unknown = domains - DOMAINS
        if unknown:
            raise ValueError(f"unknown_acl_domains:{sorted(unknown)}")
        return domains
    raise ValueError("invalid_read_acl")


def load_permissions(path: Path) -> dict[str, AgentAcl]:
    raw = yaml.safe_load(path.read_text()) or {}
    agents = raw.get("agents") or {}
    out: dict[str, AgentAcl] = {}
    for agent_id, spec in agents.items():
        spec = spec or {}
        out[str(agent_id)] = AgentAcl(
            agent_id=str(agent_id),
            read=_parse_read(spec.get("read", False)),
            draft=bool(spec.get("draft", False)),
            write=spec.get("write", False),
            tenants=frozenset(str(t) for t in (spec.get("tenants") or [])),
        )
    return out
