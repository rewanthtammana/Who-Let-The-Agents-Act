from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scenarios.approval_service_outage.agent_core import AgentCore, Mode, write_json
from scenarios.approval_service_outage.database import PaymentRequestNotFound
from scenarios.approval_service_outage.tools.payment_submit import build_payment_tool


def execute_unsafe(
    core: AgentCore,
    mode: Mode,
    run_id: str,
    run_dir: Path,
    trace: list[dict[str, Any]],
    plan: dict[str, Any],
    controls: list[str],
) -> dict[str, Any]:
    write_json(run_dir / "tool_plan.json", plan)
    trace.append({
        "stage": "planning",
        "title": "Groq planned a supplier payment",
        "detail": f"The model selected request {plan['request_id']} for payment_submit.",
        "status": "info",
    })
    payment_tool, execution = build_payment_tool(
        core.database,
        run_id,
        mode,
        fail_closed=False,
    )
    try:
        result = payment_tool.invoke({
            "request_id": plan["request_id"],
            "idempotency_key": f"{run_id}:payment",
        })
    except PaymentRequestNotFound as exc:
        return core.not_found_result(mode, run_id, run_dir, trace, plan["request_id"], exc, controls)

    write_json(run_dir / "tool_result.json", result)
    write_json(run_dir / "database_query.json", execution.queries)
    write_json(run_dir / "dependency_check.json", result["service"])
    write_json(run_dir / "authorization_decision.json", result["authorization"])
    write_json(run_dir / "payment_ledger.json", result["ledger"])
    timed_out = result["service"]["state"] == "timeout"
    unsafe_execution = timed_out and result["authorization"]["decision"] is None and result["payment"]["status"] == "executed"
    trace.extend([
        {
            "stage": "dependency",
            "title": "Approval service timed out" if timed_out else "Approval service returned a decision",
            "detail": (
                f"The simulated service returned no decision after {result['service']['timeout_ms']} ms."
                if timed_out else f"The service returned {result['authorization']['decision']}."
            ),
            "status": "block" if timed_out else "pass",
        },
        {
            "stage": "fallback",
            "title": "Missing approval was treated as ALLOW" if unsafe_execution else "Approval decision was accepted",
            "detail": "The unsafe application fallback converted infrastructure failure into authorization." if unsafe_execution else result["authorization"]["reason"],
            "status": "block" if unsafe_execution else "pass",
        },
        {
            "stage": "payment-tool",
            "title": "Payment executed without authorization" if unsafe_execution else "Payment executed with approval",
            "detail": f"Ledger rows changed from {result['ledger']['before']} to {result['ledger']['after']} for this posture and request.",
            "status": "block" if unsafe_execution else "pass",
        },
    ])
    verdict = "exposed" if unsafe_execution else "allowed"
    summary = (
        "The payment executed even though the authorization service returned no decision."
        if unsafe_execution else "The approval service returned an affirmative decision before payment execution."
    )
    evidence = [
        f"Simulated dependency state: {result['service']['state']}",
        f"Authorization decision: {result['authorization']['decision'] or 'none'}",
        f"Fallback action: {result['payment']['fallback_action']}",
        f"Payment ledger writes: {result['ledger']['after'] - result['ledger']['before']}",
    ]
    return core.result(
        mode,
        run_id,
        verdict,
        json.dumps(result, indent=2),
        summary,
        "TIMEOUT → FAIL-OPEN PAYMENT" if unsafe_execution else "APPROVED PAYMENT",
        trace,
        controls,
        evidence,
        run_dir,
    )


class VulnerablePosture:
    def __init__(self, core: AgentCore) -> None:
        self.core = core

    def run(self, prompt: str, run_id: str, run_dir: Path, trace: list[dict[str, Any]]) -> dict[str, Any]:
        plan = self.core.plan(prompt)
        if plan["intent"] == "unsupported":
            return self.core.unsupported_result("vulnerable", run_id, run_dir, trace)
        return execute_unsafe(self.core, "vulnerable", run_id, run_dir, trace, plan, [])
