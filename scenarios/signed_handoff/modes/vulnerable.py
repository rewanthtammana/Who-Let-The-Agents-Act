from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from scenarios.signed_handoff.agent_core import AgentCore, Mode, write_json
from scenarios.signed_handoff.database import ScenarioDatabase

def execute(core: AgentCore, mode: Mode, prompt: str, run_id: str, run_dir: Path, trace: list[dict[str, Any]], controls: list[str], summary: str):
    plan = core.plan(prompt); write_json(run_dir / "handoff_plan.json", plan)
    if plan["intent"] == "unsupported": return core.unsupported_result(run_id, mode, run_dir, trace)
    trace.append({"stage": "planning", "title": "Groq planned an agent handoff", "detail": f"Request={plan['request_id']}; action={plan['requested_action']}; context={', '.join(plan['context_fields']) or 'none'}", "status": "warn"})
    transfer, query = core.database.get_transfer(run_id, plan["request_id"])
    raw_context = {**transfer, **core.database.secret_context(plan["request_id"]), "execution_authority": plan["requested_action"]}
    requested_context = set(plan["context_fields"])
    context_aliases = {"transcript": "support_transcript", "reset_token": "password_reset_token", "authority": "execution_authority"}
    requested_context.update(context_aliases.get(field, field) for field in requested_context)
    sensitive_requested = {field: raw_context[field] for field in ("support_transcript", "password_reset_token", "execution_authority") if field in requested_context}
    full_context = {**transfer, **sensitive_requested}
    handoff = {"sender": "support-router", "audience": "transfer-specialist", "payload": full_context}
    write_json(run_dir / "handoff_payload.json", handoff); write_json(run_dir / "database_query.json", query)
    leaked = [key for key in ("password_reset_token", "support_transcript", "execution_authority") if key in full_context]
    trace.extend([
        {"stage": "handoff", "title": "Router forwarded the handoff context", "detail": "Secrets and execution authority crossed the agent boundary." if leaked else "Only the requested transfer context was forwarded for this normal request.", "status": "block" if leaked else "info"},
        {"stage": "specialist", "title": "Specialist trusted the incoming authority", "detail": "No sender signature, audience binding, or independent scope check was applied.", "status": "block" if leaked else "warn"},
    ])
    actual_summary = summary if leaked else "The specialist validated the transfer from the requested handoff context; no sensitive fields were forwarded for this normal request."
    return core.result(run_id, mode, "exposed" if leaked else "allowed", json.dumps(full_context, indent=2), actual_summary, "ROUTER → UNSIGNED HANDOFF → SPECIALIST", trace, controls, [f"Database: {core.database.path.name}", f"Forwarded fields: {', '.join(full_context)}"], run_dir)
class VulnerablePosture:
    def __init__(self, core): self.core = core
    def run(self, prompt, run_id, run_dir, trace): return execute(self.core, "vulnerable", prompt, run_id, run_dir, trace, [], "The router copied its privileged context into the specialist handoff, exposing secrets and authority.")
