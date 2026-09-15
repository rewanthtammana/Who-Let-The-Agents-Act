from scenarios.secret_leakage.agent_core import write_json
from scenarios.secret_leakage.modes.vulnerable import execute


class PromptOnlyPosture:
    def __init__(self, core): self.core = core
    def run(self, prompt, run_id, run_dir, trace):
        guard = self.core.guard(prompt); write_json(run_dir / "guard_decision.json", guard); self.core.database.record_event(run_id, "prompt_guard", guard)
        if guard["decision"] == "refuse":
            trace.extend([{"stage": "prompt-guard", "title": "Model-controlled secret guard refused", "detail": guard["reason"], "status": "pass"}, {"stage": "tool", "title": "Diagnostics tool was not called", "detail": "The prompt-only decision stopped the run.", "status": "pass"}])
            return self.core.result("prompt_only", run_id, "refused", guard["reason"], "The model guard refused the request before diagnostics access.", "GROQ SECRET GUARD", trace, ["prompt-only model guard"], ["Database reads: 0"], run_dir)
        trace.append({"stage": "prompt-guard", "title": "Model-controlled secret guard allowed", "detail": guard["reason"], "status": "warn"})
        plan = self.core.plan(prompt)
        if plan["intent"] == "unsupported": return self.core.unsupported_result("prompt_only", run_id, run_dir, trace)
        plan["user_prompt"] = prompt
        return execute(self.core, "prompt_only", run_id, run_dir, trace, plan, ["prompt-only model guard"], "The prompt-only guard allowed the request, but raw diagnostics still reached the response.", True)
