from __future__ import annotations

import os
import threading
import time
from datetime import UTC, date, datetime
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Sequence

from dotenv import load_dotenv
from pydantic import BaseModel


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
# Migration convenience while the previous application remains archived.
if not os.getenv("GROQ_API_KEY") and (ROOT / "old" / ".env").is_file():
    load_dotenv(ROOT / "old" / ".env")


class ModelServiceError(RuntimeError):
    """Raised when a live LangChain/Groq call cannot be completed."""


@dataclass
class ModelCallBudget:
    maximum: int
    used: int = 0

    def reserve(self) -> None:
        if self.used >= self.maximum:
            raise ModelServiceError("The agent reached its model-call safety limit")
        self.used += 1


_MODEL_BUDGET: ContextVar[ModelCallBudget | None] = ContextVar("model_call_budget", default=None)
_DAILY_MODEL_CALL_LIMIT = int(os.getenv("MODEL_DAILY_CALL_LIMIT", "10000"))
MODEL_TIMEOUT_SECONDS = float(os.getenv("MODEL_TIMEOUT_SECONDS", "45"))
_DAILY_MODEL_CALLS = 0
_DAILY_MODEL_CALL_DATE: date | None = None
_DAILY_MODEL_CALL_LOCK = threading.Lock()


@contextmanager
def model_call_budget(maximum: int):
    token = _MODEL_BUDGET.set(ModelCallBudget(maximum=max(1, maximum)))
    try:
        yield _MODEL_BUDGET.get()
    finally:
        _MODEL_BUDGET.reset(token)


def reserve_model_call() -> None:
    budget = _MODEL_BUDGET.get()
    if budget is not None:
        budget.reserve()
    global _DAILY_MODEL_CALLS, _DAILY_MODEL_CALL_DATE
    today = datetime.now(UTC).date()
    with _DAILY_MODEL_CALL_LOCK:
        if _DAILY_MODEL_CALL_DATE != today:
            _DAILY_MODEL_CALL_DATE = today
            _DAILY_MODEL_CALLS = 0
        if _DAILY_MODEL_CALLS >= _DAILY_MODEL_CALL_LIMIT:
            if budget is not None:
                budget.used = max(0, budget.used - 1)
            raise ModelServiceError("The demo reached its daily model-call safety limit")
        _DAILY_MODEL_CALLS += 1


class GuardDecision(BaseModel):
    decision: Literal["allow", "refuse"]
    reason: str
    risk_labels: list[str]


class CustomerReadPlan(BaseModel):
    intent: Literal["read_customer", "unsupported"] = "read_customer"
    customer_name: str
    fields: list[str]


class HandoffPlan(BaseModel):
    intent: Literal["validate_transfer", "unsupported"]
    request_id: str
    requested_action: Literal["validate_transfer", "execute_transfer", "none"]
    amount: float
    currency: str
    recipient: str
    context_fields: list[str]


class HandoffGuardDecision(BaseModel):
    decision: Literal["allow", "refuse"]
    reason: str
    risk_labels: list[str]


class TransactionPlan(BaseModel):
    customer_id: str
    intent: Literal["list_transactions", "unsupported"]


class TransactionGuardDecision(BaseModel):
    decision: Literal["allow", "refuse"]
    reason: str
    risk_labels: list[str]


class RefundPlan(BaseModel):
    transaction_id: str
    amount: float
    installments: int = 1
    intent: Literal["refund", "unsupported"]


class RefundGuardDecision(BaseModel):
    decision: Literal["allow", "refuse"]
    reason: str
    risk_labels: list[str]


class InvoicePlan(BaseModel):
    invoice_id: str
    requested_action: Literal["summarize", "pay", "none"]
    amount: float
    destination: str
    intent: Literal["review_invoice", "unsupported"]


class InvoiceActionPlan(BaseModel):
    requested_action: Literal["summarize", "pay", "none"]
    amount: float = 0
    destination: str = ""
    reason: str


class InvoiceGuardDecision(BaseModel):
    decision: Literal["allow", "refuse"]
    reason: str
    risk_labels: list[str]


class TenantRetrievalPlan(BaseModel):
    intent: Literal["retrieve_policy", "unsupported"]
    query: str
    requested_scope: Literal["current_tenant", "all_tenants"]


class TenantGuardDecision(BaseModel):
    decision: Literal["allow", "refuse"]
    reason: str
    risk_labels: list[str]


class SecretDiagnosticsPlan(BaseModel):
    intent: Literal["review_diagnostics", "unsupported"]
    include_environment: bool = False
    requested_action: Literal["review", "publish_report", "none"] = "review"


class SecretReportPlan(BaseModel):
    send_report: bool
    report_body: str
    reason: str


class SecretGuardDecision(BaseModel):
    decision: Literal["allow", "refuse"]
    reason: str
    risk_labels: list[str]


class ApprovalOutagePaymentPlan(BaseModel):
    intent: Literal["submit_payment", "unsupported"]
    request_id: str


class ApprovalOutageGuardDecision(BaseModel):
    decision: Literal["allow", "refuse"]
    reason: str
    risk_labels: list[str]


class MultiAgentCoordinatorPlan(BaseModel):
    intent: Literal["review_fraud_case", "unsupported"]
    case_id: str


class MultiAgentFraudReviewPlan(BaseModel):
    recommended_action: Literal["summarize", "freeze_account", "none"]
    target_account_id: str = ""
    handoff_message: str
    reason: str


class MultiAgentAccountActionPlan(BaseModel):
    action: Literal["freeze_account", "none"]
    target_account_id: str = ""
    reason: str


class MultiAgentHandoffGuardDecision(BaseModel):
    decision: Literal["allow", "refuse"]
    reason: str
    risk_labels: list[str]


class LangChainModel:
    """Small application adapter around LangChain's create_agent runtime."""

    def __init__(self) -> None:
        self.model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        configured_keys = os.getenv("GROQ_API_KEYS", "")
        self.api_keys = tuple(
            key.strip()
            for key in configured_keys.replace("\n", ",").split(",")
            if key.strip()
        ) or ((os.getenv("GROQ_API_KEY", "") or "").strip(),)
        self.api_keys = tuple(key for key in self.api_keys if key)
        self._llms: dict[str, Any] = {}
        self._key_lock = threading.Lock()
        self._next_key = 0

    @property
    def available(self) -> bool:
        return bool(self.api_keys)

    def _select_key(self) -> str:
        if not self.available:
            raise ModelServiceError("GROQ_API_KEYS or GROQ_API_KEY is not configured")
        with self._key_lock:
            key = self.api_keys[self._next_key % len(self.api_keys)]
            self._next_key += 1
        return key

    def _llm_instance(self, api_key: str):
        if not self.available:
            raise ModelServiceError("GROQ_API_KEYS or GROQ_API_KEY is not configured")
        if api_key not in self._llms:
            try:
                from langchain_groq import ChatGroq

                self._llms[api_key] = ChatGroq(
                    model=self.model,
                    temperature=0,
                    max_tokens=1024,
                    api_key=api_key,
                    max_retries=0,
                    timeout=MODEL_TIMEOUT_SECONDS,
                )
            except Exception as exc:
                raise ModelServiceError(
                    f"LangChain Groq setup failed: {type(exc).__name__}"
                ) from exc
        return self._llms[api_key]

    @staticmethod
    def _agent(
        model: Any,
        system: str,
        middleware: Sequence[Any] = (),
        response_format: type[BaseModel] | None = None,
        tools: Sequence[Any] = (),
    ):
        from langchain.agents import create_agent

        return create_agent(
            model=model,
            tools=list(tools),
            system_prompt=system,
            middleware=list(middleware),
            response_format=response_format,
        )

    def structured(
        self,
        system: str,
        user: str,
        *,
        name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        del schema  # The named Pydantic model is the authoritative schema here.
        response_model: type[BaseModel]
        if name == "overpowered_data_tool_prompt_guard":
            response_model = GuardDecision
        elif name == "overpowered_data_tool_customer_read_plan":
            response_model = CustomerReadPlan
        elif name == "handoff_prompt_guard":
            response_model = HandoffGuardDecision
        elif name == "handoff_plan":
            response_model = HandoffPlan
        elif name == "transaction_plan":
            response_model = TransactionPlan
        elif name == "transaction_prompt_guard":
            response_model = TransactionGuardDecision
        elif name == "refund_plan":
            response_model = RefundPlan
        elif name == "refund_prompt_guard":
            response_model = RefundGuardDecision
        elif name == "invoice_plan":
            response_model = InvoicePlan
        elif name == "invoice_prompt_guard":
            response_model = InvoiceGuardDecision
        elif name == "invoice_action_plan":
            response_model = InvoiceActionPlan
        elif name == "tenant_retrieval_plan":
            response_model = TenantRetrievalPlan
        elif name == "tenant_prompt_guard":
            response_model = TenantGuardDecision
        elif name == "secret_diagnostics_plan":
            response_model = SecretDiagnosticsPlan
        elif name == "secret_prompt_guard":
            response_model = SecretGuardDecision
        elif name == "secret_report_plan":
            response_model = SecretReportPlan
        elif name == "approval_service_outage_payment_plan":
            response_model = ApprovalOutagePaymentPlan
        elif name == "approval_service_outage_prompt_guard":
            response_model = ApprovalOutageGuardDecision
        elif name == "multi_agent_coordinator_plan":
            response_model = MultiAgentCoordinatorPlan
        elif name == "multi_agent_fraud_review_plan":
            response_model = MultiAgentFraudReviewPlan
        elif name == "multi_agent_account_action_plan":
            response_model = MultiAgentAccountActionPlan
        elif name == "multi_agent_handoff_guard":
            response_model = MultiAgentHandoffGuardDecision
        else:
            raise ModelServiceError(f"Unknown structured response: {name}")

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                reserve_model_call()
                api_key = self._select_key()
                agent = self._agent(
                    self._llm_instance(api_key),
                    system,
                    response_format=response_model,
                )
                result = agent.invoke(
                    {"messages": [{"role": "user", "content": user}]}
                )
                structured = result.get("structured_response")
                if isinstance(structured, BaseModel):
                    return structured.model_dump()
                if isinstance(structured, dict):
                    return structured
                raise ValueError("LangChain returned no structured response")
            except ModelServiceError:
                raise
            except Exception as exc:
                last_error = exc
                if attempt == 2 or not self._retryable(exc):
                    raise ModelServiceError(
                        f"LangChain structured call failed: {type(exc).__name__}: {self._error_detail(exc)}"
                    ) from exc
                time.sleep(0.4 * (attempt + 1))
        raise ModelServiceError(f"LangChain structured call failed: {self._error_detail(last_error)}")

    @staticmethod
    def _retryable(exc: Exception) -> bool:
        status = getattr(exc, "status_code", None) or getattr(exc, "response", None) and getattr(exc.response, "status_code", None)
        return status is None or (isinstance(status, int) and (status == 408 or status == 429 or status >= 500))

    @staticmethod
    def _error_detail(exc: Exception | None) -> str:
        if exc is None:
            return "unknown error"
        body = getattr(exc, "body", None)
        detail = str(body or exc).replace("\n", " ").strip()
        return detail[:500]

    def complete(
        self,
        system: str,
        user: str,
        *,
        middleware: Sequence[Any] = (),
    ) -> str:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                reserve_model_call()
                api_key = self._select_key()
                agent = self._agent(self._llm_instance(api_key), system, middleware)
                result = agent.invoke(
                    {"messages": [{"role": "user", "content": user}]}
                )
                messages = result.get("messages", [])
                if not messages:
                    raise ValueError("LangChain returned no messages")
                content = messages[-1].content
                if isinstance(content, str) and content.strip():
                    return content.strip()
                raise ValueError("LangChain returned an empty response")
            except ModelServiceError:
                raise
            except Exception as exc:
                last_error = exc
                if attempt == 2 or not self._retryable(exc):
                    raise ModelServiceError(
                        f"LangChain completion failed: {type(exc).__name__}: {self._error_detail(exc)}"
                    ) from exc
                time.sleep(0.4 * (attempt + 1))
        raise ModelServiceError(f"LangChain completion failed: {self._error_detail(last_error)}")


GROQ = LangChainModel()
