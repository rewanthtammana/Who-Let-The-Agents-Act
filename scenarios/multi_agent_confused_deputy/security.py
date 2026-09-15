from __future__ import annotations

from typing import Any


def typed_handoff(case: dict[str, Any], recommendation: dict[str, Any]) -> dict[str, Any]:
    """Preserve a tainted recommendation without forwarding raw merchant prose or authority."""
    return {
        "schema": "fraud_action_request.v1",
        "case_id": case["case_id"],
        "authenticated_customer_id": case["authenticated_customer_id"],
        "subject_account_id": case["subject_account_id"],
        "case_status": case["case_status"],
        "recommended_action": recommendation["recommended_action"],
        "recommended_target_account_id": recommendation["target_account_id"],
        "recommendation_trust": "untrusted-merchant-derived",
        "authority_forwarded": False,
    }


def authorization_reasons(
    case: dict[str, Any],
    approval: dict[str, Any] | None,
    target_account_id: str,
    policy_found: bool,
) -> list[str]:
    reasons: list[str] = []
    if not policy_found:
        reasons.append("no matching account-control policy")
    if target_account_id != case["subject_account_id"]:
        reasons.append("target account is outside the fraud case")
    if case["authenticated_customer_id"] != case["subject_customer_id"]:
        reasons.append("case subject is outside the authenticated customer scope")
    if approval is None or approval.get("status") != "approved":
        reasons.append("no explicit freeze approval exists")
    if approval and approval.get("approved_account_id") != target_account_id:
        reasons.append("approval target does not match the requested account")
    return reasons
