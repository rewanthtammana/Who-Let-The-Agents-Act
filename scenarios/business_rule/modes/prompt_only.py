from pathlib import Path
from typing import Any

from scenarios.business_rule.agent_core import AgentCore, write_json
from scenarios.business_rule.modes.vulnerable import execute


class PromptOnlyPosture:
    def __init__(self, core: AgentCore) -> None:
        self.core = core

    def run(self, prompt: str, run_id: str, run_dir: Path, trace: list[dict[str, Any]]) -> dict[str, Any]:
        guard = self.core.guard(prompt)
        write_json(run_dir / "guard_decision.json", guard)
        self.core.database.record_event(run_id, "prompt_guard", guard)
        if guard["decision"] == "refuse":
            trace.extend([
                {"stage": "prompt-guard", "title": "Model-controlled refund guard refused", "detail": guard["reason"], "status": "pass"},
                {"stage": "tool", "title": "Refund tool was not called", "detail": "The prompt-only decision stopped the operation before payment access.", "status": "pass"},
            ])
            return self.core.result("prompt_only", run_id, "refused", guard["reason"], "The model guard refused the refund before payment access.", "GROQ REFUND POLICY GUARD", trace, ["prompt-only model guard"], ["Payment tool calls: 0", f"Guard labels: {', '.join(guard.get('risk_labels', [])) or 'none'}"], run_dir)
        trace.append({"stage": "prompt-guard", "title": "Model-controlled refund guard allowed", "detail": guard["reason"], "status": "warn"})
        plan = self.core.plan(prompt)
        if plan["intent"] == "unsupported":
            return self.core.unsupported_result("prompt_only", run_id, run_dir, trace)
        return execute(self.core, "prompt_only", run_id, run_dir, trace, ["prompt-only model guard"], "The prompt-only guard allowed the refund, but the payment tool had no independent ceiling.", plan)
