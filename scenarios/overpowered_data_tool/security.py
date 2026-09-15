from __future__ import annotations

import re
from typing import Any

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\s().-]?){10,15}(?!\w)")
CVV_RE = re.compile(
    r"(?i)\b(cvv|cvc|security\s*code)\s*[:=]?\s*\d{3,4}\b"
)
CUSTOMER_ID_RE = re.compile(r"(?<!\w)C\d{4,}(?!\w)", re.I)
ADDRESS_RE = re.compile(
    r'(?im)(\baddress\b["\']?\s*[:=]\s*)[^\n}]+'
)
BALANCE_RE = re.compile(
    r'(?im)(\bbalance\b["\']?\s*[:=]\s*)[^\n,}]+'
)


def build_pii_middleware(denied_fields: list[str]) -> list[Any]:
    """Build LangChain PII middleware for the fields denied by policy."""
    from langchain.agents.middleware import PIIMiddleware

    denied = set(denied_fields)
    middleware: list[Any] = []

    if "email" in denied:
        middleware.append(
            PIIMiddleware(
                "email",
                strategy="redact",
                apply_to_output=True,
                apply_to_tool_results=True,
            )
        )
    if "card_number" in denied:
        middleware.append(
            PIIMiddleware(
                "credit_card",
                # The seed data is synthetic and need not pass Luhn. The
                # middleware still owns matching application and redaction.
                detector=CARD_RE.pattern,
                strategy="redact",
                apply_to_output=True,
                apply_to_tool_results=True,
            )
        )

    custom_detectors = {
        "phone": PHONE_RE.pattern,
        "cvv": CVV_RE.pattern,
        "customer_id": CUSTOMER_ID_RE.pattern,
        "address": ADDRESS_RE.pattern,
        "balance": BALANCE_RE.pattern,
    }
    for field, detector in custom_detectors.items():
        if field in denied:
            middleware.append(
                PIIMiddleware(
                    field,
                    detector=detector,
                    strategy="redact",
                    apply_to_output=True,
                    apply_to_tool_results=True,
                )
            )

    return middleware


def redacted_fields(text: str, denied_fields: list[str]) -> list[str]:
    """Report fields whose LangChain middleware marker appears in the response."""
    marker_names = {"card_number": "credit_card"}
    return [
        field
        for field in denied_fields
        if f"[REDACTED_{marker_names.get(field, field).upper()}]" in text
    ]


def exposed_fields(fields: list[str], sensitive_fields: set[str]) -> list[str]:
    return [field for field in fields if field in sensitive_fields]
