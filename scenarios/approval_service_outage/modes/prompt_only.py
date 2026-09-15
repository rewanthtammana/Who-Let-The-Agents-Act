from pathlib import Path
from typing import Any

from scenarios.approval_service_outage.agent_core import AgentCore, write_json
from scenarios.approval_service_outage.modes.vulnerable import execute_unsafe


class PromptOnlyPosture:
    def __init__(self, core: AgentCore) -> None:
        self.core = core

    def run(self, prompt: str, run_id: str, run_dir: Path, trace: list[dict[str, Any]]) -> dict[str, Any]:
        dependency = self.core.database.dependency_status()
        write_json(run_dir / "guard_context.json", dependency)
        guard = self.core.guard(prompt, dependency)
        write_json(run_dir / "guard_decision.json", guard)
        self.core.database.record_event(run_id, "prompt_guard", guard)
        if guard["decision"] == "refuse":
            trace.extend([
                {
                    "stage": "prompt-guard",
                    "title": "Model-controlled payment guard refused",
                    "detail": f"Service state={dependency['state']}. {guard['reason']}",
                    "status": "pass",
                },
                {"stage": "tool", "title": "Payment tool was not called", "detail": "The prompt-only decision stopped this request before payment access.", "status": "pass"},
            ])
            return self.core.result(
                "prompt_only",
                run_id,
                "refused",
                guard["reason"],
                "The model guard refused the request before the payment tool ran.",
                "GROQ PAYMENT GUARD",
                trace,
                ["prompt-only model guard"],
                [
                    f"Guard observed service state: {dependency['state']}",
                    "Payment tool calls: 0",
                    f"Guard labels: {', '.join(guard.get('risk_labels', [])) or 'none'}",
                ],
                run_dir,
            )
        trace.append({
            "stage": "prompt-guard",
            "title": "Model-controlled payment guard allowed",
            "detail": f"Service state={dependency['state']}. {guard['reason']}",
            "status": "warn",
        })
        plan = self.core.plan(prompt)
        if plan["intent"] == "unsupported":
            return self.core.unsupported_result("prompt_only", run_id, run_dir, trace)
        return execute_unsafe(
            self.core,
            "prompt_only",
            run_id,
            run_dir,
            trace,
            plan,
            ["prompt-only model guard"],
        )
