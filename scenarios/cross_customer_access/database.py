from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from core.sqlite import connect as connect_sqlite

SCENARIO_ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE_PATH = SCENARIO_ROOT / "_data" / "cross_customer_access.sqlite3"


class CustomerNotFound(LookupError):
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
            rows = connection.execute(
                "SELECT field_name, description, classification, sensitive FROM field_catalog ORDER BY rowid"
            ).fetchall()
        return [{**dict(row), "access": "session-scoped"} for row in rows]

    def session_authority(self, session_id: str = "demo-session") -> dict[str, str]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT principal, customer_id FROM session_context WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            raise CustomerNotFound("No authenticated customer session is available")
        return {"principal": str(row["principal"]), "customer_id": str(row["customer_id"])}

    def authenticated_customer(self, session_id: str = "demo-session") -> str:
        return self.session_authority(session_id)["customer_id"]

    def authorize_customer_read(
        self,
        requested_customer_id: str,
        session_id: str = "demo-session",
    ) -> dict[str, Any]:
        authority = self.session_authority(session_id)
        with self.connect() as connection:
            policy = connection.execute(
                "SELECT effect, transformation FROM access_policy "
                "WHERE principal = ? AND resource = ? AND purpose = ? AND action = ? "
                "ORDER BY id LIMIT 1",
                (authority["principal"], "transaction", "account_support", "read"),
            ).fetchone()
        allowed = bool(
            policy
            and policy["effect"] == "allow"
            and policy["transformation"] == "session_customer_scope"
            and requested_customer_id == authority["customer_id"]
        )
        return {
            **authority,
            "requested_customer_id": requested_customer_id,
            "allowed": allowed,
            "policy_effect": str(policy["effect"]) if policy else "deny",
            "transformation": str(policy["transformation"]) if policy else "none",
        }

    def query_transactions(self, run_id: str, customer_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        statement = (
            "SELECT transaction_id, description, amount, currency, direction "
            "FROM transactions WHERE customer_id = ? ORDER BY transaction_id"
        )
        with self.connect() as connection:
            rows = connection.execute(statement, (customer_id,)).fetchall()
            if not rows:
                raise CustomerNotFound(f"No transactions matched customer {customer_id!r}")
            connection.execute(
                "INSERT INTO audit_log(run_id, event, detail) VALUES (?, ?, ?)",
                (run_id, "transactions.read", json.dumps({"customer_id": customer_id})),
            )
        return [dict(row) for row in rows], {"statement": statement, "parameters": [customer_id]}

    def record_event(self, run_id: str, event: str, detail: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO audit_log(run_id, event, detail) VALUES (?, ?, ?)",
                (run_id, event, json.dumps(detail)),
            )

    def health(self) -> dict[str, Any]:
        with self.connect() as connection:
            customers = connection.execute("SELECT count(*) FROM customers").fetchone()[0]
            transactions = connection.execute("SELECT count(*) FROM transactions").fetchone()[0]
        return {
            "path": str(self.path.relative_to(SCENARIO_ROOT.parent.parent)),
            "customers": customers,
            "transactions": transactions,
        }
