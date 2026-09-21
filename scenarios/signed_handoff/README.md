# Unsafe Agent Handoff scenario

[Read the Unsafe Agent Handoff field guide](https://rewanthtammana.com/who-let-the-agents-act/blog/signed-handoff)

Each posture is deliberately isolated so the differences are easy to inspect:

- `modes/vulnerable.py` lets the router forward model-selected context, including a support transcript, password-reset token, or execution authority, in an unsigned handoff that the specialist trusts directly.
- `modes/prompt_only.py` adds a model-controlled handoff guard, then reuses the unsafe forwarding and receiver path when that guard allows the request.
- `modes/hardened.py` verifies the active sender and receiver registry, minimizes the payload, signs an audience-bound typed envelope, checks expiry, consumes a replay nonce, and enforces the specialist's independent validation-only scope.
- `agent_core.py` contains only shared model, prompt, run-artifact, and result plumbing. It is not a security posture.
- `agent.py` is the stable API facade used by the web app.
- `tools/transfer_validate.py` exposes validation as a LangChain `@tool`; it requires the receiver's registered action and rejects any request other than `validate_transfer` before reading SQLite.

The shared model adapter in `core/langchain_agent.py` uses LangChain `create_agent` and `ChatGroq`. The model plans the handoff context and requested action, but Hardened authenticates the delegation and limits what the receiver can do in application code.

Hardened handoffs contain only `request_id`, `amount`, `currency`, and `recipient`. `security.py` canonicalizes the envelope and applies an HMAC-SHA256 signature over sender, audience, issued-at time, expiry, nonce, and payload. Verification checks the signature, expected audience, time bounds, and nonce structure; `database.py` then atomically records the nonce so replay fails. The specialist receives the minimal authenticated payload and a validation-only tool result, never the support transcript, reset token, or transfer-execution authority.

The SQLite transfer requests, active agent registry, synthetic signing material, consumed-nonce ledger, and audit log are defined in `schema.sql` and `seed.sql`. The signing key is intentionally scenario-local teaching data, not a production key-management design. The database is generated at startup in `_data/`, and run artifacts such as `handoff_plan.json`, `handoff_payload.json`, `database_query.json`, and `tool_result.json` go in `_runs/`, keeping runtime state isolated from source files.
