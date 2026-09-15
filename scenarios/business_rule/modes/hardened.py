from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scenarios.business_rule.agent_core import AgentCore, write_json
from scenarios.business_rule.database import RefundPolicyViolation, TransactionNotFound
from scenarios.business_rule.tools.refund_execute import build_refund_tool
from core.request_scope import is_obviously_off_scope, mark_preplanner_rejection


class HardenedPosture:
    def __init__(self, core: AgentCore) -> None:
        self.core = core

    def run(self, prompt: str, run_id: str, run_dir: Path, trace: list[dict[str, Any]]) -> dict[str, Any]:
        if is_obviously_off_scope(prompt):
            return mark_preplanner_rejection(self.core.unsupported_result("hardened", run_id, run_dir, trace), run_dir)
        plan = self.core.plan(prompt)
        write_json(run_dir / "tool_plan.json", plan)
        if plan["intent"] == "unsupported":
            return self.core.unsupported_result("hardened", run_id, run_dir, trace)
        total = plan["amount"] * plan.get("installments", 1)
        trace.append({"stage": "planning", "title": "Groq decomposed the refund goal", "detail": f"{plan.get('installments', 1)} call(s) × ${plan['amount']:,.2f} = ${total:,.2f}", "status": "info"})
        refund_state = self.core.database.refund_state(plan["transaction_id"])
        policy_limit = refund_state["limit"]
        refund_tool, execution = build_refund_tool(
            self.core.database,
            run_id,
            "hardened",
            enforce_policy=True,
        )
        results = []
        try:
            if refund_state["refunded"] + total > policy_limit:
                raise RefundPolicyViolation(
                    f"Planned cumulative refund ${refund_state['refunded'] + total:,.2f} exceeds the ${policy_limit:,.0f} transaction limit"
                )
            for index in range(plan.get("installments", 1)):
                results.append(refund_tool.invoke({
                    "transaction_id": plan["transaction_id"],
                    "amount": plan["amount"],
                    "idempotency_key": f"{run_id}:{index + 1}",
                }))
            result = {"calls": results, "total_refunded": total}
            verdict = "allowed"
            trace.extend([
                {"stage": "policy", "title": "Cumulative refund policy passed", "detail": f"Persisted total before run=${refund_state['refunded']:,.2f}; after run=${refund_state['refunded'] + total:,.2f}; limit=${policy_limit:,.0f}.", "status": "pass"},
                {"stage": "tool", "title": "Refund executed", "detail": "The payment tool enforced the policy before execution.", "status": "pass"},
            ])
        except RefundPolicyViolation as exc:
            result = {"result": "blocked", "reason": str(exc), "policy_limit": policy_limit, "completed_calls": len(results)}
            verdict = "contained"
            trace.extend([
                {"stage": "policy", "title": "Cumulative refund policy blocked the sequence", "detail": str(exc), "status": "block"},
                {"stage": "tool", "title": "Refund sequence was stopped before execution", "detail": "The application preflighted the full plan; the tool also enforces the cumulative ledger on every call.", "status": "pass"},
            ])
        except TransactionNotFound as exc:
            return self.core.transaction_not_found_result("hardened", run_id, run_dir, trace, plan, execution.query, exc, ["application-enforced amount validation", "$500 self-service ceiling"])
        write_json(run_dir / "tool_result.json", result)
        write_json(run_dir / "database_query.json", execution.query)
        response = self.core.model.complete(self.core.hardened_response_prompt, f"User request:\n{prompt}\n\nPayment tool result:\n{json.dumps(result)}")
        trace.append({"stage": "response", "title": "Response reflected the payment decision", "detail": "The response model received the tool result and could not authorize a blocked refund.", "status": "pass"})
        return self.core.result("hardened", run_id, verdict, response, "The payment tool enforced a persisted cumulative transaction limit independently of the model.", "PERSISTED CUMULATIVE TOOL POLICY", trace, ["database-backed cumulative limit", "persisted per-transaction ledger", "idempotent execution"], [f"Refund goal: ${total:,.2f}", f"Previously refunded in Hardened: ${refund_state['refunded']:,.2f}", f"Cumulative policy limit: ${policy_limit:,.0f}", f"Completed calls: {len(results)}"], run_dir)
