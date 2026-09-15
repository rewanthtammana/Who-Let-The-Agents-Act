from dataclasses import dataclass
from typing import Any
from langchain_core.tools import BaseTool, tool
from scenarios.rag_tenant_isolation.database import ScenarioDatabase

@dataclass
class ToolExecution: query: dict[str, Any] | None = None

def build_document_tool(
    database: ScenarioDatabase,
    run_id: str,
    tenant_filter: bool,
    bound_tenant_id: str | None = None,
) -> tuple[BaseTool, ToolExecution]:
    execution = ToolExecution()
    @tool("policy_document_read")
    def policy_document_read(tenant_id: str, query: str) -> dict[str, Any]:
        """Retrieve the most relevant policy document."""
        if bound_tenant_id is not None and tenant_id != bound_tenant_id:
            raise ValueError("policy_document_read received a tenant outside delegated scope")
        outcome = database.retrieve(run_id, tenant_id, query, tenant_filter); execution.query = outcome["query"]; return outcome["record"]
    return policy_document_read, execution
