#!/usr/bin/env python3
"""Create static visual cards from verified synthetic live scenario runs."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# These are the representative Vulnerable/Hardened attack runs from the live lab
# review. Runtime run directories remain ignored; the exported cards preserve
# the run ID and response evidence without requiring Groq at page-load time.
CAPTURES = {
    "approval_service_outage": {
        "vulnerable": "20260912T134930-effaa8c0",
        "hardened": "20260912T134932-3d803c53",
        "title": "Approval Service Outage",
        "boundary": "timeout must never become approval",
    },
    "business_rule": {
        "vulnerable": "20260912T134941-cc9b221d",
        "hardened": "20260912T134943-a39186aa",
        "title": "Refund Limit Bypass",
        "boundary": "the cumulative limit belongs at the tool boundary",
    },
    "cross_customer_access": {
        "vulnerable": "20260912T135035-1d1f9edb",
        "hardened": "20260912T135044-13312632",
        "title": "Cross-Account Access",
        "boundary": "the authenticated customer must bind the object",
    },
    "indirect_injection": {
        "vulnerable": "20260912T135146-c3ba8cdb",
        "hardened": "20260912T135212-5eb1c1e7",
        "title": "Poisoned Invoice Instructions",
        "boundary": "document text is evidence, not payment authority",
    },
    "multi_agent_confused_deputy": {
        "vulnerable": "20260912T135401-75242998",
        "hardened": "20260912T135418-e0a17e0b",
        "title": "Confused Deputy Agent Chain",
        "boundary": "the final receiver must reauthorize action and target",
    },
    "overpowered_data_tool": {
        "vulnerable": "20260912T135550-96120d25",
        "hardened": "20260912T135559-28cfc499",
        "title": "Overpowered Data Tool",
        "boundary": "application projection must precede SQLite access",
    },
    "rag_tenant_isolation": {
        "vulnerable": "20260912T135653-52511361",
        "hardened": "20260912T135700-0891c21e",
        "title": "Multi-tenant RAG Leakage",
        "boundary": "tenant eligibility must precede similarity ranking",
    },
    "secret_leakage": {
        "vulnerable": "20260912T135746-6d5bb133",
        "hardened": "20260912T135759-738ed758",
        "title": "Secret Leakage Through Debugging",
        "boundary": "secrets must be excluded before model context",
    },
    "signed_handoff": {
        "vulnerable": "20260912T135912-2a060dd8",
        "hardened": "20260912T140155-99773922",
        "title": "Unsafe Agent Handoff",
        "boundary": "delegation must be typed, signed, and receiver-scoped",
    },
}


def read_run(scenario_dir: Path, run_id: str) -> dict[str, object]:
    path = scenario_dir / "_runs" / run_id / "response.json"
    if not path.is_file():
        raise SystemExit(f"Missing live run artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def safe_response(response: object) -> list[str]:
    text = str(response or "").replace("\\n", "\n")
    text = re.sub(r'("(?:card_number|cvv|password_reset_token|environment_secret|api_key|token)"\s*:\s*)"[^"]+"', r'\1"[synthetic sensitive value]"', text, flags=re.I)
    text = re.sub(r'([\w.+-]+@[\w.-]+\.[A-Za-z]{2,})', "[synthetic contact]", text)
    text = re.sub(r'\+?\d[\d -]{8,}\d', "[synthetic identifier]", text)
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        lines.append(line[:92] + ("…" if len(line) > 92 else ""))
        if len(lines) == 8:
            break
    return lines or ["[response body not available]"]


def svg_card(config: dict[str, str], posture: str, run: dict[str, object]) -> str:
    exposed = posture == "vulnerable"
    accent = "#d84d3d" if exposed else "#5f9b72"
    verdict = "EXPOSED" if exposed else "CONTAINED"
    run_id = str(run.get("run_id", "unknown"))
    summary = str(run.get("summary", ""))
    lines = safe_response(run.get("response"))
    response_text = "\n".join(lines)
    escaped_lines = "\n".join(
        f'<text x="112" y="{350 + index * 34}" fill="#f3f1ea" font-family="monospace" font-size="19">{html.escape(line)}</text>'
        for index, line in enumerate(lines)
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="900" viewBox="0 0 1440 900" role="img" aria-labelledby="title desc">
  <title id="title">Live {html.escape(posture)} response from the {html.escape(config["title"])} lab</title>
  <desc id="desc">A verified synthetic live run shows the {html.escape(posture)} posture and its security boundary.</desc>
  <rect width="1440" height="900" fill="#f3f1ea"/>
  <rect x="44" y="38" width="1352" height="824" rx="4" fill="#252620"/>
  <text x="78" y="86" fill="#f3f1ea" font-family="monospace" font-size="18" letter-spacing="3">WHO LET THE AGENTS ACT / LIVE LAB CAPTURE</text>
  <rect x="1150" y="58" width="210" height="42" rx="2" fill="{accent}"/>
  <text x="1255" y="85" text-anchor="middle" fill="#fff" font-family="monospace" font-size="16" font-weight="700">{verdict}</text>
  <text x="78" y="148" fill="#bbbdb3" font-family="monospace" font-size="15" letter-spacing="2">SCENARIO</text>
  <text x="78" y="184" fill="#f3f1ea" font-family="sans-serif" font-size="27" font-weight="700">{html.escape(config["title"])} · {html.escape(posture.title())}</text>
  <text x="78" y="224" fill="#bbbdb3" font-family="monospace" font-size="15" letter-spacing="2">VERIFIED RUN</text>
  <text x="78" y="258" fill="#f3f1ea" font-family="monospace" font-size="20">{html.escape(run_id)}</text>
  <line x1="78" y1="286" x2="1362" y2="286" stroke="#55574e"/>
  <text x="78" y="326" fill="{accent}" font-family="monospace" font-size="16" letter-spacing="2">OBSERVED RESPONSE</text>
  <text x="78" y="350" fill="#f3f1ea" font-family="monospace" font-size="19">{{</text>
  {escaped_lines}
  <text x="78" y="634" fill="#f3f1ea" font-family="monospace" font-size="19">}}</text>
  <rect x="78" y="674" width="1284" height="128" rx="2" fill="#33342d"/>
  <text x="108" y="714" fill="{accent}" font-family="monospace" font-size="16" letter-spacing="2">WHAT THIS PROVES</text>
  <text x="108" y="750" fill="#f3f1ea" font-family="sans-serif" font-size="21">{html.escape(summary[:112])}</text>
  <text x="108" y="782" fill="#bbbdb3" font-family="sans-serif" font-size="18">Boundary under test: {html.escape(config["boundary"])}.</text>
</svg>
'''


def main() -> None:
    for scenario_id, config in CAPTURES.items():
        scenario_dir = ROOT / "scenarios" / scenario_id
        screenshots_dir = scenario_dir / "screenshots"
        screenshots_dir.mkdir(exist_ok=True)
        article_path = scenario_dir / "article.json"
        article = json.loads(article_path.read_text(encoding="utf-8"))
        entries = []
        for posture in ("vulnerable", "hardened"):
            run = read_run(scenario_dir, config[posture])
            filename = f"live-{posture}-response.svg"
            (screenshots_dir / filename).write_text(svg_card(config, posture, run), encoding="utf-8")
            entries.append({
                "src": filename,
                "alt": f"Live {posture} lab response for {config['title']}",
                "caption": f"Live capture · {posture.title()} posture",
                "note": str(run.get("summary", "Verified synthetic run.")),
            })
        article["screenshots"] = entries
        article_path.write_text(json.dumps(article, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (screenshots_dir / "README.md").write_text(
            f"# {config['title']} captures\n\n"
            "These cards are derived from verified local runs with synthetic lab data. "
            "Sensitive values are redacted in the visual card where appropriate.\n\n"
            f"- Vulnerable run: `{config['vulnerable']}`\n"
            f"- Hardened run: `{config['hardened']}`\n",
            encoding="utf-8",
        )
        print(f"{scenario_id}: generated two captures")


if __name__ == "__main__":
    main()
