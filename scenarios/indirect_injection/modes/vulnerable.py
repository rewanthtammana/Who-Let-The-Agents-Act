from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scenarios.indirect_injection.agent_core import AgentCore, write_json
from scenarios.indirect_injection.tools.invoice_read import build_invoice_read_tool
from scenarios.indirect_injection.tools.payment_submit import build_payment_tool


def execute(core: AgentCore, mode: str, run_id: str, run_dir: Path, trace: list[dict[str, Any]], controls: list[str], plan: dict[str, Any], summary: str) -> dict[str, Any]:
    write_json(run_dir / "tool_plan.json", plan)
    read_tool, read_execution = build_invoice_read_tool(core.database, run_id)
    invoice = read_tool.invoke({"invoice_id": plan["invoice_id"]})
    write_json(run_dir / "invoice_result.json", invoice)
    write_json(run_dir / "invoice_query.json", read_execution.query)
    trace.append({"stage": "retrieval", "title": "Invoice document retrieved", "detail": "Vendor-controlled text entered the agent flow as untrusted content.", "status": "warn"})
    action = core.decide_action(plan.get("user_prompt", ""), invoice)
    write_json(run_dir / "observation_action_plan.json", action)
    trace.append({"stage": "replanning", "title": "Agent reconsidered its plan after the tool observation", "detail": action["reason"], "status": "block" if action["requested_action"] == "pay" else "info"})
    if action["requested_action"] == "pay":
        payment_tool, payment_execution = build_payment_tool(core.database, run_id)
        result = payment_tool.invoke({"invoice_id": plan["invoice_id"], "amount": action["amount"], "beneficiary": action["destination"]})
        write_json(run_dir / "payment_result.json", result)
        write_json(run_dir / "payment_query.json", payment_execution.query)
        trace.extend([
            {"stage": "planning", "title": "Model treated document content as an action", "detail": f"Payment destination={action['destination']}; amount=${action['amount']:,.2f}", "status": "block"},
            {"stage": "tool", "title": "Payment submitted without beneficiary policy", "detail": "The vulnerable payment tool accepted the document-proposed destination.", "status": "block"},
        ])
        return core.result(mode, run_id, "exposed", json.dumps(result, indent=2), summary, "TOOL OBSERVATION → REPLAN → PAYMENT", trace, controls, ["Document: poisoned", f"Beneficiary: {action['destination']}", "Tool authorization: absent"], run_dir)
    trace.append({"stage": "response", "title": "Read-only invoice result returned", "detail": "No payment action was requested.", "status": "info"})
    return core.result(mode, run_id, "allowed", json.dumps(invoice, indent=2), "The invoice was reviewed without a side effect.", "INVOICE RETRIEVAL → RAW RESULT", trace, controls, ["Document: retrieved", "Payment tool calls: 0"], run_dir)


class VulnerablePosture:
    def __init__(self, core: AgentCore) -> None:
        self.core = core

    def run(self, prompt: str, run_id: str, run_dir: Path, trace: list[dict[str, Any]]) -> dict[str, Any]:
        plan = self.core.plan(prompt)
        if plan["intent"] == "unsupported":
            return self.core.unsupported_result("vulnerable", run_id, run_dir, trace)
        plan["user_prompt"] = prompt
        return execute(self.core, "vulnerable", run_id, run_dir, trace, [], plan, "The agent replanned from a poisoned tool observation and submitted its payment.")
