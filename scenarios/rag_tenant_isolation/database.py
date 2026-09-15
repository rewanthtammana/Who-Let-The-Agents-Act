from __future__ import annotations
import json, re, sqlite3
from pathlib import Path
from typing import Any
from core.sqlite import connect as connect_sqlite

SCENARIO_ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE_PATH = SCENARIO_ROOT / "_data" / "rag_tenant_isolation.sqlite3"

class DocumentNotFound(LookupError): pass

class ScenarioDatabase:
    def __init__(self, path: Path = DEFAULT_DATABASE_PATH) -> None: self.path = Path(path)
    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True); c = connect_sqlite(self.path); c.row_factory = sqlite3.Row; return c
    def initialize(self) -> None:
        with self.connect() as c:
            c.executescript((SCENARIO_ROOT / "schema.sql").read_text(encoding="utf-8")); c.executescript((SCENARIO_ROOT / "seed.sql").read_text(encoding="utf-8"))
    def field_catalog(self) -> list[dict[str, Any]]:
        with self.connect() as c: rows = c.execute("SELECT field_name, description, classification, sensitive FROM field_catalog ORDER BY rowid").fetchall()
        return [{**dict(row), "access": "tenant-scoped"} for row in rows]
    def retrieval_policy(
        self,
        principal: str = "support_agent",
        resource: str = "policy_document",
        purpose: str = "policy_lookup",
        action: str = "read",
    ) -> dict[str, Any]:
        with self.connect() as c:
            row = c.execute(
                "SELECT effect, transformation FROM access_policy "
                "WHERE principal = ? AND resource = ? AND purpose = ? AND action = ? "
                "ORDER BY id LIMIT 1",
                (principal, resource, purpose, action),
            ).fetchone()
        if row is None:
            return {"allowed": False, "effect": "deny", "transformation": "none"}
        return {
            "allowed": row["effect"] == "allow" and row["transformation"] == "tenant_acl_before_ranking",
            "effect": str(row["effect"]),
            "transformation": str(row["transformation"]),
        }
    def retrieve(self, run_id: str, tenant_id: str, query: str, tenant_filter: bool) -> dict[str, Any]:
        statement = "SELECT tenant_id, source, classification, similarity, content FROM documents WHERE tenant_id = ?" if tenant_filter else "SELECT tenant_id, source, classification, similarity, content FROM documents"
        params = [tenant_id] if tenant_filter else []
        with self.connect() as c:
            rows = c.execute(statement, params).fetchall()
            if not rows: raise DocumentNotFound("No policy document matched the request")
            def tokens(value: str) -> set[str]:
                return {token[:-1] if token.endswith("s") and len(token) > 3 else token for token in re.findall(r"[a-z0-9]+", value.lower())}
            terms = tokens(query)
            def rank(row):
                document_terms = tokens(f"{row['source']} {row['content']}")
                lexical = len(terms & document_terms) / max(1, len(terms))
                return lexical + float(row["similarity"])
            row = max(rows, key=rank)
            record = dict(row)
            record["query_score"] = round(rank(row), 3)
            c.execute("INSERT INTO audit_log(run_id, event, detail) VALUES (?, ?, ?)", (run_id, "document.retrieve", json.dumps({"tenant_filter": tenant_filter, "tenant_id": tenant_id, "query": query})))
        return {"record": record, "query": {"statement": statement, "parameters": params, "semantic_query": query}}
    def record_event(self, run_id: str, event: str, detail: dict[str, Any]) -> None:
        with self.connect() as c: c.execute("INSERT INTO audit_log(run_id, event, detail) VALUES (?, ?, ?)", (run_id, event, json.dumps(detail)))
    def health(self) -> dict[str, Any]:
        with self.connect() as c: count = c.execute("SELECT count(*) FROM documents").fetchone()[0]
        return {"path": str(self.path.relative_to(SCENARIO_ROOT.parent.parent)), "documents": count}
