"""Validate the file and metadata contract shared by all scenarios."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REQUIRED_FILES = {
    "__init__.py",
    "agent.py",
    "agent_core.py",
    "database.py",
    "schema.sql",
    "seed.sql",
    "scenario.json",
    "article.json",
    "hardened_response_prompt.txt",
    "unsupported_response_prompt.txt",
    "modes/__init__.py",
    "modes/vulnerable.py",
    "modes/prompt_only.py",
    "modes/hardened.py",
    "tools/__init__.py",
}
ALTERNATE_FILES = {
    "planner_prompt.txt": "coordinator_prompt.txt",
    "prompt_guard.txt": "handoff_guard_prompt.txt",
}
ARTICLE_KEYS = {
    "dek",
    "threat_model",
    "attack_path",
    "prompt_only_failure",
    "hardened_controls",
    "observe",
    "engineering_notes",
}
SCENARIO_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate(root: Path) -> list[str]:
    scenarios_root = root / "scenarios"
    errors: list[str] = []
    seen_ids: set[str] = set()
    scenario_dirs = sorted(path.parent for path in scenarios_root.glob("*/scenario.json"))

    if not scenario_dirs:
        return ["scenarios/: no scenario.json files found"]

    for scenario_dir in scenario_dirs:
        label = scenario_dir.relative_to(root).as_posix()
        for relative_path in sorted(REQUIRED_FILES):
            if not (scenario_dir / relative_path).is_file():
                errors.append(f"{label}: missing {relative_path}")
        for primary, alternate in ALTERNATE_FILES.items():
            if not (scenario_dir / primary).is_file() and not (scenario_dir / alternate).is_file():
                errors.append(f"{label}: missing {primary} (or scenario-specific {alternate})")

        try:
            config = json.loads((scenario_dir / "scenario.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{label}: invalid scenario.json ({exc})")
            continue

        scenario_id = config.get("id")
        if not isinstance(scenario_id, str) or not SCENARIO_ID.fullmatch(scenario_id):
            errors.append(f"{label}: id must be lowercase kebab-case")
        elif scenario_id in seen_ids:
            errors.append(f"{label}: duplicate scenario id {scenario_id}")
        else:
            seen_ids.add(scenario_id)

        for key in ("id", "title", "number", "prompts"):
            if key not in config:
                errors.append(f"{label}: scenario.json missing {key}")
        if isinstance(config.get("prompts"), dict) and not config["prompts"]:
            errors.append(f"{label}: scenario.json prompts must not be empty")

        try:
            article = json.loads((scenario_dir / "article.json").read_text(encoding="utf-8"))
            missing_article_keys = ARTICLE_KEYS - article.keys()
            for key in sorted(missing_article_keys):
                errors.append(f"{label}: article.json missing {key}")
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{label}: invalid article.json ({exc})")

        tool_files = [path for path in (scenario_dir / "tools").glob("*.py") if path.name != "__init__.py"]
        if not tool_files:
            errors.append(f"{label}: tools/ must contain at least one tool module")

    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = validate(root)
    if errors:
        print("Scenario structure validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"Scenario structure validation passed ({len(list((root / 'scenarios').glob('*/scenario.json')))} scenarios).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
