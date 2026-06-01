from __future__ import annotations

import argparse
import asyncio
from typing import Any

import aiohttp

from common import (
    BINANCE_FAPI_URL,
    DATA_DIR,
    fetch_json,
    hb_pair_to_binance_symbol,
    latest_json_file,
    load_config,
    pct_change,
    read_json,
    safe_float,
    now_ts,
    utc_now,
    write_json,
    write_versioned_json,
    zscore,
)


def _history_path(trading_pair: str):
    return DATA_DIR / "perp_pressure" / "history" / f"{trading_pair.replace('-', '_')}.json"


def _load_history(trading_pair: str) -> list[dict[str, Any]]:
    path = _history_path(trading_pair)
    if not path.exists():
        return []
    return read_json(path)


def _save_history(trading_pair: str, rows: list[dict[str, Any]]) -> None:
    write_json(_history_path(trading_pair), rows[-500:])


def _nearest_older(rows: list[dict[str, Any]], current_ts: float, seconds: int) -> dict[str, Any] | None:
    target = current_ts - seconds
    older = [row for row in rows if row.get("timestamp", 0) <= target]
    if not older:
        return None
    return max(older, key=lambda row: row.get("timestamp", 0))


async def collect_perp_pressure(trading_pairs: list[str] | None = None) -> dict[str, Any]:
    config = load_config()
    if trading_pairs is None:
        snapshot = read_json(latest_json_file(DATA_DIR / "market_snapshots"))
        trading_pairs = snapshot["trading_pairs"]
        snapshot_markets = snapshot.get("markets", {})
    else:
        snapshot_markets = {}

    thresholds = config.get("thresholds", {})
    now = now_ts()
    payload: dict[str, Any] = {
        "source": "hummingbot_api_plus_binance_fapi",
        "created_at": utc_now(),
        "trading_pairs": trading_pairs,
        "markets": {},
    }

    async with aiohttp.ClientSession() as session:
        for pair in trading_pairs:
            symbol = hb_pair_to_binance_symbol(pair)
            funding_info = (snapshot_markets.get(pair) or {}).get("funding_info") or {}
            result: dict[str, Any] = {"trading_pair": pair, "symbol": symbol, "errors": []}

            try:
                oi = await fetch_json(session, f"{BINANCE_FAPI_URL}/fapi/v1/openInterest", params={"symbol": symbol})
                result["open_interest"] = safe_float(oi.get("openInterest"))
                result["open_interest_time"] = oi.get("time")
            except Exception as exc:
                result["errors"].append(f"open_interest: {exc}")
                result["open_interest"] = None

            try:
                premium = await fetch_json(session, f"{BINANCE_FAPI_URL}/fapi/v1/premiumIndex", params={"symbol": symbol})
            except Exception:
                premium = {}

            mark_price = safe_float(funding_info.get("mark_price")) or safe_float(premium.get("markPrice"))
            index_price = safe_float(funding_info.get("index_price")) or safe_float(premium.get("indexPrice"))
            funding_rate = safe_float(funding_info.get("funding_rate")) or safe_float(premium.get("lastFundingRate"))

            basis_pct = None
            if mark_price is not None and index_price not in (None, 0):
                basis_pct = (mark_price - index_price) / index_price * 100

            history = _load_history(pair)
            current_row = {
                "timestamp": now,
                "created_at": payload["created_at"],
                "open_interest": result["open_interest"],
                "funding_rate": funding_rate,
                "basis_pct": basis_pct,
                "mark_price": mark_price,
                "index_price": index_price,
            }
            one_hour = _nearest_older(history, now, 3600)
            one_day = _nearest_older(history, now, 86400)
            history.append(current_row)
            _save_history(pair, history)

            result.update(current_row)
            result["funding_rate_pct"] = funding_rate * 100 if funding_rate is not None else None
            result["funding_rate_zscore"] = zscore(funding_rate, [row.get("funding_rate") for row in history])
            result["open_interest_change_1h_pct"] = pct_change(result["open_interest"], (one_hour or {}).get("open_interest"))
            result["open_interest_change_24h_pct"] = pct_change(result["open_interest"], (one_day or {}).get("open_interest"))
            result["basis_alert"] = abs(basis_pct or 0) >= float(thresholds.get("extreme_basis_pct", 0.2))
            result["funding_alert"] = abs(result["funding_rate_pct"] or 0) >= float(
                thresholds.get("extreme_funding_rate_pct", 0.03)
            )
            result["oi_alert"] = abs(result["open_interest_change_1h_pct"] or 0) >= float(
                thresholds.get("extreme_oi_change_1h_pct", 8)
            )
            payload["markets"][pair] = result

    return payload


async def main() -> None:
    parser = argparse.ArgumentParser(description="Collect USDC perpetual pressure data.")
    parser.add_argument("--pairs", nargs="*")
    args = parser.parse_args()
    payload = await collect_perp_pressure(trading_pairs=args.pairs or None)
    output_path = write_versioned_json(DATA_DIR / "perp_pressure", payload)
    print(output_path)


if __name__ == "__main__":
    asyncio.run(main())
