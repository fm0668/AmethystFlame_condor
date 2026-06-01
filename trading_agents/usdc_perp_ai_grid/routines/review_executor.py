from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any

from common import AGENT_DIR, HummingbotAPI, load_config, utc_now


def _render_review(executor_id: str, executor: dict[str, Any]) -> str:
    return f"""# Executor Review

Executor ID: {executor_id}
Generated At: {utc_now()}

## Result

- Status: {executor.get("status", "unknown")}
- Trading Pair: {executor.get("trading_pair", "unknown")}
- Net PnL: {executor.get("net_pnl_quote", executor.get("pnl", "unknown"))}
- Fees: {executor.get("fees", "unknown")}
- Funding: {executor.get("funding", "unknown")}

## Decision Review

- Pair selection:
- Direction selection:
- Boundary quality:
- Step quality:
- Exit quality:

## What Worked

## What Failed

## Rule Candidate

## Do Not Promote Yet
"""


async def review_executor(executor_id: str) -> Path:
    config = load_config()
    api_config = config["api"]
    async with HummingbotAPI(api_config["url"], api_config["username"], api_config["password"]) as api:
        try:
            executor = await api.get(f"/executors/{executor_id}")
        except Exception as exc:
            executor = {"status": "error", "error": str(exc)}

    output_dir = AGENT_DIR / "reviews" / "executors"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{executor_id}.md"
    output_path.write_text(_render_review(executor_id, executor), encoding="utf-8")
    return output_path


async def main() -> None:
    parser = argparse.ArgumentParser(description="Create a markdown review for one executor.")
    parser.add_argument("executor_id")
    args = parser.parse_args()
    print(await review_executor(args.executor_id))


if __name__ == "__main__":
    asyncio.run(main())

