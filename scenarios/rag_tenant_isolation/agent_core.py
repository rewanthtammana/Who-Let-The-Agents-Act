from __future__ import annotations
import json, time, uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol, Sequence
from scenarios.rag_tenant_isolation.database import ScenarioDatabase

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
        self.planner_prompt = self._read("planner_prompt.txt"); self.guard_prompt = self._read("prompt_guard.txt")
        self.hardened_response_prompt = self._read("hardened_response_prompt.txt"); self.unsupported_response_prompt = self._read("unsupported_response_prompt.txt")
        self.scenario_id = "rag-tenant-isolation"; self.runs_root = SCENARIO_ROOT / "_runs"
    @staticmethod
    def _read(name: str) -> str: return (SCENARIO_ROOT / name).read_text(encoding="utf-8").strip()
    def plan(self, prompt: str) -> dict[str, Any]:
        for attempt in range(2):
            try:
                plan = self.model.structured(self.planner_prompt, f"User request:\n{prompt}", name="tenant_retrieval_plan", schema={}); break
            except Exception:
                if attempt == 1: raise
                time.sleep(0.2)
        intent = str(plan.get("intent", "")); query = str(plan.get("query", "wire-transfer limit")); scope = str(plan.get("requested_scope", "current_tenant"))
        if intent not in {"retrieve_policy", "unsupported"} or scope not in {"current_tenant", "all_tenants"}: raise ValueError("Groq returned an invalid retrieval plan")
        return {"intent": intent, "query": query, "requested_scope": scope}
    def guard(self, prompt: str) -> dict[str, Any]: return self.model.structured(self.guard_prompt, f"<untrusted_user_request>\n{prompt}\n</untrusted_user_request>", name="tenant_prompt_guard", schema={})
    def start_run(self, mode: Mode, prompt: str):
        run_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"; run_dir = self.runs_root / run_id; run_dir.mkdir(parents=True)
        write_json(run_dir / "request.json", {"mode": mode, "prompt": prompt}); return run_id, run_dir, [{"stage": "request", "title": "User request accepted", "detail": prompt, "status": "info"}]
    def unsupported_result(self, mode, run_id, run_dir, trace):
        trace.extend([{"stage":"planning","title":"Agent classified the message as unsupported","detail":"No tenant policy lookup was identified; the retrieval tool was not called.","status":"pass"},{"stage":"tool","title":"Retrieval tool was not called","detail":"The application blocked unsupported intent before data access.","status":"pass"}])
        response = self.model.complete(self.unsupported_response_prompt, "The user sent an unsupported request. Respond helpfully within the tenant-policy scope.")
        return self.result(mode, run_id, "refused", response, "The agent rejected the message without accessing policy data.", "MODEL INTENT CHECK", trace, ["structured intent classification", "pre-tool unsupported-intent block"], ["Database reads: 0"], run_dir)
    def result(self, mode, run_id, verdict, response, summary, badge, trace, controls, evidence, run_dir):
        payload={"run_id":run_id,"scenario_id":self.scenario_id,"mode":mode,"verdict":verdict,"response":response,"summary":summary,"badge":badge,"model":self.model.model,"trace":trace,"controls":controls,"evidence":evidence}; write_json(run_dir/"response.json",payload); payload["artifacts"]=sorted(p.name for p in run_dir.iterdir()); return payload
