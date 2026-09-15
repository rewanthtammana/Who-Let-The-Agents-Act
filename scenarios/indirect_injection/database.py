from __future__ import annotations

import json
import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from core.sqlite import connect as connect_sqlite

SCENARIO_ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE_PATH = SCENARIO_ROOT / "_data" / "indirect_injection.sqlite3"


class InvoiceNotFound(LookupError):
    pass


class BeneficiaryNotAuthorized(ValueError):
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
            placeholder = connection.execute(
                "SELECT document_sha256 FROM invoices WHERE invoice_id = 'INV-884'"
            ).fetchone()
        if placeholder and placeholder["document_sha256"] == "seed-placeholder":
            self.load_fixture("clean")

    def field_catalog(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT field_name, description, classification, sensitive FROM field_catalog ORDER BY rowid").fetchall()
        access = {
            "document_text": "untrusted",
            "approved_beneficiary": "trusted",
            "document_sha256": "provenance",
            "document_variant": "provenance",
        }
        return [{**dict(row), "access": access.get(row["field_name"], "allow")} for row in rows]

    def invoice_context(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT invoice_id, amount_due, currency, approved_beneficiary, document_text, "
                "document_filename, document_variant, document_sha256, document_version, document_updated_at "
                "FROM invoices ORDER BY invoice_id"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_invoice(self, run_id: str, invoice_id: str) -> dict[str, Any]:
        statement = (
            "SELECT invoice_id, amount_due, currency, approved_beneficiary, document_text, "
            "document_filename, document_variant, document_sha256, document_version, document_updated_at "
            "FROM invoices WHERE invoice_id = ?"
        )
        with self.connect() as connection:
            row = connection.execute(statement, (invoice_id,)).fetchone()
            if row is None:
                raise InvoiceNotFound(f"No invoice matched {invoice_id!r}")
            connection.execute("INSERT INTO audit_log(run_id, event, detail) VALUES (?, ?, ?)", (run_id, "invoice.read", json.dumps({"invoice_id": invoice_id})))
        return {"record": dict(row), "query": {"statement": statement, "parameters": [invoice_id]}}

    def replace_document(
        self,
        invoice_id: str,
        document_text: str,
        filename: str,
        variant: str = "uploaded",
    ) -> dict[str, Any]:
        """Attach vendor text to a known invoice without changing trusted fields."""
        if not document_text.strip():
            raise ValueError("The uploaded invoice is empty")
        if len(document_text.encode("utf-8")) > 1_000_000:
            raise ValueError("The uploaded invoice is larger than 1 MB after text extraction")
        normalized_id = invoice_id.strip().upper()
        document_hash = hashlib.sha256(document_text.encode("utf-8")).hexdigest()
        safe_filename = Path(filename).name[:200]
        with self.connect() as connection:
            updated = connection.execute(
                "UPDATE invoices SET document_text = ?, document_filename = ?, document_variant = ?, "
                "document_sha256 = ?, document_version = document_version + 1, "
                "document_updated_at = CURRENT_TIMESTAMP WHERE invoice_id = ?",
                (document_text, safe_filename, variant, document_hash, normalized_id),
            ).rowcount
            if not updated:
                raise InvoiceNotFound(f"No invoice matched {invoice_id!r}")
            connection.execute("INSERT INTO audit_log(run_id, event, detail) VALUES (?, ?, ?)", (f"upload-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}", "invoice.upload", json.dumps({"invoice_id": normalized_id, "filename": safe_filename, "variant": variant, "sha256": document_hash})))
            version = connection.execute(
                "SELECT document_version FROM invoices WHERE invoice_id = ?",
                (normalized_id,),
            ).fetchone()[0]
        return {
            "invoice_id": normalized_id,
            "filename": safe_filename,
            "variant": variant,
            "sha256": document_hash,
            "version": int(version),
            "characters": len(document_text),
        }

    def load_fixture(self, variant: str) -> dict[str, Any]:
        fixtures = {
            "clean": "default_invoice.txt",
            "attack": "malicious_invoice.txt",
            "bypass": "malicious_invoice_approved_test.txt",
        }
        if variant not in fixtures:
            raise ValueError("Unknown invoice fixture")
        filename = fixtures[variant]
        return self.replace_document(
            "INV-884",
            (SCENARIO_ROOT / filename).read_text(encoding="utf-8"),
            filename,
            variant,
        )

    def reset_runtime(self) -> dict[str, Any]:
        fixture = self.load_fixture("clean")
        with self.connect() as connection:
            connection.execute("DELETE FROM audit_log")
        return fixture

    def submit_payment(self, run_id: str, invoice_id: str, amount: float, beneficiary: str, approved_only: bool = False) -> dict[str, Any]:
        invoice = self.get_invoice(run_id, invoice_id)["record"]
        if approved_only and (
            beneficiary != invoice["approved_beneficiary"]
            or amount != float(invoice["amount_due"])
        ):
            raise BeneficiaryNotAuthorized(
                f"Payment details are not approved for {invoice_id}"
            )
        connection_detail = {"invoice_id": invoice_id, "amount": amount, "beneficiary": beneficiary}
        self.record_event(run_id, "payment.submit", connection_detail)
        return {"invoice_id": invoice_id, "amount": amount, "currency": invoice["currency"], "beneficiary": beneficiary, "status": "submitted"}

    def record_event(self, run_id: str, event: str, detail: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute("INSERT INTO audit_log(run_id, event, detail) VALUES (?, ?, ?)", (run_id, event, json.dumps(detail)))

    def health(self) -> dict[str, Any]:
        with self.connect() as connection:
            count = connection.execute("SELECT count(*) FROM invoices").fetchone()[0]
            active = connection.execute(
                "SELECT document_filename, document_variant, document_sha256, document_version "
                "FROM invoices WHERE invoice_id = 'INV-884'"
            ).fetchone()
        return {
            "path": str(self.path.relative_to(SCENARIO_ROOT.parent.parent)),
            "invoices": count,
            "active_document": dict(active) if active else None,
        }
