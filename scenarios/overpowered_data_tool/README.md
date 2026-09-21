# Overpowered Data Tool scenario

[Read the Overpowered Data Tool field guide](https://rewanthtammana.com/who-let-the-agents-act/blog/overpowered-data-tool)

Each posture is deliberately isolated so the differences are easy to inspect:

- `modes/vulnerable.py` lets the model choose fields and returns the SQLite tool result directly.
- `modes/prompt_only.py` adds a model-controlled prompt guard, then reuses the unsafe execution path.
- `modes/hardened.py` keeps the model planner, but applies database-backed role/purpose/field authorization, server-side projection, and LangChain PII middleware.
- `agent_core.py` contains only shared model, run-artifact, and database plumbing. It is not a security posture.
- `agent.py` is the stable API facade used by the web app.
- `tools/customer_read.py` exposes the database action as a LangChain `@tool`; its per-run allowlist is enforced before SQLite is touched.

The shared model adapter in `core/langchain_agent.py` uses LangChain `create_agent` and `ChatGroq`. The scenario deliberately keeps authorization outside the model runtime so the Hardened boundary remains inspectable.

Hardened output uses LangChain `PIIMiddleware`. It uses the built-in middleware strategy for common PII and a scenario detector for the synthetic card format and banking-specific fields; the demo card is fake and is not required to pass Luhn validation.

The SQLite catalog and access policy are in `schema.sql` and `seed.sql`. The demo uses one support-agent policy, but models the production direction: field metadata is separate from access rules, and decisions depend on principal, resource, purpose, and action rather than one global allow flag. The database is generated at startup in `_data/`, and run artifacts go in `_runs/`, keeping runtime state isolated from source files.
