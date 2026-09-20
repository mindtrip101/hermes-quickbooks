from __future__ import annotations

from typing import Any

from .api_surface import register_official_surface

PERIOD_PROP = {
    "type": "string",
    "description": "this_month, last_month, this_quarter, last_quarter, this_year, last_year, q3, ytd",
}
DATE = {"type": "string", "description": "YYYY-MM-DD"}
TENANT = {"type": "string", "description": "Optional tenant id. Defaults to the agent's authorized company."}
QUERY = {"type": "string", "description": "Display name search fragment. Not raw SQL."}
ENTITY_ID = {"type": "string", "description": "QuickBooks object Id"}
MAXRESULTS = {"type": "integer", "minimum": 1, "maximum": 100}


def _obj(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        schema["required"] = required
    return schema


TOOLS: dict[str, dict[str, Any]] = {
    "qbo_health": {
        "risk": "read",
        "domain": "system",
        "needs_api": False,
        "description": "Connector health, OAuth status, pending approvals. Never returns secrets.",
        "schema": _obj({}),
    },
    "qbo_get_company_info": {
        "risk": "read",
        "domain": "company",
        "needs_api": True,
        "description": "CompanyInfo for the authorized QuickBooks company.",
        "schema": _obj({"tenant_id": TENANT}),
    },
    "qbo_search_customers": {
        "risk": "read",
        "domain": "customers",
        "needs_api": True,
        "description": "Search customers by display name.",
        "schema": _obj({"query": QUERY, "maxresults": MAXRESULTS, "tenant_id": TENANT}),
    },
    "qbo_get_customer": {
        "risk": "read",
        "domain": "customers",
        "needs_api": True,
        "description": "Get one customer by Id.",
        "schema": _obj({"customer_id": ENTITY_ID, "tenant_id": TENANT}, ["customer_id"]),
    },
    "qbo_get_customer_balance": {
        "risk": "read",
        "domain": "customers",
        "needs_api": True,
        "description": "Customer.Balance for one customer.",
        "schema": _obj({"customer_id": ENTITY_ID, "tenant_id": TENANT}, ["customer_id"]),
    },
    "qbo_get_customer_invoices": {
        "risk": "read",
        "domain": "invoices",
        "needs_api": True,
        "description": "Invoices for a customer.",
        "schema": _obj({"customer_id": ENTITY_ID, "maxresults": MAXRESULTS, "tenant_id": TENANT}, ["customer_id"]),
    },
    "qbo_search_invoices": {
        "risk": "read",
        "domain": "invoices",
        "needs_api": True,
        "description": "Search invoices by document number fragment.",
        "schema": _obj({"query": QUERY, "maxresults": MAXRESULTS, "tenant_id": TENANT}),
    },
    "qbo_get_invoice": {
        "risk": "read",
        "domain": "invoices",
        "needs_api": True,
        "description": "Get one invoice by Id.",
        "schema": _obj({"invoice_id": ENTITY_ID, "tenant_id": TENANT}, ["invoice_id"]),
    },
    "qbo_get_open_invoices": {
        "risk": "read",
        "domain": "ar",
        "needs_api": True,
        "description": "Invoices with outstanding Balance > 0.",
        "schema": _obj({"maxresults": MAXRESULTS, "tenant_id": TENANT}),
    },
    "qbo_get_overdue_invoices": {
        "risk": "read",
        "domain": "ar",
        "needs_api": True,
        "description": "Open invoices with DueDate before today.",
        "schema": _obj({"maxresults": MAXRESULTS, "tenant_id": TENANT}),
    },
    "qbo_create_invoice_draft": {
        "risk": "draft",
        "domain": "drafts",
        "needs_api": False,
        "description": "Stage a local invoice proposal. Does not POST to QuickBooks; QBO has no API draft state.",
        "schema": _obj(
            {
                "customer_id": ENTITY_ID,
                "line_amount": {"type": "number"},
                "description": {"type": "string"},
                "due_date": DATE,
                "memo": {"type": "string"},
                "tenant_id": TENANT,
            },
            ["customer_id", "line_amount"],
        ),
    },
    "qbo_create_customer_draft": {
        "risk": "draft",
        "domain": "drafts",
        "needs_api": False,
        "description": "Stage a local customer proposal. Not a QuickBooks customer until operator execute.",
        "schema": _obj({"display_name": {"type": "string"}, "email": {"type": "string"}, "tenant_id": TENANT}, ["display_name"]),
    },
    "qbo_create_vendor_draft": {
        "risk": "draft",
        "domain": "drafts",
        "needs_api": False,
        "description": "Stage a local vendor proposal. Not posted to QuickBooks.",
        "schema": _obj({"display_name": {"type": "string"}, "email": {"type": "string"}, "tenant_id": TENANT}, ["display_name"]),
    },
    "qbo_create_bill_draft": {
        "risk": "draft",
        "domain": "drafts",
        "needs_api": False,
        "description": "Stage a local bill proposal. Not posted to QuickBooks.",
        "schema": _obj(
            {
                "vendor_id": ENTITY_ID,
                "line_amount": {"type": "number"},
                "due_date": DATE,
                "description": {"type": "string"},
                "tenant_id": TENANT,
            },
            ["vendor_id", "line_amount"],
        ),
    },
    "qbo_search_payments": {
        "risk": "read",
        "domain": "payments",
        "needs_api": True,
        "description": "List recent payments.",
        "schema": _obj({"maxresults": MAXRESULTS, "tenant_id": TENANT}),
    },
    "qbo_get_payment": {
        "risk": "read",
        "domain": "payments",
        "needs_api": True,
        "description": "Get one payment by Id.",
        "schema": _obj({"payment_id": ENTITY_ID, "tenant_id": TENANT}, ["payment_id"]),
    },
    "qbo_search_vendors": {
        "risk": "read",
        "domain": "vendors",
        "needs_api": True,
        "description": "Search vendors by display name.",
        "schema": _obj({"query": QUERY, "maxresults": MAXRESULTS, "tenant_id": TENANT}),
    },
    "qbo_get_vendor": {
        "risk": "read",
        "domain": "vendors",
        "needs_api": True,
        "description": "Get one vendor by Id.",
        "schema": _obj({"vendor_id": ENTITY_ID, "tenant_id": TENANT}, ["vendor_id"]),
    },
    "qbo_search_bills": {
        "risk": "read",
        "domain": "bills",
        "needs_api": True,
        "description": "Search bills by document number fragment.",
        "schema": _obj({"query": QUERY, "maxresults": MAXRESULTS, "tenant_id": TENANT}),
    },
    "qbo_get_bill": {
        "risk": "read",
        "domain": "bills",
        "needs_api": True,
        "description": "Get one bill by Id.",
        "schema": _obj({"bill_id": ENTITY_ID, "tenant_id": TENANT}, ["bill_id"]),
    },
    "qbo_get_unpaid_bills": {
        "risk": "read",
        "domain": "ap",
        "needs_api": True,
        "description": "Bills with outstanding Balance > 0.",
        "schema": _obj({"maxresults": MAXRESULTS, "tenant_id": TENANT}),
    },
    "qbo_get_upcoming_bills": {
        "risk": "read",
        "domain": "ap",
        "needs_api": True,
        "description": "Unpaid bills due within N days (default 14).",
        "schema": _obj({"days": {"type": "integer", "minimum": 1, "maximum": 90}, "tenant_id": TENANT}),
    },
    "qbo_search_expenses": {
        "risk": "read",
        "domain": "expenses",
        "needs_api": True,
        "description": "Search QBO Purchase entities (expenses). There is no Expense entity.",
        "schema": _obj({"period": PERIOD_PROP, "start_date": DATE, "end_date": DATE, "maxresults": MAXRESULTS, "tenant_id": TENANT}),
    },
    "qbo_get_expense": {
        "risk": "read",
        "domain": "expenses",
        "needs_api": True,
        "description": "Get one Purchase by Id.",
        "schema": _obj({"purchase_id": ENTITY_ID, "tenant_id": TENANT}, ["purchase_id"]),
    },
    "qbo_summarize_expenses": {
        "risk": "read",
        "domain": "expenses",
        "needs_api": True,
        "description": "Sum Purchases by account for a period. Calculated from source Purchases.",
        "schema": _obj({"period": PERIOD_PROP, "start_date": DATE, "end_date": DATE, "tenant_id": TENANT}),
    },
    "qbo_get_accounts": {
        "risk": "read",
        "domain": "accounts",
        "needs_api": True,
        "description": "Chart of accounts.",
        "schema": _obj({"maxresults": MAXRESULTS, "tenant_id": TENANT}),
    },
    "qbo_get_account": {
        "risk": "read",
        "domain": "accounts",
        "needs_api": True,
        "description": "Get one account by Id.",
        "schema": _obj({"account_id": ENTITY_ID, "tenant_id": TENANT}, ["account_id"]),
    },
    "qbo_get_account_balances": {
        "risk": "read",
        "domain": "accounts",
        "needs_api": True,
        "description": "Account.CurrentBalance for active accounts.",
        "schema": _obj({"tenant_id": TENANT}),
    },
    "qbo_profit_and_loss": {
        "risk": "read",
        "domain": "reports",
        "needs_api": True,
        "description": "QBO ProfitAndLoss report.",
        "schema": _obj({"period": PERIOD_PROP, "start_date": DATE, "end_date": DATE, "accounting_method": {"type": "string"}, "tenant_id": TENANT}),
    },
    "qbo_balance_sheet": {
        "risk": "read",
        "domain": "reports",
        "needs_api": True,
        "description": "QBO BalanceSheet report.",
        "schema": _obj({"period": PERIOD_PROP, "start_date": DATE, "end_date": DATE, "accounting_method": {"type": "string"}, "tenant_id": TENANT}),
    },
    "qbo_cash_flow": {
        "risk": "read",
        "domain": "reports",
        "needs_api": True,
        "description": "QBO CashFlow report.",
        "schema": _obj({"period": PERIOD_PROP, "start_date": DATE, "end_date": DATE, "tenant_id": TENANT}),
    },
    "qbo_accounts_receivable_aging": {
        "risk": "read",
        "domain": "ar",
        "needs_api": True,
        "description": "QBO AgedReceivables report.",
        "schema": _obj({"report_date": DATE, "tenant_id": TENANT}),
    },
    "qbo_accounts_payable_aging": {
        "risk": "read",
        "domain": "ap",
        "needs_api": True,
        "description": "QBO AgedPayables report.",
        "schema": _obj({"report_date": DATE, "tenant_id": TENANT}),
    },
    "qbo_sales_report": {
        "risk": "read",
        "domain": "reports",
        "needs_api": True,
        "description": "QBO SalesByCustomer report.",
        "schema": _obj({"period": PERIOD_PROP, "start_date": DATE, "end_date": DATE, "tenant_id": TENANT}),
    },
    "qbo_expense_report": {
        "risk": "read",
        "domain": "expenses",
        "needs_api": True,
        "description": "Expense section of ProfitAndLoss plus Purchase totals. Mixed source/calculated.",
        "schema": _obj({"period": PERIOD_PROP, "start_date": DATE, "end_date": DATE, "tenant_id": TENANT}),
    },
    "qbo_list_approvals": {
        "risk": "read",
        "domain": "approvals",
        "needs_api": False,
        "description": "List local approval-queue metadata. Cannot approve or execute.",
        "schema": _obj({"status": {"type": "string"}, "tenant_id": TENANT}),
    },
}

register_official_surface(
    TOOLS,
    obj=_obj,
    query=QUERY,
    entity_id=ENTITY_ID,
    maxresults=MAXRESULTS,
    tenant=TENANT,
    period=PERIOD_PROP,
    date=DATE,
)
TOOL_NAMES = list(TOOLS.keys())
