from scenarios.rag_tenant_isolation.agent_core import AgentCore, Mode, ModelClient
from scenarios.rag_tenant_isolation.database import ScenarioDatabase
from scenarios.rag_tenant_isolation.modes.vulnerable import VulnerablePosture
from scenarios.rag_tenant_isolation.modes.prompt_only import PromptOnlyPosture
from scenarios.rag_tenant_isolation.modes.hardened import HardenedPosture
class RagTenantIsolationAgent:
    def __init__(self,database:ScenarioDatabase,model:ModelClient):
        self.core=AgentCore(database,model); self.planner_prompt=self.core.planner_prompt; self.guard_prompt=self.core.guard_prompt; self.hardened_response_prompt=self.core.hardened_response_prompt; self.unsupported_response_prompt=self.core.unsupported_response_prompt
        self.vulnerable=VulnerablePosture(self.core); self.prompt_only=PromptOnlyPosture(self.core); self.hardened=HardenedPosture(self.core)
    def run(self,mode:Mode,prompt:str)->dict:
        if mode not in {"vulnerable","prompt_only","hardened"}: raise ValueError(f"Unsupported security posture: {mode}")
        run_id,run_dir,trace=self.core.start_run(mode,prompt); return getattr(self,mode).run(prompt,run_id,run_dir,trace)
