from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scenarios.cross_customer_access.agent_core import AgentCore, write_json
from scenarios.cross_customer_access.tools.transaction_read import build_transaction_tool
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
        requested = plan["customer_id"]
        decision = self.core.database.authorize_customer_read(requested)
        authenticated = decision["customer_id"]
        trace.extend([
            {"stage": "planning", "title": "Groq selected a customer ID", "detail": f"Requested={requested}", "status": "info"},
            {"stage": "identity", "title": "Delegating human identity resolved", "detail": f"Principal={decision['principal']}; authenticated customer={authenticated}", "status": "pass"},
        ])
        if not decision["allowed"]:
            trace.extend([
                {"stage": "authorization", "title": "Delegated authority did not cover the requested account", "detail": f"The agent may act only for {authenticated}; {requested} was refused rather than silently substituted.", "status": "block"},
                {"stage": "tool", "title": "Transaction tool was not called", "detail": "Foreign records never entered agent context.", "status": "pass"},
            ])
            response = self.core.model.complete(
                self.core.hardened_response_prompt,
                "Application authorization decision: denied. No transaction records were read.",
            )
            trace.append({"stage": "response", "title": "Model explained the enforced denial", "detail": "The response model received only the policy decision and no foreign records.", "status": "pass"})
            return self.core.result("hardened", run_id, "contained", response, "The application bound the agent's authority to the delegating human before data access.", "DELEGATED HUMAN AUTHORITY", trace, ["human-to-agent identity binding", "object-level authorization", "pre-tool denial"], [f"Requested customer: {requested}", f"Authorized customer: {authenticated}", "Database reads: 0"], run_dir)
        trace.append({"stage": "authorization", "title": "Database policy matched delegated authority", "detail": f"effect={decision['policy_effect']}; transformation={decision['transformation']}", "status": "pass"})
        transaction_read, execution = build_transaction_tool(self.core.database, run_id, bound_customer_id=authenticated)
        result = transaction_read.invoke({"customer_id": authenticated})
        write_json(run_dir / "tool_result.json", result)
        write_json(run_dir / "database_query.json", execution.query)
        trace.append({"stage": "database", "title": "Scoped transaction query executed", "detail": "WHERE customer_id = authenticated_session_customer", "status": "pass"})
        response = self.core.model.complete(self.core.hardened_response_prompt, f"User request:\n{prompt}\n\nAuthorized transaction records:\n{json.dumps(result)}")
        trace.append({"stage": "response", "title": "Response used authorized records only", "detail": "The requested customer ID did not control the database scope.", "status": "pass"})
        return self.core.result("hardened", run_id, "allowed", response, "Database-backed policy enforced delegated human authority before querying SQLite.", "HUMAN-BOUND AGENT AUTHORITY", trace, ["database-backed delegation policy", "object-level authorization", "parameterized scoped query"], [f"Requested customer: {requested}", f"Authorized customer: {authenticated}", "Foreign records returned: 0"], run_dir)
