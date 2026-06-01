from __future__ import annotations

import argparse
from typing import Any

from common import DATA_DIR, latest_json_file, load_config, read_json, utc_now, write_versioned_json


def _select_candidate(candidates: list[dict[str, Any]], trading_pair: str | None) -> dict[str, Any]:
    if trading_pair:
        for candidate in candidates:
            if candidate["trading_pair"] == trading_pair:
                return candidate
        raise ValueError(f"Candidate not found for {trading_pair}")
    for candidate in candidates:
        if candidate.get("tradable"):
            return candidate
    if candidates:
        return candidates[0]
    raise ValueError("No candidates available")


def build_grid_plan(trading_pair: str | None = None) -> dict[str, Any]:
    config = load_config()
    grid_config = config.get("grid", {})
    candidates_path = latest_json_file(DATA_DIR / "candidates")
    candidates_payload = read_json(candidates_path)
    candidate = _select_candidate(candidates_payload.get("candidates", []), trading_pair)

    price = candidate.get("price")
    if not price:
        raise ValueError(f"Candidate {candidate['trading_pair']} has no price")

    atr_pct = candidate.get("atr_pct") or 0.01
    high = candidate.get("high_24h") or price * (1 + 2 * atr_pct)
    low = candidate.get("low_24h") or price * (1 - 2 * atr_pct)
    regime = candidate.get("market_regime")

    if regime == "uptrend":
        grid_mode = "long_grid"
        start_price = max(low, price * (1 - 2.0 * atr_pct))
        end_price = min(high, price * (1 + 1.5 * atr_pct))
    elif regime == "downtrend":
        grid_mode = "short_grid"
        start_price = min(high, price * (1 + 2.0 * atr_pct))
        end_price = max(low, price * (1 - 1.5 * atr_pct))
    else:
        grid_mode = "neutral_grid"
        start_price = low
        end_price = high

    plan = {
        "connector_name": candidates_payload.get("connector_name") or config.get("connector_name", "binance_perpetual"),
        "trading_pair": candidate["trading_pair"],
        "grid_mode": grid_mode,
        "start_price": round(float(start_price), 8),
        "end_price": round(float(end_price), 8),
        "limit_price": None,
        "total_amount_quote": float(grid_config.get("total_amount_quote", 100)),
        "min_spread_between_orders": max(
            float(grid_config.get("min_spread_between_orders", 0.004)),
            min(max(atr_pct / 2, 0.003), 0.02),
        ),
        "max_open_orders": int(grid_config.get("max_open_orders", 8)),
        "leverage": int(grid_config.get("leverage", 1)),
        "triple_barrier_config": grid_config.get(
            "triple_barrier", {"stop_loss": 0.03, "take_profit": 0.02, "time_limit": 86400}
        ),
        "decision_reason": (
            f"score={candidate.get('score')}; regime={regime}; "
            f"reasons={','.join(candidate.get('reason_codes', []))}; "
            f"alerts={','.join(candidate.get('market_alerts', [])) or 'none'}"
        ),
        "invalidation_conditions": [
            "spread exceeds configured threshold",
            "depth_50bps_quote falls below configured threshold",
            "funding, basis, or open interest becomes extreme against the grid direction",
            "price breaks the planned boundary with strong volume",
        ],
        "source_candidate_file": str(candidates_path),
        "created_at": utc_now(),
    }
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a deterministic draft grid plan from candidates.")
    parser.add_argument("--pair")
    args = parser.parse_args()
    plan = build_grid_plan(args.pair)
    output_path = write_versioned_json(DATA_DIR / "grid_plans", plan)
    print(output_path)


if __name__ == "__main__":
    main()

