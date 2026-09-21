# Contributing

Thanks for helping improve Who Let the Agents Act.

## Good contributions

- Add or improve an agent-security scenario.
- Strengthen an application-enforced boundary.
- Improve the field guide, accessibility, or reproducibility.
- Add focused tests for a security property.

## Guidelines

- Use synthetic data only. Never commit secrets, credentials, or personal data.
- Keep vulnerable behavior intentional, isolated, and clearly labeled.
- Keep authorization outside the model and document the boundary being tested.
- Preserve the existing API response shape and non-technical UI.
- Run the checks in `README.md` before opening a pull request.

## Adding a scenario

Start by copying [`templates/scenario`](./templates/scenario) to `scenarios/<directory_name>`. Keep the directory name lowercase with underscores and use a stable lowercase kebab-case internal `id` in `scenario.json`. Add a title-aligned public `slug` and an `aliases` array containing any previous public names so old links continue to redirect.

Each scenario is self-contained and must include:

- `agent.py` and neutral `agent_core.py`.
- `database.py`, `schema.sql`, and `seed.sql` using synthetic data only.
- `modes/vulnerable.py`, `modes/prompt_only.py`, and `modes/hardened.py`.
- At least one explicit tool module under `tools/`.
- `planner_prompt.txt`, `prompt_guard.txt`, `hardened_response_prompt.txt`, and `unsupported_response_prompt.txt` (multi-agent scenarios may use clearly named coordinator and handoff equivalents).
- `scenario.json` for UI metadata and `article.json` for the field guide.

Keep security decisions in application code and keep the three postures easy to compare. Use `security.py` for deterministic policy or DLP when the scenario needs it. Do not share scenario databases or seed data with another scenario.

Register the new scenario in [`scenarios/registry.py`](./scenarios/registry.py). Only add routes to `app.py` when the scenario needs an API operation beyond the standard run, reset, and metadata endpoints.

Before opening a pull request:

1. Run `python3 scripts/validate_scenarios.py`.
2. Run the syntax check, unit tests, and frontend check listed in `README.md`.
3. With Groq configured, run `python3 scripts/verify_matrix.py --scenario <scenario-id>` and test at least one arbitrary unsupported request.
4. Confirm generated `_data/` and `_runs/` files remain ignored and that the article explains the attack path, prompt-only failure, hardened controls, and evidence to inspect.

For security issues, see `SECURITY.md`.
