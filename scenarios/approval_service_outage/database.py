from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from core.sqlite import connect as connect_sqlite
from scenarios.approval_service_outage.security import resolve_payment_authorization

SCENARIO_ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE_PATH = SCENARIO_ROOT / "_data" / "approval_service_outage.sqlite3"


class PaymentRequestNotFound(LookupError):
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
        return [{**dict(row), "access": "payment-scoped"} for row in rows]

    def dependency_status(self) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT service_name, state, timeout_ms, updated_at FROM dependency_state WHERE service_name = ?",
                ("payment-approval-service",),
            ).fetchone()
        if row is None:
            raise RuntimeError("Approval service fixture is not configured")
        return {**dict(row), "simulated": True}

    def set_dependency_state(self, state: str) -> dict[str, Any]:
        if state not in {"healthy", "timeout"}:
            raise ValueError("Dependency state must be healthy or timeout")
        with self.connect() as connection:
            connection.execute(
                "UPDATE dependency_state SET state = ?, updated_at = CURRENT_TIMESTAMP WHERE service_name = ?",
                (state, "payment-approval-service"),
            )
        return self.dependency_status()

    def submit_payment(
        self,
        run_id: str,
        request_id: str,
        posture: str,
        idempotency_key: str,
        *,
        fail_closed: bool,
    ) -> dict[str, Any]:
        request_statement = (
            "SELECT request_id, supplier, amount, currency, status "
            "FROM payment_requests WHERE request_id = ?"
        )
        policy_statement = (
            "SELECT r.decision, r.reason FROM approval_rules r "
            "JOIN access_policy p ON p.principal = ? AND p.resource = ? "
            "AND p.purpose = ? AND p.action = ? AND p.effect = 'allow' "
            "WHERE r.request_id = ?"
        )
        with self.connect() as connection:
            request = connection.execute(request_statement, (request_id,)).fetchone()
            if request is None:
                raise PaymentRequestNotFound(f"No payment request matched {request_id!r}")
            existing = connection.execute(
                "SELECT fallback_action FROM payment_events WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing is not None:
                return {
                    "request": dict(request),
                    "service": self.dependency_status(),
                    "authorization": {"decision": "approved", "reason": "Idempotent replay"},
                    "payment": {"status": "already_executed", "fallback_action": existing["fallback_action"]},
                    "ledger": {"before": 1, "after": 1},
                    "queries": {"request": {"statement": request_statement, "parameters": [request_id]}},
                }

            service = connection.execute(
                "SELECT service_name, state, timeout_ms FROM dependency_state WHERE service_name = ?",
                ("payment-approval-service",),
            ).fetchone()
            if service is None:
                raise RuntimeError("Approval service fixture is not configured")

            approval = None
            if service["state"] == "healthy":
                approval = connection.execute(
                    policy_statement,
                    ("payment_agent", "supplier_payment", "accounts_payable", "submit", request_id),
                ).fetchone()

            decision = approval["decision"] if approval is not None else None
            reason = approval["reason"] if approval is not None else f"No decision: simulated timeout after {service['timeout_ms']} ms"
            ledger_before = connection.execute(
                "SELECT count(*) FROM payment_events WHERE posture = ? AND request_id = ?",
                (posture, request_id),
            ).fetchone()[0]

            authorized, fallback_action = resolve_payment_authorization(
                decision,
                dependency_state=service["state"],
                fail_closed=fail_closed,
            )

            if authorized:
                connection.execute(
                    "INSERT INTO payment_events "
                    "(run_id, request_id, posture, idempotency_key, amount, authorization_decision, dependency_state, fallback_action) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (run_id, request_id, posture, idempotency_key, request["amount"], decision, service["state"], fallback_action),
                )
                payment = {"status": "executed", "fallback_action": fallback_action}
            elif decision is None:
                connection.execute(
                    "INSERT INTO pending_payments (run_id, request_id, posture, reason) VALUES (?, ?, ?, ?)",
                    (run_id, request_id, posture, reason),
                )
                payment = {"status": "queued", "fallback_action": fallback_action}
            else:
                payment = {"status": "blocked", "fallback_action": fallback_action}

            ledger_after = connection.execute(
                "SELECT count(*) FROM payment_events WHERE posture = ? AND request_id = ?",
                (posture, request_id),
            ).fetchone()[0]
            audit_detail = {
                "request_id": request_id,
                "posture": posture,
                "dependency_state": service["state"],
                "authorization_decision": decision,
                "fallback_action": fallback_action,
                "payment_status": payment["status"],
            }
            connection.execute(
                "INSERT INTO audit_log(run_id, event, detail) VALUES (?, ?, ?)",
                (run_id, "payment.submit", json.dumps(audit_detail)),
            )

        return {
            "request": dict(request),
            "service": {**dict(service), "simulated": True},
            "authorization": {"decision": decision, "reason": reason},
            "payment": payment,
            "ledger": {"before": ledger_before, "after": ledger_after},
            "queries": {
                "request": {"statement": request_statement, "parameters": [request_id]},
                "approval": {
                    "statement": policy_statement,
                    "parameters": ["payment_agent", "supplier_payment", "accounts_payable", "submit", request_id],
                    "executed": service["state"] == "healthy",
                },
            },
        }

    def record_event(self, run_id: str, event: str, detail: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO audit_log(run_id, event, detail) VALUES (?, ?, ?)",
                (run_id, event, json.dumps(detail)),
            )

    def reset_runtime(self) -> dict[str, Any]:
        with self.connect() as connection:
            connection.execute("DELETE FROM payment_events")
            connection.execute("DELETE FROM pending_payments")
            connection.execute("DELETE FROM audit_log")
            connection.execute(
                "UPDATE dependency_state SET state = 'healthy', updated_at = CURRENT_TIMESTAMP WHERE service_name = ?",
                ("payment-approval-service",),
            )
        return {"dependency": self.dependency_status(), "payments_cleared": True}

    def health(self) -> dict[str, Any]:
        with self.connect() as connection:
            count = connection.execute("SELECT count(*) FROM payment_requests").fetchone()[0]
            executed = connection.execute("SELECT count(*) FROM payment_events").fetchone()[0]
            queued = connection.execute("SELECT count(*) FROM pending_payments").fetchone()[0]
        return {
            "path": str(self.path.relative_to(SCENARIO_ROOT.parent.parent)),
            "payment_requests": count,
            "executed_payments": executed,
            "queued_payments": queued,
            "dependency": self.dependency_status(),
        }
