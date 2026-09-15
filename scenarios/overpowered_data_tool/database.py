from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any
from core.sqlite import connect as connect_sqlite

SCENARIO_ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE_PATH = SCENARIO_ROOT / "_data" / "overpowered_data_tool.sqlite3"
SAFE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")


class CustomerNotFound(LookupError):
    pass


class ScenarioDatabase:
    def __init__(self, path: Path = DEFAULT_DATABASE_PATH) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        connection = connect_sqlite(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript((SCENARIO_ROOT / "schema.sql").read_text(encoding="utf-8"))
            connection.executescript((SCENARIO_ROOT / "seed.sql").read_text(encoding="utf-8"))

    def field_catalog(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT field_name, description, classification, sensitive, mask_strategy "
                "FROM field_catalog ORDER BY rowid"
            ).fetchall()
            policies = connection.execute(
                "SELECT field_name FROM access_policy "
                "WHERE principal = 'support_agent' AND resource = 'customer' "
                "AND purpose = 'support_case' AND action = 'read' AND effect = 'allow'"
            ).fetchall()
        allowed = {row["field_name"] for row in policies}
        return [{**dict(row), "access": "allow" if row["field_name"] in allowed else "deny"} for row in rows]

    def available_fields(self) -> list[str]:
        return [item["field_name"] for item in self.field_catalog()]

    def authorized_fields(
        self,
        principal: str = "support_agent",
        resource: str = "customer",
        purpose: str = "support_case",
        action: str = "read",
    ) -> set[str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT field_name FROM access_policy "
                "WHERE principal = ? AND resource = ? AND purpose = ? "
                "AND action = ? AND effect = 'allow'",
                (principal, resource, purpose, action),
            ).fetchall()
        return {row["field_name"] for row in rows}

    def sensitive_fields(self) -> set[str]:
        return {item["field_name"] for item in self.field_catalog() if item["sensitive"]}

    def customer_candidates(self, customer_name: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
        """Resolve a name to safe identity candidates before protected reads."""
        statement = (
            "SELECT customer_id, name FROM customers "
            "WHERE lower(name) = lower(?) OR lower(name) LIKE lower(?) "
            "ORDER BY CASE WHEN lower(name) = lower(?) THEN 0 ELSE 1 END, name"
        )
        parameters = (customer_name, f"%{customer_name}%", customer_name)
        with self.connect() as connection:
            rows = connection.execute(statement, parameters).fetchall()
        return [dict(row) for row in rows], {"statement": statement, "parameters": list(parameters)}

    def query_customer(self, run_id: str, customer_name: str, fields: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
        allowed = set(self.available_fields())
        selected = list(dict.fromkeys(fields))
        if not selected or any(field not in allowed or not SAFE_IDENTIFIER.fullmatch(field) for field in selected):
            raise ValueError("customer.read received an invalid field projection")

        projection = ", ".join(f'"{field}"' for field in selected)
        statement = (
            f"SELECT {projection} FROM customers "
            "WHERE lower(name) = lower(?) OR lower(name) LIKE lower(?) "
            "ORDER BY CASE WHEN lower(name) = lower(?) THEN 0 ELSE 1 END LIMIT 1"
        )
        parameters = (customer_name, f"%{customer_name}%", customer_name)
        with self.connect() as connection:
            row = connection.execute(statement, parameters).fetchone()
            if row is None:
                raise CustomerNotFound(f"No customer matched {customer_name!r}")
            result = dict(row)
            connection.execute(
                "INSERT INTO audit_log(run_id, event, detail) VALUES (?, ?, ?)",
                (run_id, "customer.read", json.dumps({"customer_name": customer_name, "fields": selected})),
            )
        return result, {"statement": statement, "parameters": [customer_name, f"%{customer_name}%", customer_name]}

    def record_event(self, run_id: str, event: str, detail: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO audit_log(run_id, event, detail) VALUES (?, ?, ?)",
                (run_id, event, json.dumps(detail)),
            )

    def health(self) -> dict[str, Any]:
        with self.connect() as connection:
            customer_count = connection.execute("SELECT count(*) FROM customers").fetchone()[0]
            field_count = connection.execute("SELECT count(*) FROM field_catalog").fetchone()[0]
        return {
            "path": str(self.path.relative_to(SCENARIO_ROOT.parent.parent)),
            "customers": customer_count,
            "fields": field_count,
        }
