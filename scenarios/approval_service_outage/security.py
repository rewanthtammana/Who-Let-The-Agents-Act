from __future__ import annotations

from typing import Literal

FallbackAction = Literal["none", "allow", "queue"]


def resolve_payment_authorization(
    approval_decision: str | None,
    *,
    dependency_state: str,
    fail_closed: bool,
) -> tuple[bool, FallbackAction]:
    """Resolve availability separately from authorization; absence is never an approval in Hardened."""
    if dependency_state not in {"healthy", "timeout"}:
        raise ValueError("Unsupported approval dependency state")
    if approval_decision not in {None, "approved", "denied"}:
        raise ValueError("Unsupported approval decision")
    if approval_decision == "approved":
        return True, "none"
    if approval_decision == "denied":
        return False, "none"
    if dependency_state != "timeout":
        return False, "none"
    return (False, "queue") if fail_closed else (True, "allow")
