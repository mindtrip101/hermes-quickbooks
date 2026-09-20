from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATUSES = ("pending", "approved", "rejected", "executed", "failed", "expired")


class ApprovalError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ApprovalStore:
    def __init__(self, path: Path, ttl_seconds: int = 7 * 24 * 3600):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS actions (
                    id TEXT PRIMARY KEY,
                    ts TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    tenant TEXT NOT NULL,
                    realm TEXT,
                    action_type TEXT NOT NULL,
                    risk TEXT NOT NULL,
                    params_json TEXT NOT NULL,
                    description TEXT NOT NULL,
                    estimated_impact TEXT,
                    status TEXT NOT NULL,
                    approving_user TEXT,
                    executed_ts TEXT,
                    qbo_object_id TEXT,
                    result_json TEXT,
                    requestid TEXT,
                    expires_at REAL NOT NULL
                )
                """
            )
            conn.commit()

    def create(
        self,
        *,
        agent: str,
        tenant: str,
        realm: str | None,
        action_type: str,
        risk: str,
        params: dict[str, Any],
        description: str,
        estimated_impact: str | None = None,
        requestid: str | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        action_id = str(uuid.uuid4())
        requestid = requestid or action_id.replace("-", "")[:50]
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO actions (
                    id, ts, agent, tenant, realm, action_type, risk, params_json, description,
                    estimated_impact, status, requestid, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    action_id,
                    now,
                    agent,
                    tenant,
                    realm,
                    action_type,
                    risk,
                    json.dumps(params),
                    description,
                    estimated_impact,
                    requestid,
                    time.time() + self.ttl_seconds,
                ),
            )
            conn.commit()
        return self.get(action_id)

    def get(self, action_id: str) -> dict[str, Any]:
        self.expire()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
        if not row:
            raise ApprovalError("not_found")
        return self._row(row)

    def list(self, status: str | None = None, tenant: str | None = None) -> list[dict[str, Any]]:
        self.expire()
        sql = "SELECT * FROM actions"
        clauses = []
        args: list[Any] = []
        if status:
            clauses.append("status = ?")
            args.append(status)
        if tenant:
            clauses.append("tenant = ?")
            args.append(tenant)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY ts DESC LIMIT 100"
        with self._connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [self._row(row) for row in rows]

    def pending_count(self) -> int:
        self.expire()
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM actions WHERE status = 'pending'").fetchone()
        return int(row["n"] if row else 0)

    def decide(self, action_id: str, *, decision: str, user: str, agent: str | None = None) -> dict[str, Any]:
        if decision not in {"approved", "rejected"}:
            raise ApprovalError("invalid_decision")
        if not user:
            raise ApprovalError("operator_user_required")
        action = self.get(action_id)
        if user == action["agent"] or (agent and user == agent):
            raise ApprovalError("self_approve_forbidden")
        if action["status"] == "expired":
            raise ApprovalError("expired")
        if action["status"] != "pending":
            raise ApprovalError("not_pending")
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE actions SET status = ?, approving_user = ? WHERE id = ?",
                (decision, user, action_id),
            )
            conn.commit()
        return self.get(action_id)

    def mark_executed(self, action_id: str, *, qbo_object_id: str | None, result: dict[str, Any], status: str = "executed") -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE actions
                SET status = ?, executed_ts = ?, qbo_object_id = ?, result_json = ?
                WHERE id = ?
                """,
                (status, datetime.now(timezone.utc).isoformat(), qbo_object_id, json.dumps(result), action_id),
            )
            conn.commit()
        return self.get(action_id)

    def expire(self) -> None:
        now = time.time()
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE actions SET status = 'expired' WHERE status = 'pending' AND expires_at < ?",
                (now,),
            )
            conn.commit()

    def _row(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["params"] = json.loads(data.pop("params_json"))
        result = data.pop("result_json")
        data["result"] = json.loads(result) if result else None
        return data
