from __future__ import annotations

import argparse
import asyncio
from typing import Any

import aiohttp

from common import BINANCE_FAPI_URL, DATA_DIR, binance_symbol_to_hb_pair, fetch_json, load_config, safe_float, write_versioned_json


async def discover_usdc_perp_universe(
    quote_asset: str = "USDC",
    max_pairs: int = 32,
    min_24h_quote_volume: float = 0,
) -> dict[str, Any]:
    async with aiohttp.ClientSession() as session:
        exchange_info, tickers = await asyncio.gather(
            fetch_json(session, f"{BINANCE_FAPI_URL}/fapi/v1/exchangeInfo"),
            fetch_json(session, f"{BINANCE_FAPI_URL}/fapi/v1/ticker/24hr"),
        )

    ticker_by_symbol = {item["symbol"]: item for item in tickers}
    markets: list[dict[str, Any]] = []
    for symbol_info in exchange_info.get("symbols", []):
        if symbol_info.get("quoteAsset") != quote_asset:
            continue
        if symbol_info.get("contractType") != "PERPETUAL":
            continue
        if symbol_info.get("status") != "TRADING":
            continue

        symbol = symbol_info["symbol"]
        ticker = ticker_by_symbol.get(symbol, {})
        quote_volume = safe_float(ticker.get("quoteVolume"), 0) or 0
        if quote_volume < min_24h_quote_volume:
            continue

        markets.append(
            {
                "symbol": symbol,
                "trading_pair": binance_symbol_to_hb_pair(symbol, quote_asset),
                "base_asset": symbol_info.get("baseAsset"),
                "quote_asset": quote_asset,
                "contract_type": symbol_info.get("contractType"),
                "status": symbol_info.get("status"),
                "onboard_date": symbol_info.get("onboardDate"),
                "price_change_pct_24h": safe_float(ticker.get("priceChangePercent")),
                "quote_volume_24h": quote_volume,
                "last_price": safe_float(ticker.get("lastPrice")),
            }
        )

    markets.sort(key=lambda item: item.get("quote_volume_24h") or 0, reverse=True)
    selected = markets[:max_pairs]
    return {
        "source": "binance_fapi",
        "quote_asset": quote_asset,
        "max_pairs": max_pairs,
        "min_24h_quote_volume": min_24h_quote_volume,
        "count": len(selected),
        "trading_pairs": [item["trading_pair"] for item in selected],
        "markets": selected,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Discover Binance USDC perpetual universe.")
    parser.add_argument("--max-pairs", type=int)
    parser.add_argument("--min-24h-quote-volume", type=float)
    args = parser.parse_args()

    config = load_config()
    payload = await discover_usdc_perp_universe(
        quote_asset=config.get("quote_asset", "USDC"),
        max_pairs=args.max_pairs or int(config.get("max_pairs", 32)),
        min_24h_quote_volume=(
            args.min_24h_quote_volume
            if args.min_24h_quote_volume is not None
            else float(config.get("scan", {}).get("min_24h_quote_volume", 0))
        ),
    )
    output_path = write_versioned_json(DATA_DIR / "universe", payload)
    print(output_path)


if __name__ == "__main__":
    asyncio.run(main())

