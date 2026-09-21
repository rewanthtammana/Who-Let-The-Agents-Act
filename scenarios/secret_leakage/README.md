# Secret Leakage Through Debugging scenario

[Read the Secret Leakage Through Debugging field guide](https://rewanthtammana.com/who-let-the-agents-act/blog/secret-leakage)

Each posture is deliberately isolated so the differences are easy to inspect:

- `modes/vulnerable.py` returns raw diagnostics, lets the model compose a downstream incident report from that observation, and allows the outbound tool to publish secret-bearing content.
- `modes/prompt_only.py` guards only the initial request, then reuses the unsafe diagnostics and report path when that guard allows the request.
- `modes/hardened.py` projects safe diagnostic fields before model context, requires database-backed authorization for publishing, and enforces secret DLP on the report body and final response.
- `agent_core.py` contains the separate diagnostics planner, report-action planner, model, run-artifact, and result plumbing. It is not a security posture.
- `agent.py` is the stable API facade used by the web app.
- `tools/diagnostics_read.py` and `tools/report_publish.py` expose the read and outbound actions as separate LangChain `@tool` boundaries; Hardened disables secret projection and passes explicit publish authority into the outbound tool.

The shared model adapter in `core/langchain_agent.py` uses LangChain `create_agent` and `ChatGroq`. The scenario deliberately includes a second planning step after diagnostics so a secret can be traced from tool observation to downstream action, while Hardened constrains both surfaces in application code.

Hardened always queries only `provider`, `status`, and `upstream_timeout`, excluding `environment_secret` before replanning. Publishing requires both a model-requested `publish_report` action and an `access_policy` match whose transformation is `redact_secrets`. `security.py` detects synthetic provider keys, AWS-style access keys, bearer tokens, JWTs, and common key/value credential forms. The report body is redacted before invocation, the tool blocks unauthorized or secret-bearing content, and the final response is scanned and redacted again.

The SQLite diagnostic record, field catalog, separate read and publish access policies, and audit log are defined in `schema.sql` and `seed.sql`. All credential material is synthetic and belongs only to this scenario. The database is generated at startup in `_data/`, and run artifacts such as `tool_plan.json`, `database_query.json`, `tool_result.json`, `report_plan.json`, and `report_result.json` go in `_runs/`, keeping runtime state isolated from source files.
