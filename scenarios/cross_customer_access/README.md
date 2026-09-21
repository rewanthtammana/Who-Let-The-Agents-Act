# Cross-Account Access scenario

[Read the Cross-Account Access field guide](https://rewanthtammana.com/who-let-the-agents-act/blog/cross-customer-access)

Each posture is deliberately isolated so the differences are easy to inspect:

- `modes/vulnerable.py` lets the model select a customer ID, then runs `transaction_read` with the broad `support_agent_service` identity and returns the SQLite result directly.
- `modes/prompt_only.py` adds a model-controlled ownership guard, then reuses the unsafe execution path when that guard allows the request.
- `modes/hardened.py` resolves the authenticated principal and customer from session state, applies database-backed object-level authorization before the tool call, and binds the tool to the authorized customer ID.
- `agent_core.py` contains only shared model, prompt, run-artifact, and result plumbing. It is not a security posture.
- `agent.py` is the stable API facade used by the web app.
- `tools/transaction_read.py` exposes the database action as a LangChain `@tool`; Hardened supplies a per-run `bound_customer_id` that is checked before SQLite is touched.

The shared model adapter in `core/langchain_agent.py` uses LangChain `create_agent` and `ChatGroq`. The model may propose a customer ID, but the Hardened path treats that value as untrusted input rather than delegated authority.

Hardened authorization loads `demo-session` from `session_context`, resolves its principal and customer, and matches principal, resource, purpose, and action in `access_policy`. A foreign customer ID is refused before `transaction_read` runs, while an allowed read uses a parameterized query scoped to the authenticated customer. The application refuses mismatches instead of silently replacing the requested ID, and the response model receives only the denial or authorized transaction rows.

The SQLite customer data, session binding, field catalog, access policy, transactions, and audit log are defined in `schema.sql` and `seed.sql`. The synthetic session maps to customer `C100`, while separate foreign customers make object-level denial observable. The database is generated at startup in `_data/`, and run artifacts such as `tool_plan.json`, `database_query.json`, and `tool_result.json` go in `_runs/`, keeping runtime state isolated from source files.
