from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from core.sqlite import connect as connect_sqlite
from scenarios.multi_agent_confused_deputy.security import authorization_reasons

SCENARIO_ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE_PATH = SCENARIO_ROOT / "_data" / "multi_agent_confused_deputy.sqlite3"


class FraudCaseNotFound(LookupError):
    pass


class AccountNotFound(LookupError):
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
        access = {"merchant_note": "untrusted", "note_variant": "provenance", "subject_account_id": "case-scoped"}
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT field_name, description, classification, sensitive FROM field_catalog ORDER BY rowid"
            ).fetchall()
        return [{**dict(row), "access": access.get(row["field_name"], "allow")} for row in rows]

    def get_case(self, run_id: str, case_id: str) -> dict[str, Any]:
        statement = (
            "SELECT f.case_id, f.authenticated_customer_id, f.subject_account_id, "
            "a.customer_id AS subject_customer_id, f.merchant_name, f.disputed_amount, "
            "f.currency, f.case_status, f.merchant_note, f.note_variant "
            "FROM fraud_cases f JOIN bank_accounts a ON a.account_id = f.subject_account_id "
            "WHERE f.case_id = ?"
        )
        with self.connect() as connection:
            row = connection.execute(statement, (case_id,)).fetchone()
            if row is None:
                raise FraudCaseNotFound(f"No fraud case matched {case_id!r}")
            connection.execute(
                "INSERT INTO audit_log(run_id, event, detail) VALUES (?, ?, ?)",
                (run_id, "fraud_case.read", json.dumps({"case_id": case_id})),
            )
        return {"record": dict(row), "query": {"statement": statement, "parameters": [case_id]}}

    def freeze_account(
        self,
        run_id: str,
        case_id: str,
        target_account_id: str,
        posture: str,
        *,
        enforce_policy: bool,
    ) -> dict[str, Any]:
        case_statement = (
            "SELECT f.case_id, f.authenticated_customer_id, f.subject_account_id, "
            "a.customer_id AS subject_customer_id, f.case_status "
            "FROM fraud_cases f JOIN bank_accounts a ON a.account_id = f.subject_account_id "
            "WHERE f.case_id = ?"
        )
        account_statement = "SELECT account_id, customer_id, customer_name, status FROM bank_accounts WHERE account_id = ?"
        policy_statement = (
            "SELECT effect, transformation FROM access_policy "
            "WHERE principal = ? AND resource = ? AND purpose = ? AND action = ?"
        )
        approval_statement = (
            "SELECT status, approved_account_id, reason FROM case_action_approvals "
            "WHERE case_id = ? AND action = ?"
        )
        with self.connect() as connection:
            case_row = connection.execute(case_statement, (case_id,)).fetchone()
            if case_row is None:
                raise FraudCaseNotFound(f"No fraud case matched {case_id!r}")
            policy = connection.execute(
                policy_statement,
                ("account-control-agent", "bank_account", "fraud_case", "freeze"),
            ).fetchone()
            approval_row = connection.execute(approval_statement, (case_id, "freeze")).fetchone()
            case = dict(case_row)
            approval = dict(approval_row) if approval_row else None
            reasons = authorization_reasons(case, approval, target_account_id, policy is not None and policy["effect"] == "allow")
            authorized = not enforce_policy or not reasons
            account = None
            if authorized:
                account = connection.execute(account_statement, (target_account_id,)).fetchone()
                if account is None:
                    raise AccountNotFound(f"No account matched {target_account_id!r}")
            before = connection.execute(
                "SELECT count(*) FROM account_freeze_events WHERE posture = ? AND account_id = ?",
                (posture, target_account_id),
            ).fetchone()[0]
            if authorized:
                connection.execute(
                    "INSERT INTO account_freeze_events "
                    "(run_id, case_id, account_id, posture, authorization_status) VALUES (?, ?, ?, ?, ?)",
                    (run_id, case_id, target_account_id, posture, "authorized" if enforce_policy else "unchecked"),
                )
                status = "frozen"
            else:
                status = "blocked"
            after = connection.execute(
                "SELECT count(*) FROM account_freeze_events WHERE posture = ? AND account_id = ?",
                (posture, target_account_id),
            ).fetchone()[0]
            decision = {"allowed": authorized, "reasons": reasons, "policy_enforced": enforce_policy}
            connection.execute(
                "INSERT INTO audit_log(run_id, event, detail) VALUES (?, ?, ?)",
                (run_id, "account.freeze", json.dumps({"case_id": case_id, "target_account_id": target_account_id, "status": status, **decision})),
            )
        return {
            "result": {
                "status": status,
                "case_id": case_id,
                "target_account_id": target_account_id,
                **({"account_owner": account["customer_name"]} if account is not None else {}),
            },
            "authorization": decision,
            "ledger": {"before": before, "after": after},
            "queries": {
                "case": {"statement": case_statement, "parameters": [case_id]},
                "account": {"statement": account_statement, "parameters": [target_account_id], "executed": authorized},
                "policy": {"statement": policy_statement, "parameters": ["account-control-agent", "bank_account", "fraud_case", "freeze"]},
                "approval": {"statement": approval_statement, "parameters": [case_id, "freeze"]},
            },
        }

    def registry(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT agent_id, audience, allowed_action, status FROM agent_registry ORDER BY rowid"
            ).fetchall()
        return [dict(row) for row in rows]

    def record_event(self, run_id: str, event: str, detail: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO audit_log(run_id, event, detail) VALUES (?, ?, ?)",
                (run_id, event, json.dumps(detail)),
            )

    def reset_runtime(self) -> dict[str, int]:
        with self.connect() as connection:
            connection.execute("DELETE FROM account_freeze_events")
            connection.execute("DELETE FROM audit_log")
        return {"freeze_events_cleared": 1}

    def health(self) -> dict[str, Any]:
        with self.connect() as connection:
            cases = connection.execute("SELECT count(*) FROM fraud_cases").fetchone()[0]
            freezes = connection.execute("SELECT count(*) FROM account_freeze_events").fetchone()[0]
        return {
            "path": str(self.path.relative_to(SCENARIO_ROOT.parent.parent)),
            "fraud_cases": cases,
            "freeze_events": freezes,
            "agents": len(self.registry()),
        }
