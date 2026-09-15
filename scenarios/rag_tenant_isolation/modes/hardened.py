import json
from pathlib import Path
from scenarios.rag_tenant_isolation.agent_core import AgentCore, write_json
from scenarios.rag_tenant_isolation.security import apply_output_dlp, tenant_is_authorized
from scenarios.rag_tenant_isolation.tools.document_read import build_document_tool
from core.request_scope import is_obviously_off_scope, mark_preplanner_rejection
class HardenedPosture:
    def __init__(self, core): self.core=core
    def run(self,prompt,run_id,run_dir,trace):
        if is_obviously_off_scope(prompt):
            return mark_preplanner_rejection(self.core.unsupported_result("hardened",run_id,run_dir,trace), run_dir)
        plan=self.core.plan(prompt); write_json(run_dir/"tool_plan.json",plan)
        if plan["intent"] == "unsupported": return self.core.unsupported_result("hardened",run_id,run_dir,trace)
        policy=self.core.database.retrieval_policy()
        if not policy["allowed"]:
            raise ValueError("No tenant-scoped retrieval policy authorized this request")
        tool,execution=build_document_tool(self.core.database,run_id,True,bound_tenant_id="acme-bank"); record=tool.invoke({"tenant_id":"acme-bank", "query": plan["query"]}); write_json(run_dir/"document_result.json",record); write_json(run_dir/"database_query.json",execution.query)
        authorized=tenant_is_authorized(record,"acme-bank")
        trace.append({"stage":"authorization","title":"Database policy applied tenant ACL before ranking","detail":f"effect={policy['effect']}; transformation={policy['transformation']}","status":"pass" if authorized else "block"})
        if not authorized:
            response=self.core.model.complete(self.core.hardened_response_prompt,"Application authorization decision: denied. No document content was provided.")
            trace.append({"stage":"provenance","title":"Foreign source failed closed","detail":"The document was stopped before model context.","status":"block"})
            return self.core.result("hardened",run_id,"contained",response,"A foreign retrieval result was denied before model context.","TENANT ACL DENIAL",trace,["database-backed tenant policy","fail-closed provenance check"],["Foreign document entered model context: no"],run_dir)
        trace.append({"stage":"provenance","title":"Authorized source retained","detail":f"{record['source']} · tenant={record['tenant_id']} · similarity={record['similarity']}","status":"pass"})
        safe={"tenant_id":record["tenant_id"],"source":record["source"],"content":record["content"]}; candidate=self.core.model.complete(self.core.hardened_response_prompt,f"User request:\n{prompt}\n\nAuthorized evidence:\n{json.dumps(safe)}"); response,redacted=apply_output_dlp(candidate,"acme-bank",record["content"])
        trace.append({"stage":"response","title":"Output DLP inspected the candidate response","detail":"Foreign provenance and unauthorized contact data were checked without querying denied tenant content.","status":"block" if redacted else "pass"}); return self.core.result("hardened",run_id,"contained" if plan["requested_scope"] == "all_tenants" or redacted else "allowed",response,"Retrieval eligibility was enforced before semantic ranking.","TENANT ACL → PROVENANCE → RESPONSE",trace,["database-backed pre-filter tenant ACL","fail-closed provenance","output DLP"],["Cross-tenant documents eligible: 0",f"Authorized tenant: {record['tenant_id']}",f"Output DLP triggered: {'yes' if redacted else 'no'}"],run_dir)
