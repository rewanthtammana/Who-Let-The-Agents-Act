# Multi-tenant RAG Leakage scenario

[Read the Multi-tenant RAG Leakage field guide](https://rewanthtammana.com/who-let-the-agents-act/blog/rag-tenant-isolation)

Each posture is deliberately isolated so the differences are easy to inspect:

- `modes/vulnerable.py` ranks the global document corpus from the model's semantic query and returns the highest-scoring record even when it belongs to another tenant.
- `modes/prompt_only.py` adds a model-controlled tenant guard, then reuses the retriever whose effective scope can still remain global after an allowed decision.
- `modes/hardened.py` loads database policy, restricts document eligibility to the bound tenant before ranking, verifies returned provenance fail-closed, and applies an independent output DLP check.
- `agent_core.py` contains only shared model, prompt, run-artifact, and result plumbing. It is not a security posture.
- `agent.py` is the stable API facade used by the web app.
- `tools/document_read.py` exposes retrieval as a LangChain `@tool`; Hardened binds the tool to `acme-bank` and rejects any other tenant ID before SQLite is touched.

The shared model adapter in `core/langchain_agent.py` uses LangChain `create_agent` and `ChatGroq`. The model supplies the semantic query and requested scope, but the Hardened candidate set is computed by application and database policy before query-dependent ranking.

Hardened requires an `access_policy` match whose transformation is `tenant_acl_before_ranking`, applies `WHERE tenant_id = ?` before lexical-plus-stored-similarity ranking, and verifies the selected record still belongs to the authorized tenant before model context. `security.py` then rejects a candidate response containing foreign `*-bank` provenance or email addresses absent from the authorized evidence. The DLP check never queries denied tenant documents, so the backstop does not create a second privileged retrieval path.

The SQLite corpus, tenant provenance, classification, stored similarity values, field catalog, access policy, and audit log are defined in `schema.sql` and `seed.sql`. Multiple documents for both Acme Bank and Northstar Bank make pre-filtering and ranking behavior reproducible. The database is generated at startup in `_data/`, and run artifacts such as `tool_plan.json`, `database_query.json`, and `document_result.json` go in `_runs/`, keeping runtime state isolated from source files.
