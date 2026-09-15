from scenarios.signed_handoff.agent_core import write_json
from scenarios.signed_handoff.modes.vulnerable import execute
class PromptOnlyPosture:
    def __init__(self, core): self.core = core
    def run(self, prompt, run_id, run_dir, trace):
        guard = self.core.guard(prompt); write_json(run_dir / "guard_decision.json", guard); self.core.database.record_event(run_id, "prompt_guard", guard)
        if guard["decision"] == "refuse":
            trace.extend([{ "stage": "prompt-guard", "title": "Model-controlled guard refused", "detail": guard["reason"], "status": "pass" }, {"stage": "handoff", "title": "Handoff was not sent", "detail": "The prompt-only decision stopped the run.", "status": "pass"}])
            return self.core.result(run_id, "prompt_only", "refused", guard["reason"], "The model guard refused the unsafe handoff before it reached the specialist.", "GROQ HANDOFF GUARD", trace, ["prompt-only model guard"], [f"Guard labels: {', '.join(guard.get('risk_labels', [])) or 'none'}", "Database reads: 0"], run_dir)
        trace.append({"stage": "prompt-guard", "title": "Model-controlled guard allowed", "detail": guard["reason"], "status": "warn"})
        return execute(self.core, "prompt_only", prompt, run_id, run_dir, trace, ["prompt-only model guard"], "The prompt-only guard allowed the handoff, but the receiving boundary still trusted the raw payload.")
