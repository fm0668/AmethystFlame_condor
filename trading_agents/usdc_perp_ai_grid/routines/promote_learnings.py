from __future__ import annotations

import argparse
from pathlib import Path

from common import AGENT_DIR


def promote_learnings() -> Path:
    output_path = AGENT_DIR / "learning_candidates.md"
    review_dir = AGENT_DIR / "reviews" / "daily"
    lines = [
        "# Learning Candidates",
        "",
        "Review these manually before promoting anything into learnings.md or the decision policy.",
        "",
    ]
    for review in sorted(review_dir.glob("*.md"))[-14:]:
        text = review.read_text(encoding="utf-8")
        if "## Candidate Learnings" in text:
            lines.append(f"## {review.stem}")
            lines.append("")
            lines.append("Extract repeated, testable patterns from this review.")
            lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect manually reviewable learning candidates.")
    parser.parse_args()
    print(promote_learnings())


if __name__ == "__main__":
    main()

