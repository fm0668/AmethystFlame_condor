# USDC Perpetual AI Grid Decision Policy

## Preconditions

Before creating a grid executor, the agent must have:

- A fresh universe file from `binance_usdc_universe.py`.
- A fresh market snapshot from `collect_market_snapshot.py`.
- A fresh contract pressure file from `collect_perp_pressure.py`.
- Candidate features from `compute_grid_features.py`.
- A grid plan that passes `validate_grid_plan.py`.

If any item is missing, stale, or contains errors for the target pair, the agent must reject the trade.

## No-Trade Conditions

Do not create a new grid when any of these are true:

- Market data is missing or older than the configured freshness window.
- Spread is above the configured threshold.
- `depth_50bps_quote` is below the configured threshold.
- The proposed grid step is not wide enough to cover fees, slippage, and safety margin.
- Funding, basis, or open interest is extremely crowded in the same direction as the plan.
- Price has just broken a key boundary and has not formed a new stable range.
- The same pair already has an active grid and no replacement decision was made.
- Daily loss or exposure limits have already been reached.

## Grid Type

Long grid:

- Use only when the market is range-bound near the lower part of the range or in a controlled uptrend.
- Funding and OI must not show extreme long crowding.

Short grid:

- Use only when the market is range-bound near the upper part of the range or in a controlled downtrend.
- Funding and OI must not show extreme short crowding.

Neutral grid:

- Use only when range quality is acceptable, trend strength is limited, and funding, basis, and OI are not extreme.

## Output

The agent must output a JSON grid plan. Natural-language-only recommendations are not valid.

The plan must explain:

- Why the pair was selected.
- Why the grid direction was selected.
- Why the boundaries are reasonable.
- Why the step is wide enough.
- Which conditions invalidate the plan.

