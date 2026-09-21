# Refund Limit Bypass scenario

[Read the Refund Limit Bypass field guide](https://rewanthtammana.com/who-let-the-agents-act/blog/business-rule)

Each posture is deliberately isolated so the differences are easy to inspect:

- `modes/vulnerable.py` lets the model choose a refund amount and installment count, then executes every call without a cumulative transaction ceiling.
- `modes/prompt_only.py` adds a model-controlled refund guard, then reuses the unsafe repeated-call path when that guard allows the request.
- `modes/hardened.py` preflights the complete installment plan against persisted state, while every individual tool call independently enforces the cumulative limit, original transaction amount, and idempotency key.
- `agent_core.py` contains only shared model, prompt, run-artifact, error, and result plumbing. It is not a security posture.
- `agent.py` is the stable API facade used by the web app.
- `tools/refund_execute.py` exposes the payment action as a LangChain `@tool`; Hardened enables the tool-side policy recheck before a refund event is written.

The shared model adapter in `core/langchain_agent.py` uses LangChain `create_agent` and `ChatGroq`. The model may decompose one refund goal into multiple calls, but the Hardened boundary evaluates the complete state transition and rechecks each call in application code.

Hardened resolves the configured ceiling from `refund_policy`, totals prior Hardened refund events for the transaction, and uses the lower of the configured `$500` limit and the original payment amount. It blocks an oversized plan before any installment executes, then repeats the cumulative check inside `execute_refund` to protect direct or concurrent tool use. Stable operation keys make an exact retry return `already_completed`, while reuse for a different transaction or amount is rejected.

The SQLite transactions, field catalog, access policy, cumulative refund policy, audit log, and posture-separated refund ledger are defined in `schema.sql` and `seed.sql`. Separating events by posture prevents intentionally vulnerable runs from contaminating Hardened policy state. The database is generated at startup in `_data/`, and run artifacts such as `tool_plan.json`, `database_query.json`, and `tool_result.json` go in `_runs/`, keeping runtime state isolated from source files.
