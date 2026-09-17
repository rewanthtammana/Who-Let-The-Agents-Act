# Technicals

This document covers the architecture, scenario conventions, deployment options, and verification workflow for Who Let the Agents Act.

## Architecture

Groq uses LangChain `create_agent` to produce structured plans, reconsider plans after tool observations, and generate bounded responses. Application code validates intent, authorization, projections, business rules, and tool arguments. Vulnerable and Prompt-only modes intentionally expose unsafe paths; Hardened mode contains them.

Every scenario identifies the model decision that creates risk and the deterministic boundary that contains a compromised agent. Multi-step scenarios preserve the causal chain in artifacts: initial plan, tool observation, follow-up plan, enforcement, and outcome.

Unsupported natural-language requests are classified before tool access and receive model-generated, scenario-scoped replies. Presets only populate the prompt editor. Outcomes and responses are produced at runtime; Groq failures are surfaced.

### Hardened request flow

Groq is an untrusted planner, not the authorization boundary:

```text
user request -> deterministic obvious-risk gate -> Groq structured plan
             -> application validation and policy -> restricted tool -> bounded response
```

The deterministic gate stops clearly unrelated or instruction-override/bulk-access requests before planning. For the remaining requests, Groq may propose an intent, identifier, field, or action, but application code validates it and the tool independently enforces identity, tenant, field, business-rule, approval, provenance, and DLP controls. Only the authorized result is returned to Groq for response wording. A model mistake may cause a refusal or contained result; it must not grant authority.

Vulnerable and Prompt-only modes intentionally omit some application boundaries so the lab can demonstrate why prompt instructions alone are insufficient. Each scenario field guide maps this shared flow to its specific policy.

## Scenario structure

Each scenario is self-contained:

```text
scenarios/<scenario_id>/
  __init__.py
  agent.py                 # stable facade used by the API
  agent_core.py            # neutral shared plumbing only
  database.py              # scenario-specific SQLite access
  security.py              # deterministic security checks or DLP
  tools/                   # explicit LangChain tool wrappers
  schema.sql               # schema and policy tables
  seed.sql                 # synthetic scenario data
  scenario.json            # UI and scenario metadata
  *_prompt.txt             # model instructions, when needed
  modes/
    vulnerable.py
    prompt_only.py
    hardened.py
  _data/                   # generated, ignored SQLite database
  _runs/                   # generated, ignored per-run artifacts
```

Keep schema, seed data, prompts, and policy definitions source-controlled. Generated SQLite files and per-run artifacts belong in `_data/` and `_runs/`, and should remain ignored. Use synthetic data only.

Keep field metadata separate from access rules: use a catalog for classification, sensitivity, and masking strategy, and an access-policy table for principal, resource, purpose, action, effect, and transformation. Do not replace this with a single global per-field authorization flag.

## Runtime behavior

The UI sends only the selected mode and user prompt. Groq dynamically interprets the prompt and creates a structured tool plan where the scenario needs one. The application validates the model response and executes a real parameterized SQLite query. Vulnerable and Prompt-only paths intentionally demonstrate raw-result exposure. Hardened mode applies authorization and projection before data enters model context, then applies LangChain PII middleware to model output and tool-result surfaces.

The current Overpowered Data Tool API response includes:

```text
run_id, scenario_id, mode, verdict, response, summary, badge,
model, trace, controls, evidence, artifacts
```

Runtime scenario databases are seeded per browser session, not shared between visitors. Session state expires after `SESSION_TTL_SECONDS` (30 minutes by default), and reset, fixture, and dependency controls affect only the current session. The UI provides both current-scenario reset and full-session reset actions.

The poisoned-invoice scenario accepts TXT, Markdown, CSV, JSON, DOCX, and PDF vendor uploads. Uploads replace only the untrusted document text for the existing synthetic invoice; trusted amount, currency, and beneficiary data cannot be changed by the document. Clean, Vulnerable-mode attack, and Prompt-only bypass fixtures are downloadable from the scenario UI.

## Docker and deployment

Docker Compose is the recommended development path. The repository is mounted into the container, so backend and frontend edits are picked up by the reload process and generated runtime files remain local.

```bash
docker compose up --build -d
docker compose logs -f who-let-the-agents-act
```

Use `docker compose restart` after a runtime change, `docker compose up -d --build` after changing `requirements.txt`, and `docker compose down` to stop the app. To use another host port:

```bash
APP_PORT=8001 docker compose up -d
```

The included Compose stack can deploy the lab on a small Linux host with Docker, a public DNS record, and ports 80/443 open. Set `DOMAIN` in `.env`, along with `COOKIE_SECURE=1` and `GROQ_API_KEYS`, then run:

```bash
./deploy.sh
```

The script starts the app behind Caddy and waits for `/api/health`. Caddy obtains and renews the HTTPS certificate for `DOMAIN`; DNS must already point to the host. Keep the application port bound to localhost and do not set `TRUST_PROXY_HEADERS=1` unless the host is behind a proxy whose client-IP headers you control.

Retained HTTP access logging is opt-in. Set `ACCESS_LOG_ENABLED=1` in the deployment environment to write rotated JSON access logs to `logs/caddy/`; the default is disabled so a new deployment does not accumulate request history or consume disk unexpectedly. The default rotation keeps at most 90 compressed files of up to 100 MiB each, with a 90-day age limit. Override `ACCESS_LOG_ROLL_SIZE`, `ACCESS_LOG_ROLL_KEEP`, or `ACCESS_LOG_ROLL_KEEP_FOR` when needed. The deployment workflow passes these values from GitHub Actions secrets; leave `ACCESS_LOG_ENABLED` unset or set it to `0` for deployments that do not need retained logs.

This is a public educational demo deployment, not a production banking service. It has no user authentication, uses anonymous per-process limits, and intentionally includes vulnerable modes. Put an additional edge/WAF and shared rate-limit or budget controls in front of multi-instance deployments. The interactive lab requires a server-side Groq key and should not be exposed directly to the public internet without an HTTPS reverse proxy and provider-budget controls.

## Verification

Run the static checks and tests:

```bash
python3 scripts/validate_scenarios.py
python3 -m py_compile app.py run.py core/*.py scenarios/*/*.py scenarios/*/modes/*.py scenarios/*/tools/*.py
python3 -m unittest discover -s tests -v
node --check static/app.js && node --check static/blog.js && node --check static/theme.js && node --check static/github-callout.js
```

With the app running and Groq configured, verify one scenario or the complete live matrix:

```bash
python3 scripts/verify_matrix.py --scenario overpowered-data-tool
python3 scripts/verify_matrix.py
```

The matrix asserts the expected progression for all three presets and modes, plus an unrelated natural-language request that must produce zero database/tool access.

## Responsible disclosure

If you find a way for a Hardened path to access denied data, cross a tenant or identity boundary, replay a handoff, duplicate a protected side effect, or publish an unauthorized secret-bearing report, open an issue with the scenario, prompt, mode, run artifacts, expected boundary, and observed result. Never include real secrets or personal data.
