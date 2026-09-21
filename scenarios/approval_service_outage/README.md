# Approval Service Outage scenario

[Read the Approval Service Outage field guide](https://rewanthtammana.com/who-let-the-agents-act/blog/approval-service-outage)

Each posture is deliberately isolated so the differences are easy to inspect:

- `modes/vulnerable.py` treats a simulated approval timeout and missing decision as permission, then writes the payment ledger through the unsafe fail-open tool path.
- `modes/prompt_only.py` shows dependency health to a model-controlled payment guard, then reuses the fail-open path when that guard allows the request.
- `modes/hardened.py` requires an affirmative approval at the payment boundary, blocks explicit denials, and safely queues requests whose approval decision is unavailable without writing the execution ledger.
- `agent_core.py` contains only shared model, prompt, dependency-context, run-artifact, error, and result plumbing. It is not a security posture.
- `agent.py` is the stable API facade used by the web app.
- `tools/payment_submit.py` exposes the side effect as a LangChain `@tool`; it validates `PAY-0000` request IDs and bounded idempotency keys before invoking the scenario database with an explicit fail-open or fail-closed posture.

The shared model adapter in `core/langchain_agent.py` uses LangChain `create_agent` and `ChatGroq`. The model chooses which valid payment request to submit, but it does not control the simulated dependency state, approval decision, fallback policy, or payment ledger.

Hardened separates availability from authorization in `security.py`: only `approved` returns authority, `denied` blocks, and a timeout with no decision produces the `queue` fallback rather than `allow`. `database.py` persists the pending request for later review, performs no payment ledger write, and records the decision and dependency state in the audit log. A stable idempotency key prevents recovery or retry from duplicating an already handled payment. The healthy `PAY-3003` fixture provides an explicit-denial comparison distinct from an outage.

The SQLite payment requests, field catalog, access policy, approval rules, simulated dependency state, executed-payment ledger, pending queue, and audit log are defined in `schema.sql` and `seed.sql`. The outage is an explicit lab condition rather than a model inference. The database is generated at startup in `_data/`, and run artifacts such as `dependency_check.json`, `authorization_decision.json`, `database_query.json`, and `payment_ledger.json` go in `_runs/`, keeping runtime state isolated from source files.
