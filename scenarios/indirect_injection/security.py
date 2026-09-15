"""Deterministic document/action policy for the indirect-injection scenario."""

from typing import Any


def beneficiary_is_authorized(invoice: dict[str, Any], beneficiary: str) -> bool:
    """Only the beneficiary from the trusted invoice record may be authorized."""
    return beneficiary == invoice["approved_beneficiary"]
