from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from core.sqlite import connect as connect_sqlite

SCENARIO_ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE_PATH = SCENARIO_ROOT / "_data" / "secret_leakage.sqlite3"


class ScenarioDatabase:
    def __init__(self, path: Path = DEFAULT_DATABASE_PATH) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = connect_sqlite(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript((SCENARIO_ROOT / "schema.sql").read_text(encoding="utf-8"))
            connection.executescript((SCENARIO_ROOT / "seed.sql").read_text(encoding="utf-8"))

    def field_catalog(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT field_name, description, classification, sensitive FROM field_catalog ORDER BY rowid").fetchall()
        return [{**dict(row), "access": "allow" if not row["sensitive"] else "deny"} for row in rows]

    def read_diagnostics(self, run_id: str, include_environment: bool) -> dict[str, Any]:
        fields = "provider, status, upstream_timeout, environment_secret" if include_environment else "provider, status, upstream_timeout"
        with self.connect() as connection:
            row = connection.execute(f"SELECT {fields} FROM diagnostics WHERE id = 1").fetchone()
            connection.execute("INSERT INTO audit_log(run_id, event, detail) VALUES (?, ?, ?)", (run_id, "diagnostics.read", json.dumps({"include_environment": include_environment})))
        return {"record": dict(row), "query": {"statement": f"SELECT {fields} FROM diagnostics WHERE id = 1", "parameters": []}}

    def record_event(self, run_id: str, event: str, detail: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute("INSERT INTO audit_log(run_id, event, detail) VALUES (?, ?, ?)", (run_id, event, json.dumps(detail)))

    def action_allowed(
        self,
        action: str,
        principal: str = "support_agent",
        resource: str = "incident_report",
        purpose: str = "incident_response",
    ) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT effect, transformation FROM access_policy "
                "WHERE principal = ? AND resource = ? AND purpose = ? AND action = ? "
                "ORDER BY id LIMIT 1",
                (principal, resource, purpose, action),
            ).fetchone()
        return bool(row and row["effect"] == "allow" and row["transformation"] == "redact_secrets")

    def health(self) -> dict[str, Any]:
        return {"path": str(self.path.relative_to(SCENARIO_ROOT.parent.parent)), "diagnostics": 1}
