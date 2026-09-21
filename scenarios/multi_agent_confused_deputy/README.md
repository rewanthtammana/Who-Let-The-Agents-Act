# Confused Deputy Agent Chain scenario

[Read the Confused Deputy Agent Chain field guide](https://rewanthtammana.com/who-let-the-agents-act/blog/confused-deputy-agent-chain)

Each posture is deliberately isolated so the differences are easy to inspect:

- `modes/vulnerable.py` passes merchant-controlled evidence through a coordinator, fraud reviewer, and account-control agent, laundering it into authoritative prose and an unchecked account-freeze action.
- `modes/prompt_only.py` adds a model-controlled guard between the reviewer and receiver, then reuses the unsafe handoff and freeze path when that guard allows the recommendation.
- `modes/hardened.py` verifies the registered three-agent chain, creates a typed taint-aware handoff without raw merchant prose or delegated authority, and requires the final tool to reauthorize both the action and target.
- `agent_core.py` contains the coordinator, fraud-review, handoff-guard, account-control, response-model, run-artifact, and result plumbing. It is not a security posture.
- `agent.py` is the stable API facade used by the web app.
- `tools/case_read.py` and `tools/account_freeze.py` expose case retrieval and account control as separate LangChain `@tool` actions; both validate identifier formats, and Hardened enables receiver-side policy before any account lookup or write.

The shared model adapter in `core/langchain_agent.py` uses LangChain `create_agent` and `ChatGroq`. Three distinct structured model decisions remain visible, but no upstream agent recommendation grants authority to the final side-effecting tool.

Hardened verifies active coordinator-to-reviewer, reviewer-to-controller, and controller-to-tool relationships in `agent_registry`. `security.py` builds a `fraud_action_request.v1` handoff that preserves the case ID, authenticated customer, subject account, case status, recommendation, target, and an explicit `untrusted-merchant-derived` label, while setting `authority_forwarded` to false. At the receiver, authorization requires a matching account-control policy, a target equal to the case subject, a subject inside the authenticated customer scope, and an explicit approval for the same account. Unauthorized target details are not queried merely to explain a denial.

The SQLite bank accounts, fraud cases, field catalog, access policy, case-action approvals, agent registry, freeze-event ledger, and audit log are defined in `schema.sql` and `seed.sql`. The run artifacts preserve every plan and handoff so the multi-hop causal chain stays inspectable. The database is generated at startup in `_data/`, and artifacts such as `coordinator_plan.json`, `fraud_review_plan.json`, `handoff_payload.json`, `account_control_plan.json`, and `authorization_decision.json` go in `_runs/`, keeping runtime state isolated from source files.
