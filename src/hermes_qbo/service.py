from __future__ import annotations

import hmac
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .acl import AgentAcl, load_permissions
from .approvals import ApprovalError, ApprovalStore
from .audit import AuditLog
from .catalog import TOOLS
from .envelope import wrap
from .intuit import IntuitClient, IntuitError
from .oauth import OAuthError, OAuthManager, TokenStore
from .periods import iso, resolve_period
from .query import SAFE_ID, QueryError, compile_query
from .redaction import redact
from .settings import Settings
from .tenants import Tenant, load_tenants


class ConnectorError(RuntimeError):
    def __init__(self, code: str, http_status: int = 400):
        super().__init__(code)
        self.code = code
        self.http_status = http_status


def _read_secret(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text().strip()


class Connector:
    def __init__(
        self,
        settings: Settings,
        *,
        oauth: OAuthManager | None = None,
        intuit: IntuitClient | None = None,
        today: date | None = None,
    ):
        self.settings = settings
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.permissions = load_permissions(settings.config_dir / "permissions.yaml")
        self.default_tenant, self.tenants = load_tenants(settings.config_dir / "tenants.yaml")
        self.tokens = TokenStore(settings.tokens_dir)
        self.oauth = oauth or OAuthManager(settings, self.tokens)
        self.intuit = intuit or IntuitClient(settings, self.oauth)
        self.approvals = ApprovalStore(settings.db_path)
        self.audit = AuditLog(settings.audit_path)
        self.today = today
        self.adapter_token = _read_secret(settings.secrets_dir / "adapter_token")
        self.operator_token = _read_secret(settings.secrets_dir / "operator_token")

    def _today(self) -> date:
        return self.today or date.today()

    def check_adapter(self, token: str | None) -> None:
        if not self.adapter_token or not token or not hmac.compare_digest(self.adapter_token, token):
            raise ConnectorError("adapter_unauthorized", 401)

    def check_operator(self, token: str | None) -> None:
        if not self.operator_token or not token or not hmac.compare_digest(self.operator_token, token):
            raise ConnectorError("operator_unauthorized", 401)

    def agent(self, agent_id: str) -> AgentAcl:
        acl = self.permissions.get(agent_id)
        if not acl:
            raise ConnectorError("unknown_agent", 403)
        return acl

    def resolve_tenant(self, agent: AgentAcl, tenant_id: str | None) -> Tenant:
        tenant_id = (tenant_id or self.default_tenant).strip()
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            raise ConnectorError("unknown_tenant", 404)
        if not agent.can_access_tenant(tenant.tenant_id) or agent.agent_id not in tenant.allowed_agents:
            raise ConnectorError("tenant_denied", 403)
        return tenant

    def authorize_url(self, tenant_id: str | None = None) -> dict[str, Any]:
        tenant = self.tenants.get(tenant_id or self.default_tenant)
        if not tenant:
            raise ConnectorError("unknown_tenant", 404)
        environment = tenant.environment if tenant.environment in {"sandbox", "production"} else "sandbox"
        return self.oauth.authorize_url(tenant.tenant_id, environment)

    def health(self, tenant_id: str | None = None) -> dict[str, Any]:
        tenant = self.tenants.get(tenant_id or self.default_tenant)
        tenant_id = tenant.tenant_id if tenant else (tenant_id or self.default_tenant)
        tokens = self.tokens.public_status(tenant_id)
        api_ok = "unknown"
        company = tokens.get("company_name")
        oauth_state = tokens.get("oauth")
        try:
            if oauth_state == "valid":
                info = self.intuit.get_entity(tenant_id, "CompanyInfo", self.tokens.load(tenant_id).realm_id)  # type: ignore[union-attr]
                company = (info.get("CompanyName") or company)
                if company:
                    self.oauth.note_company_name(tenant_id, str(company))
                api_ok = "ok"
            elif oauth_state == "expired":
                self.oauth.ensure_access(tenant_id)
                api_ok = "ok"
                oauth_state = "valid"
            else:
                api_ok = "not_connected"
        except OAuthError as exc:
            oauth_state = exc.code
            api_ok = "oauth_error"
        except Exception:
            api_ok = "error"
        configured = self.oauth.credentials_configured("production") or self.oauth.credentials_configured("sandbox")
        tenants_public = {}
        for tid, spec in self.tenants.items():
            status = self.tokens.public_status(tid)
            tenants_public[tid] = {
                "display_name": spec.display_name,
                "configured_environment": spec.environment,
                "oauth": status.get("oauth"),
                "company": status.get("company_name"),
                "token_environment": status.get("environment"),
            }
        status = "HEALTHY" if configured and oauth_state == "valid" and api_ok == "ok" else "DEGRADED"
        return {
            "status": status,
            "service": "hermes-qbo",
            "environment": self.settings.environment,
            "company": company,
            "oauth": oauth_state if configured else "not_configured",
            "last_token_refresh": tokens.get("last_token_refresh"),
            "api_connectivity": api_ok,
            "permissions": "loaded" if self.permissions else "missing",
            "pending_approvals": self.approvals.pending_count(),
            "last_successful_request": self.audit.last_success,
            "redirect_uri": self.settings.redirect_uri,
            "allow_production_writes": self.settings.allow_production_writes,
            "tenants": tenants_public,
        }

    def dispatch(self, *, agent_id: str, tool: str, arguments: dict[str, Any] | None, request_id: str | None = None) -> dict[str, Any]:
        started = time.monotonic()
        arguments = dict(arguments or {})
        meta = TOOLS.get(tool)
        tenant_id = None
        risk = "unknown"
        error = None
        success = False
        if not meta:
            self.audit.write({"agent": agent_id, "tool": tool, "success": False, "error": "unknown_tool", "classification": "unknown", "parameters": redact(arguments)})
            return wrap(tool=tool, tenant="", environment=self.settings.environment, data={}, incomplete=True, errors=["unknown_tool"])
        try:
            agent = self.agent(agent_id)
            tenant = self.resolve_tenant(agent, arguments.pop("tenant_id", None))
            tenant_id = tenant.tenant_id
            risk = meta["risk"]
            domain = meta["domain"]
            if risk == "read" and not agent.can_read(domain):
                raise ConnectorError("read_denied", 403)
            if risk == "draft" and not agent.can_draft():
                raise ConnectorError("draft_denied", 403)
            if risk == "write" and agent.write_mode() == "deny":
                raise ConnectorError("write_denied", 403)
            if tool == "qbo_health":
                result = wrap(tool=tool, tenant=tenant.tenant_id, environment=self.settings.environment, data=self.health(tenant.tenant_id), value_kind="source")
            else:
                result = self._run(agent, tenant, tool, meta, arguments)
            success = bool(result.get("ok", True))
            return result
        except OAuthError as exc:
            error = exc.code
            return wrap(
                tool=tool,
                tenant=tenant_id or "",
                environment=self.settings.environment,
                data={"reauthorization_required": True, "message": exc.detail or "Authorize QuickBooks in a browser. Do not send your Intuit password to Hermes."},
                incomplete=True,
                errors=[exc.code],
            )
        except (IntuitError, QueryError, ApprovalError, ConnectorError, ValueError) as exc:
            code = getattr(exc, "code", None) or type(exc).__name__
            error = str(code)
            return wrap(
                tool=tool,
                tenant=tenant_id or "",
                environment=self.settings.environment,
                data={"denied": True},
                incomplete=True,
                errors=[error],
            )
        finally:
            realm = None
            if tenant_id:
                stored = self.tokens.load(tenant_id)
                realm = stored.realm_id if stored else None
            self.audit.write(
                {
                    "agent": agent_id,
                    "request_id": request_id,
                    "tool": tool,
                    "tenant": tenant_id,
                    "realm": realm,
                    "operation": tool,
                    "classification": risk,
                    "parameters": redact(arguments),
                    "success": success,
                    "latency_ms": int((time.monotonic() - started) * 1000),
                    "error": error,
                    "qbo_ids": None,
                }
            )

    def _run(self, agent: AgentAcl, tenant: Tenant, tool: str, meta: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
        if tool == "qbo_list_approvals":
            items = self.approvals.list(status=args.get("status"), tenant=tenant.tenant_id)
            return wrap(tool=tool, tenant=tenant.tenant_id, environment=self.settings.environment, data={"approvals": items}, value_kind="source")
        if meta["risk"] == "draft" or meta.get("kind") == "draft":
            return self._draft(agent, tenant, tool, args)
        kind = meta.get("kind")
        extra: dict[str, Any] = {}
        if kind == "entity_search":
            data = self._search(tenant, str(meta["entity"]), args, str(meta["search_field"]))
        elif kind == "entity_get":
            data = self._get(tenant, str(meta["entity"]), args.get(str(meta["id_arg"])))
        elif kind == "aging_report":
            data = self._aging(tenant, args, str(meta["report"]))
        elif kind == "report":
            if meta.get("report_period", True):
                data = self._report(tenant, args, str(meta["report"]), method=bool(meta.get("report_method")))
                start, end, _ = resolve_period(args, self._today())
                extra["date_range"] = {"start": iso(start), "end": iso(end)}
                extra["report_basis"] = str(args.get("accounting_method") or "Accrual")
            else:
                payload = self.intuit.report(tenant.tenant_id, str(meta["report"]), {})
                data = {"report": meta["report"], "header": payload.get("Header"), "rows": payload.get("Rows"), "columns": payload.get("Columns")}
        elif kind == "preferences":
            data = self._preferences(tenant, args)
        else:
            handler = {
                "qbo_get_company_info": self._company,
                "qbo_search_customers": lambda t, a: self._search(t, "Customer", a, "DisplayName"),
                "qbo_get_customer": lambda t, a: self._get(t, "Customer", a.get("customer_id")),
                "qbo_get_customer_balance": self._customer_balance,
                "qbo_get_customer_invoices": self._customer_invoices,
                "qbo_search_invoices": lambda t, a: self._search(t, "Invoice", a, "DocNumber"),
                "qbo_get_invoice": lambda t, a: self._get(t, "Invoice", a.get("invoice_id")),
                "qbo_get_open_invoices": lambda t, a: self._open_txns(t, "Invoice", a),
                "qbo_get_overdue_invoices": lambda t, a: self._overdue(t, "Invoice", a),
                "qbo_search_payments": lambda t, a: self._list_entity(t, "Payment", a),
                "qbo_get_payment": lambda t, a: self._get(t, "Payment", a.get("payment_id")),
                "qbo_search_vendors": lambda t, a: self._search(t, "Vendor", a, "DisplayName"),
                "qbo_get_vendor": lambda t, a: self._get(t, "Vendor", a.get("vendor_id")),
                "qbo_search_bills": lambda t, a: self._search(t, "Bill", a, "DocNumber"),
                "qbo_get_bill": lambda t, a: self._get(t, "Bill", a.get("bill_id")),
                "qbo_get_unpaid_bills": lambda t, a: self._open_txns(t, "Bill", a),
                "qbo_get_upcoming_bills": self._upcoming_bills,
                "qbo_search_expenses": self._search_purchases,
                "qbo_get_expense": lambda t, a: self._get(t, "Purchase", a.get("purchase_id")),
                "qbo_summarize_expenses": self._summarize_expenses,
                "qbo_get_accounts": lambda t, a: self._list_entity(t, "Account", a),
                "qbo_get_account": lambda t, a: self._get(t, "Account", a.get("account_id")),
                "qbo_get_account_balances": self._account_balances,
                "qbo_profit_and_loss": lambda t, a: self._report(t, a, "ProfitAndLoss"),
                "qbo_balance_sheet": lambda t, a: self._report(t, a, "BalanceSheet"),
                "qbo_cash_flow": lambda t, a: self._report(t, a, "CashFlow", method=False),
                "qbo_accounts_receivable_aging": lambda t, a: self._aging(t, a, "AgedReceivables"),
                "qbo_accounts_payable_aging": lambda t, a: self._aging(t, a, "AgedPayables"),
                "qbo_sales_report": lambda t, a: self._report(t, a, "SalesByCustomer", method=False),
                "qbo_expense_report": self._expense_report,
            }[tool]
            data = handler(tenant, args)
        value_kind = "calculated" if tool in {"qbo_summarize_expenses", "qbo_get_customer_balance", "qbo_get_account_balances"} else "mixed" if tool == "qbo_expense_report" else "source"
        if tool in {"qbo_profit_and_loss", "qbo_balance_sheet", "qbo_cash_flow", "qbo_sales_report", "qbo_expense_report"}:
            start, end, _ = resolve_period(args, self._today())
            extra["date_range"] = {"start": iso(start), "end": iso(end)}
            extra["report_basis"] = str(args.get("accounting_method") or "Accrual")
        return wrap(
            tool=tool,
            tenant=tenant.tenant_id,
            environment=self.settings.environment,
            data=data,
            value_kind=value_kind,
            **extra,
        )

    def _require_id(self, value: Any) -> str:
        text = str(value or "")
        if not SAFE_ID.match(text):
            raise ConnectorError("invalid_id")
        return text

    def _search_text(self, args: dict[str, Any]) -> str | None:
        query = str(args.get("query") or "").strip()
        if not query:
            return None
        if len(query) > 80 or any(ch in query for ch in "'\\\n;%"):
            raise ConnectorError("invalid_query")
        return query

    def _max(self, args: dict[str, Any]) -> int:
        return max(1, min(int(args.get("maxresults") or 50), 100))

    def _company(self, tenant: Tenant, args: dict[str, Any]) -> dict[str, Any]:
        tokens = self.oauth.ensure_access(tenant.tenant_id)
        info = self.intuit.get_entity(tenant.tenant_id, "CompanyInfo", tokens.realm_id)
        if info.get("CompanyName"):
            self.oauth.note_company_name(tenant.tenant_id, str(info["CompanyName"]))
        return info

    def _get(self, tenant: Tenant, entity: str, entity_id: Any) -> dict[str, Any]:
        return self.intuit.get_entity(tenant.tenant_id, entity, self._require_id(entity_id))

    def _search(self, tenant: Tenant, entity: str, args: dict[str, Any], field: str) -> dict[str, Any]:
        query = self._search_text(args)
        filters = [(field, "LIKE", f"%{query}%")] if query else []
        sql = compile_query(entity, filters=filters, maxresults=self._max(args))
        return {"entities": self.intuit.query(tenant.tenant_id, sql), "qbo_query": sql}

    def _list_entity(self, tenant: Tenant, entity: str, args: dict[str, Any]) -> dict[str, Any]:
        sql = compile_query(entity, maxresults=self._max(args))
        return {"entities": self.intuit.query(tenant.tenant_id, sql), "qbo_query": sql}

    def _customer_balance(self, tenant: Tenant, args: dict[str, Any]) -> dict[str, Any]:
        customer = self._get(tenant, "Customer", args.get("customer_id"))
        return {
            "customer_id": customer.get("Id"),
            "display_name": customer.get("DisplayName"),
            "balance": customer.get("Balance"),
            "value_kind": "source",
            "source_field": "Customer.Balance",
        }

    def _customer_invoices(self, tenant: Tenant, args: dict[str, Any]) -> dict[str, Any]:
        customer_id = self._require_id(args.get("customer_id"))
        sql = compile_query("Invoice", filters=[("CustomerRef", "=", customer_id)], maxresults=self._max(args))
        return {"entities": self.intuit.query(tenant.tenant_id, sql), "qbo_query": sql}

    def _open_txns(self, tenant: Tenant, entity: str, args: dict[str, Any]) -> dict[str, Any]:
        sql = compile_query(entity, filters=[("Balance", ">", "0")], maxresults=self._max(args))
        return {"entities": self.intuit.query(tenant.tenant_id, sql), "qbo_query": sql}

    def _overdue(self, tenant: Tenant, entity: str, args: dict[str, Any]) -> dict[str, Any]:
        sql = compile_query(
            entity,
            filters=[("Balance", ">", "0"), ("DueDate", "<", iso(self._today()))],
            maxresults=self._max(args),
        )
        rows = self.intuit.query(tenant.tenant_id, sql)
        annotated = []
        for row in rows:
            due = str(row.get("DueDate") or "")[:10]
            days = None
            try:
                days = (self._today() - date.fromisoformat(due)).days
            except ValueError:
                days = None
            item = dict(row)
            item["days_overdue"] = days
            item["days_overdue_kind"] = "calculated"
            annotated.append(item)
        return {"entities": annotated, "qbo_query": sql, "as_of": iso(self._today())}

    def _upcoming_bills(self, tenant: Tenant, args: dict[str, Any]) -> dict[str, Any]:
        days = max(1, min(int(args.get("days") or 14), 90))
        end = self._today() + timedelta(days=days)
        sql = compile_query(
            "Bill",
            filters=[("Balance", ">", "0"), ("DueDate", ">=", iso(self._today())), ("DueDate", "<=", iso(end))],
            maxresults=50,
        )
        return {"entities": self.intuit.query(tenant.tenant_id, sql), "qbo_query": sql, "window_days": days}

    def _search_purchases(self, tenant: Tenant, args: dict[str, Any]) -> dict[str, Any]:
        start, end, label = resolve_period(args, self._today())
        sql = compile_query(
            "Purchase",
            filters=[("TxnDate", ">=", iso(start)), ("TxnDate", "<=", iso(end))],
            maxresults=self._max(args),
        )
        return {"entities": self.intuit.query(tenant.tenant_id, sql), "qbo_query": sql, "period": label, "qbo_entity": "Purchase"}

    def _summarize_expenses(self, tenant: Tenant, args: dict[str, Any]) -> dict[str, Any]:
        payload = self._search_purchases(tenant, args)
        totals: dict[str, float] = {}
        for row in payload["entities"]:
            account = ((row.get("AccountRef") or {}).get("name")) or "unknown"
            try:
                amount = float(row.get("TotalAmt") or 0)
            except (TypeError, ValueError):
                amount = 0.0
            totals[account] = round(totals.get(account, 0.0) + amount, 2)
        ranked = sorted(({"account": k, "total": v, "value_kind": "calculated"} for k, v in totals.items()), key=lambda x: x["total"], reverse=True)
        return {"categories": ranked, "source": "Purchase", "period": payload.get("period")}

    def _account_balances(self, tenant: Tenant, args: dict[str, Any]) -> dict[str, Any]:
        sql = compile_query("Account", maxresults=100)
        rows = self.intuit.query(tenant.tenant_id, sql)
        return {
            "accounts": [
                {
                    "id": row.get("Id"),
                    "name": row.get("Name"),
                    "type": row.get("AccountType"),
                    "balance": row.get("CurrentBalance"),
                    "source_field": "Account.CurrentBalance",
                }
                for row in rows
            ]
        }

    def _report(self, tenant: Tenant, args: dict[str, Any], name: str, method: bool = True) -> dict[str, Any]:
        start, end, label = resolve_period(args, self._today())
        params: dict[str, Any] = {"start_date": iso(start), "end_date": iso(end)}
        if method:
            params["accounting_method"] = str(args.get("accounting_method") or "Accrual")
        payload = self.intuit.report(tenant.tenant_id, name, params)
        header = payload.get("Header") or {}
        return {"report": name, "period": label, "header": header, "rows": payload.get("Rows"), "columns": payload.get("Columns")}

    def _aging(self, tenant: Tenant, args: dict[str, Any], name: str) -> dict[str, Any]:
        report_date = str(args.get("report_date") or iso(self._today()))
        payload = self.intuit.report(tenant.tenant_id, name, {"report_date": report_date})
        return {"report": name, "header": payload.get("Header"), "rows": payload.get("Rows"), "columns": payload.get("Columns")}

    def _preferences(self, tenant: Tenant, args: dict[str, Any]) -> dict[str, Any]:
        return self.intuit.request(tenant.tenant_id, "GET", "preferences")

    def _expense_report(self, tenant: Tenant, args: dict[str, Any]) -> dict[str, Any]:
        pnl = self._report(tenant, args, "ProfitAndLoss")
        summary = self._summarize_expenses(tenant, args)
        return {"profit_and_loss": pnl, "purchase_totals": summary, "qbo_expense_entity": "Purchase"}

    def _draft(self, agent: AgentAcl, tenant: Tenant, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        tokens = self.tokens.load(tenant.tenant_id)
        estimated = None
        if args.get("line_amount") is not None:
            estimated = str(args.get("line_amount"))
        action = self.approvals.create(
            agent=agent.agent_id,
            tenant=tenant.tenant_id,
            realm=tokens.realm_id if tokens else None,
            action_type=tool,
            risk="draft",
            params=args,
            description=f"Local {tool} proposal. Not a QuickBooks transaction.",
            estimated_impact=estimated,
        )
        return wrap(
            tool=tool,
            tenant=tenant.tenant_id,
            environment=self.settings.environment,
            data={
                "action": action,
                "warning": "This is a local proposal only. QuickBooks Online has no API draft state for this object. It has not been posted.",
            },
            posted=False,
            extra={"approval_id": action["id"]},
        )

    def operator_decide(self, action_id: str, *, decision: str, user: str) -> dict[str, Any]:
        return self.approvals.decide(action_id, decision=decision, user=user)

    def import_tokens(self, tenant_id: str | None, payload: dict[str, Any]) -> dict[str, Any]:
        tenant = self.tenants.get(tenant_id or self.default_tenant)
        if not tenant:
            raise ConnectorError("unknown_tenant", 404)
        try:
            self.oauth.import_tokens(
                tenant.tenant_id,
                realm_id=str(payload.get("realm_id") or payload.get("realmId") or ""),
                access_token=str(payload.get("access_token") or ""),
                refresh_token=str(payload.get("refresh_token") or ""),
                environment=str(payload.get("environment") or tenant.environment or "production"),
                expires_in=int(payload.get("expires_in") or 3600),
                refresh_expires_in=(int(payload["x_refresh_token_expires_in"]) if payload.get("x_refresh_token_expires_in") else None),
                company_name=(str(payload["company_name"]) if payload.get("company_name") else None),
            )
        except OAuthError as exc:
            raise ConnectorError(exc.code, 409 if exc.code == "realm_in_use" else 400) from exc
        status = self.tokens.public_status(tenant.tenant_id)
        return {
            "ok": True,
            "tenant_id": tenant.tenant_id,
            "company": status.get("company_name"),
            "oauth": status.get("oauth"),
            "environment": status.get("environment"),
        }

    def operator_execute(self, action_id: str, *, user: str) -> dict[str, Any]:
        action = self.approvals.get(action_id)
        if action["status"] == "executed":
            return action
        if action["status"] != "approved":
            raise ConnectorError("not_approved", 409)
        if action["approving_user"] == action["agent"] or user == action["agent"]:
            raise ConnectorError("self_approve_forbidden", 403)
        if not user:
            raise ConnectorError("operator_user_required", 401)
        tenant = self.tenants[action["tenant"]]
        stored = self.tokens.load(action["tenant"])
        is_production = tenant.environment == "production" or (stored is not None and stored.environment == "production")
        if is_production and not self.settings.allow_production_writes:
            raise ConnectorError("production_writes_held", 403)
        body, entity = self._body_for_action(action)
        try:
            payload = self.intuit.create(action["tenant"], entity, body, action["requestid"])
        except IntuitError as exc:
            failed = self.approvals.mark_executed(action_id, qbo_object_id=None, result={"error": exc.code}, status="failed")
            return failed
        qbo_id = None
        entity_payload = payload.get(entity) if isinstance(payload.get(entity), dict) else None
        if entity_payload is None:
            for key, value in payload.items():
                if isinstance(value, dict) and str(key).lower() == entity.lower():
                    entity_payload = value
                    break
        if isinstance(entity_payload, dict):
            qbo_id = entity_payload.get("Id")
        return self.approvals.mark_executed(action_id, qbo_object_id=qbo_id, result={"qbo": payload}, status="executed")

    def _body_for_action(self, action: dict[str, Any]) -> tuple[dict[str, Any], str]:
        params = action["params"]
        kind = action["action_type"]
        if kind == "qbo_create_invoice_draft":
            amount = float(params["line_amount"])
            return (
                {
                    "CustomerRef": {"value": str(params["customer_id"])},
                    "Line": [
                        {
                            "Amount": amount,
                            "DetailType": "SalesItemLineDetail",
                            "Description": str(params.get("description") or "Staged invoice"),
                            "SalesItemLineDetail": {"Qty": 1, "UnitPrice": amount},
                        }
                    ],
                    "PrivateNote": str(params.get("memo") or ""),
                },
                "Invoice",
            )
        if kind == "qbo_create_customer_draft":
            return ({"DisplayName": str(params["display_name"])}, "Customer")
        if kind == "qbo_create_vendor_draft":
            return ({"DisplayName": str(params["display_name"])}, "Vendor")
        if kind == "qbo_create_bill_draft":
            amount = float(params["line_amount"])
            return (
                {
                    "VendorRef": {"value": str(params["vendor_id"])},
                    "Line": [
                        {
                            "Amount": amount,
                            "DetailType": "AccountBasedExpenseLineDetail",
                            "Description": str(params.get("description") or "Staged bill"),
                            "AccountBasedExpenseLineDetail": {"AccountRef": {"value": "1"}},
                        }
                    ],
                },
                "Bill",
            )
        if kind in {"qbo_create_estimate_draft", "qbo_create_sales_receipt_draft", "qbo_create_credit_memo_draft"}:
            amount = float(params["line_amount"])
            entity = {
                "qbo_create_estimate_draft": "Estimate",
                "qbo_create_sales_receipt_draft": "SalesReceipt",
                "qbo_create_credit_memo_draft": "CreditMemo",
            }[kind]
            return (
                {
                    "CustomerRef": {"value": str(params["customer_id"])},
                    "Line": [
                        {
                            "Amount": amount,
                            "DetailType": "SalesItemLineDetail",
                            "Description": str(params.get("description") or f"Staged {entity}"),
                            "SalesItemLineDetail": {"Qty": 1, "UnitPrice": amount},
                        }
                    ],
                    "PrivateNote": str(params.get("memo") or ""),
                },
                entity,
            )
        if kind == "qbo_create_purchase_draft":
            amount = float(params["line_amount"])
            return (
                {
                    "PaymentType": "Cash",
                    "AccountRef": {"value": "1"},
                    "Line": [
                        {
                            "Amount": amount,
                            "DetailType": "AccountBasedExpenseLineDetail",
                            "Description": str(params.get("description") or "Staged purchase"),
                            "AccountBasedExpenseLineDetail": {"AccountRef": {"value": "1"}},
                        }
                    ],
                    "PrivateNote": str(params.get("memo") or ""),
                },
                "Purchase",
            )
        if kind == "qbo_create_payment_draft":
            return (
                {
                    "CustomerRef": {"value": str(params["customer_id"])},
                    "TotalAmt": float(params["line_amount"]),
                    "PrivateNote": str(params.get("memo") or ""),
                },
                "Payment",
            )
        if kind == "qbo_create_item_draft":
            return (
                {
                    "Name": str(params["display_name"]),
                    "Type": "Service",
                    "IncomeAccountRef": {"value": "1"},
                },
                "Item",
            )
        if kind == "qbo_create_journal_entry_draft":
            amount = float(params["line_amount"])
            return (
                {
                    "PrivateNote": str(params.get("memo") or params.get("description") or "Staged journal entry"),
                    "Line": [
                        {
                            "Amount": amount,
                            "DetailType": "JournalEntryLineDetail",
                            "JournalEntryLineDetail": {"PostingType": "Debit", "AccountRef": {"value": "1"}},
                        },
                        {
                            "Amount": amount,
                            "DetailType": "JournalEntryLineDetail",
                            "JournalEntryLineDetail": {"PostingType": "Credit", "AccountRef": {"value": "2"}},
                        },
                    ],
                },
                "JournalEntry",
            )
        if kind == "qbo_create_purchase_order_draft":
            amount = float(params["line_amount"])
            return (
                {
                    "VendorRef": {"value": str(params["vendor_id"])},
                    "Line": [
                        {
                            "Amount": amount,
                            "DetailType": "AccountBasedExpenseLineDetail",
                            "Description": str(params.get("description") or "Staged purchase order"),
                            "AccountBasedExpenseLineDetail": {"AccountRef": {"value": "1"}},
                        }
                    ],
                    "PrivateNote": str(params.get("memo") or ""),
                },
                "PurchaseOrder",
            )
        raise ConnectorError("unsupported_execute")
