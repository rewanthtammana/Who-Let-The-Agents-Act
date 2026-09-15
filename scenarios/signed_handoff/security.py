from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from typing import Any


def _canonical(envelope: dict[str, Any]) -> bytes:
    signed = {key: value for key, value in envelope.items() if key != "signature"}
    return json.dumps(signed, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_envelope(
    sender: str,
    audience: str,
    payload: dict[str, Any],
    key: str,
    ttl_seconds: int = 300,
) -> dict[str, Any]:
    issued_at = int(time.time())
    envelope = {
        "sender": sender,
        "audience": audience,
        "issued_at": issued_at,
        "expires_at": issued_at + ttl_seconds,
        "nonce": uuid.uuid4().hex,
        "payload": payload,
    }
    envelope["signature"] = hmac.new(
        key.encode("utf-8"), _canonical(envelope), hashlib.sha256
    ).hexdigest()
    return envelope


def verify_envelope(
    envelope: dict[str, Any], expected_audience: str, key: str
) -> tuple[bool, str]:
    signature = str(envelope.get("signature", ""))
    expected = hmac.new(
        key.encode("utf-8"), _canonical(envelope), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return False, "signature mismatch"
    if envelope.get("audience") != expected_audience:
        return False, "audience mismatch"
    now = int(time.time())
    if int(envelope.get("issued_at", 0)) > now + 30:
        return False, "issued-at time is in the future"
    if int(envelope.get("expires_at", 0)) < now:
        return False, "handoff expired"
    if not envelope.get("nonce"):
        return False, "nonce missing"
    return True, "signature, audience, expiry, and nonce structure verified"
