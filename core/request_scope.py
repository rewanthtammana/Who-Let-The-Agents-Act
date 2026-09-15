"""Model-independent admission checks used by the hardened posture."""

from __future__ import annotations

import json
import re


_UNRELATED = re.compile(
    r"\b(?:what can (?:you|this assistant) do|how does this app work|"
    r"tell me (?:a )?joke|what(?:'s| is) the weather|good morning|"
    r"good afternoon|good evening|hello there|hi there)\b",
    re.IGNORECASE,
)
_OVERRIDE = re.compile(
    r"\b(?:ignore|bypass|override)\b.{0,80}\b(?:scenario|"
    r"instructions?|safeguards?|security|policy|rules?)\b",
    re.IGNORECASE,
)
_BROAD_ACCESS = re.compile(
    r"\b(?:every|all|any)\b.{0,50}\b(?:record|customer|account|"
    r"transaction|secret|credential|system prompt|bank|document)s?\b|"
    r"\b(?:administrator|admin)\b.{0,50}\b(?:give|show|dump|export|"
    r"send|reveal|list)\b",
    re.IGNORECASE,
)


def is_obviously_off_scope(prompt: str) -> bool:
    """Reject only high-confidence unrelated or override/bulk-access input."""

    text = " ".join(prompt.split())
    if _OVERRIDE.search(text) and _BROAD_ACCESS.search(text):
        return True
    return bool(_UNRELATED.search(text)) and not _BROAD_ACCESS.search(text)


def mark_preplanner_rejection(result: dict, run_dir) -> dict:
    """Annotate the normal unsupported response with the admission control."""

    result["summary"] = "The hardened admission gate rejected an obviously off-scope request before planning or tool access."
    result["badge"] = "DETERMINISTIC SCOPE GATE"
    result.setdefault("controls", []).append("model-independent pre-planner scope gate")
    result.setdefault("evidence", []).append("Planner/tool calls: 0")
    result["trace"].insert(1, {
        "stage": "admission",
        "title": "Hardened admission gate rejected the message",
        "detail": "The request matched an obvious unrelated or override/bulk-access pattern; Groq planning and tools were not called.",
        "status": "block",
    })
    (run_dir / "response.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return result
