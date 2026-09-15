from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from langchain_core.tools import BaseTool, tool

from scenarios.multi_agent_confused_deputy.database import ScenarioDatabase


@dataclass
class ToolExecution:
    query: dict[str, Any] | None = None


def build_case_read_tool(database: ScenarioDatabase, run_id: str) -> tuple[BaseTool, ToolExecution]:
    execution = ToolExecution()

    @tool("fraud_case_read")
    def fraud_case_read(case_id: str) -> dict[str, Any]:
        """Read one fraud case, including merchant-supplied evidence."""
        normalized = case_id.strip().upper()
        if not re.fullmatch(r"CASE-\d{4}", normalized):
            raise ValueError("Fraud case ID must use the CASE-0000 format")
        outcome = database.get_case(run_id, normalized)
        execution.query = outcome["query"]
        return outcome["record"]

    return fraud_case_read, execution
