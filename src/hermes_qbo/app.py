from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Header, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .catalog import TOOL_NAMES, TOOLS
from .oauth import OAuthError
from .service import Connector, ConnectorError
from .settings import load_settings

SETTINGS = load_settings()
CONNECTOR = Connector(SETTINGS)
app = FastAPI(title="hermes-qbo", version="0.1.0")


def _adapter(header: str | None) -> None:
    CONNECTOR.check_adapter(header)


def _operator(header: str | None) -> None:
    CONNECTOR.check_operator(header)


@app.get("/health")
def health() -> dict[str, Any]:
    data = CONNECTOR.health()
    return {"status": "ok" if data.get("status") in {"HEALTHY", "DEGRADED"} else "error", **{k: v for k, v in data.items() if k != "status"}, "connector": data.get("status")}


@app.get("/v1/health")
def v1_health(x_qbo_adapter_token: str | None = Header(default=None), x_qbo_agent_id: str | None = Header(default=None)) -> dict[str, Any]:
    _adapter(x_qbo_adapter_token)
    return CONNECTOR.dispatch(agent_id=x_qbo_agent_id or "hermes-operator", tool="qbo_health", arguments={})


@app.post("/v1/tools/{name}")
def call_tool(
    name: str,
    request: dict[str, Any],
    x_qbo_adapter_token: str | None = Header(default=None),
    x_qbo_agent_id: str | None = Header(default=None),
    x_request_id: str | None = Header(default=None),
) -> dict[str, Any]:
    _adapter(x_qbo_adapter_token)
    agent = x_qbo_agent_id or ""
    if not agent:
        raise ConnectorError("unknown_agent", 403)
    arguments = request.get("arguments") if isinstance(request.get("arguments"), dict) else request
    # Model-supplied agent/tenant spoofing: tenant is still ACL-checked; agent comes only from header.
    arguments.pop("agent_id", None)
    arguments.pop("approve", None)
    arguments.pop("write", None)
    return CONNECTOR.dispatch(agent_id=agent, tool=name, arguments=arguments, request_id=x_request_id)


@app.get("/v1/tool-schemas")
def schemas(x_qbo_adapter_token: str | None = Header(default=None)) -> dict[str, Any]:
    _adapter(x_qbo_adapter_token)
    return {"tools": TOOL_NAMES, "schemas": {name: TOOLS[name]["schema"] for name in TOOL_NAMES}}


@app.get("/v1/oauth/start")
def oauth_start(tenant_id: str | None = Query(default=None), x_qbo_operator_token: str | None = Header(default=None)) -> dict[str, Any]:
    _operator(x_qbo_operator_token)
    payload = CONNECTOR.authorize_url(tenant_id)
    payload["instructions"] = [
        "Use Development keys for sandbox sample companies and Production keys for live QuickBooks companies.",
        "Register the redirect URI exactly as QBO_REDIRECT_URI. Development may use http://localhost:<port>/oauth/callback (hostname localhost, not 127.0.0.1). Production requires HTTPS.",
        "Install Client ID and Client Secret as 0600 files named sandbox_client_id/sandbox_client_secret or production_client_id/production_client_secret in QBO_SECRETS_DIR.",
        "Run qbo auth-url --tenant <id>, open authorize_url in a browser, and pick the company for that tenant. Authorize once per company.",
        "Never send an Intuit password to Hermes or this connector. Production writes stay held unless QBO_ALLOW_PRODUCTION_WRITES is true.",
    ]
    return payload


@app.post("/v1/oauth/import")
def oauth_import(request: dict[str, Any], x_qbo_operator_token: str | None = Header(default=None)) -> dict[str, Any]:
    _operator(x_qbo_operator_token)
    tenant_id = str(request.get("tenant_id") or "") or None
    return CONNECTOR.import_tokens(tenant_id, request)


@app.get("/oauth/ready")
def oauth_ready() -> HTMLResponse:
    return HTMLResponse(
        "<html><body><p>QuickBooks connector tunnel is working.</p>"
        "<p>Leave this SSH tunnel open, then use <code>qbo auth-url</code> and the Intuit authorize page.</p>"
        "<p>Production OAuth uses redirect URI <code>https://developer.intuit.com/v2/OAuth2Playground/RedirectUrl</code>.</p>"
        "</body></html>"
    )


@app.get("/oauth/callback")
def oauth_callback(code: str | None = None, state: str | None = None, realmId: str | None = None, error: str | None = None) -> HTMLResponse:
    if error or not code or not state or not realmId:
        return HTMLResponse("<html><body>Authorization was not completed. You can close this window.</body></html>", status_code=400)
    try:
        CONNECTOR.oauth.exchange_code(code=code, state=state, realm_id=realmId)
    except OAuthError:
        return HTMLResponse("<html><body>Authorization failed. Invalid or expired state. Restart qbo auth-url.</body></html>", status_code=400)
    return HTMLResponse("<html><body>QuickBooks company connected. You can close this window and return to Hermes.</body></html>")


@app.get("/v1/approvals")
def list_approvals(
    status: str | None = Query(default=None),
    x_qbo_adapter_token: str | None = Header(default=None),
    x_qbo_agent_id: str | None = Header(default=None),
) -> dict[str, Any]:
    _adapter(x_qbo_adapter_token)
    return CONNECTOR.dispatch(agent_id=x_qbo_agent_id or "hermes-operator", tool="qbo_list_approvals", arguments={"status": status})


@app.post("/v1/approvals/{action_id}/decision")
def decide(
    action_id: str,
    request: dict[str, Any],
    x_qbo_operator_token: str | None = Header(default=None),
    x_qbo_adapter_token: str | None = Header(default=None),
) -> dict[str, Any]:
    if x_qbo_adapter_token and not x_qbo_operator_token:
        raise ConnectorError("operator_required", 403)
    _operator(x_qbo_operator_token)
    user = str(request.get("user") or "")
    decision = str(request.get("decision") or "")
    if decision in {"approve", "approved"}:
        decision = "approved"
    elif decision in {"reject", "rejected"}:
        decision = "rejected"
    return CONNECTOR.operator_decide(action_id, decision=decision, user=user)


@app.post("/v1/approvals/{action_id}/execute")
def execute(
    action_id: str,
    request: dict[str, Any],
    x_qbo_operator_token: str | None = Header(default=None),
    x_qbo_adapter_token: str | None = Header(default=None),
) -> dict[str, Any]:
    if x_qbo_adapter_token and not x_qbo_operator_token:
        raise ConnectorError("operator_required", 403)
    _operator(x_qbo_operator_token)
    return CONNECTOR.operator_execute(action_id, user=str(request.get("user") or ""))


@app.exception_handler(ConnectorError)
async def connector_error(_request: Request, exc: ConnectorError) -> JSONResponse:
    return JSONResponse({"ok": False, "errors": [exc.code]}, status_code=exc.http_status)


@app.exception_handler(OAuthError)
async def oauth_error(_request: Request, exc: OAuthError) -> JSONResponse:
    return JSONResponse({"ok": False, "errors": [exc.code], "message": exc.detail}, status_code=401)
