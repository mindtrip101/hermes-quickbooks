#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE = os.environ.get("QBO_BASE", "http://127.0.0.1:14112")


def token() -> str:
    explicit = os.environ.get("QBO_OPERATOR_TOKEN_FILE")
    if explicit:
        path = Path(explicit)
    else:
        path = Path(os.environ.get("QBO_SECRETS_DIR", "./secrets")) / "operator_token"
    return path.read_text().strip()


def call(method: str, path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = Request(BASE + path, data=data, method=method)
    req.add_header("Accept", "application/json")
    req.add_header("X-QBO-Operator-Token", token())
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"ok": False, "errors": [f"http_{exc.code}"], "body": raw[:300]}
        payload.setdefault("http_status", exc.code)
        return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Operator CLI for hermes-qbo. Cannot be invoked by Hermes tools.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("health")
    auth = sub.add_parser("auth-url")
    auth.add_argument("--tenant", default="company_a")
    approvals = sub.add_parser("approvals")
    approvals.add_argument("--status", default="pending")
    decide = sub.add_parser("approve")
    decide.add_argument("action_id")
    decide.add_argument("--user", required=True)
    decide.add_argument("--execute", action="store_true")
    reject = sub.add_parser("reject")
    reject.add_argument("action_id")
    reject.add_argument("--user", required=True)
    execute = sub.add_parser("execute")
    execute.add_argument("action_id")
    execute.add_argument("--user", required=True)
    imported = sub.add_parser("import-tokens")
    imported.add_argument("--tenant", default="company_a")
    args = parser.parse_args()
    if args.cmd == "health":
        print(json.dumps(call("GET", "/health"), indent=2))
        return
    if args.cmd == "auth-url":
        print(json.dumps(call("GET", "/v1/oauth/start?" + urlencode({"tenant_id": args.tenant})), indent=2))
        return
    if args.cmd == "import-tokens":
        raw = json.loads(sys.stdin.read())
        if not isinstance(raw, dict):
            raise SystemExit("import-tokens expects a JSON object on stdin")
        raw["tenant_id"] = args.tenant
        print(json.dumps(call("POST", "/v1/oauth/import", raw), indent=2))
        return
    if args.cmd == "approvals":
        print(json.dumps(call("GET", "/v1/approvals?" + urlencode({"status": args.status})), indent=2))
        return
    if args.cmd == "approve":
        payload = call("POST", f"/v1/approvals/{args.action_id}/decision", {"decision": "approved", "user": args.user})
        if args.execute:
            payload = call("POST", f"/v1/approvals/{args.action_id}/execute", {"user": args.user})
        print(json.dumps(payload, indent=2))
        return
    if args.cmd == "reject":
        print(json.dumps(call("POST", f"/v1/approvals/{args.action_id}/decision", {"decision": "rejected", "user": args.user}), indent=2))
        return
    if args.cmd == "execute":
        print(json.dumps(call("POST", f"/v1/approvals/{args.action_id}/execute", {"user": args.user}), indent=2))


if __name__ == "__main__":
    main()
