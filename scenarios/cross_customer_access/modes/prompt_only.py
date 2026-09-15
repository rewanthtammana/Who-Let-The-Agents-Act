from pathlib import Path
from typing import Any

from scenarios.cross_customer_access.agent_core import AgentCore, write_json
from scenarios.cross_customer_access.modes.vulnerable import execute


class PromptOnlyPosture:
    def __init__(self, core: AgentCore) -> None:
        self.core = core

    def run(self, prompt: str, run_id: str, run_dir: Path, trace: list[dict[str, Any]]) -> dict[str, Any]:
        guard = self.core.guard(prompt)
        write_json(run_dir / "guard_decision.json", guard)
        self.core.database.record_event(run_id, "prompt_guard", guard)
        if guard["decision"] == "refuse":
            trace.extend([
                {"stage": "prompt-guard", "title": "Model-controlled ownership guard refused", "detail": guard["reason"], "status": "pass"},
                {"stage": "tool", "title": "Transaction tool was not called", "detail": "The prompt-only decision stopped the run.", "status": "pass"},
            ])
            return self.core.result("prompt_only", run_id, "refused", guard["reason"], "The model guard refused the cross-customer request before database access.", "GROQ OWNERSHIP GUARD", trace, ["prompt-only model guard"], ["Database reads: 0", f"Guard labels: {', '.join(guard.get('risk_labels', [])) or 'none'}"], run_dir)
        trace.append({"stage": "prompt-guard", "title": "Model-controlled ownership guard allowed", "detail": guard["reason"], "status": "warn"})
        plan = self.core.plan(prompt)
        if plan["intent"] == "unsupported":
            return self.core.unsupported_result("prompt_only", run_id, run_dir, trace)
        return execute(self.core, "prompt_only", run_id, run_dir, trace, ["prompt-only model guard"], "The prompt-only guard allowed the request, but the transaction tool still trusted the raw customer ID.", plan)
