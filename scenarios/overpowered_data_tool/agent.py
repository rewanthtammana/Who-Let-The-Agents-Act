from __future__ import annotations

from scenarios.overpowered_data_tool.agent_core import AgentCore, Mode, ModelClient
from scenarios.overpowered_data_tool.database import ScenarioDatabase
from scenarios.overpowered_data_tool.modes.hardened import HardenedPosture
from scenarios.overpowered_data_tool.modes.prompt_only import PromptOnlyPosture
from scenarios.overpowered_data_tool.modes.vulnerable import VulnerablePosture


class OverpoweredDataToolAgent:
    """Stable API facade; security postures are intentionally separate modules."""

    def __init__(self, database: ScenarioDatabase, model: ModelClient) -> None:
        self.core = AgentCore(database, model)
        self.database = database
        self.model = model
        self.planner_prompt = self.core.planner_prompt
        self.guard_prompt = self.core.guard_prompt
        self.hardened_response_prompt = self.core.hardened_response_prompt
        self.unsupported_response_prompt = self.core.unsupported_response_prompt
        self.vulnerable = VulnerablePosture(self.core)
        self.prompt_only = PromptOnlyPosture(self.core)
        self.hardened = HardenedPosture(self.core)

    def _guard(self, prompt: str):
        return self.core.guard(prompt)

    def _plan(self, prompt: str):
        return self.core.plan(prompt)

    def run(self, mode: Mode, prompt: str) -> dict:
        if mode not in {"vulnerable", "prompt_only", "hardened"}:
            raise ValueError(f"Unsupported security posture: {mode}")

        run_id, run_dir, trace = self.core.start_run(mode, prompt)
        if mode == "vulnerable":
            return self.vulnerable.run(prompt, run_id, run_dir, trace)
        if mode == "prompt_only":
            return self.prompt_only.run(prompt, run_id, run_dir, trace)
        if mode == "hardened":
            return self.hardened.run(prompt, run_id, run_dir, trace)

        raise AssertionError("validated security posture was not dispatched")
