from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scenarios.overpowered_data_tool.agent_core import AgentCore, Mode, write_json
from scenarios.overpowered_data_tool.security import exposed_fields
from scenarios.overpowered_data_tool.tools.customer_read import build_customer_read_tool


def execute_return_direct(
    core: AgentCore,
    mode: Mode,
    prompt: str,
    run_id: str,
    run_dir: Path,
    trace: list[dict[str, Any]],
    controls: list[str],
    summary: str,
) -> dict[str, Any]:
    """Execute the deliberately unsafe tool path shared by two teaching modes."""
    plan = core.plan(prompt)
    if plan.get("intent") == "unsupported":
        return core.unsupported_result(mode, run_id, run_dir, trace)
    write_json(run_dir / "tool_plan.json", plan)

    requested_fields = plan["fields"]
    trace.append(
        {
            "stage": "planning",
            "title": "Groq planned customer.read",
            "detail": (
                f"Customer={plan['customer_name']}; "
                f"fields={', '.join(requested_fields)}"
            ),
            "status": "warn",
        }
    )

    available_fields = set(core.database.available_fields())
    authorized_fields = [
        field for field in requested_fields if field in available_fields
    ]
    denied_fields = [
        field for field in requested_fields if field not in available_fields
    ]
    trace.append(
        {
            "stage": "authorization",
            "title": "No field restriction applied",
            "detail": (
                f"Allowed={', '.join(authorized_fields) or 'none'}; "
                f"denied={', '.join(denied_fields) or 'none'}"
            ),
            "status": "block",
        }
    )

    tool_result: dict[str, Any] = {}
    query: dict[str, Any] | None = None
    if authorized_fields:
        customer_read, execution = build_customer_read_tool(
            core.database,
            run_id,
            available_fields,
        )
        tool_result = customer_read.invoke(
            {
                "customer_name": plan["customer_name"],
                "fields": authorized_fields,
            }
        )
        query = execution.query

    write_json(run_dir / "tool_result.json", tool_result)
    write_json(run_dir / "database_query.json", query)
    trace.append(
        {
            "stage": "database",
            "title": (
                "LangChain @tool customer_read executed"
                if query
                else "Database query skipped"
            ),
            "detail": (
                "Scenario database returned: "
                f"{', '.join(tool_result) or 'no fields'}"
            ),
            "status": "block",
        }
    )

    leaked_fields = exposed_fields(
        list(tool_result),
        core.database.sensitive_fields(),
    )
    trace.append(
        {
            "stage": "return-direct",
            "title": "Raw database result became the response",
            "detail": (
                "Sensitive fields exposed: "
                f"{', '.join(leaked_fields) or 'none'}"
            ),
            "status": "block" if leaked_fields else "warn",
        }
    )

    evidence = [
        f"Database: {core.database.path.name}",
        f"Requested fields: {', '.join(requested_fields)}",
        f"Denied fields: {', '.join(denied_fields) or 'none'}",
    ]
    return core.result(
        run_id=run_id,
        mode=mode,
        verdict="exposed" if leaked_fields else "allowed",
        response=json.dumps(tool_result, indent=2),
        summary=summary,
        badge="LANGCHAIN PLAN → @TOOL → SQLITE RETURN-DIRECT",
        trace=trace,
        controls=controls,
        evidence=evidence,
        run_dir=run_dir,
    )


class VulnerablePosture:
    """No guard and no field-level authorization."""

    def __init__(self, core: AgentCore) -> None:
        self.core = core

    def run(
        self,
        prompt: str,
        run_id: str,
        run_dir: Path,
        trace: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return execute_return_direct(
            core=self.core,
            mode="vulnerable",
            prompt=prompt,
            run_id=run_id,
            run_dir=run_dir,
            trace=trace,
            controls=[],
            summary=(
                "Groq selected the fields, SQLite supplied the values, "
                "and the unsafe return-direct tool exposed its raw result."
            ),
        )
