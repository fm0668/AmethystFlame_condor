from __future__ import annotations

import argparse
import asyncio
from typing import Any

from common import DATA_DIR, HummingbotAPI, load_config, utc_now, write_versioned_json


async def review_active_grids() -> dict[str, Any]:
    config = load_config()
    api_config = config["api"]
    async with HummingbotAPI(api_config["url"], api_config["username"], api_config["password"]) as api:
        try:
            executors = await api.post(
                "/executors/search",
                {"executor_types": ["grid_executor"], "status": "RUNNING", "limit": 100},
            )
        except Exception as exc:
            executors = {"error": str(exc), "data": []}

    return {
        "created_at": utc_now(),
        "active_grid_executors": executors.get("data", executors if isinstance(executors, list) else []),
        "errors": [executors["error"]] if isinstance(executors, dict) and executors.get("error") else [],
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Review currently active grid executors.")
    parser.parse_args()
    payload = await review_active_grids()
    output_path = write_versioned_json(DATA_DIR / "reviews" / "executors", payload)
    print(output_path)


if __name__ == "__main__":
    asyncio.run(main())

