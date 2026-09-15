from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from scenarios.signed_handoff.agent_core import write_json
from scenarios.signed_handoff.security import sign_envelope, verify_envelope
from scenarios.signed_handoff.tools.transfer_validate import build_transfer_tool
from core.request_scope import is_obviously_off_scope, mark_preplanner_rejection
class HardenedPosture:
    def __init__(self, core): self.core = core
    def run(self, prompt: str, run_id: str, run_dir: Path, trace: list[dict[str, Any]]):
        if is_obviously_off_scope(prompt):
            return mark_preplanner_rejection(self.core.unsupported_result(run_id, "hardened", run_dir, trace), run_dir)
        plan = self.core.plan(prompt); write_json(run_dir / "handoff_plan.json", plan)
        if plan["intent"] == "unsupported": return self.core.unsupported_result(run_id, "hardened", run_dir, trace)
        sender = self.core.database.registry("support-router"); receiver = self.core.database.registry("transfer-specialist")
        sender_active = sender is not None and sender["status"] == "active"
        audience_registered = sender is not None and sender["audience"] == "transfer-specialist" and receiver is not None and receiver["status"] == "active"
        trace.append({"stage": "planning", "title": "Groq requested a typed handoff", "detail": f"Request={plan['request_id']}; action={plan['requested_action']}", "status": "info"})
        trusted_transfer, router_query = self.core.database.get_transfer(run_id, plan["request_id"])
        allowed_context = {key: trusted_transfer[key] for key in ("request_id", "amount", "currency", "recipient")}
        signing_key = self.core.database.signing_key("support-router")
        if not sender_active or not audience_registered or not signing_key:
            raise ValueError("The router is not authorized to create this handoff")
        handoff = sign_envelope("support-router", "transfer-specialist", allowed_context, signing_key)
        signature_valid, verification_reason = verify_envelope(handoff, "transfer-specialist", signing_key)
        nonce_fresh = False
        if signature_valid:
            nonce_fresh = self.core.database.consume_nonce(
                handoff["nonce"],
                handoff["sender"],
                handoff["audience"],
                handoff["expires_at"],
            )
        envelope_valid = signature_valid and nonce_fresh
        verification_detail = (
            f"{verification_reason}; nonce consumed and replay-protected"
            if envelope_valid
            else "Envelope verification failed or the nonce was already consumed"
        )
        trace.append({"stage": "handoff-policy", "title": "Receiver verified the signed envelope", "detail": verification_detail, "status": "pass" if envelope_valid else "block"})
        write_json(run_dir / "handoff_payload.json", handoff)
        tool, execution = build_transfer_tool(self.core.database, run_id, receiver["allowed_action"] if receiver else "")
        result = tool.invoke({"request_id": plan["request_id"], "action": "validate_transfer"}) if envelope_valid else {}
        write_json(run_dir / "tool_result.json", result); write_json(run_dir / "database_query.json", {"router_lookup": router_query, "receiver_lookup": execution.query})
        trace.append({"stage": "specialist", "title": "Receiver agent applied an independent scope", "detail": "A separate transfer-specialist agent received only the authenticated, replay-protected payload and validation-only tool result.", "status": "pass" if envelope_valid else "block"})
        response = self.core.model.complete(self.core.hardened_response_prompt, f"Typed handoff payload:\n{json.dumps(allowed_context)}\n\nValidation result:\n{json.dumps(result)}")
        trace.append({"stage": "response", "title": "Specialist answered from minimal context", "detail": "The response model never received the transcript or reset token.", "status": "pass"})
        risky_fields = {"support_transcript", "password_reset_token", "execution_authority"}
        return self.core.result(run_id, "hardened", "contained" if risky_fields.intersection(plan["context_fields"]) or plan["requested_action"] == "execute_transfer" else "allowed", response, "The application authenticated and minimized the handoff, then enforced the specialist's independent validation scope.", "SIGNED TYPED HANDOFF + RECEIVER POLICY", trace, ["active sender registry", "audience-bound typed payload", "receiver-side action scope", "least-privilege model context"], [f"Handoff fields: {', '.join(allowed_context)}", "Secrets forwarded: 0", "Execution authority forwarded: 0"], run_dir)
