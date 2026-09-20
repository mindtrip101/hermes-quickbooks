from __future__ import annotations

import json
import os
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from .redaction import redact
from .settings import Settings


class OAuthError(RuntimeError):
    def __init__(self, code: str, detail: str | None = None):
        super().__init__(code)
        self.code = code
        self.detail = detail


def _now() -> float:
    return time.time()


def _iso(ts: float | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str
    access_expires_at: float
    refresh_expires_at: float | None
    realm_id: str
    environment: str
    updated_at: float
    company_name: str | None = None

    def access_valid(self, skew: int = 120) -> bool:
        return bool(self.access_token) and self.access_expires_at > _now() + skew


class TokenStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, tenant_id: str) -> Path:
        return self.root / tenant_id / "tokens.json"

    def load(self, tenant_id: str) -> TokenSet | None:
        path = self._path(tenant_id)
        if not path.exists():
            return None
        raw = json.loads(path.read_text())
        try:
            return TokenSet(
                access_token=str(raw.get("access_token") or ""),
                refresh_token=str(raw.get("refresh_token") or ""),
                access_expires_at=float(raw.get("access_expires_at") or 0),
                refresh_expires_at=(float(raw["refresh_expires_at"]) if raw.get("refresh_expires_at") else None),
                realm_id=str(raw.get("realm_id") or ""),
                environment=str(raw.get("environment") or "sandbox"),
                updated_at=float(raw.get("updated_at") or 0),
                company_name=raw.get("company_name"),
            )
        except (TypeError, ValueError):
            return None

    def save(self, tenant_id: str, tokens: TokenSet) -> None:
        path = self._path(tenant_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "access_expires_at": tokens.access_expires_at,
            "refresh_expires_at": tokens.refresh_expires_at,
            "realm_id": tokens.realm_id,
            "environment": tokens.environment,
            "updated_at": tokens.updated_at,
            "company_name": tokens.company_name,
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload))
        os.chmod(tmp, 0o600)
        tmp.replace(path)
        os.chmod(path, 0o600)

    def realm_owner(self, realm_id: str, *, exclude: str | None = None) -> str | None:
        if not realm_id or not self.root.exists():
            return None
        for path in self.root.glob("*/tokens.json"):
            tenant_id = path.parent.name
            if exclude and tenant_id == exclude:
                continue
            tokens = self.load(tenant_id)
            if tokens and tokens.realm_id == realm_id:
                return tenant_id
        return None

    def public_status(self, tenant_id: str) -> dict[str, Any]:
        tokens = self.load(tenant_id)
        if not tokens:
            return {"oauth": "missing", "realm_id_present": False, "last_token_refresh": None}
        return {
            "oauth": "valid" if tokens.access_valid() else "expired",
            "realm_id_present": bool(tokens.realm_id),
            "last_token_refresh": _iso(tokens.updated_at),
            "environment": tokens.environment,
            "company_name": tokens.company_name,
        }


class OAuthManager:
    def __init__(self, settings: Settings, store: TokenStore, http: httpx.Client | None = None):
        self.settings = settings
        self.store = store
        self.http = http or httpx.Client(timeout=20.0)
        self._states: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _secret(self, name: str) -> str:
        path = self.settings.secrets_dir / name
        if not path.exists():
            return ""
        return path.read_text().strip()

    def client_credentials(self, environment: str) -> tuple[str, str]:
        env = environment if environment in {"sandbox", "production"} else "sandbox"
        client_id = self._secret(f"{env}_client_id") or self._secret("client_id")
        client_secret = self._secret(f"{env}_client_secret") or self._secret("client_secret")
        return client_id, client_secret

    def credentials_configured(self, environment: str) -> bool:
        client_id, client_secret = self.client_credentials(environment)
        return bool(client_id and client_secret)

    def authorize_url(self, tenant_id: str, environment: str) -> dict[str, Any]:
        client_id, client_secret = self.client_credentials(environment)
        if not client_id or not client_secret:
            raise OAuthError(
                "credentials_missing",
                "Place Intuit Production Client ID and Client Secret in the QuickBooks secrets directory, then retry."
                if environment == "production"
                else "Place Intuit Development Client ID and Client Secret in the QuickBooks secrets directory, then retry.",
            )
        state = secrets.token_urlsafe(24)
        with self._lock:
            self._states[state] = {
                "tenant_id": tenant_id,
                "environment": environment,
                "exp": _now() + 600,
            }
        params = {
            "client_id": client_id,
            "scope": "com.intuit.quickbooks.accounting",
            "redirect_uri": self.settings.redirect_uri,
            "response_type": "code",
            "state": state,
        }
        return {
            "authorize_url": f"{self.settings.authorize_url}?{urlencode(params)}",
            "redirect_uri": self.settings.redirect_uri,
            "environment": environment,
            "tenant_id": tenant_id,
            "scope": "com.intuit.quickbooks.accounting",
            "expires_in_seconds": 600,
        }

    def _basic(self, environment: str) -> tuple[str, str]:
        client_id, client_secret = self.client_credentials(environment)
        if not client_id or not client_secret:
            raise OAuthError("credentials_missing")
        return client_id, client_secret

    def _parse_token_response(self, payload: dict[str, Any], environment: str, realm_id: str, existing: TokenSet | None = None) -> TokenSet:
        access = str(payload.get("access_token") or "")
        refresh = str(payload.get("refresh_token") or (existing.refresh_token if existing else ""))
        if not access or not refresh:
            raise OAuthError("token_response_incomplete")
        expires_in = int(payload.get("expires_in") or 3600)
        refresh_expires = payload.get("x_refresh_token_expires_in")
        now = _now()
        return TokenSet(
            access_token=access,
            refresh_token=refresh,
            access_expires_at=now + expires_in,
            refresh_expires_at=(now + int(refresh_expires)) if refresh_expires else (existing.refresh_expires_at if existing else None),
            realm_id=realm_id or (existing.realm_id if existing else ""),
            environment=environment,
            updated_at=now,
            company_name=existing.company_name if existing else None,
        )

    def exchange_code(self, *, code: str, state: str, realm_id: str) -> TokenSet:
        with self._lock:
            meta = self._states.pop(state, None)
        if not meta or meta["exp"] < _now():
            raise OAuthError("invalid_state")
        owner = self.store.realm_owner(realm_id, exclude=meta["tenant_id"])
        if owner:
            raise OAuthError("realm_in_use", f"That QuickBooks company is already connected as {owner}.")
        client_id, client_secret = self._basic(meta["environment"])
        response = self.http.post(
            self.settings.token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.settings.redirect_uri,
            },
            auth=(client_id, client_secret),
            headers={"Accept": "application/json"},
        )
        if response.status_code >= 400:
            raise OAuthError("token_exchange_failed")
        tokens = self._parse_token_response(response.json(), meta["environment"], realm_id)
        self.store.save(meta["tenant_id"], tokens)
        return tokens

    def import_tokens(
        self,
        tenant_id: str,
        *,
        realm_id: str,
        access_token: str,
        refresh_token: str,
        environment: str,
        expires_in: int = 3600,
        refresh_expires_in: int | None = None,
        company_name: str | None = None,
    ) -> TokenSet:
        environment = environment if environment in {"sandbox", "production"} else "sandbox"
        realm_id = str(realm_id or "").strip()
        access_token = str(access_token or "").strip()
        refresh_token = str(refresh_token or "").strip()
        if not realm_id or not access_token or not refresh_token:
            raise OAuthError("token_response_incomplete")
        owner = self.store.realm_owner(realm_id, exclude=tenant_id)
        if owner:
            raise OAuthError("realm_in_use", f"That QuickBooks company is already connected as {owner}.")
        now = _now()
        tokens = TokenSet(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_at=now + max(60, int(expires_in or 3600)),
            refresh_expires_at=(now + int(refresh_expires_in)) if refresh_expires_in else None,
            realm_id=realm_id,
            environment=environment,
            updated_at=now,
            company_name=company_name,
        )
        self.store.save(tenant_id, tokens)
        return tokens

    def refresh(self, tenant_id: str, tokens: TokenSet) -> TokenSet:
        client_id, client_secret = self._basic(tokens.environment)
        response = self.http.post(
            self.settings.token_url,
            data={"grant_type": "refresh_token", "refresh_token": tokens.refresh_token},
            auth=(client_id, client_secret),
            headers={"Accept": "application/json"},
        )
        if response.status_code >= 400:
            raise OAuthError("reauthorization_required", "Refresh token was rejected. Open the authorize URL again.")
        refreshed = self._parse_token_response(response.json(), tokens.environment, tokens.realm_id, existing=tokens)
        self.store.save(tenant_id, refreshed)
        return refreshed

    def ensure_access(self, tenant_id: str) -> TokenSet:
        tokens = self.store.load(tenant_id)
        if not tokens:
            raise OAuthError("reauthorization_required", "No QuickBooks tokens stored for this company.")
        if tokens.access_valid():
            return tokens
        if not tokens.refresh_token:
            raise OAuthError("reauthorization_required")
        return self.refresh(tenant_id, tokens)

    def note_company_name(self, tenant_id: str, name: str) -> None:
        tokens = self.store.load(tenant_id)
        if not tokens:
            return
        tokens.company_name = name
        self.store.save(tenant_id, tokens)

    def debug_safe(self, payload: dict[str, Any]) -> dict[str, Any]:
        return redact(payload)
