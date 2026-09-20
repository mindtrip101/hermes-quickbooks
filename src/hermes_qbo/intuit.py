from __future__ import annotations

import time
from typing import Any, Callable

import httpx

from .oauth import OAuthError, OAuthManager, TokenSet
from .settings import Settings


class IntuitError(RuntimeError):
    def __init__(self, code: str, status: int | None = None, retryable: bool = False):
        super().__init__(code)
        self.code = code
        self.status = status
        self.retryable = retryable


def _fault_code(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "intuit_error"
    fault = payload.get("Fault") or payload.get("fault") or {}
    errors = fault.get("Error") or fault.get("error") or []
    if errors and isinstance(errors, list) and isinstance(errors[0], dict):
        return str(errors[0].get("code") or errors[0].get("Message") or "intuit_error")
    return "intuit_error"


class IntuitClient:
    def __init__(self, settings: Settings, oauth: OAuthManager, http: httpx.Client | None = None):
        self.settings = settings
        self.oauth = oauth
        self.http = http or httpx.Client(timeout=settings.read_timeout)
        self.last_latency_ms: int | None = None

    def _headers(self, tokens: TokenSet, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {tokens.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if extra:
            headers.update(extra)
        return headers

    def _url(self, tokens: TokenSet, path: str) -> str:
        base = self.settings.api_base(tokens.environment)
        return f"{base}/v3/company/{tokens.realm_id}/{path.lstrip('/')}"

    def request(
        self,
        tenant_id: str,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        write: bool = False,
        requestid: str | None = None,
        retry_write: bool = False,
    ) -> dict[str, Any]:
        if write and retry_write:
            raise IntuitError("write_retry_forbidden")
        params = dict(params or {})
        params.setdefault("minorversion", self.settings.minor_version)
        if requestid:
            params["requestid"] = requestid[:50]
        attempts = 1 if write else self.settings.max_retries
        last_error: IntuitError | None = None
        refreshed = False
        for attempt in range(attempts):
            tokens = self.oauth.ensure_access(tenant_id)
            started = time.monotonic()
            try:
                response = self.http.request(
                    method,
                    self._url(tokens, path),
                    params=params,
                    json=json,
                    headers=self._headers(tokens),
                    timeout=self.settings.write_timeout if write else self.settings.read_timeout,
                )
            except httpx.TimeoutException as exc:
                last_error = IntuitError("timeout", retryable=not write)
                if write:
                    raise last_error from exc
                time.sleep(min(2 ** attempt, 8))
                continue
            except httpx.HTTPError as exc:
                last_error = IntuitError("network", retryable=not write)
                if write:
                    raise last_error from exc
                time.sleep(min(2 ** attempt, 8))
                continue
            self.last_latency_ms = int((time.monotonic() - started) * 1000)
            if response.status_code == 401 and not refreshed:
                tokens = self.oauth.refresh(tenant_id, tokens)
                refreshed = True
                continue
            if response.status_code == 401:
                raise OAuthError("reauthorization_required")
            if response.status_code == 403:
                raise IntuitError("forbidden", 403)
            if response.status_code == 404:
                raise IntuitError("not_found", 404)
            if response.status_code == 409:
                raise IntuitError("conflict", 409)
            if response.status_code == 429:
                if write:
                    raise IntuitError("rate_limited", 429, retryable=False)
                retry_after = float(response.headers.get("Retry-After") or (2 ** attempt))
                time.sleep(min(retry_after, 8))
                last_error = IntuitError("rate_limited", 429, retryable=True)
                continue
            if response.status_code >= 500:
                last_error = IntuitError("intuit_unavailable", response.status_code, retryable=not write)
                if write:
                    raise last_error
                time.sleep(min(2 ** attempt, 8))
                continue
            if response.status_code >= 400:
                try:
                    payload = response.json()
                except Exception:
                    payload = {}
                raise IntuitError(_fault_code(payload), response.status_code)
            if not response.content:
                return {}
            return response.json()
        raise last_error or IntuitError("request_failed")

    def query(self, tenant_id: str, sql: str) -> list[dict[str, Any]]:
        payload = self.request(tenant_id, "GET", "query", params={"query": sql})
        wrapper = payload.get("QueryResponse") or {}
        for key, value in wrapper.items():
            if key in {"startPosition", "maxResults", "totalCount"}:
                continue
            if isinstance(value, list):
                return value
        return []

    def get_entity(self, tenant_id: str, entity: str, entity_id: str) -> dict[str, Any]:
        payload = self.request(tenant_id, "GET", f"{entity.lower()}/{entity_id}")
        for key, value in payload.items():
            if isinstance(value, dict) and key.lower() == entity.lower():
                return value
        return payload

    def report(self, tenant_id: str, name: str, params: dict[str, Any]) -> dict[str, Any]:
        return self.request(tenant_id, "GET", f"reports/{name}", params=params)

    def create(self, tenant_id: str, entity: str, body: dict[str, Any], requestid: str) -> dict[str, Any]:
        return self.request(
            tenant_id,
            "POST",
            entity.lower(),
            json=body,
            write=True,
            requestid=requestid,
        )
