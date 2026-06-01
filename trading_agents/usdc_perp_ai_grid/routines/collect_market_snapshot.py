from __future__ import annotations

import argparse
import asyncio
from typing import Any

from common import DATA_DIR, HummingbotAPI, gather_limited, latest_json_file, load_config, read_json, utc_now, write_versioned_json


async def _safe_call(label: str, coro: Any) -> dict[str, Any]:
    try:
        return {"ok": True, "data": await coro}
    except Exception as exc:
        return {"ok": False, "error": f"{label}: {exc}"}


async def collect_market_snapshot(
    trading_pairs: list[str] | None = None,
    connector_name: str | None = None,
    interval: str | None = None,
    max_records: int | None = None,
    order_book_depth: int | None = None,
) -> dict[str, Any]:
    config = load_config()
    api_config = config["api"]
    connector = connector_name or config.get("connector_name", "binance_perpetual")
    scan_config = config.get("scan", {})
    interval = interval or scan_config.get("candles_interval", "1h")
    max_records = max_records or int(scan_config.get("candles_records", 72))
    order_book_depth = order_book_depth or int(scan_config.get("order_book_depth", 100))
    concurrency = int(scan_config.get("max_concurrency", 4))

    if trading_pairs is None:
        universe = read_json(latest_json_file(DATA_DIR / "universe"))
        trading_pairs = universe["trading_pairs"]

    snapshot: dict[str, Any] = {
        "source": "hummingbot_api",
        "created_at": utc_now(),
        "connector_name": connector,
        "interval": interval,
        "max_records": max_records,
        "order_book_depth": order_book_depth,
        "trading_pairs": trading_pairs,
        "markets": {},
        "errors": {},
    }

    async with HummingbotAPI(api_config["url"], api_config["username"], api_config["password"]) as api:
        prices_result = await _safe_call(
            "prices",
            api.post("/market-data/prices", {"connector_name": connector, "trading_pairs": trading_pairs}),
        )
        trading_rules_result = await _safe_call(
            "trading_rules",
            api.get(f"/connectors/{connector}/trading-rules", {"trading_pairs": trading_pairs}),
        )

        if prices_result["ok"]:
            prices = prices_result["data"].get("prices", prices_result["data"])
        else:
            prices = {}
            snapshot["errors"]["prices"] = prices_result["error"]

        if trading_rules_result["ok"]:
            trading_rules = trading_rules_result["data"]
        else:
            trading_rules = {}
            snapshot["errors"]["trading_rules"] = trading_rules_result["error"]

        async def collect_pair(pair: str) -> tuple[str, dict[str, Any]]:
            candles, order_book, funding = await asyncio.gather(
                _safe_call(
                    f"{pair} candles",
                    api.post(
                        "/market-data/candles",
                        {
                            "connector_name": connector,
                            "trading_pair": pair,
                            "interval": interval,
                            "max_records": max_records,
                        },
                    ),
                ),
                _safe_call(
                    f"{pair} order_book",
                    api.post(
                        "/market-data/order-book",
                        {"connector_name": connector, "trading_pair": pair, "depth": order_book_depth},
                    ),
                ),
                _safe_call(
                    f"{pair} funding",
                    api.post("/market-data/funding-info", {"connector_name": connector, "trading_pair": pair}),
                ),
            )
            pair_payload = {
                "trading_pair": pair,
                "price": prices.get(pair),
                "trading_rule": trading_rules.get(pair),
                "candles": candles.get("data") if candles["ok"] else None,
                "order_book": order_book.get("data") if order_book["ok"] else None,
                "funding_info": funding.get("data") if funding["ok"] else None,
                "errors": [r["error"] for r in [candles, order_book, funding] if not r["ok"]],
            }
            return pair, pair_payload

        results = await gather_limited(concurrency, [collect_pair(pair) for pair in trading_pairs])
        snapshot["markets"] = {pair: payload for pair, payload in results}

    return snapshot


async def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Hummingbot market snapshot for USDC perpetual pairs.")
    parser.add_argument("--pairs", nargs="*")
    args = parser.parse_args()
    payload = await collect_market_snapshot(trading_pairs=args.pairs or None)
    output_path = write_versioned_json(DATA_DIR / "market_snapshots", payload)
    print(output_path)


if __name__ == "__main__":
    asyncio.run(main())

