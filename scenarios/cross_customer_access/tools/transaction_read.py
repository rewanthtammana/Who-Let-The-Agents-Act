from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.tools import BaseTool, tool

from scenarios.cross_customer_access.database import ScenarioDatabase


@dataclass
class ToolExecution:
    query: dict[str, Any] | None = None


def build_transaction_tool(
    database: ScenarioDatabase,
    run_id: str,
    bound_customer_id: str | None = None,
) -> tuple[BaseTool, ToolExecution]:
    execution = ToolExecution()

    @tool("transaction_read")
    def transaction_read(customer_id: str) -> list[dict[str, Any]]:
        """Read recent transactions for one customer."""
        if bound_customer_id is not None and customer_id != bound_customer_id:
            raise ValueError("transaction_read received a customer outside session scope")
        result, execution.query = database.query_transactions(run_id, customer_id)
        return result

    return transaction_read, execution
