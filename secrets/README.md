# Secrets directory

Create these files with mode 600. Never commit the values.

| File | Contents |
| --- | --- |
| `sandbox_client_id` | Intuit Development Client ID |
| `sandbox_client_secret` | Intuit Development Client Secret |
| `production_client_id` | Intuit Production Client ID (live companies) |
| `production_client_secret` | Intuit Production Client Secret |
| `adapter_token` | Shared secret Hermes MCP → this connector |
| `operator_token` | Shared secret for CLI OAuth start / approve / execute |

Generate tokens with `openssl rand -hex 32`. Copy `adapter_token` to the Hermes host as `QBO_ADAPTER_TOKEN_FILE`.
