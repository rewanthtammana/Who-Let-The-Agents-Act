from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.tools import BaseTool, tool

from scenarios.indirect_injection.database import ScenarioDatabase


@dataclass
class ToolExecution:
    query: dict[str, Any] | None = None


def build_invoice_read_tool(database: ScenarioDatabase, run_id: str) -> tuple[BaseTool, ToolExecution]:
    execution = ToolExecution()

    @tool("invoice_read")
    def invoice_read(invoice_id: str) -> dict[str, Any]:
        """Read one invoice and its retrieved vendor document."""
        outcome = database.get_invoice(run_id, invoice_id)
        execution.query = outcome["query"]
        return outcome["record"]

    return invoice_read, execution
