from __future__ import annotations

import argparse
import math
import statistics
from typing import Any

from common import (
    DATA_DIR,
    candle_close,
    candle_high,
    candle_low,
    candle_volume,
    latest_json_file,
    load_config,
    read_json,
    safe_float,
    utc_now,
    write_versioned_json,
)


def _levels(order_book: dict[str, Any], side: str) -> list[dict[str, float]]:
    return [
        {"price": safe_float(item.get("price")), "amount": safe_float(item.get("amount"))}
        for item in (order_book or {}).get(side, [])
        if safe_float(item.get("price")) is not None and safe_float(item.get("amount")) is not None
    ]


def _depth_quote(levels: list[dict[str, float]], mid_price: float, bps: float, is_bid: bool) -> float:
    if mid_price <= 0:
        return 0.0
    if is_bid:
        min_price = mid_price * (1 - bps / 10000)
        selected = [level for level in levels if level["price"] >= min_price]
    else:
        max_price = mid_price * (1 + bps / 10000)
        selected = [level for level in levels if level["price"] <= max_price]
    return sum(level["price"] * level["amount"] for level in selected)


def _atr_pct(candles: list[dict[str, Any]], period: int = 14) -> float | None:
    if len(candles) < period + 1:
        return None
    true_ranges = []
    prev_close = candle_close(candles[-period - 1])
    for candle in candles[-period:]:
        high = candle_high(candle)
        low = candle_low(candle)
        close = candle_close(candle)
        if None in (high, low, prev_close):
            return None
        true_ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
        prev_close = close
    last_close = candle_close(candles[-1])
    if last_close in (None, 0):
        return None
    return statistics.mean(true_ranges) / last_close


def _realized_volatility(candles: list[dict[str, Any]]) -> float | None:
    closes = [candle_close(candle) for candle in candles if candle_close(candle)]
    if len(closes) < 12:
        return None
    returns = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes)) if closes[i - 1] > 0]
    if len(returns) < 2:
        return None
    return statistics.pstdev(returns) * math.sqrt(len(returns))


def _regime(candles: list[dict[str, Any]], atr_pct: float | None) -> tuple[str, float | None]:
    closes = [candle_close(candle) for candle in candles if candle_close(candle)]
    if len(closes) < 24:
        return "unstable", None
    change_24 = (closes[-1] - closes[-24]) / closes[-24]
    trend_strength = abs(change_24) / max(atr_pct or 0.001, 0.001)
    if trend_strength > 2.5 and change_24 > 0:
        return "uptrend", trend_strength
    if trend_strength > 2.5 and change_24 < 0:
        return "downtrend", trend_strength
    high = max(closes[-24:])
    low = min(closes[-24:])
    if high > 0 and (high - low) / closes[-1] > 0.12:
        return "breakout", trend_strength
    return "range", trend_strength


def _score_feature(feature: dict[str, Any], thresholds: dict[str, Any]) -> tuple[int, list[str], list[str]]:
    score = 100
    reasons: list[str] = []
    alerts: list[str] = []

    spread = feature.get("spread_bps")
    if spread is None:
        score -= 25
        alerts.append("missing_spread")
    elif spread > float(thresholds.get("max_spread_bps", 8)):
        score -= 30
        alerts.append("wide_spread")
    else:
        reasons.append("spread_ok")

    depth = feature.get("order_book_depth_50bps_quote") or 0
    if depth < float(thresholds.get("min_depth_50bps_quote", 50000)):
        score -= 25
        alerts.append("thin_depth_50bps")
    else:
        reasons.append("depth_ok")

    atr = feature.get("atr_pct")
    if atr is None:
        score -= 15
        alerts.append("missing_atr")
    elif atr < float(thresholds.get("min_atr_pct", 0.006)):
        score -= 10
        alerts.append("low_volatility")
    elif atr > float(thresholds.get("max_atr_pct", 0.08)):
        score -= 20
        alerts.append("high_volatility")
    else:
        reasons.append("volatility_ok")

    if feature.get("funding_alert"):
        score -= 15
        alerts.append("funding_extreme")
    if feature.get("basis_alert"):
        score -= 10
        alerts.append("basis_extreme")
    if feature.get("oi_alert"):
        score -= 10
        alerts.append("oi_extreme")
    if not any([feature.get("funding_alert"), feature.get("basis_alert"), feature.get("oi_alert")]):
        reasons.append("perp_pressure_ok")

    if feature.get("market_regime") == "unstable":
        score -= 25
        alerts.append("unstable_regime")
    elif feature.get("market_regime") == "range":
        reasons.append("range_regime")

    return max(score, 0), reasons, alerts


def compute_grid_features() -> dict[str, Any]:
    config = load_config()
    thresholds = config.get("thresholds", {})
    snapshot = read_json(latest_json_file(DATA_DIR / "market_snapshots"))
    pressure = read_json(latest_json_file(DATA_DIR / "perp_pressure"))
    pressure_markets = pressure.get("markets", {})

    payload: dict[str, Any] = {
        "created_at": utc_now(),
        "connector_name": snapshot.get("connector_name"),
        "source_snapshot": str(latest_json_file(DATA_DIR / "market_snapshots")),
        "source_pressure": str(latest_json_file(DATA_DIR / "perp_pressure")),
        "candidates": [],
    }

    for pair, market in snapshot.get("markets", {}).items():
        order_book = market.get("order_book") or {}
        bids = _levels(order_book, "bids")
        asks = _levels(order_book, "asks")
        candles = market.get("candles") or []
        pressure_item = pressure_markets.get(pair, {})

        best_bid = bids[0]["price"] if bids else None
        best_ask = asks[0]["price"] if asks else None
        mid_price = None
        spread_bps = None
        if best_bid and best_ask:
            mid_price = (best_bid + best_ask) / 2
            spread_bps = (best_ask - best_bid) / mid_price * 10000
        elif market.get("price"):
            mid_price = safe_float(market.get("price"))

        atr = _atr_pct(candles)
        realized_vol = _realized_volatility(candles)
        market_regime, trend_strength = _regime(candles, atr)
        closes = [candle_close(candle) for candle in candles if candle_close(candle)]
        highs = [candle_high(candle) for candle in candles if candle_high(candle)]
        lows = [candle_low(candle) for candle in candles if candle_low(candle)]
        volumes = [candle_volume(candle) for candle in candles if candle_volume(candle)]

        high_24h = max(highs[-24:]) if len(highs) >= 24 else (max(highs) if highs else None)
        low_24h = min(lows[-24:]) if len(lows) >= 24 else (min(lows) if lows else None)
        volume_24h = sum(volumes[-24:]) if len(volumes) >= 24 else (sum(volumes) if volumes else None)
        volume_baseline = statistics.mean(volumes[-72:-24]) if len(volumes) >= 72 else None
        volume_anomaly_ratio = volume_24h / volume_baseline if volume_24h and volume_baseline else None

        feature = {
            "trading_pair": pair,
            "price": mid_price,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread_bps": spread_bps,
            "order_book_depth_20bps_quote": (
                _depth_quote(bids, mid_price or 0, 20, True) + _depth_quote(asks, mid_price or 0, 20, False)
            ),
            "order_book_depth_50bps_quote": (
                _depth_quote(bids, mid_price or 0, 50, True) + _depth_quote(asks, mid_price or 0, 50, False)
            ),
            "atr_pct": atr,
            "realized_volatility": realized_vol,
            "market_regime": market_regime,
            "trend_strength": trend_strength,
            "high_24h": high_24h,
            "low_24h": low_24h,
            "volume_24h": volume_24h,
            "volume_anomaly_ratio": volume_anomaly_ratio,
            "funding_rate_pct": pressure_item.get("funding_rate_pct"),
            "funding_rate_zscore": pressure_item.get("funding_rate_zscore"),
            "basis_pct": pressure_item.get("basis_pct"),
            "open_interest": pressure_item.get("open_interest"),
            "open_interest_change_1h_pct": pressure_item.get("open_interest_change_1h_pct"),
            "open_interest_change_24h_pct": pressure_item.get("open_interest_change_24h_pct"),
            "funding_alert": pressure_item.get("funding_alert", False),
            "basis_alert": pressure_item.get("basis_alert", False),
            "oi_alert": pressure_item.get("oi_alert", False),
            "trading_rule": market.get("trading_rule"),
            "raw_errors": market.get("errors", []) + pressure_item.get("errors", []),
        }
        score, reasons, alerts = _score_feature(feature, thresholds)
        feature["score"] = score
        feature["reason_codes"] = reasons
        feature["market_alerts"] = alerts
        feature["tradable"] = score >= int(thresholds.get("min_score", 60)) and not market.get("errors")
        payload["candidates"].append(feature)

    payload["candidates"].sort(key=lambda item: item.get("score", 0), reverse=True)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute AI grid features from latest snapshot and pressure data.")
    parser.parse_args()
    payload = compute_grid_features()
    output_path = write_versioned_json(DATA_DIR / "candidates", payload)
    print(output_path)


if __name__ == "__main__":
    main()

