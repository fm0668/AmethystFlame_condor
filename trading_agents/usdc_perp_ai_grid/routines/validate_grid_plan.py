from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import DATA_DIR, latest_json_file, load_config, read_json, utc_now, write_versioned_json


REQUIRED_FIELDS = {
    "connector_name",
    "trading_pair",
    "grid_mode",
    "start_price",
    "end_price",
    "total_amount_quote",
    "min_spread_between_orders",
    "max_open_orders",
    "leverage",
    "triple_barrier_config",
    "decision_reason",
    "invalidation_conditions",
}


def validate_grid_plan(plan: dict[str, Any], candidate: dict[str, Any] | None = None) -> dict[str, Any]:
    config = load_config()
    grid_config = config.get("grid", {})
    errors: list[str] = []
    warnings: list[str] = []

    missing = sorted(REQUIRED_FIELDS - set(plan))
    if missing:
        errors.append(f"missing_fields: {', '.join(missing)}")

    if plan.get("grid_mode") not in {"long_grid", "short_grid", "neutral_grid"}:
        errors.append("grid_mode must be long_grid, short_grid, or neutral_grid")

    start = plan.get("start_price")
    end = plan.get("end_price")
    if not isinstance(start, (int, float)) or start <= 0:
        errors.append("start_price must be positive")
    if not isinstance(end, (int, float)) or end <= 0:
        errors.append("end_price must be positive")
    if isinstance(start, (int, float)) and isinstance(end, (int, float)) and start == end:
        errors.append("start_price and end_price must differ")

    min_spread = plan.get("min_spread_between_orders")
    configured_min_spread = float(grid_config.get("min_spread_between_orders", 0.004))
    if not isinstance(min_spread, (int, float)) or min_spread < configured_min_spread:
        errors.append(f"min_spread_between_orders must be >= {configured_min_spread}")

    max_open_orders = plan.get("max_open_orders")
    if not isinstance(max_open_orders, int) or max_open_orders < 2:
        errors.append("max_open_orders must be an integer >= 2")

    total_amount = plan.get("total_amount_quote")
    if not isinstance(total_amount, (int, float)) or total_amount <= 0:
        errors.append("total_amount_quote must be positive")

    if candidate:
        if not candidate.get("tradable"):
            warnings.append("source candidate is not marked tradable")
        trading_rule = candidate.get("trading_rule") or {}
        min_notional = trading_rule.get("min_notional_size") or trading_rule.get("min_order_value") or 0
        try:
            min_order_quote = float(min_notional) * 1.2
        except (TypeError, ValueError):
            min_order_quote = 0
        if total_amount and max_open_orders and min_order_quote:
            per_order = total_amount / max_open_orders
            if per_order < min_order_quote:
                errors.append(f"per order quote amount {per_order:.4f} is below min notional buffer {min_order_quote:.4f}")
        if candidate.get("market_alerts"):
            warnings.append(f"candidate alerts: {', '.join(candidate['market_alerts'])}")

    return {
        "created_at": utc_now(),
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "plan": plan,
    }


def _find_candidate(plan: dict[str, Any]) -> dict[str, Any] | None:
    try:
        candidates = read_json(latest_json_file(DATA_DIR / "candidates")).get("candidates", [])
    except FileNotFoundError:
        return None
    for candidate in candidates:
        if candidate.get("trading_pair") == plan.get("trading_pair"):
            return candidate
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a USDC perpetual AI grid plan.")
    parser.add_argument("--plan")
    args = parser.parse_args()
    plan_path = Path(args.plan) if args.plan else latest_json_file(DATA_DIR / "grid_plans")
    plan = read_json(plan_path)
    result = validate_grid_plan(plan, _find_candidate(plan))
    output_path = write_versioned_json(DATA_DIR / "validation", result)
    print(output_path)
    if not result["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
