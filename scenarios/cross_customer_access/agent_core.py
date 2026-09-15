from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol, Sequence

from scenarios.cross_customer_access.database import ScenarioDatabase

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
        self.planner_prompt = self._read("planner_prompt.txt")
        self.guard_prompt = self._read("prompt_guard.txt")
        self.hardened_response_prompt = self._read("hardened_response_prompt.txt")
        self.unsupported_response_prompt = self._read("unsupported_response_prompt.txt")
        self.runs_root = SCENARIO_ROOT / "_runs"

    @staticmethod
    def _read(name: str) -> str:
        return (SCENARIO_ROOT / name).read_text(encoding="utf-8").strip()

    def plan(self, prompt: str) -> dict[str, str]:
        for attempt in range(2):
            try:
                plan = self.model.structured(
                    self.planner_prompt,
                    f"Authenticated session customer: C100\nUser request:\n{prompt}",
                    name="transaction_plan",
                    schema={},
                )
                break
            except Exception:
                if attempt == 1:
                    raise
                time.sleep(0.2)
        customer_id = str(plan.get("customer_id", "")).strip().upper()
        intent = str(plan.get("intent", ""))
        if intent == "unsupported":
            return {"customer_id": customer_id or "C100", "intent": intent}
        if not customer_id or intent not in {"list_transactions", "unsupported"}:
            raise ValueError("Groq returned an invalid transaction plan")
        return {"customer_id": customer_id, "intent": intent}

    def guard(self, prompt: str) -> dict[str, Any]:
        return self.model.structured(
            self.guard_prompt,
            f"<untrusted_user_request>\n{prompt}\n</untrusted_user_request>",
            name="transaction_prompt_guard",
            schema={},
        )

    def start_run(self, mode: Mode, prompt: str) -> tuple[str, Path, list[dict[str, Any]]]:
        run_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
        run_dir = self.runs_root / run_id
        run_dir.mkdir(parents=True)
        write_json(run_dir / "request.json", {"mode": mode, "prompt": prompt})
        return run_id, run_dir, [{"stage": "request", "title": "User request accepted", "detail": prompt, "status": "info"}]

    def unsupported_result(self, mode: Mode, run_id: str, run_dir: Path, trace: list[dict[str, Any]]) -> dict[str, Any]:
        trace.extend([
            {"stage": "planning", "title": "Agent classified the message as unsupported", "detail": "No transaction lookup was identified; the scenario database was not queried.", "status": "pass"},
            {"stage": "tool", "title": "Transaction tool was not called", "detail": "Only supported transaction lookups can reach the data service.", "status": "pass"},
        ])
        response = self.model.complete(self.unsupported_response_prompt, "The user sent an unsupported request. Respond helpfully within the transaction-lookup scope.")
        return self.result(mode, run_id, "refused", response, "The agent rejected the message because it was not a supported transaction lookup.", "AGENT INTENT CHECK", trace, ["structured intent classification", "no database access for unsupported input"], ["Database reads: 0"], run_dir)

    def result(self, mode: Mode, run_id: str, verdict: str, response: str, summary: str, badge: str, trace: list[dict[str, Any]], controls: list[str], evidence: list[str], run_dir: Path) -> dict[str, Any]:
        payload = {"run_id": run_id, "scenario_id": self.scenario_id, "mode": mode, "verdict": verdict, "response": response, "summary": summary, "badge": badge, "model": self.model.model, "trace": trace, "controls": controls, "evidence": evidence}
        write_json(run_dir / "response.json", payload)
        payload["artifacts"] = sorted(path.name for path in run_dir.iterdir())
        return payload
