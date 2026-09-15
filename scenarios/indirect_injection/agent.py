from scenarios.indirect_injection.agent_core import AgentCore, Mode, ModelClient
from scenarios.indirect_injection.database import ScenarioDatabase
from scenarios.indirect_injection.modes.hardened import HardenedPosture
from scenarios.indirect_injection.modes.prompt_only import PromptOnlyPosture
from scenarios.indirect_injection.modes.vulnerable import VulnerablePosture


class IndirectInjectionAgent:
    def __init__(self, database: ScenarioDatabase, model: ModelClient) -> None:
        self.core = AgentCore(database, model)
        self.planner_prompt = self.core.planner_prompt
        self.guard_prompt = self.core.guard_prompt
        self.hardened_response_prompt = self.core.hardened_response_prompt
        self.unsupported_response_prompt = self.core.unsupported_response_prompt
        self.vulnerable = VulnerablePosture(self.core)
        self.prompt_only = PromptOnlyPosture(self.core)
        self.hardened = HardenedPosture(self.core)

    def run(self, mode: Mode, prompt: str) -> dict:
        if mode not in {"vulnerable", "prompt_only", "hardened"}:
            raise ValueError(f"Unsupported security posture: {mode}")
        run_id, run_dir, trace = self.core.start_run(mode, prompt)
        return getattr(self, mode).run(prompt, run_id, run_dir, trace)
