from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol, Sequence

from scenarios.business_rule.database import ScenarioDatabase, TransactionNotFound

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

    def plan(self, prompt: str) -> dict[str, Any]:
        for attempt in range(2):
            try:
                plan = self.model.structured(self.planner_prompt, f"User request:\n{prompt}", name="refund_plan", schema={})
                break
            except Exception:
                if attempt == 1:
                    raise
                time.sleep(0.2)
        transaction_id = str(plan.get("transaction_id", "")).strip().upper()
        intent = str(plan.get("intent", ""))
        try:
            amount = float(plan.get("amount", 0))
            installments = int(plan.get("installments", 1))
        except (TypeError, ValueError) as exc:
            raise ValueError("Groq returned an invalid refund amount") from exc
        if intent == "unsupported":
            return {"transaction_id": transaction_id or "TX-2841", "amount": amount or 0.0, "installments": max(1, installments), "intent": intent}
        if not transaction_id or amount <= 0 or installments < 1 or installments > 20 or intent not in {"refund", "unsupported"}:
            raise ValueError("Groq returned an invalid refund plan")
        return {"transaction_id": transaction_id, "amount": amount, "installments": installments, "intent": intent}

    def guard(self, prompt: str) -> dict[str, Any]:
        return self.model.structured(self.guard_prompt, f"<untrusted_user_request>\n{prompt}\n</untrusted_user_request>", name="refund_prompt_guard", schema={})

    def start_run(self, mode: Mode, prompt: str) -> tuple[str, Path, list[dict[str, Any]]]:
        run_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
        run_dir = self.runs_root / run_id
        run_dir.mkdir(parents=True)
        write_json(run_dir / "request.json", {"mode": mode, "prompt": prompt})
        return run_id, run_dir, [{"stage": "request", "title": "User request accepted", "detail": prompt, "status": "info"}]

    def unsupported_result(self, mode: Mode, run_id: str, run_dir: Path, trace: list[dict[str, Any]]) -> dict[str, Any]:
        trace.extend([
            {"stage": "planning", "title": "Agent classified the message as unsupported", "detail": "No refund request was identified; the payment tool was not called.", "status": "pass"},
            {"stage": "tool", "title": "Refund tool was not called", "detail": "Only supported refund requests can reach the payment service.", "status": "pass"},
        ])
        response = self.model.complete(self.unsupported_response_prompt, "The user sent an unsupported request. Respond helpfully within the refund scope.")
        return self.result(mode, run_id, "refused", response, "The agent rejected the message because it was not a supported refund request.", "AGENT INTENT CHECK", trace, ["structured intent classification", "no payment tool access"], ["Payment tool calls: 0"], run_dir)

    def transaction_not_found_result(
        self,
        mode: Mode,
        run_id: str,
        run_dir: Path,
        trace: list[dict[str, Any]],
        plan: dict[str, Any],
        query: dict[str, Any] | None,
        exc: TransactionNotFound,
        controls: list[str],
    ) -> dict[str, Any]:
        """Return an inspectable run when the requested transaction is absent."""
        detail = str(exc)
        tool_result = {"result": "error", "reason": detail}
        write_json(run_dir / "tool_result.json", tool_result)
        if query is not None:
            write_json(run_dir / "database_query.json", query)
        trace.extend([
            {"stage": "database", "title": "Transaction lookup returned no match", "detail": detail, "status": "block"},
            {"stage": "tool", "title": "Refund was not executed", "detail": "The payment tool stopped after SQLite found no matching transaction.", "status": "pass"},
        ])
        return self.result(
            mode,
            run_id,
            "error",
            detail,
            "The requested transaction was not found, so no refund was executed.",
            "TRANSACTION LOOKUP FAILED",
            trace,
            controls,
            [f"Requested transaction: {plan['transaction_id']}", "Database rows matched: 0", "Payment tool execution: no"],
            run_dir,
        )

    def result(self, mode: Mode, run_id: str, verdict: str, response: str, summary: str, badge: str, trace: list[dict[str, Any]], controls: list[str], evidence: list[str], run_dir: Path) -> dict[str, Any]:
        payload = {"run_id": run_id, "scenario_id": self.scenario_id, "mode": mode, "verdict": verdict, "response": response, "summary": summary, "badge": badge, "model": self.model.model, "trace": trace, "controls": controls, "evidence": evidence}
        write_json(run_dir / "response.json", payload)
        payload["artifacts"] = sorted(path.name for path in run_dir.iterdir())
        return payload
