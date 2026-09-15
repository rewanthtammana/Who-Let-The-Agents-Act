# Scenario contribution template

Copy this directory to `scenarios/<directory_name>/`, replacing placeholders
with scenario-specific code and content. Use a lowercase underscore directory
name and a lowercase kebab-case `id` in `scenario.json`.

Required implementation pieces:

- `agent.py`: stable facade exposing `run(mode, prompt)`.
- `agent_core.py`: neutral model, run-artifact, and database plumbing.
- `modes/`: separate `vulnerable.py`, `prompt_only.py`, and `hardened.py`.
- `database.py`, `schema.sql`, and `seed.sql`: isolated synthetic state.
- `tools/`: explicit LangChain tools that validate arguments before access.
- Prompt files and `scenario.json`: runtime behavior and UI metadata. Multi-agent scenarios may use named coordinator and handoff prompt files instead of the standard planner and guard names.
- `article.json`: field-guide explanation of the threat and controls.

Use an existing scenario as the implementation reference. Before opening a PR,
run `python3 scripts/validate_scenarios.py`, the checks in `README.md`, and the
full live matrix when Groq is configured. Register the scenario in
`scenarios/registry.py` and add any scenario-specific API routes to `app.py`.

`security.py` is optional for simple scenarios, but deterministic policy and
output checks should live there when the scenario needs them. Never commit
`_data/`, `_runs/`, secrets, credentials, or real personal data.
