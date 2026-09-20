"""Official QuickBooks Online Accounting API surface.

Sources (Intuit):
- Accounting API overview: https://developer.intuit.com/app/developer/qbo/docs/learn/explore-the-quickbooks-online-api
- All entities: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/account
- REST operations: https://developer.intuit.com/app/developer/qbo/docs/learn/rest-api-features
- OAuth 2.0: https://developer.intuit.com/app/developer/qbo/docs/develop/authentication-and-authorization/oauth-2.0
- Reports: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/accountlist
- Minor versions: https://developer.intuit.com/app/developer/qbo/docs/learn/explore-the-quickbooks-online-api/minor-versions

This connector implements the QBO v3 REST Accounting API (JSON, minorversion 75).
It does not implement Intuit Payments, Payroll, or Commerce.
Writes to live companies are operator-execute only and remain gated by default.
"""

from __future__ import annotations

from typing import Any

TXN_FIELDS = frozenset(
    {
        "Id",
        "DocNumber",
        "TxnDate",
        "TotalAmt",
        "Balance",
        "DueDate",
        "MetaData",
        "CustomerRef",
        "VendorRef",
        "EntityRef",
        "AccountRef",
        "PaymentType",
        "PrivateNote",
        "Name",
        "DisplayName",
    }
)
NAME_FIELDS = frozenset(
    {
        "Id",
        "DisplayName",
        "Name",
        "Active",
        "Balance",
        "CompanyName",
        "PrimaryEmailAddr",
        "FullyQualifiedName",
        "Type",
        "AccountType",
        "AccountSubType",
        "CurrentBalance",
        "GivenName",
        "FamilyName",
    }
)

# Official v3 Accounting entities that this connector exposes as search/get tools.
# First-class tools (Customer, Invoice, Payment, Vendor, Bill, Purchase, Account, CompanyInfo)
# keep their existing names and are listed in CORE_QUERY_FIELDS.
ENTITIES: list[dict[str, str]] = [
    {"entity": "Estimate", "domain": "estimates", "search": "DocNumber", "id_arg": "estimate_id", "fields": "txn", "search_tool": "qbo_search_estimates", "get_tool": "qbo_get_estimate", "docs": "estimate"},
    {"entity": "CreditMemo", "domain": "sales", "search": "DocNumber", "id_arg": "credit_memo_id", "fields": "txn", "search_tool": "qbo_search_credit_memos", "get_tool": "qbo_get_credit_memo", "docs": "creditmemo"},
    {"entity": "SalesReceipt", "domain": "sales", "search": "DocNumber", "id_arg": "sales_receipt_id", "fields": "txn", "search_tool": "qbo_search_sales_receipts", "get_tool": "qbo_get_sales_receipt", "docs": "salesreceipt"},
    {"entity": "RefundReceipt", "domain": "sales", "search": "DocNumber", "id_arg": "refund_receipt_id", "fields": "txn", "search_tool": "qbo_search_refund_receipts", "get_tool": "qbo_get_refund_receipt", "docs": "refundreceipt"},
    {"entity": "PurchaseOrder", "domain": "purchasing", "search": "DocNumber", "id_arg": "purchase_order_id", "fields": "txn", "search_tool": "qbo_search_purchase_orders", "get_tool": "qbo_get_purchase_order", "docs": "purchaseorder"},
    {"entity": "JournalEntry", "domain": "journals", "search": "DocNumber", "id_arg": "journal_entry_id", "fields": "txn", "search_tool": "qbo_search_journal_entries", "get_tool": "qbo_get_journal_entry", "docs": "journalentry"},
    {"entity": "Deposit", "domain": "banking", "search": "TxnDate", "id_arg": "deposit_id", "fields": "txn", "search_tool": "qbo_search_deposits", "get_tool": "qbo_get_deposit", "docs": "deposit"},
    {"entity": "Transfer", "domain": "banking", "search": "TxnDate", "id_arg": "transfer_id", "fields": "txn", "search_tool": "qbo_search_transfers", "get_tool": "qbo_get_transfer", "docs": "transfer"},
    {"entity": "BillPayment", "domain": "ap", "search": "DocNumber", "id_arg": "bill_payment_id", "fields": "txn", "search_tool": "qbo_search_bill_payments", "get_tool": "qbo_get_bill_payment", "docs": "billpayment"},
    {"entity": "VendorCredit", "domain": "ap", "search": "DocNumber", "id_arg": "vendor_credit_id", "fields": "txn", "search_tool": "qbo_search_vendor_credits", "get_tool": "qbo_get_vendor_credit", "docs": "vendorcredit"},
    {"entity": "CreditCardPayment", "domain": "banking", "search": "TxnDate", "id_arg": "credit_card_payment_id", "fields": "txn", "search_tool": "qbo_search_credit_card_payments", "get_tool": "qbo_get_credit_card_payment", "docs": "creditcardpayment"},
    {"entity": "TimeActivity", "domain": "time", "search": "TxnDate", "id_arg": "time_activity_id", "fields": "txn", "search_tool": "qbo_search_time_activities", "get_tool": "qbo_get_time_activity", "docs": "timeactivity"},
    {"entity": "Item", "domain": "items", "search": "Name", "id_arg": "item_id", "fields": "name", "search_tool": "qbo_search_items", "get_tool": "qbo_get_item", "docs": "item"},
    {"entity": "Employee", "domain": "employees", "search": "DisplayName", "id_arg": "employee_id", "fields": "name", "search_tool": "qbo_search_employees", "get_tool": "qbo_get_employee", "docs": "employee"},
    {"entity": "Class", "domain": "lists", "search": "Name", "id_arg": "class_id", "fields": "name", "search_tool": "qbo_search_classes", "get_tool": "qbo_get_class", "docs": "class"},
    {"entity": "Department", "domain": "lists", "search": "Name", "id_arg": "department_id", "fields": "name", "search_tool": "qbo_search_departments", "get_tool": "qbo_get_department", "docs": "department"},
    {"entity": "PaymentMethod", "domain": "lists", "search": "Name", "id_arg": "payment_method_id", "fields": "name", "search_tool": "qbo_search_payment_methods", "get_tool": "qbo_get_payment_method", "docs": "paymentmethod"},
    {"entity": "Term", "domain": "lists", "search": "Name", "id_arg": "term_id", "fields": "name", "search_tool": "qbo_search_terms", "get_tool": "qbo_get_term", "docs": "term"},
    {"entity": "TaxCode", "domain": "tax", "search": "Name", "id_arg": "tax_code_id", "fields": "name", "search_tool": "qbo_search_tax_codes", "get_tool": "qbo_get_tax_code", "docs": "taxcode"},
    {"entity": "TaxRate", "domain": "tax", "search": "Name", "id_arg": "tax_rate_id", "fields": "name", "search_tool": "qbo_search_tax_rates", "get_tool": "qbo_get_tax_rate", "docs": "taxrate"},
    {"entity": "TaxAgency", "domain": "tax", "search": "DisplayName", "id_arg": "tax_agency_id", "fields": "name", "search_tool": "qbo_search_tax_agencies", "get_tool": "qbo_get_tax_agency", "docs": "taxagency"},
    {"entity": "CompanyCurrency", "domain": "company", "search": "Name", "id_arg": "currency_id", "fields": "name", "search_tool": "qbo_search_currencies", "get_tool": "qbo_get_currency", "docs": "companycurrency"},
    {"entity": "CustomerType", "domain": "customers", "search": "Name", "id_arg": "customer_type_id", "fields": "name", "search_tool": "qbo_search_customer_types", "get_tool": "qbo_get_customer_type", "docs": "customertype"},
    {"entity": "Budget", "domain": "reports", "search": "Name", "id_arg": "budget_id", "fields": "name", "search_tool": "qbo_search_budgets", "get_tool": "qbo_get_budget", "docs": "budget"},
    {"entity": "Attachable", "domain": "company", "search": "FileName", "id_arg": "attachable_id", "fields": "name", "search_tool": "qbo_search_attachables", "get_tool": "qbo_get_attachable", "docs": "attachable"},
    {"entity": "ExchangeRate", "domain": "company", "search": "SourceCurrencyCode", "id_arg": "exchange_rate_id", "fields": "name", "search_tool": "qbo_search_exchange_rates", "get_tool": "qbo_get_exchange_rate", "docs": "exchangerate"},
    {"entity": "RecurringTransaction", "domain": "lists", "search": "Name", "id_arg": "recurring_transaction_id", "fields": "name", "search_tool": "qbo_search_recurring_transactions", "get_tool": "qbo_get_recurring_transaction", "docs": "recurringtransaction"},
]

REPORTS: list[dict[str, Any]] = [
    {"tool": "qbo_trial_balance", "report": "TrialBalance", "period": True, "method": True, "domain": "reports"},
    {"tool": "qbo_general_ledger", "report": "GeneralLedger", "period": True, "method": True, "domain": "reports"},
    {"tool": "qbo_profit_and_loss_detail", "report": "ProfitAndLossDetail", "period": True, "method": True, "domain": "reports"},
    {"tool": "qbo_journal_report", "report": "JournalReport", "period": True, "method": True, "domain": "reports"},
    {"tool": "qbo_aged_receivable_detail", "report": "AgedReceivableDetail", "aging": True, "domain": "ar"},
    {"tool": "qbo_aged_payable_detail", "report": "AgedPayableDetail", "aging": True, "domain": "ap"},
    {"tool": "qbo_customer_balance_report", "report": "CustomerBalance", "aging": True, "domain": "ar"},
    {"tool": "qbo_customer_balance_detail", "report": "CustomerBalanceDetail", "aging": True, "domain": "ar"},
    {"tool": "qbo_vendor_balance_report", "report": "VendorBalance", "aging": True, "domain": "ap"},
    {"tool": "qbo_vendor_balance_detail", "report": "VendorBalanceDetail", "aging": True, "domain": "ap"},
    {"tool": "qbo_inventory_valuation", "report": "InventoryValuationSummary", "period": True, "method": False, "domain": "items"},
    {"tool": "qbo_inventory_valuation_detail", "report": "InventoryValuationDetail", "period": True, "method": False, "domain": "items"},
    {"tool": "qbo_transaction_list", "report": "TransactionList", "period": True, "method": False, "domain": "reports"},
    {"tool": "qbo_transaction_list_by_customer", "report": "TransactionListByCustomer", "period": True, "method": False, "domain": "reports"},
    {"tool": "qbo_transaction_list_by_vendor", "report": "TransactionListByVendor", "period": True, "method": False, "domain": "reports"},
    {"tool": "qbo_sales_by_product", "report": "ItemSales", "period": True, "method": False, "domain": "reports"},
    {"tool": "qbo_sales_by_class", "report": "ClassSales", "period": True, "method": False, "domain": "reports"},
    {"tool": "qbo_sales_by_department", "report": "DepartmentSales", "period": True, "method": False, "domain": "reports"},
    {"tool": "qbo_tax_summary", "report": "TaxSummary", "period": True, "method": False, "domain": "tax"},
    {"tool": "qbo_account_list_report", "report": "AccountList", "period": False, "method": False, "domain": "accounts"},
]

CORE_QUERY_FIELDS: dict[str, frozenset[str]] = {
    "Customer": NAME_FIELDS,
    "Invoice": TXN_FIELDS,
    "Payment": TXN_FIELDS,
    "Vendor": NAME_FIELDS,
    "Bill": TXN_FIELDS,
    "Purchase": TXN_FIELDS,
    "Account": NAME_FIELDS,
    "CompanyInfo": frozenset({"Id", "CompanyName", "LegalName", "CompanyAddr", "Country", "MetaData"}),
}

ACL_DOMAINS = {
    "system",
    "company",
    "customers",
    "invoices",
    "payments",
    "vendors",
    "bills",
    "expenses",
    "accounts",
    "reports",
    "ar",
    "ap",
    "drafts",
    "approvals",
    "estimates",
    "sales",
    "purchasing",
    "journals",
    "banking",
    "time",
    "items",
    "employees",
    "lists",
    "tax",
}

OUT_OF_SCOPE = [
    "Intuit Payments API (charges, cards, merchant boarding)",
    "Payroll API",
    "Commerce API",
    "Sales Order (not in the public QBO Accounting API; use Estimate)",
    "Attachable binary upload/download",
    "Batch and CDC change-data-capture endpoints",
    "Hard-delete / void from the LLM; production writes stay operator-gated",
]

ENTITY_DOCS = "https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities"


def entity_fields(kind: str) -> frozenset[str]:
    return TXN_FIELDS if kind == "txn" else NAME_FIELDS | {"FileName", "SourceCurrencyCode", "ContentType"}


def query_fields() -> dict[str, frozenset[str]]:
    fields = dict(CORE_QUERY_FIELDS)
    for spec in ENTITIES:
        extra = entity_fields(spec["fields"])
        if spec["search"] not in extra:
            extra = extra | {spec["search"]}
        fields[spec["entity"]] = extra
    return fields


def docs_url(slug: str) -> str:
    return f"{ENTITY_DOCS}/{slug}"


def register_official_surface(
    tools: dict[str, dict[str, Any]],
    *,
    obj,
    query,
    entity_id,
    maxresults,
    tenant,
    period,
    date,
) -> None:
    for spec in ENTITIES:
        entity = spec["entity"]
        search_name = spec["search_tool"]
        get_name = spec["get_tool"]
        if search_name not in tools:
            tools[search_name] = {
                "risk": "read",
                "domain": spec["domain"],
                "needs_api": True,
                "kind": "entity_search",
                "entity": entity,
                "search_field": spec["search"],
                "description": (
                    f"Query official QBO Accounting {entity} entities "
                    f"(GET /v3/company/{{realmId}}/query). Docs: {docs_url(spec['docs'])}"
                ),
                "schema": obj({"query": query, "maxresults": maxresults, "tenant_id": tenant}),
            }
        if get_name not in tools:
            tools[get_name] = {
                "risk": "read",
                "domain": spec["domain"],
                "needs_api": True,
                "kind": "entity_get",
                "entity": entity,
                "id_arg": spec["id_arg"],
                "description": (
                    f"Read one official QBO {entity} by Id "
                    f"(GET /v3/company/{{realmId}}/{spec['docs']}/{{id}})."
                ),
                "schema": obj({spec["id_arg"]: entity_id, "tenant_id": tenant}, [spec["id_arg"]]),
            }
    for spec in REPORTS:
        name = spec["tool"]
        if name in tools:
            continue
        props: dict[str, Any] = {"tenant_id": tenant}
        if spec.get("period"):
            props.update({"period": period, "start_date": date, "end_date": date})
            if spec.get("method"):
                props["accounting_method"] = {"type": "string"}
        if spec.get("aging"):
            props["report_date"] = date
        tools[name] = {
            "risk": "read",
            "domain": spec["domain"],
            "needs_api": True,
            "kind": "aging_report" if spec.get("aging") else "report",
            "report": spec["report"],
            "report_method": bool(spec.get("method")),
            "report_period": bool(spec.get("period")),
            "description": (
                f"Official QBO Reports API {spec['report']} "
                f"(GET /v3/company/{{realmId}}/reports/{spec['report']})."
            ),
            "schema": obj(props),
        }
    if "qbo_get_preferences" not in tools:
        tools["qbo_get_preferences"] = {
            "risk": "read",
            "domain": "company",
            "needs_api": True,
            "kind": "preferences",
            "description": "Official QBO Preferences entity (GET /v3/company/{realmId}/preferences).",
            "schema": obj({"tenant_id": tenant}),
        }
    extra_drafts = [
        ("qbo_create_estimate_draft", "Stage a local Estimate proposal. Not posted to QuickBooks.", ["customer_id", "line_amount"]),
        ("qbo_create_sales_receipt_draft", "Stage a local SalesReceipt proposal. Not posted to QuickBooks.", ["customer_id", "line_amount"]),
        ("qbo_create_credit_memo_draft", "Stage a local CreditMemo proposal. Not posted to QuickBooks.", ["customer_id", "line_amount"]),
        ("qbo_create_purchase_draft", "Stage a local Purchase (expense/check/credit card) proposal. Not posted.", ["line_amount"]),
        ("qbo_create_payment_draft", "Stage a local Payment proposal. Not posted to QuickBooks.", ["customer_id", "line_amount"]),
        ("qbo_create_item_draft", "Stage a local Item proposal. Not posted to QuickBooks.", ["display_name"]),
        ("qbo_create_journal_entry_draft", "Stage a local JournalEntry proposal. Not posted to QuickBooks.", ["line_amount"]),
        ("qbo_create_purchase_order_draft", "Stage a local PurchaseOrder proposal. Not posted to QuickBooks.", ["vendor_id", "line_amount"]),
    ]
    for name, description, required in extra_drafts:
        if name in tools:
            continue
        props = {
            "customer_id": entity_id,
            "vendor_id": entity_id,
            "line_amount": {"type": "number"},
            "display_name": {"type": "string"},
            "description": {"type": "string"},
            "memo": {"type": "string"},
            "due_date": date,
            "tenant_id": tenant,
        }
        tools[name] = {
            "risk": "draft",
            "domain": "drafts",
            "needs_api": False,
            "kind": "draft",
            "description": description,
            "schema": obj(props, required),
        }
