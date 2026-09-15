from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol, Sequence

from scenarios.secret_leakage.database import ScenarioDatabase

Mode = Literal["vulnerable", "prompt_only", "hardened"]
SCENARIO_ROOT = Path(__file__).resolve().parent


class ModelClient(Protocol):
    model: str
    def structured(self, system: str, user: str, *, name: str, schema: dict[str, Any]) -> dict[str, Any]: ...
    def complete(self, system: str, user: str, *, middleware: Sequence[Any] = ()) -> str: ...


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


class AgentCore:
    def __init__(self, database: ScenarioDatabase, model: ModelClient) -> None:
        self.database, self.model = database, model
        self.scenario_id = "secret-leakage"
        self.planner_prompt = self._read("planner_prompt.txt")
        self.report_prompt = self._read("report_action_prompt.txt")
        self.guard_prompt = self._read("prompt_guard.txt")
        self.hardened_response_prompt = self._read("hardened_response_prompt.txt")
        self.unsupported_response_prompt = self._read("unsupported_response_prompt.txt")
        self.runs_root = SCENARIO_ROOT / "_runs"

    @staticmethod
    def _read(name: str) -> str:
        return (SCENARIO_ROOT / name).read_text(encoding="utf-8").strip()

    def plan(self, prompt: str) -> dict[str, Any]:
        for attempt in range(2):
            try:
                plan = self.model.structured(self.planner_prompt, f"User request:\n{prompt}", name="secret_diagnostics_plan", schema={})
                break
            except Exception:
                if attempt == 1: raise
                time.sleep(0.2)
        intent = str(plan.get("intent", ""))
        if intent not in {"review_diagnostics", "unsupported"}:
            raise ValueError("Groq returned an invalid diagnostics plan")
        requested_action = str(plan.get("requested_action", "none"))
        if requested_action not in {"review", "publish_report", "none"}:
            raise ValueError("Groq returned an invalid diagnostics action")
        return {
            "intent": intent,
            "include_environment": bool(plan.get("include_environment", False)),
            "requested_action": requested_action,
        }

    def guard(self, prompt: str) -> dict[str, Any]:
        return self.model.structured(self.guard_prompt, f"<untrusted_user_request>\n{prompt}\n</untrusted_user_request>", name="secret_prompt_guard", schema={})

    def plan_report(self, prompt: str, diagnostics: dict[str, Any]) -> dict[str, Any]:
        result = self.model.structured(
            self.report_prompt,
            f"User goal:\n{prompt}\n\nDiagnostics tool observation:\n{json.dumps(diagnostics, indent=2)}",
            name="secret_report_plan",
            schema={},
        )
        return {
            "send_report": bool(result.get("send_report", False)),
            "report_body": str(result.get("report_body", "")),
            "reason": str(result.get("reason", "")),
        }

    def start_run(self, mode: Mode, prompt: str) -> tuple[str, Path, list[dict[str, Any]]]:
        run_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
        run_dir = self.runs_root / run_id; run_dir.mkdir(parents=True)
        write_json(run_dir / "request.json", {"mode": mode, "prompt": prompt})
        return run_id, run_dir, [{"stage": "request", "title": "User request accepted", "detail": prompt, "status": "info"}]

    def unsupported_result(self, mode: Mode, run_id: str, run_dir: Path, trace: list[dict[str, Any]]) -> dict[str, Any]:
        trace.extend([{"stage": "planning", "title": "Agent classified the message as unsupported", "detail": "No payment diagnostics request was identified; no diagnostics tool was called.", "status": "pass"}, {"stage": "tool", "title": "Diagnostics tool was not called", "detail": "The application blocked unsupported intent before data access.", "status": "pass"}])
        response = self.model.complete(self.unsupported_response_prompt, "The user sent an unsupported request. Respond helpfully within the diagnostics scope.")
        return self.result(mode, run_id, "refused", response, "The agent rejected the message without accessing diagnostics data.", "MODEL INTENT CHECK", trace, ["structured intent classification", "pre-tool unsupported-intent block"], ["Database reads: 0"], run_dir)

    def result(self, mode: str, run_id: str, verdict: str, response: str, summary: str, badge: str, trace: list[dict[str, Any]], controls: list[str], evidence: list[str], run_dir: Path) -> dict[str, Any]:
        payload = {"run_id": run_id, "scenario_id": self.scenario_id, "mode": mode, "verdict": verdict, "response": response, "summary": summary, "badge": badge, "model": self.model.model, "trace": trace, "controls": controls, "evidence": evidence}
        write_json(run_dir / "response.json", payload); payload["artifacts"] = sorted(path.name for path in run_dir.iterdir()); return payload
