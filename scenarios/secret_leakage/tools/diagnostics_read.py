from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.tools import BaseTool, tool

from scenarios.secret_leakage.database import ScenarioDatabase


@dataclass
class ToolExecution:
    query: dict[str, Any] | None = None


def build_diagnostics_tool(database: ScenarioDatabase, run_id: str, allow_secrets: bool) -> tuple[BaseTool, ToolExecution]:
    execution = ToolExecution()

    @tool("diagnostics_read")
    def diagnostics_read(include_environment: bool = False) -> dict[str, Any]:
        """Read payment provider diagnostics."""
        result = database.read_diagnostics(run_id, include_environment and allow_secrets)
        execution.query = result["query"]
        return result["record"]

    return diagnostics_read, execution
