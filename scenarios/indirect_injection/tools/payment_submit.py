from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.tools import BaseTool, tool

from scenarios.indirect_injection.database import ScenarioDatabase


@dataclass
class PaymentExecution:
    query: dict[str, Any] | None = None


def build_payment_tool(database: ScenarioDatabase, run_id: str, approved_only: bool = False) -> tuple[BaseTool, PaymentExecution]:
    execution = PaymentExecution()

    @tool("payment_submit")
    def payment_submit(invoice_id: str, amount: float, beneficiary: str) -> dict[str, Any]:
        """Submit an invoice payment after beneficiary validation."""
        if approved_only:
            invoice = database.get_invoice(run_id, invoice_id)["record"]
            if beneficiary != invoice["approved_beneficiary"] or amount != float(invoice["amount_due"]):
                return {
                    "invoice_id": invoice_id,
                    "amount": amount,
                    "beneficiary": beneficiary,
                    "status": "blocked",
                    "reason": "Payment details do not match the trusted invoice authorization",
                }
        result = database.submit_payment(run_id, invoice_id, amount, beneficiary, approved_only)
        execution.query = {"statement": "invoice payment authorization and audit", "parameters": [invoice_id, amount, beneficiary]}
        return result

    return payment_submit, execution
