from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scenarios.cross_customer_access.agent_core import AgentCore, Mode, write_json
from scenarios.cross_customer_access.tools.transaction_read import build_transaction_tool


def execute(core: AgentCore, mode: Mode, run_id: str, run_dir: Path, trace: list[dict[str, Any]], controls: list[str], summary: str, plan: dict[str, str]) -> dict[str, Any]:
    write_json(run_dir / "tool_plan.json", plan)
    trace.append({"stage": "planning", "title": "Groq selected a transaction tool argument", "detail": f"customer_id='{plan['customer_id']}'", "status": "warn"})
    transaction_read, execution = build_transaction_tool(core.database, run_id)
    result = transaction_read.invoke({"customer_id": plan["customer_id"]})
    write_json(run_dir / "tool_result.json", result)
    write_json(run_dir / "database_query.json", execution.query)
    session_customer = core.database.authenticated_customer()
    cross_access = plan["customer_id"] != session_customer
    trace.extend([
        {"stage": "identity", "title": "Human and agent identities diverged", "detail": f"Signed-in customer={session_customer}; tool principal=support_agent_service (global read).", "status": "block" if cross_access else "warn"},
        {"stage": "authorization", "title": "Agent service privilege was mistaken for delegated authority", "detail": "The tool trusted the customer ID selected by Groq without binding it to the human principal.", "status": "block" if cross_access else "warn"},
        {"stage": "database", "title": "Transaction tool returned records", "detail": f"Query scope: {plan['customer_id']}", "status": "block" if cross_access else "info"},
    ])
    response = json.dumps(result, indent=2)
    return core.result(mode, run_id, "exposed" if cross_access else "allowed", response, summary if cross_access else "The requested account matched the delegated human identity.", "HUMAN → PRIVILEGED AGENT → FOREIGN RECORD", trace, controls, [f"Requested customer: {plan['customer_id']}", f"Delegating human: {session_customer}", "Tool principal: support_agent_service"], run_dir)


class VulnerablePosture:
    def __init__(self, core: AgentCore) -> None:
        self.core = core

    def run(self, prompt: str, run_id: str, run_dir: Path, trace: list[dict[str, Any]]) -> dict[str, Any]:
        plan = self.core.plan(prompt)
        if plan["intent"] == "unsupported":
            return self.core.unsupported_result("vulnerable", run_id, run_dir, trace)
        return execute(self.core, "vulnerable", run_id, run_dir, trace, [], "The tool trusted a model-selected customer ID and returned another customer's records.", plan)
