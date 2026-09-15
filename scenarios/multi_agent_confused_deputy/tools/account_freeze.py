from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from langchain_core.tools import BaseTool, tool

from scenarios.multi_agent_confused_deputy.database import ScenarioDatabase


@dataclass
class ToolExecution:
    queries: dict[str, Any] | None = None


def build_account_freeze_tool(
    database: ScenarioDatabase,
    run_id: str,
    posture: str,
    *,
    enforce_policy: bool,
) -> tuple[BaseTool, ToolExecution]:
    execution = ToolExecution()

    @tool("account_freeze")
    def account_freeze(case_id: str, target_account_id: str) -> dict[str, Any]:
        """Freeze a bank account as a fraud-case action."""
        normalized_case = case_id.strip().upper()
        normalized_account = target_account_id.strip().upper()
        if not re.fullmatch(r"CASE-\d{4}", normalized_case):
            raise ValueError("Fraud case ID must use the CASE-0000 format")
        if not re.fullmatch(r"A\d{3}", normalized_account):
            raise ValueError("Account ID must use the A000 format")
        outcome = database.freeze_account(
            run_id,
            normalized_case,
            normalized_account,
            posture,
            enforce_policy=enforce_policy,
        )
        execution.queries = outcome["queries"]
        return {key: value for key, value in outcome.items() if key != "queries"}

    return account_freeze, execution
