from __future__ import annotations
import json, sqlite3
from pathlib import Path
from typing import Any
from core.sqlite import connect as connect_sqlite

SCENARIO_ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE_PATH = SCENARIO_ROOT / "_data" / "signed_handoff.sqlite3"

class TransferNotFound(LookupError): pass

class ScenarioDatabase:
    def __init__(self, path: Path = DEFAULT_DATABASE_PATH) -> None: self.path = Path(path)
    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        c = connect_sqlite(self.path); c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON"); return c
    def initialize(self) -> None:
        with self.connect() as c:
            c.executescript((SCENARIO_ROOT / "schema.sql").read_text())
            c.executescript((SCENARIO_ROOT / "seed.sql").read_text())
    def get_transfer(self, run_id: str, request_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        statement = "SELECT request_id, customer_name, amount, currency, recipient, status FROM transfer_requests WHERE request_id = ?"
        with self.connect() as c:
            row = c.execute(statement, (request_id,)).fetchone()
            if row is None: raise TransferNotFound(f"No transfer matched {request_id!r}")
            result = dict(row)
            c.execute("INSERT INTO audit_log(run_id,event,detail) VALUES (?,?,?)", (run_id, "transfer.read", json.dumps({"request_id": request_id})))
        return result, {"statement": statement, "parameters": [request_id]}
    def registry(self, agent_id: str) -> dict[str, Any] | None:
        with self.connect() as c:
            row = c.execute("SELECT agent_id, audience, status, allowed_action FROM agent_registry WHERE agent_id = ?", (agent_id,)).fetchone()
        return dict(row) if row else None
    def signing_key(self, agent_id: str) -> str | None:
        with self.connect() as c:
            row = c.execute(
                "SELECT synthetic_key FROM agent_signing_keys WHERE agent_id = ?",
                (agent_id,),
            ).fetchone()
        return str(row["synthetic_key"]) if row else None
    def consume_nonce(self, nonce: str, sender: str, audience: str, expires_at: int) -> bool:
        if not nonce:
            return False
        with self.connect() as c:
            c.execute("DELETE FROM consumed_nonces WHERE expires_at < unixepoch()")
            try:
                c.execute(
                    "INSERT INTO consumed_nonces(nonce, sender, audience, expires_at) VALUES (?, ?, ?, ?)",
                    (nonce, sender, audience, expires_at),
                )
            except sqlite3.IntegrityError:
                return False
        return True
    def secret_context(self, request_id: str) -> dict[str, str]:
        with self.connect() as c:
            row = c.execute("SELECT support_transcript, password_reset_token FROM transfer_requests WHERE request_id = ?", (request_id,)).fetchone()
        return dict(row) if row else {}
    def record_event(self, run_id: str, event: str, detail: dict[str, Any]) -> None:
        with self.connect() as c: c.execute("INSERT INTO audit_log(run_id,event,detail) VALUES (?,?,?)", (run_id, event, json.dumps(detail)))
    def health(self) -> dict[str, Any]:
        with self.connect() as c: count = c.execute("SELECT count(*) FROM transfer_requests").fetchone()[0]
        return {"path": str(self.path.relative_to(SCENARIO_ROOT.parent.parent)), "transfer_requests": count}
    def reset_runtime(self) -> None:
        with self.connect() as c:
            c.execute("DELETE FROM consumed_nonces")
            c.execute("DELETE FROM audit_log")
