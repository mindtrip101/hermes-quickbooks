# Official API mapping

Intuit QBO v3 Accounting REST, `minorversion` 75.

Base URLs:

- Sandbox: `https://sandbox-quickbooks.api.intuit.com/v3/company/{realmId}/`
- Production: `https://quickbooks.api.intuit.com/v3/company/{realmId}/`

Operations (https://developer.intuit.com/app/developer/qbo/docs/learn/rest-api-features):

| Action | HTTP |
| --- | --- |
| Query | `GET .../query?query=SELECT * FROM Entity ...` |
| Read one | `GET .../{entity}/{id}` |
| Report | `GET .../reports/{ReportName}` |
| Create (operator execute only) | `POST .../{entity}` with `requestid` |

Entity docs root: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/

## First-class tools (custom logic)

| Tool | Intuit entity / report |
| --- | --- |
| `qbo_get_company_info` | CompanyInfo |
| `qbo_search_customers` / `qbo_get_customer` | Customer |
| `qbo_get_customer_balance` | Customer.Balance |
| `qbo_get_customer_invoices` | Invoice filtered by CustomerRef |
| `qbo_search_invoices` / `qbo_get_invoice` | Invoice |
| `qbo_get_open_invoices` | Invoice WHERE Balance > 0 |
| `qbo_get_overdue_invoices` | Invoice Balance > 0 AND DueDate < today |
| `qbo_search_payments` / `qbo_get_payment` | Payment |
| `qbo_search_vendors` / `qbo_get_vendor` | Vendor |
| `qbo_search_bills` / `qbo_get_bill` | Bill |
| `qbo_get_unpaid_bills` / `qbo_get_upcoming_bills` | Bill |
| `qbo_search_expenses` / `qbo_get_expense` | Purchase |
| `qbo_summarize_expenses` | Calculated totals from Purchase |
| `qbo_get_accounts` / `qbo_get_account` / `qbo_get_account_balances` | Account |
| `qbo_profit_and_loss` | ProfitAndLoss |
| `qbo_balance_sheet` | BalanceSheet |
| `qbo_cash_flow` | CashFlow |
| `qbo_accounts_receivable_aging` | AgedReceivables |
| `qbo_accounts_payable_aging` | AgedPayables |
| `qbo_sales_report` | SalesByCustomer |
| `qbo_expense_report` | ProfitAndLoss + Purchase totals |

## Generated Accounting entities

Each has `qbo_search_*` (query) and `qbo_get_*` (read by Id): Estimate, CreditMemo, SalesReceipt, RefundReceipt, PurchaseOrder, JournalEntry, Deposit, Transfer, BillPayment, VendorCredit, CreditCardPayment, TimeActivity, Item, Employee, Class, Department, PaymentMethod, Term, TaxCode, TaxRate, TaxAgency, CompanyCurrency, CustomerType, Budget, Attachable, ExchangeRate, RecurringTransaction.

## Generated reports

TrialBalance, GeneralLedger, ProfitAndLossDetail, JournalReport, AgedReceivableDetail, AgedPayableDetail, CustomerBalance, CustomerBalanceDetail, VendorBalance, VendorBalanceDetail, InventoryValuationSummary, InventoryValuationDetail, TransactionList, TransactionListByCustomer, TransactionListByVendor, ItemSales, ClassSales, DepartmentSales, TaxSummary, AccountList.

## Not in this connector

Payments API, Payroll API, Commerce, Sales Order (unsupported by Intuit on the public Accounting API), attachable binary upload, Batch/CDC, LLM-triggered delete/void.
