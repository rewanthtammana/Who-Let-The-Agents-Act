from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scenarios.overpowered_data_tool.agent_core import AgentCore, write_json
from scenarios.overpowered_data_tool.security import build_pii_middleware, redacted_fields
from scenarios.overpowered_data_tool.tools.customer_read import build_customer_read_tool
from core.request_scope import is_obviously_off_scope, mark_preplanner_rejection


class HardenedPosture:
    """Application authorization and DLP remain authoritative."""

    def __init__(self, core: AgentCore) -> None:
        self.core = core

    def run(
        self,
        prompt: str,
        run_id: str,
        run_dir: Path,
        trace: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if is_obviously_off_scope(prompt):
            return mark_preplanner_rejection(self.core.unsupported_result("hardened", run_id, run_dir, trace), run_dir)
        plan = self.core.plan(prompt)
        write_json(run_dir / "tool_plan.json", plan)
        if plan.get("intent") == "unsupported":
            return self.core.unsupported_result("hardened", run_id, run_dir, trace)

        candidates, candidate_query = self.core.database.customer_candidates(plan["customer_name"])
        write_json(run_dir / "identity_candidates.json", candidates)
        write_json(run_dir / "identity_query.json", candidate_query)
        if len(candidates) > 1:
            return self.core.ambiguous_customer_result(
                "hardened", run_id, run_dir, trace, candidates
            )

        requested_fields = plan["fields"]
        trace.append(
            {
                "stage": "planning",
                "title": "Groq planned customer.read",
                "detail": (
                    f"Customer={plan['customer_name']}; "
                    f"fields={', '.join(requested_fields)}"
                ),
                "status": "info",
            }
        )

        authorized_policy_fields = self.core.database.authorized_fields(
            principal="support_agent",
            resource="customer",
            purpose="support_case",
            action="read",
        )
        authorized_fields = [
            field for field in requested_fields if field in authorized_policy_fields
        ]
        denied_fields = [
            field for field in requested_fields if field not in authorized_policy_fields
        ]
        trace.append(
            {
                "stage": "authorization",
                "title": "Application policy filtered tool arguments",
                "detail": (
                    f"Allowed={', '.join(authorized_fields) or 'none'}; "
                    f"denied={', '.join(denied_fields) or 'none'}"
                ),
                "status": "pass",
            }
        )

        tool_result: dict[str, Any] = {}
        query: dict[str, Any] | None = None
        if authorized_fields:
            customer_read, execution = build_customer_read_tool(
                self.core.database,
                run_id,
                authorized_policy_fields,
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
                "status": "pass",
            }
        )

        response = self.core.model.complete(
            self.core.hardened_response_prompt,
            (
                f"User request:\n{prompt}\n\n"
                "Authorized customer.read result:\n"
                f"{json.dumps(tool_result, indent=2)}\n\n"
                f"Denied fields:\n{json.dumps(denied_fields)}"
            ),
            middleware=build_pii_middleware(denied_fields),
        )
        middleware_redactions = redacted_fields(response, denied_fields)

        trace.extend(
            [
                {
                    "stage": "model",
                    "title": "Groq received authorized data only",
                    "detail": "Denied fields never entered model context.",
                    "status": "pass",
                },
                {
                    "stage": "output-dlp",
                    "title": "LangChain PII middleware completed",
                    "detail": (
                        "Redacted fields: "
                        f"{', '.join(middleware_redactions) or 'none'}"
                    ),
                    "status": "pass",
                },
            ]
        )

        evidence = [
            f"Database: {self.core.database.path.name}",
            f"Requested fields: {', '.join(requested_fields)}",
            f"Denied fields: {', '.join(denied_fields) or 'none'}",
        ]
        return self.core.result(
            run_id=run_id,
            mode="hardened",
            verdict=(
                "contained"
                if denied_fields or middleware_redactions
                else "allowed"
            ),
            response=response,
            summary=(
                "Groq answered from the database projection enforced by "
                "application policy; output DLP remained authoritative."
            ),
            badge="LANGCHAIN AGENT + APPLICATION DLP",
            trace=trace,
            controls=[
                "database-backed role/purpose/field policy",
                "server-side field projection",
                "LangChain PII middleware",
            ],
            evidence=evidence,
            run_dir=run_dir,
        )
