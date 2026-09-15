from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.tools import BaseTool, tool

from scenarios.business_rule.database import ScenarioDatabase


@dataclass
class ToolExecution:
    query: dict[str, Any] | None = None


def build_refund_tool(
    database: ScenarioDatabase,
    run_id: str,
    posture: str,
    enforce_policy: bool = False,
) -> tuple[BaseTool, ToolExecution]:
    execution = ToolExecution()

    @tool("refund_execute")
    def refund_execute(transaction_id: str, amount: float, idempotency_key: str) -> dict[str, Any]:
        """Execute a refund for one payment."""
        execution.query = {
            "statement": "SELECT transaction_id, merchant, currency, status FROM refund_transactions WHERE transaction_id = ?",
            "parameters": [transaction_id],
        }
        outcome = database.execute_refund(
            run_id,
            transaction_id,
            amount,
            posture,
            idempotency_key,
            enforce_policy,
        )
        execution.query = outcome["query"]
        return outcome["result"]

    return refund_execute, execution
