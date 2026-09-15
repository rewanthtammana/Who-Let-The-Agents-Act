from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from core.sqlite import connect as connect_sqlite

SCENARIO_ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE_PATH = SCENARIO_ROOT / "_data" / "business_rule.sqlite3"


class TransactionNotFound(LookupError):
    pass


class RefundPolicyViolation(ValueError):
    pass


class ScenarioDatabase:
    def __init__(self, path: Path = DEFAULT_DATABASE_PATH) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = connect_sqlite(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript((SCENARIO_ROOT / "schema.sql").read_text(encoding="utf-8"))
            connection.executescript((SCENARIO_ROOT / "seed.sql").read_text(encoding="utf-8"))

    def field_catalog(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT field_name, description, classification, sensitive FROM field_catalog ORDER BY rowid").fetchall()
        return [{**dict(row), "access": "transaction-scoped"} for row in rows]

    def refund_limit(
        self,
        principal: str = "support_agent",
        resource: str = "refund_transaction",
        purpose: str = "refund_request",
        action: str = "execute",
    ) -> float:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT max_cumulative_amount FROM refund_policy "
                "WHERE principal = ? AND resource = ? AND purpose = ? AND action = ?",
                (principal, resource, purpose, action),
            ).fetchone()
        if row is None:
            raise RefundPolicyViolation("No refund execution policy matched this request")
        return float(row["max_cumulative_amount"])

    def refund_state(self, transaction_id: str, posture: str = "hardened") -> dict[str, float]:
        with self.connect() as connection:
            transaction = connection.execute(
                "SELECT original_amount FROM refund_transactions WHERE transaction_id = ?",
                (transaction_id,),
            ).fetchone()
            if transaction is None:
                raise TransactionNotFound(f"No transaction matched {transaction_id!r}")
            refunded = float(connection.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM refund_events WHERE posture = ? AND transaction_id = ?",
                (posture, transaction_id),
            ).fetchone()[0])
        configured_limit = self.refund_limit()
        effective_limit = min(configured_limit, float(transaction["original_amount"]))
        return {"refunded": refunded, "limit": effective_limit, "remaining": max(0.0, effective_limit - refunded)}

    def execute_refund(
        self,
        run_id: str,
        transaction_id: str,
        amount: float,
        posture: str,
        idempotency_key: str,
        enforce_policy: bool = False,
    ) -> dict[str, Any]:
        if amount <= 0:
            raise ValueError("Refund amount must be positive")
        if not idempotency_key.strip():
            raise ValueError("Refund idempotency key is required")
        statement = "SELECT transaction_id, merchant, original_amount, currency, status FROM refund_transactions WHERE transaction_id = ?"
        with self.connect() as connection:
            row = connection.execute(statement, (transaction_id,)).fetchone()
            if row is None:
                raise TransactionNotFound(f"No transaction matched {transaction_id!r}")
            existing = connection.execute(
                "SELECT transaction_id, amount FROM refund_events WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing is not None:
                if existing["transaction_id"] != transaction_id or float(existing["amount"]) != amount:
                    raise RefundPolicyViolation("The idempotency key was already used for a different refund")
                return {
                    "result": {
                        **dict(row),
                        "refund_amount": amount,
                        "result": "already_completed",
                        "idempotent_replay": True,
                    },
                    "query": {"statement": statement, "parameters": [transaction_id]},
                }
            refunded = float(connection.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM refund_events WHERE posture = ? AND transaction_id = ?",
                (posture, transaction_id),
            ).fetchone()[0])
            policy_limit = self.refund_limit() if enforce_policy else None
            effective_limit = min(policy_limit, float(row["original_amount"])) if policy_limit is not None else None
            if effective_limit is not None and refunded + amount > effective_limit:
                raise RefundPolicyViolation(
                    f"Cumulative refund ${refunded + amount:,.2f} exceeds the ${effective_limit:,.0f} transaction limit"
                )
            connection.execute(
                "INSERT INTO refund_events(run_id, transaction_id, posture, idempotency_key, amount) VALUES (?, ?, ?, ?, ?)",
                (run_id, transaction_id, posture, idempotency_key, amount),
            )
            result = {**dict(row), "refund_amount": amount, "cumulative_refund": refunded + amount, "result": "completed"}
            connection.execute("INSERT INTO audit_log(run_id, event, detail) VALUES (?, ?, ?)", (run_id, "refund.execute", json.dumps({"transaction_id": transaction_id, "amount": amount, "posture": posture, "idempotency_key": idempotency_key})))
        return {"result": result, "query": {"statement": statement, "parameters": [transaction_id]}}

    def reset_runtime(self) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM refund_events")
            connection.execute("DELETE FROM audit_log")

    def record_event(self, run_id: str, event: str, detail: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute("INSERT INTO audit_log(run_id, event, detail) VALUES (?, ?, ?)", (run_id, event, json.dumps(detail)))

    def health(self) -> dict[str, Any]:
        with self.connect() as connection:
            count = connection.execute("SELECT count(*) FROM refund_transactions").fetchone()[0]
        return {"path": str(self.path.relative_to(SCENARIO_ROOT.parent.parent)), "refund_transactions": count}
