from __future__ import annotations

from pathlib import Path
from typing import Any

from scenarios.overpowered_data_tool.agent_core import AgentCore, write_json
from scenarios.overpowered_data_tool.modes.vulnerable import execute_return_direct


class PromptOnlyPosture:
    """A model-controlled guard in front of the same unsafe tool path."""

    def __init__(self, core: AgentCore) -> None:
        self.core = core

    def run(
        self,
        prompt: str,
        run_id: str,
        run_dir: Path,
        trace: list[dict[str, Any]],
    ) -> dict[str, Any]:
        guard = self.core.guard(prompt)
        write_json(run_dir / "guard_decision.json", guard)
        self.core.database.record_event(run_id, "prompt_guard", guard)

        if guard["decision"] == "refuse":
            trace.extend(
                [
                    {
                        "stage": "prompt-guard",
                        "title": "Model-controlled guard refused",
                        "detail": guard["reason"],
                        "status": "pass",
                    },
                    {
                        "stage": "tool",
                        "title": "customer.read was not called",
                        "detail": (
                            "The prompt-only decision stopped this run "
                            "before database access."
                        ),
                        "status": "pass",
                    },
                ]
            )
            return self.core.result(
                run_id=run_id,
                mode="prompt_only",
                verdict="refused",
                response=guard["reason"],
                summary=(
                    "The model-controlled privacy prompt refused the request. "
                    "No customer query ran."
                ),
                badge="GROQ GUARD DECISION",
                trace=trace,
                controls=["prompt-only model guard"],
                evidence=[
                    "Database reads: 0",
                    (
                        "Guard labels: "
                        f"{', '.join(guard['risk_labels']) or 'none'}"
                    ),
                ],
                run_dir=run_dir,
            )

        trace.append(
            {
                "stage": "prompt-guard",
                "title": "Model-controlled guard allowed",
                "detail": guard["reason"],
                "status": "warn",
            }
        )
        return execute_return_direct(
            core=self.core,
            mode="prompt_only",
            prompt=prompt,
            run_id=run_id,
            run_dir=run_dir,
            trace=trace,
            controls=["prompt-only model guard"],
            summary=(
                "The prompt-only guard allowed the request, but no application "
                "field boundary protected the raw tool result."
            ),
        )
