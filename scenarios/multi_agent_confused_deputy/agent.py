from scenarios.multi_agent_confused_deputy.agent_core import AgentCore, Mode, ModelClient
from scenarios.multi_agent_confused_deputy.database import ScenarioDatabase
from scenarios.multi_agent_confused_deputy.modes.hardened import HardenedPosture
from scenarios.multi_agent_confused_deputy.modes.prompt_only import PromptOnlyPosture
from scenarios.multi_agent_confused_deputy.modes.vulnerable import VulnerablePosture


class MultiAgentConfusedDeputyAgent:
    def __init__(self, database: ScenarioDatabase, model: ModelClient) -> None:
        self.core = AgentCore(database, model)
        self.planner_prompt = self.core.planner_prompt
        self.fraud_review_prompt = self.core.fraud_review_prompt
        self.account_control_prompt = self.core.account_control_prompt
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
