# Poisoned Invoice Instructions scenario

[Read the Poisoned Invoice Instructions field guide](https://rewanthtammana.com/who-let-the-agents-act/blog/poisoned-invoice-instructions)

Each posture is deliberately isolated so the differences are easy to inspect:

- `modes/vulnerable.py` retrieves vendor-controlled invoice text, lets the model replan from that observation, and submits a document-proposed payment without an independent beneficiary policy.
- `modes/prompt_only.py` guards only the initial user request, then reuses the unsafe retrieval, observation-replanning, and payment path after an allowed decision.
- `modes/hardened.py` keeps document text explicitly untrusted and requires every model-proposed amount and beneficiary to match bank-controlled invoice fields at the payment tool.
- `agent_core.py` contains the separate user-request planner, observation-action planner, model, run-artifact, and result plumbing. It is not a security posture.
- `agent.py` is the stable API facade used by the web app.
- `tools/invoice_read.py` and `tools/payment_submit.py` expose retrieval and payment as separate LangChain `@tool` actions; Hardened enables the payment tool's trusted-field authorization check.

The shared model adapter in `core/langchain_agent.py` uses LangChain `create_agent` and `ChatGroq`. This scenario deliberately performs a second structured model decision after retrieval so the delayed injection is visible, while application code remains authoritative over the side effect.

Hardened allows vendor text to influence summarization and even propose a payment, but it does not let that text supply authority. The payment is submitted only when the proposed beneficiary exactly equals `approved_beneficiary` and the amount exactly equals `amount_due`; otherwise the tool returns a blocked result. The response model receives only trusted invoice fields plus the enforced payment result. Uploaded TXT, Markdown, CSV, JSON, DOCX, and PDF content is extracted as text, capped at 1 MB, attached only to a known synthetic invoice, and cannot replace the trusted payment columns.

The SQLite invoices, trusted payment fields, field catalog, access policy, document provenance, and audit log are defined in `schema.sql` and `seed.sql`. `default_invoice.txt`, `malicious_invoice.txt`, and `malicious_invoice_approved_test.txt` provide repeatable clean, attack, and bypass fixtures; filename, variant, version, update time, and SHA-256 remain inspectable. The database is generated at startup in `_data/`, and run artifacts such as `tool_plan.json`, `invoice_result.json`, `observation_action_plan.json`, and `payment_result.json` go in `_runs/`, keeping runtime state isolated from source files.
