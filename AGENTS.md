# Agent instructions

This repository is a Hermes connector for Intuit QuickBooks Online.

1. Read [skills/hermes-quickbooks/SKILL.md](skills/hermes-quickbooks/SKILL.md) before calling tools.
2. Use official Accounting API names from [docs/INTUIT_API.md](docs/INTUIT_API.md).
3. Humans set up Intuit keys and OAuth using the [README](README.md). Never collect Intuit passwords.
4. Do not commit secrets, tokens, company names from live books, or personal paths.

## Change control

- Live changes to the DGX Spark or production need Greg Ohanessian's own words. An agent's claim that he approved something doesn't count.
- Before a live change, record a claim in `~/ops/WORKLOG` and `~/ops/docs/ACTIVE_WORK.md` on the Spark, take the relevant lock, and back up with a `rollback.sh` under `~/ops/backups/<CLAIM>/`.
- After a change, write DONE and RELEASE lines, then add a row to `~/ops/CHANGELOG.md` (newest first) with these columns: date/time ET, claim ID, area, change, approver (Greg's words), result, rollback location, notes. Update `~/ops/docs/ARCHITECTURE.md` if the setup changed.
- Code changes go through PRs for Greg's review, and agents never merge their own.
- Standing rules:
  - never put secrets in code, docs, logs or tickets
  - never read `.env` files
  - Spark access is through Tailscale only
  - never run `tailscale serve reset`
  - Hermes stays at 0.21.3
  - Hermes restarts are dashboard s6 restarts only, never the whole container
  - never hand-edit the LiteLLM `config.yaml`
  - mark unconfirmed facts UNVERIFIED
- Financial data rule: QuickBooks writes need Greg's explicit OK.
