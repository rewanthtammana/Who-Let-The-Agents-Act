from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol, Sequence

from scenarios.multi_agent_confused_deputy.database import ScenarioDatabase

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
        self.database = database
        self.model = model
        config = json.loads((SCENARIO_ROOT / "scenario.json").read_text(encoding="utf-8"))
        self.scenario_id = config["id"]
        self.planner_prompt = self._read("coordinator_prompt.txt")
        self.fraud_review_prompt = self._read("fraud_review_agent_prompt.txt")
        self.account_control_prompt = self._read("account_control_agent_prompt.txt")
        self.guard_prompt = self._read("handoff_guard_prompt.txt")
        self.hardened_response_prompt = self._read("hardened_response_prompt.txt")
        self.unsupported_response_prompt = self._read("unsupported_response_prompt.txt")
        self.runs_root = SCENARIO_ROOT / "_runs"

    @staticmethod
    def _read(name: str) -> str:
        return (SCENARIO_ROOT / name).read_text(encoding="utf-8").strip()

    def coordinate(self, prompt: str) -> dict[str, Any]:
        plan = self._structured(
            self.planner_prompt,
            f"User request:\n{prompt}",
            name="multi_agent_coordinator_plan",
        )
        intent = str(plan.get("intent", ""))
        case_id = str(plan.get("case_id", "")).strip().upper()
        if intent == "unsupported":
            return {"intent": intent, "case_id": ""}
        if intent != "review_fraud_case" or not case_id:
            raise ValueError("Groq returned an invalid fraud-case coordination plan")
        return {"intent": intent, "case_id": case_id}

    def review_case(self, prompt: str, case: dict[str, Any]) -> dict[str, Any]:
        result = self._structured(
            self.fraud_review_prompt,
            (
                f"User goal:\n{prompt}\n\n"
                f"<merchant_supplied_case_observation>\n{json.dumps(case, indent=2)}\n"
                f"</merchant_supplied_case_observation>"
            ),
            name="multi_agent_fraud_review_plan",
        )
        action = str(result.get("recommended_action", "none"))
        if action not in {"summarize", "freeze_account", "none"}:
            raise ValueError("Groq returned an invalid fraud-review recommendation")
        return {
            "recommended_action": action,
            "target_account_id": str(result.get("target_account_id", "")).strip().upper(),
            "handoff_message": str(result.get("handoff_message", "")).strip(),
            "reason": str(result.get("reason", "")).strip(),
        }

    def guard_handoff(self, prompt: str, case: dict[str, Any], recommendation: dict[str, Any]) -> dict[str, Any]:
        return self._structured(
            self.guard_prompt,
            (
                f"Original user request:\n{prompt}\n\n"
                f"Trusted case identity:\ncase_id={case['case_id']}\nsubject_account_id={case['subject_account_id']}\n\n"
                f"<untrusted_agent_handoff>\n{json.dumps(recommendation, indent=2)}\n</untrusted_agent_handoff>"
            ),
            name="multi_agent_handoff_guard",
        )

    def receive_handoff(self, handoff: dict[str, Any]) -> dict[str, Any]:
        result = self._structured(
            self.account_control_prompt,
            f"Incoming handoff:\n{json.dumps(handoff, indent=2)}",
            name="multi_agent_account_action_plan",
        )
        action = str(result.get("action", "none"))
        if action not in {"freeze_account", "none"}:
            raise ValueError("Groq returned an invalid account-control action")
        return {
            "action": action,
            "target_account_id": str(result.get("target_account_id", "")).strip().upper(),
            "reason": str(result.get("reason", "")).strip(),
        }

    def _structured(self, system: str, user: str, *, name: str) -> dict[str, Any]:
        for attempt in range(2):
            try:
                return self.model.structured(system, user, name=name, schema={})
            except Exception:
                if attempt == 1:
                    raise
                time.sleep(0.2)
        raise AssertionError("unreachable")

    def start_run(self, mode: Mode, prompt: str) -> tuple[str, Path, list[dict[str, Any]]]:
        run_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
        run_dir = self.runs_root / run_id
        run_dir.mkdir(parents=True)
        write_json(run_dir / "request.json", {"mode": mode, "prompt": prompt})
        return run_id, run_dir, [{"stage": "request", "title": "User request accepted", "detail": prompt, "status": "info"}]

    def unsupported_result(self, mode: Mode, run_id: str, run_dir: Path, trace: list[dict[str, Any]]) -> dict[str, Any]:
        trace.extend([
            {"stage": "coordinator", "title": "Coordinator classified the message as unsupported", "detail": "No fraud-case review was identified.", "status": "pass"},
            {"stage": "agents", "title": "No downstream agent was invoked", "detail": "Case retrieval, handoff, and account-control tools all remained untouched.", "status": "pass"},
        ])
        response = self.model.complete(
            self.unsupported_response_prompt,
            "The user sent an unsupported request. Respond helpfully within the fraud-case review scope.",
        )
        return self.result(
            mode, run_id, "refused", response,
            "The coordinator rejected the message before case data or downstream agents were accessed.",
            "COORDINATOR INTENT CHECK", trace,
            ["structured coordinator intent", "pre-retrieval unsupported-intent block"],
            ["Database reads: 0", "Downstream agent calls: 0", "Freeze tool calls: 0"], run_dir,
        )

    def result(
        self,
        mode: Mode,
        run_id: str,
        verdict: str,
        response: str,
        summary: str,
        badge: str,
        trace: list[dict[str, Any]],
        controls: list[str],
        evidence: list[str],
        run_dir: Path,
    ) -> dict[str, Any]:
        payload = {
            "run_id": run_id,
            "scenario_id": self.scenario_id,
            "mode": mode,
            "verdict": verdict,
            "response": response,
            "summary": summary,
            "badge": badge,
            "model": self.model.model,
            "trace": trace,
            "controls": controls,
            "evidence": evidence,
        }
        write_json(run_dir / "response.json", payload)
        payload["artifacts"] = sorted(path.name for path in run_dir.iterdir())
        return payload
