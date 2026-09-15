from __future__ import annotations
import json, uuid
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol, Sequence
from scenarios.signed_handoff.database import ScenarioDatabase

Mode = Literal["vulnerable", "prompt_only", "hardened"]
SCENARIO_ROOT = Path(__file__).resolve().parent
class ModelClient(Protocol):
    model: str
    def structured(self, system: str, user: str, *, name: str, schema: dict[str, Any]) -> dict[str, Any]: ...
    def complete(self, system: str, user: str, *, middleware: Sequence[Any] = ()) -> str: ...
def write_json(path: Path, payload: Any) -> None: path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
class AgentCore:
    def __init__(self, database: ScenarioDatabase, model: ModelClient) -> None:
        self.database, self.model = database, model
        self.scenario_id = json.loads((SCENARIO_ROOT / "scenario.json").read_text())["id"]
        self.planner_prompt = self._read("planner_prompt.txt"); self.guard_prompt = self._read("prompt_guard.txt"); self.hardened_response_prompt = self._read("hardened_response_prompt.txt"); self.unsupported_response_prompt = self._read("unsupported_response_prompt.txt")
        self.runs_root = SCENARIO_ROOT / "_runs"
    @staticmethod
    def _read(name: str) -> str: return (SCENARIO_ROOT / name).read_text(encoding="utf-8").strip()
    def plan(self, prompt: str) -> dict[str, Any]:
        for attempt in range(2):
            try:
                plan = self.model.structured(self.planner_prompt, f"Available request ID: TR-2048\nUser request:\n{prompt}", name="handoff_plan", schema={})
                break
            except Exception:
                if attempt == 1: raise
                time.sleep(0.2)
        required = ("intent", "request_id", "requested_action", "amount", "currency", "recipient", "context_fields")
        if any(key not in plan for key in required) or plan["intent"] not in {"validate_transfer", "unsupported"} or plan["requested_action"] not in {"validate_transfer", "execute_transfer", "none"}: raise ValueError("Groq returned an invalid handoff plan")
        return {"intent": plan["intent"], "request_id": str(plan["request_id"]).strip(), "requested_action": plan["requested_action"], "amount": float(plan["amount"]), "currency": str(plan["currency"]), "recipient": str(plan["recipient"]), "context_fields": list(dict.fromkeys(plan["context_fields"]))}
    def unsupported_result(self, run_id, mode, run_dir, trace):
        trace.extend([{"stage": "planning", "title": "Agent classified the message as unsupported", "detail": "No transfer request was identified; the scenario database was not queried.", "status": "pass"}, {"stage": "handoff", "title": "No handoff was created", "detail": "The specialist only receives typed transfer-validation requests.", "status": "pass"}])
        response = self.model.complete(self.unsupported_response_prompt, "The user sent an unsupported request. Respond helpfully within the transfer-validation scope.")
        return self.result(run_id, mode, "refused", response, "The agent rejected the message because it was not a supported transfer-validation request.", "AGENT INTENT CHECK", trace, ["structured intent classification", "no database access for unsupported input"], ["Database reads: 0"], run_dir)
    def guard(self, prompt: str) -> dict[str, Any]:
        for attempt in range(2):
            try:
                return self.model.structured(self.guard_prompt, f"<untrusted_user_request>\n{prompt}\n</untrusted_user_request>", name="handoff_prompt_guard", schema={})
            except Exception:
                if attempt == 1: raise
                time.sleep(0.2)
        raise AssertionError("unreachable")
    def start_run(self, mode: Mode, prompt: str):
        run_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"; run_dir = self.runs_root / run_id; run_dir.mkdir(parents=True)
        write_json(run_dir / "request.json", {"mode": mode, "prompt": prompt})
        return run_id, run_dir, [{"stage": "request", "title": "User request accepted", "detail": prompt, "status": "info"}]
    def result(self, run_id, mode, verdict, response, summary, badge, trace, controls, evidence, run_dir):
        payload = {"run_id": run_id, "scenario_id": self.scenario_id, "mode": mode, "verdict": verdict, "response": response, "summary": summary, "badge": badge, "model": self.model.model, "trace": trace, "controls": controls, "evidence": evidence}
        write_json(run_dir / "response.json", payload); payload["artifacts"] = sorted(p.name for p in run_dir.iterdir()); return payload
