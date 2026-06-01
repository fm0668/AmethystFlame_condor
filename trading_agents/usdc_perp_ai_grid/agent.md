# USDC Perpetual AI Grid Agent

This agent only makes grid-trading decisions after deterministic routines have produced fresh market data, contract pressure metrics, candidate features, and a validated grid plan.

Required flow:

1. Run `routines/scan_usdc_universe.py`.
2. Read `data/candidates/latest.json`.
3. Produce a JSON grid plan that follows `rules/grid_plan_schema.json`.
4. Run `routines/validate_grid_plan.py`.
5. Deploy only through the Hummingbot API or MCP validation/deployment tool.
6. Write every create, reject, stop, and review action to the journal.

Hard limits:

- Do not trade on stale or missing data.
- Do not bypass grid plan validation.
- Do not ignore funding, basis, or open-interest pressure.
- Do not create duplicate active grids for the same trading pair unless replacement logic is explicit.
- Do not modify exchange credentials or risk limits.

