from __future__ import annotations

import argparse
import asyncio

from binance_usdc_universe import discover_usdc_perp_universe
from collect_market_snapshot import collect_market_snapshot
from collect_perp_pressure import collect_perp_pressure
from common import DATA_DIR, load_config, write_versioned_json
from compute_grid_features import compute_grid_features


async def scan_usdc_universe() -> dict:
    config = load_config()
    universe = await discover_usdc_perp_universe(
        quote_asset=config.get("quote_asset", "USDC"),
        max_pairs=int(config.get("max_pairs", 32)),
        min_24h_quote_volume=float(config.get("scan", {}).get("min_24h_quote_volume", 0)),
    )
    write_versioned_json(DATA_DIR / "universe", universe)
    snapshot = await collect_market_snapshot(trading_pairs=universe["trading_pairs"])
    write_versioned_json(DATA_DIR / "market_snapshots", snapshot)
    pressure = await collect_perp_pressure(trading_pairs=universe["trading_pairs"])
    write_versioned_json(DATA_DIR / "perp_pressure", pressure)
    candidates = compute_grid_features()
    write_versioned_json(DATA_DIR / "candidates", candidates)
    return {
        "universe_count": universe["count"],
        "candidate_count": len(candidates.get("candidates", [])),
        "top_candidates": candidates.get("candidates", [])[:5],
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full USDC perpetual market scan.")
    parser.parse_args()
    result = await scan_usdc_universe()
    print(result)


if __name__ == "__main__":
    asyncio.run(main())

