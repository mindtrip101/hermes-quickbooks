# Official Intuit QuickBooks Online Accounting API coverage

This connector is mapped to Intuit’s **QuickBooks Online Accounting API** (v3 REST, JSON).

Canonical Intuit pages:

- [What you can do with the Accounting API](https://developer.intuit.com/app/developer/qbo/docs/learn/explore-the-quickbooks-online-api)
- [REST operations and minor versions](https://developer.intuit.com/app/developer/qbo/docs/learn/rest-api-features)
- [All entities](https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/account)
- [OAuth 2.0](https://developer.intuit.com/app/developer/qbo/docs/develop/authentication-and-authorization/oauth-2.0)
- [Reports](https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/accountlist)

Default query parameter: `minorversion=75`.

## Authentication

OAuth 2.0 authorization-code flow.

- Authorize: `https://appcenter.intuit.com/connect/oauth2`
- Token: `https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer`
- Scope: `com.intuit.quickbooks.accounting`
- Sandbox API host: `https://sandbox-quickbooks.api.intuit.com`
- Production API host: `https://quickbooks.api.intuit.com`

Development keys → sandbox sample companies only. Production keys → live companies. Redirect URI must match the Intuit app exactly (`localhost` hostname for Development HTTP; HTTPS hostname for Production).

## Operations used

| Connector action | Intuit operation |
| --- | --- |
| Search / list | `GET /v3/company/{realmId}/query?query=SELECT * FROM {Entity} ... MAXRESULTS n` |
| Get one | `GET /v3/company/{realmId}/{entity}/{id}` |
| Reports | `GET /v3/company/{realmId}/reports/{ReportName}` |
| Preferences | `GET /v3/company/{realmId}/preferences` |
| CompanyInfo | `GET /v3/company/{realmId}/companyinfo/{realmId}` |
| Operator execute | `POST /v3/company/{realmId}/{entity}` with idempotent `requestid` |

The model cannot send raw query language. `compile_query` allowlists entity and field names from `api_surface.py`.

## Entity coverage

| Intuit entity | Tools | Notes |
| --- | --- | --- |
| CompanyInfo | `qbo_get_company_info` | |
| Preferences | `qbo_get_preferences` | |
| Customer | `qbo_search_customers`, `qbo_get_customer`, `qbo_get_customer_balance`, `qbo_get_customer_invoices` | |
| Invoice | `qbo_search_invoices`, `qbo_get_invoice`, `qbo_get_open_invoices`, `qbo_get_overdue_invoices` | |
| Payment | `qbo_search_payments`, `qbo_get_payment` | |
| Vendor | `qbo_search_vendors`, `qbo_get_vendor` | |
| Bill | `qbo_search_bills`, `qbo_get_bill`, `qbo_get_unpaid_bills`, `qbo_get_upcoming_bills` | |
| Purchase | `qbo_search_expenses`, `qbo_get_expense`, `qbo_summarize_expenses` | There is no Expense entity |
| Account | `qbo_get_accounts`, `qbo_get_account`, `qbo_get_account_balances` | |
| Estimate | `qbo_search_estimates`, `qbo_get_estimate` | Public API substitute for Sales Order |
| CreditMemo | `qbo_search_credit_memos`, `qbo_get_credit_memo` | |
| SalesReceipt | `qbo_search_sales_receipts`, `qbo_get_sales_receipt` | |
| RefundReceipt | `qbo_search_refund_receipts`, `qbo_get_refund_receipt` | |
| PurchaseOrder | `qbo_search_purchase_orders`, `qbo_get_purchase_order` | |
| JournalEntry | `qbo_search_journal_entries`, `qbo_get_journal_entry` | |
| Deposit | `qbo_search_deposits`, `qbo_get_deposit` | |
| Transfer | `qbo_search_transfers`, `qbo_get_transfer` | |
| BillPayment | `qbo_search_bill_payments`, `qbo_get_bill_payment` | |
| VendorCredit | `qbo_search_vendor_credits`, `qbo_get_vendor_credit` | |
| CreditCardPayment | `qbo_search_credit_card_payments`, `qbo_get_credit_card_payment` | |
| TimeActivity | `qbo_search_time_activities`, `qbo_get_time_activity` | |
| Item | `qbo_search_items`, `qbo_get_item` | |
| Employee | `qbo_search_employees`, `qbo_get_employee` | Directory only; not Payroll |
| Class | `qbo_search_classes`, `qbo_get_class` | |
| Department | `qbo_search_departments`, `qbo_get_department` | |
| PaymentMethod | `qbo_search_payment_methods`, `qbo_get_payment_method` | |
| Term | `qbo_search_terms`, `qbo_get_term` | |
| TaxCode / TaxRate / TaxAgency | `qbo_search_tax_*` / `qbo_get_tax_*` | |
| CompanyCurrency | `qbo_search_currencies`, `qbo_get_currency` | |
| CustomerType | `qbo_search_customer_types`, `qbo_get_customer_type` | |
| Budget | `qbo_search_budgets`, `qbo_get_budget` | |
| Attachable | `qbo_search_attachables`, `qbo_get_attachable` | Metadata only |
| ExchangeRate | `qbo_search_exchange_rates`, `qbo_get_exchange_rate` | |
| RecurringTransaction | `qbo_search_recurring_transactions`, `qbo_get_recurring_transaction` | |

## Report coverage

| Tool | Intuit report name |
| --- | --- |
| `qbo_profit_and_loss` | ProfitAndLoss |
| `qbo_profit_and_loss_detail` | ProfitAndLossDetail |
| `qbo_balance_sheet` | BalanceSheet |
| `qbo_cash_flow` | CashFlow |
| `qbo_trial_balance` | TrialBalance |
| `qbo_general_ledger` | GeneralLedger |
| `qbo_journal_report` | JournalReport |
| `qbo_accounts_receivable_aging` | AgedReceivables |
| `qbo_aged_receivable_detail` | AgedReceivableDetail |
| `qbo_accounts_payable_aging` | AgedPayables |
| `qbo_aged_payable_detail` | AgedPayableDetail |
| `qbo_customer_balance_report` | CustomerBalance |
| `qbo_customer_balance_detail` | CustomerBalanceDetail |
| `qbo_vendor_balance_report` | VendorBalance |
| `qbo_vendor_balance_detail` | VendorBalanceDetail |
| `qbo_sales_report` | SalesByCustomer |
| `qbo_sales_by_product` | ItemSales |
| `qbo_sales_by_class` | ClassSales |
| `qbo_sales_by_department` | DepartmentSales |
| `qbo_inventory_valuation` | InventoryValuationSummary |
| `qbo_inventory_valuation_detail` | InventoryValuationDetail |
| `qbo_transaction_list` | TransactionList |
| `qbo_transaction_list_by_customer` | TransactionListByCustomer |
| `qbo_transaction_list_by_vendor` | TransactionListByVendor |
| `qbo_tax_summary` | TaxSummary |
| `qbo_account_list_report` | AccountList |
| `qbo_expense_report` | ProfitAndLoss mixed with Purchase totals |

## Draft / write mapping

Local drafts are **not** Intuit objects. Operator execute POSTs:

| Draft tool | POST entity |
| --- | --- |
| `qbo_create_invoice_draft` | Invoice |
| `qbo_create_customer_draft` | Customer |
| `qbo_create_vendor_draft` | Vendor |
| `qbo_create_bill_draft` | Bill |
| `qbo_create_estimate_draft` | Estimate |
| `qbo_create_sales_receipt_draft` | SalesReceipt |
| `qbo_create_credit_memo_draft` | CreditMemo |
| `qbo_create_purchase_draft` | Purchase |
| `qbo_create_payment_draft` | Payment |
| `qbo_create_item_draft` | Item |
| `qbo_create_journal_entry_draft` | JournalEntry |
| `qbo_create_purchase_order_draft` | PurchaseOrder |

Production POSTs require `QBO_ALLOW_PRODUCTION_WRITES=true` plus operator execute.

## Intentionally not implemented

- Intuit Payments API
- Payroll API
- Commerce / merchant boarding
- Sales Order (Intuit: not in the public Accounting API; use Estimate)
- Attachable file bytes
- Batch and CDC
- Delete/void from the LLM
