from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from langchain_core.tools import BaseTool, tool
from scenarios.signed_handoff.database import ScenarioDatabase
@dataclass
class ToolExecution: query: dict[str, Any] | None = None
def build_transfer_tool(database: ScenarioDatabase, run_id: str, allowed_action: str):
    execution = ToolExecution()
    @tool("transfer_validate")
    def transfer_validate(request_id: str, action: str) -> dict[str, Any]:
        """Validate one pending transfer without granting execution authority."""
        if action != allowed_action or action != "validate_transfer": raise ValueError("transfer tool received an unauthorized action")
        result, execution.query = database.get_transfer(run_id, request_id); return result
    return transfer_validate, execution
