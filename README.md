# hermes-quickbooks

A connector that gives [Hermes](https://github.com/NousResearch/hermes-agent) typed tools for **Intuit QuickBooks Online** using the official QBO v3 Accounting API.

Hermes never talks to Intuit directly. This service is the security boundary: OAuth 2.0, per-agent ACL, tenant isolation, local drafts, operator-only writes, and JSONL audit.

> QuickBooks Online company data is **untrusted input**. Names, memos, and descriptions are data, never instructions.

## What it covers

Implements the [QuickBooks Online Accounting API](https://developer.intuit.com/app/developer/qbo/docs/learn/explore-the-quickbooks-online-api) (REST JSON, `minorversion=75`):

- Name lists: Customer, Vendor, Account, Item, Employee, Class, Department, Term, PaymentMethod, TaxCode, TaxRate, TaxAgency, CustomerType, CompanyCurrency
- Sales: Invoice, Payment, Estimate, CreditMemo, SalesReceipt, RefundReceipt
- Purchasing: Bill, BillPayment, VendorCredit, Purchase (QBO has **no Expense entity**), PurchaseOrder
- Banking / journals: Deposit, Transfer, CreditCardPayment, JournalEntry
- Other: TimeActivity, Budget, Attachable (metadata), ExchangeRate, RecurringTransaction, Preferences, CompanyInfo
- Reports: ProfitAndLoss, BalanceSheet, CashFlow, TrialBalance, GeneralLedger, aging, sales, inventory, tax, transaction lists

**Out of scope:** Intuit Payments (cards), Payroll, Commerce, and Sales Order (not in the public Accounting API). LLM-initiated production writes stay gated.

Full mapping: [docs/INTUIT_API.md](docs/INTUIT_API.md). Agent playbook: [skills/hermes-quickbooks/SKILL.md](skills/hermes-quickbooks/SKILL.md). Hermes wiring: [docs/HERMES.md](docs/HERMES.md).

## Requirements

- Docker (or Python 3.12+)
- An Intuit Developer account and a QuickBooks Online app
- A Hermes agent (or any MCP client) to call the tools
- A browser for the one-time OAuth consent (never type your Intuit password into the agent)

---

## 1. Create an Intuit Developer account and app

Official docs:

- Get started: https://developer.intuit.com/app/developer/qbo/docs/get-started
- OAuth 2.0: https://developer.intuit.com/app/developer/qbo/docs/develop/authentication-and-authorization/oauth-2.0
- Create an app: https://developer.intuit.com/app/developer/qbo/docs/get-started/start-developing-with-the-quickbooks-online-accounting-api

### Account

1. Open [https://developer.intuit.com](https://developer.intuit.com) and sign in with an Intuit account (the same login you use for QuickBooks Online is fine).
2. Accept the developer terms if prompted.
3. Open **My Apps** (or **Dashboard** → **Apps**).

### App

1. Click **Create an app**.
2. Choose **QuickBooks Online and Payments**.
3. Name the app something you will recognize on the consent screen (this name is shown to the company admin).
4. Under APIs, select **Com.intuit.quickbooks.accounting** only. Do not add Payments unless you separately intend to process cards.
5. Save the app.

You now have two key sets on the app:

| Tab | What it can access | Typical use |
| --- | --- | --- |
| **Development** → Keys & OAuth | Intuit **sandbox sample companies** only | First connection and tests |
| **Production** → Keys & OAuth | **Live** QuickBooks Online companies | Real books after sandbox works |

Development Client ID/Secret cannot read a live company. Production keys cannot be used against sandbox sample companies.

## 2. Generate keys and register the redirect URI

Open the app → **Keys & credentials** (or **Keys & OAuth**).

### Development (sandbox)

1. Copy **Client ID** and **Client Secret**. Treat the secret like a password. Do not commit it, paste it into chat, or put it in Hermes prompts.
2. Under **Redirect URIs**, add exactly:

   `http://localhost:14112/oauth/callback`

   Rules from Intuit:

   - Use the hostname `localhost`, not `127.0.0.1` (IP addresses are rejected).
   - Match the URI character-for-character with `QBO_REDIRECT_URI` (no extra trailing slash).
   - Development allows `http://localhost`. Production does not.

3. Scopes: `com.intuit.quickbooks.accounting`.

### Production (live company)

1. Complete Intuit’s production app requirements if the Production tab is locked (app details, terms, sometimes a review). Then copy the **Production** Client ID and Client Secret. They are different from Development.
2. Production redirect URIs must be **HTTPS hostnames**. `http://localhost` is typically rejected.
3. A supported option is Intuit’s OAuth 2.0 Playground redirect:

   `https://developer.intuit.com/v2/OAuth2Playground/RedirectUrl`

   Add that exact URI on the Production Keys & OAuth tab, and set `QBO_REDIRECT_URI` to the same value. After consent you copy the `code` and `realmId` from the playground and import them with `qbo import-tokens`.

4. One Intuit login can own multiple QBO companies. The consent screen lets you pick which company to connect. Authorize **once per company / tenant**.

## 3. Install this connector

```sh
git clone https://github.com/YOUR_GITHUB_USERNAME/hermes-quickbooks.git
cd hermes-quickbooks
cp config/tenants.example.yaml config/tenants.yaml
cp .env.example .env
mkdir -p secrets data
chmod 700 secrets data
```

Create secret files (mode `600`). Values go in the files, never in git:

```sh
install -m 600 /dev/stdin secrets/sandbox_client_id      # paste Development Client ID, then Ctrl-D
install -m 600 /dev/stdin secrets/sandbox_client_secret  # paste Development Client Secret, then Ctrl-D
install -m 600 /dev/stdin secrets/production_client_id     # optional until you connect a live company
install -m 600 /dev/stdin secrets/production_client_secret
openssl rand -hex 32 | install -m 600 /dev/stdin secrets/adapter_token
openssl rand -hex 32 | install -m 600 /dev/stdin secrets/operator_token
```

Edit `config/tenants.yaml` (display names only; no secrets) and `config/permissions.yaml` (which Hermes agent ids may read/draft).

Start the service:

```sh
docker compose up -d --build
curl -sS http://127.0.0.1:14112/health
```

Run tests without Docker:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

## 4. Connect QuickBooks (browser OAuth)

Never send your Intuit password to Hermes or to this connector. Authorization happens in **your browser**.

### Sandbox (Development keys)

1. Confirm `QBO_REDIRECT_URI=http://localhost:14112/oauth/callback` and that this URI is registered on the Development tab.
2. Export the operator token and request an authorize URL:

```sh
export QBO_SECRETS_DIR="$PWD/secrets"
python3 src/hermes_qbo/cli.py auth-url --tenant company_a
```

3. Open `authorize_url` from the JSON in a browser. Sign in at Intuit if asked. Pick a **sandbox sample company**. Approve Accounting access.
4. Intuit redirects to `http://localhost:14112/oauth/callback`. You should see “QuickBooks company connected.”
5. Confirm: `python3 src/hermes_qbo/cli.py health` → `oauth: valid` and a company name.

Access tokens last about 60 minutes. Refresh tokens last about 100 days and **rotate**; the connector stores each new refresh token under `data/tenants/<id>/tokens.json`. If refresh fails, tools return `reauthorization_required` instead of failing silently.

### Live company (Production keys)

1. Put Production Client ID/Secret in `secrets/production_client_id` and `secrets/production_client_secret`.
2. Register and set `QBO_REDIRECT_URI` to your HTTPS redirect (Playground URI is supported).
3. Restart the container so it reloads secrets.
4. Run `auth-url` for that tenant. On the Intuit picker, choose the **live** company, not a sandbox sample.
5. If you used the Playground redirect, copy `code`, `realmId`, and tokens from the playground and import:

```sh
python3 src/hermes_qbo/cli.py import-tokens --tenant company_a <<'EOF'
{"realm_id":"1234567890","access_token":"...","refresh_token":"...","environment":"production","expires_in":3600}
EOF
```

6. Repeat with a different tenant id for a second company. The same realm cannot be attached to two tenants.

Production writes stay held until you explicitly set `QBO_ALLOW_PRODUCTION_WRITES=true`. Default is `false`.

## 5. Give Hermes the tools

See [docs/HERMES.md](docs/HERMES.md) for `config.yaml` snippets. Minimum:

- Copy `mcp/qbo_mcp.py` onto the Hermes host.
- Copy `secrets/adapter_token` to the path `QBO_ADAPTER_TOKEN_FILE`.
- Register MCP servers `quickbooks` (desktop/API) and optionally `quickbooks_telegram`.
- Set `tools.include` to the connector tool list (`GET /v1/tool-schemas` after the service is up).
- Put [skills/hermes-quickbooks/SKILL.md](skills/hermes-quickbooks/SKILL.md) where the agent can read it (Hermes skills/context directory, or a Cursor project skill).

Agent identity is the MCP **environment** (`QBO_AGENT_ID`), never a tool argument.

## 6. Operator approval (writes)

Draft tools (`qbo_create_*_draft`) store a **local** proposal. QuickBooks Online has no API draft/non-posting invoice state. `posted_to_quickbooks` is always `false` until an operator runs execute.

```sh
python3 src/hermes_qbo/cli.py approvals
python3 src/hermes_qbo/cli.py reject ACTION_ID --user operator
python3 src/hermes_qbo/cli.py approve ACTION_ID --user operator
python3 src/hermes_qbo/cli.py execute ACTION_ID --user operator   # sandbox, or production if writes are enabled
```

There is no `qbo_approve` MCP tool. The approving user must not equal the requesting agent id.

## Environment variables

| Name | Default | Meaning |
| --- | --- | --- |
| `QUICKBOOKS_ENV` | `sandbox` | Default API host if a tenant has no token environment yet |
| `QBO_ALLOW_PRODUCTION_WRITES` | `false` | Must be true **and** operator execute to POST to a live company |
| `QBO_BIND` / `QBO_PORT` | `0.0.0.0` / `14112` | Bind inside the container; compose publishes `127.0.0.1:14112` |
| `QBO_DATA_DIR` | `/data` | Tokens, approvals SQLite, audit JSONL |
| `QBO_SECRETS_DIR` | `/secrets` | Client id/secret, adapter token, operator token |
| `QBO_CONFIG_DIR` | `/app/config` | `permissions.yaml`, `tenants.yaml` |
| `QBO_REDIRECT_URI` | `http://localhost:14112/oauth/callback` | Must match the Intuit app exactly |
| `QBO_MINOR_VERSION` | `75` | QBO Accounting minor version |

## Security model

- LLM is not the security boundary.
- Adapter token authenticates Hermes → connector. Operator token authenticates CLI approve/execute/OAuth start.
- Per-agent read/draft/write ACL and per-tenant allowlists.
- Query compiler allowlists entities and fields (no raw SQL from the model).
- Secrets stay on disk mode `600`. Tokens are never returned in health or tool envelopes.

## License

MIT. QuickBooks and Intuit are trademarks of Intuit Inc. This project is not affiliated with Intuit.
