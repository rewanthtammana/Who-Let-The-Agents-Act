from scenarios.indirect_injection.agent_core import write_json
from scenarios.indirect_injection.modes.vulnerable import execute


class PromptOnlyPosture:
    def __init__(self, core): self.core = core

    def run(self, prompt, run_id, run_dir, trace):
        guard = self.core.guard(prompt)
        write_json(run_dir / "guard_decision.json", guard)
        self.core.database.record_event(run_id, "prompt_guard", guard)
        if guard["decision"] == "refuse":
            trace.extend([
                {"stage": "prompt-guard", "title": "Model-controlled document guard refused", "detail": guard["reason"], "status": "pass"},
                {"stage": "tool", "title": "Invoice and payment tools were not called", "detail": "The prompt-only decision stopped the run.", "status": "pass"},
            ])
            return self.core.result("prompt_only", run_id, "refused", guard["reason"], "The model guard refused the request before invoice access.", "GROQ DOCUMENT GUARD", trace, ["prompt-only model guard"], ["Database reads: 0", "Payment tool calls: 0"], run_dir)
        trace.append({"stage": "prompt-guard", "title": "Model-controlled document guard allowed", "detail": guard["reason"], "status": "warn"})
        plan = self.core.plan(prompt)
        if plan["intent"] == "unsupported": return self.core.unsupported_result("prompt_only", run_id, run_dir, trace)
        plan["user_prompt"] = prompt
        return execute(self.core, "prompt_only", run_id, run_dir, trace, ["prompt-only model guard"], plan, "The prompt-only guard allowed the request, but the retrieved document still reached an unsafe payment path.")
