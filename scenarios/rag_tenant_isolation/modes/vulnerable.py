import json
from pathlib import Path
from scenarios.rag_tenant_isolation.agent_core import AgentCore, write_json
from scenarios.rag_tenant_isolation.tools.document_read import build_document_tool

def execute(core: AgentCore, mode: str, run_id: str, run_dir: Path, trace: list[dict], controls: list[str], plan: dict) -> dict:
    write_json(run_dir / "tool_plan.json", plan); tool, execution = build_document_tool(core.database, run_id, plan["requested_scope"] == "current_tenant"); record = tool.invoke({"tenant_id":"acme-bank", "query": plan["query"]}); write_json(run_dir / "document_result.json", record); write_json(run_dir / "database_query.json", execution.query)
    foreign = record["tenant_id"] != "acme-bank"; trace.extend([{"stage":"retrieval","title":"Query-dependent global ranking","detail":f"The agent query '{plan['query']}' selected {record['source']} (score={record['query_score']}) before tenant authorization.","status":"block" if foreign else "warn"},{"stage":"output","title":"Foreign policy disclosed" if foreign else "Own policy returned","detail":record["content"],"status":"block" if foreign else "pass"}])
    response = json.dumps(record, indent=2); return core.result(mode, run_id, "exposed" if foreign else "allowed", response, "The model cannot reliably repair an authorization failure that happened during retrieval." if foreign else "The normal request returned the current tenant's policy.", "GLOBAL RETRIEVAL → RAW RESULT", trace, controls, [f"Tenant returned: {record['tenant_id']}", "Tenant ACL: absent"], run_dir)

class VulnerablePosture:
    def __init__(self, core): self.core=core
    def run(self, prompt, run_id, run_dir, trace):
        plan=self.core.plan(prompt)
        if plan["intent"] == "unsupported": return self.core.unsupported_result("vulnerable",run_id,run_dir,trace)
        return execute(self.core,"vulnerable",run_id,run_dir,trace,[],plan)
