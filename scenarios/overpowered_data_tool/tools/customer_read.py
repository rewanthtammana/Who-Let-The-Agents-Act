from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.tools import BaseTool, tool

from scenarios.overpowered_data_tool.database import ScenarioDatabase


@dataclass
class ToolExecution:
    result: dict[str, Any] | None = None
    query: dict[str, Any] | None = None


def build_customer_read_tool(
    database: ScenarioDatabase,
    run_id: str,
    allowed_fields: set[str],
) -> tuple[BaseTool, ToolExecution]:
    """Create a per-run customer.read tool with an application field boundary."""
    execution = ToolExecution()

    @tool("customer_read")
    def customer_read(customer_name: str, fields: list[str]) -> dict[str, Any]:
        """Read selected fields for one customer from the scenario SQLite database."""
        selected_fields = list(dict.fromkeys(fields))
        outside_policy = any(
            field not in allowed_fields for field in selected_fields
        )
        if not selected_fields or outside_policy:
            raise ValueError(
                "customer_read tool received a field outside application policy"
            )

        result, query = database.query_customer(
            run_id,
            customer_name,
            selected_fields,
        )
        execution.result = result
        execution.query = query
        return result

    return customer_read, execution
