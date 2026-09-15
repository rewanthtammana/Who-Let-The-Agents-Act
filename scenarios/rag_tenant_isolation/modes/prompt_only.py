from scenarios.rag_tenant_isolation.agent_core import write_json
from scenarios.rag_tenant_isolation.modes.vulnerable import execute
class PromptOnlyPosture:
    def __init__(self, core): self.core=core
    def run(self,prompt,run_id,run_dir,trace):
        guard=self.core.guard(prompt); write_json(run_dir/"guard_decision.json",guard); self.core.database.record_event(run_id,"prompt_guard",guard)
        if guard.get("decision") == "refuse":
            trace.extend([{"stage":"prompt-guard","title":"Model-controlled tenant guard refused","detail":guard.get("reason","The request crossed a tenant boundary."),"status":"pass"},{"stage":"tool","title":"Retrieval tool was not called","detail":"The prompt-only decision stopped the run.","status":"pass"}]); return self.core.result("prompt_only",run_id,"refused",guard.get("reason","Request refused."),"The model guard refused the request before retrieval.","GROQ TENANT GUARD",trace,["prompt-only model guard"],["Database reads: 0"],run_dir)
        trace.append({"stage":"prompt-guard","title":"Model-controlled tenant guard allowed","detail":guard.get("reason","The model allowed the request."),"status":"warn"})
        plan=self.core.plan(prompt)
        if plan["intent"] == "unsupported": return self.core.unsupported_result("prompt_only",run_id,run_dir,trace)
        return execute(self.core,"prompt_only",run_id,run_dir,trace,["prompt-only model guard"],plan)
