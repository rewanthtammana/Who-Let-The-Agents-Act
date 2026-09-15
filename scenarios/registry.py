"""Scenario registry.

Keep scenario-specific imports and construction here so adding a scenario does
not require editing the web application itself. Every entry is:

    scenario_id -> (config, shared_database, shared_agent, scenario_root)

The shared database and agent are prototypes used to create isolated
per-browser-session instances in ``app.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

from scenarios.approval_service_outage.agent import ApprovalOutageAgent
from scenarios.approval_service_outage.database import ScenarioDatabase as ApprovalOutageDatabase
from scenarios.business_rule.agent import BusinessRuleAgent
from scenarios.business_rule.database import ScenarioDatabase as BusinessRuleDatabase
from scenarios.cross_customer_access.agent import CrossCustomerAccessAgent
from scenarios.cross_customer_access.database import ScenarioDatabase as CrossCustomerDatabase
from scenarios.indirect_injection.agent import IndirectInjectionAgent
from scenarios.indirect_injection.database import ScenarioDatabase as IndirectInjectionDatabase
from scenarios.multi_agent_confused_deputy.agent import MultiAgentConfusedDeputyAgent
from scenarios.multi_agent_confused_deputy.database import ScenarioDatabase as MultiAgentDatabase
from scenarios.overpowered_data_tool.agent import OverpoweredDataToolAgent
from scenarios.overpowered_data_tool.database import ScenarioDatabase as OverpoweredDataDatabase
from scenarios.rag_tenant_isolation.agent import RagTenantIsolationAgent
from scenarios.rag_tenant_isolation.database import ScenarioDatabase as RagTenantDatabase
from scenarios.secret_leakage.agent import SecretLeakageAgent
from scenarios.secret_leakage.database import ScenarioDatabase as SecretLeakageDatabase
from scenarios.signed_handoff.agent import SignedHandoffAgent
from scenarios.signed_handoff.database import ScenarioDatabase as SignedHandoffDatabase
from core.langchain_agent import GROQ

ROOT = Path(__file__).resolve().parent


def _register(root: Path, database_type: type, agent_type: type):
    config = json.loads((root / "scenario.json").read_text(encoding="utf-8"))
    database = database_type()
    database.initialize()
    agent = agent_type(database, GROQ)
    return config, database, agent, root


_registrations = [
    (ROOT / "overpowered_data_tool", OverpoweredDataDatabase, OverpoweredDataToolAgent),
    (ROOT / "cross_customer_access", CrossCustomerDatabase, CrossCustomerAccessAgent),
    (ROOT / "signed_handoff", SignedHandoffDatabase, SignedHandoffAgent),
    (ROOT / "business_rule", BusinessRuleDatabase, BusinessRuleAgent),
    (ROOT / "indirect_injection", IndirectInjectionDatabase, IndirectInjectionAgent),
    (ROOT / "rag_tenant_isolation", RagTenantDatabase, RagTenantIsolationAgent),
    (ROOT / "secret_leakage", SecretLeakageDatabase, SecretLeakageAgent),
    (ROOT / "approval_service_outage", ApprovalOutageDatabase, ApprovalOutageAgent),
    (ROOT / "multi_agent_confused_deputy", MultiAgentDatabase, MultiAgentConfusedDeputyAgent),
]

SCENARIOS = {config["id"]: entry for entry in (_register(*item) for item in _registrations) for config in [entry[0]]}
DATABASE = SCENARIOS["overpowered-data-tool"][1]
INJECTION_ROOT = SCENARIOS["indirect-injection"][3]
