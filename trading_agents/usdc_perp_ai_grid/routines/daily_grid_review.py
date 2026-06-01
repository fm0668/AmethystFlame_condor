from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from common import AGENT_DIR, DATA_DIR, latest_json_file, read_json


def daily_grid_review(day: str | None = None) -> Path:
    review_day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    candidates = {}
    validation = {}
    try:
        candidates = read_json(latest_json_file(DATA_DIR / "candidates"))
    except FileNotFoundError:
        pass
    try:
        validation = read_json(latest_json_file(DATA_DIR / "validation"))
    except FileNotFoundError:
        pass

    top_candidates = candidates.get("candidates", [])[:10]
    lines = [
        f"# Daily AI Grid Review - {review_day}",
        "",
        "## Summary",
        "",
        f"- Candidate count: {len(candidates.get('candidates', []))}",
        f"- Last validation valid: {validation.get('valid', 'n/a')}",
        "",
        "## Top Candidates",
        "",
    ]
    for item in top_candidates:
        lines.append(
            f"- {item.get('trading_pair')}: score={item.get('score')} regime={item.get('market_regime')} "
            f"alerts={','.join(item.get('market_alerts', [])) or 'none'}"
        )
    lines.extend(
        [
            "",
            "## Best Decisions",
            "",
            "## Worst Decisions",
            "",
            "## Missed Opportunities",
            "",
            "## Bad Signals",
            "",
            "## Market Regime Notes",
            "",
            "## Candidate Learnings",
            "",
            "## Policy Change Proposals",
            "",
        ]
    )
    output_dir = AGENT_DIR / "reviews" / "daily"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{review_day}.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a daily AI grid review markdown file.")
    parser.add_argument("--day")
    args = parser.parse_args()
    print(daily_grid_review(args.day))


if __name__ == "__main__":
    main()

