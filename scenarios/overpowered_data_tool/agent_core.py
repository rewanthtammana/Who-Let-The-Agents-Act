from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol, Sequence

from scenarios.overpowered_data_tool.database import ScenarioDatabase

Mode = Literal["vulnerable", "prompt_only", "hardened"]
SCENARIO_ROOT = Path(__file__).resolve().parent


class ModelClient(Protocol):
    model: str

    def structured(
        self,
        system: str,
        user: str,
        *,
        name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]: ...

    def complete(
        self,
        system: str,
        user: str,
        *,
        middleware: Sequence[Any] = (),
    ) -> str: ...


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, default=str),
        encoding="utf-8",
    )


class AgentCore:
    """Neutral shared plumbing. Security decisions live in the mode modules."""

    def __init__(
        self,
        database: ScenarioDatabase,
        model: ModelClient,
    ) -> None:
        self.database = database
        self.model = model
        self.scenario_id = json.loads(
            (SCENARIO_ROOT / "scenario.json").read_text(encoding="utf-8")
        )["id"]
        self.planner_prompt = self._read("planner_prompt.txt")
        self.guard_prompt = self._read("prompt_guard.txt")
        self.hardened_response_prompt = self._read(
            "hardened_response_prompt.txt"
        )
        self.unsupported_response_prompt = self._read("unsupported_response_prompt.txt")
        self.runs_root = SCENARIO_ROOT / "_runs"

    @staticmethod
    def _read(name: str) -> str:
        return (SCENARIO_ROOT / name).read_text(
            encoding="utf-8"
        ).strip()

    def guard(self, prompt: str) -> dict[str, Any]:
        """Ask Groq for the deliberately fragile Prompt-only decision."""
        return self.model.structured(
            self.guard_prompt,
            f"<untrusted_user_request>\n{prompt}\n</untrusted_user_request>",
            name="overpowered_data_tool_prompt_guard",
            schema={
                "type": "object",
                "properties": {
                    "decision": {
                        "type": "string",
                        "enum": ["allow", "refuse"],
                    },
                    "reason": {"type": "string"},
                    "risk_labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 6,
                    },
                },
                "required": ["decision", "reason", "risk_labels"],
                "additionalProperties": False,
            },
        )

    def plan(self, prompt: str) -> dict[str, Any]:
        """Ask Groq to select a customer and fields from the live catalog."""
        policy = self.database.field_catalog()
        available_fields = [item["field_name"] for item in policy]
        field_catalog = "\n".join(
            f"- {item['field_name']}: {item['description']}"
            for item in policy
        )

        plan = self.model.structured(
            self.planner_prompt,
            (
                f"Available customer.read fields:\n{field_catalog}\n\n"
                f"User request:\n{prompt}"
            ),
            name="overpowered_data_tool_customer_read_plan",
            schema={
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string"},
                    "fields": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": available_fields,
                        },
                        "minItems": 1,
                        "maxItems": len(available_fields),
                    },
                },
                "required": ["customer_name", "fields"],
                "additionalProperties": False,
            },
        )

        customer_name = str(plan.get("customer_name", "")).strip()
        if not customer_name or customer_name.lower() not in prompt.lower():
            return {"intent": "unsupported", "customer_name": "", "fields": []}
        requested_fields = list(dict.fromkeys(plan.get("fields", [])))
        invalid_field = any(
            field not in available_fields for field in requested_fields
        )
        if not customer_name or not requested_fields or invalid_field:
            raise ValueError(
                "Groq returned an invalid customer.read plan"
            )

        return {
            "intent": "read_customer",
            "customer_name": customer_name,
            "fields": requested_fields,
        }

    def unsupported_result(
        self,
        mode: Mode,
        run_id: str,
        run_dir: Path,
        trace: list[dict[str, Any]],
    ) -> dict[str, Any]:
        trace.extend([
            {"stage": "planning", "title": "Agent classified the message as unsupported", "detail": "No specific customer field request was identified; the customer database was not queried.", "status": "pass"},
            {"stage": "tool", "title": "customer.read was not called", "detail": "Only explicit customer-record requests can reach the data service.", "status": "pass"},
        ])
        response = self.model.complete(self.unsupported_response_prompt, "The user sent an unsupported request. Respond helpfully within the customer-record scope.")
        return self.result(run_id, mode, "refused", response, "The agent rejected the message because it was not a supported customer-record request.", "AGENT INTENT CHECK", trace, ["structured intent classification", "no customer database access"], ["Database reads: 0"], run_dir)

    def ambiguous_customer_result(
        self,
        mode: Mode,
        run_id: str,
        run_dir: Path,
        trace: list[dict[str, Any]],
        candidates: list[dict[str, str]],
    ) -> dict[str, Any]:
        names = ", ".join(candidate["name"] for candidate in candidates)
        trace.extend([
            {
                "stage": "identity",
                "title": "Application found multiple matching customers",
                "detail": f"The name matched: {names}. Protected customer fields were not read.",
                "status": "block",
            },
            {
                "stage": "tool",
                "title": "customer.read was not called",
                "detail": "The application requires an unambiguous customer identity before accessing record fields.",
                "status": "pass",
            },
        ])
        response = self.model.complete(
            self.unsupported_response_prompt,
            (
                "The application found more than one customer matching the user's name. "
                f"Ask the user to clarify which exact customer they mean: {names}. "
                "Do not claim to have retrieved any customer fields."
            ),
        )
        return self.result(
            run_id,
            mode,
            "refused",
            response,
            "The request was paused because the customer name was ambiguous.",
            "AMBIGUOUS CUSTOMER IDENTITY",
            trace,
            ["deterministic candidate resolution", "no protected field read"],
            [f"Matching customers: {len(candidates)}", "customer.read calls: 0", "Protected fields read: 0"],
            run_dir,
        )

    def start_run(
        self,
        mode: Mode,
        prompt: str,
    ) -> tuple[str, Path, list[dict[str, Any]]]:
        run_id = (
            f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-"
            f"{uuid.uuid4().hex[:8]}"
        )
        run_dir = self.runs_root / run_id
        run_dir.mkdir(parents=True)
        write_json(
            run_dir / "request.json",
            {"mode": mode, "prompt": prompt},
        )
        trace = [
            {
                "stage": "request",
                "title": "User request accepted",
                "detail": prompt,
                "status": "info",
            }
        ]
        return run_id, run_dir, trace

    def result(
        self,
        run_id: str,
        mode: Mode,
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
        payload["artifacts"] = sorted(
            path.name for path in run_dir.iterdir()
        )
        return payload
