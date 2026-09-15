from pathlib import Path
from typing import Any

from scenarios.multi_agent_confused_deputy.agent_core import AgentCore, write_json
from scenarios.multi_agent_confused_deputy.modes.vulnerable import prepare_unsafe_chain, execute_unsafe_receiver


class PromptOnlyPosture:
    def __init__(self, core: AgentCore) -> None:
        self.core = core

    def run(self, prompt: str, run_id: str, run_dir: Path, trace: list[dict[str, Any]]) -> dict[str, Any]:
        prepared = prepare_unsafe_chain(self.core, "prompt_only", prompt, run_id, run_dir, trace)
        if isinstance(prepared, dict):
            return prepared
        case, recommendation, handoff = prepared
        guard = self.core.guard_handoff(prompt, case, recommendation)
        write_json(run_dir / "handoff_guard_decision.json", guard)
        self.core.database.record_event(run_id, "handoff.prompt_guard", guard)
        if guard["decision"] == "refuse":
            trace.extend([
                {
                    "stage": "handoff-guard",
                    "title": "Model-controlled handoff guard refused",
                    "detail": guard["reason"],
                    "status": "pass",
                },
                {
                    "stage": "account-control-agent",
                    "title": "Receiver agent was not invoked",
                    "detail": "The advisory guard stopped this handoff before the unsafe account-control path.",
                    "status": "pass",
                },
            ])
            return self.core.result(
                "prompt_only", run_id, "refused", guard["reason"],
                "The model guard recognized the obvious poisoned handoff before Account Control received it.",
                "GROQ HANDOFF GUARD", trace,
                ["prompt-only model handoff guard"],
                [
                    "Agents invoked: 2",
                    f"Evidence provenance: {case['note_variant']}",
                    "Account Control calls: 0",
                    "Freeze tool calls: 0",
                    f"Guard labels: {', '.join(guard.get('risk_labels', [])) or 'none'}",
                ], run_dir,
            )
        trace.append({
            "stage": "handoff-guard",
            "title": "Model-controlled handoff guard allowed",
            "detail": guard["reason"],
            "status": "warn",
        })
        return execute_unsafe_receiver(
            self.core,
            "prompt_only",
            run_id,
            run_dir,
            trace,
            case,
            recommendation,
            handoff,
            ["prompt-only model handoff guard"],
        )
