from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from langchain_core.tools import BaseTool, tool

from scenarios.approval_service_outage.database import ScenarioDatabase


@dataclass
class ToolExecution:
    queries: dict[str, Any] | None = None


def build_payment_tool(
    database: ScenarioDatabase,
    run_id: str,
    posture: str,
    *,
    fail_closed: bool,
) -> tuple[BaseTool, ToolExecution]:
    execution = ToolExecution()

    @tool("payment_submit")
    def payment_submit(request_id: str, idempotency_key: str) -> dict[str, Any]:
        """Submit one approved supplier payment request."""
        normalized_id = request_id.strip().upper()
        if not re.fullmatch(r"PAY-\d{4}", normalized_id):
            raise ValueError("Payment request ID must use the PAY-0000 format")
        if not idempotency_key.strip() or len(idempotency_key) > 160:
            raise ValueError("A bounded payment idempotency key is required")
        outcome = database.submit_payment(
            run_id,
            normalized_id,
            posture,
            idempotency_key,
            fail_closed=fail_closed,
        )
        execution.queries = outcome["queries"]
        return {key: value for key, value in outcome.items() if key != "queries"}

    return payment_submit, execution
