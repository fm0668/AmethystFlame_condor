# AmethystFlame USDC AI Grid Project Memory

Date: 2026-06-01

## Workspace Roots

- `D:\AmethystFlame_HB01\AmethystFlame_condor`
- `D:\AmethystFlame_HB01\AmethystFlame_hummingbot-api`
- `D:\AmethystFlame_HB01\AmethystFlame_HB`

## Design Decision

Follow `Condor_AI网格VPS部署与代理决策规范方案-V2.md`.

Implementation order:

1. Build a Condor agent-local data loop first.
2. Move stable market data and validation services into `hummingbot-api`.
3. Keep Hummingbot Client changes non-invasive: scripts and controllers only.
4. Do not modify Hummingbot core execution code during the first phase.

## Implemented Files

Condor:

- `trading_agents/usdc_perp_ai_grid/agent.md`
- `trading_agents/usdc_perp_ai_grid/config.yml`
- `trading_agents/usdc_perp_ai_grid/rules/grid_decision_policy.md`
- `trading_agents/usdc_perp_ai_grid/rules/grid_plan_schema.json`
- `trading_agents/usdc_perp_ai_grid/routines/binance_usdc_universe.py`
- `trading_agents/usdc_perp_ai_grid/routines/collect_market_snapshot.py`
- `trading_agents/usdc_perp_ai_grid/routines/collect_perp_pressure.py`
- `trading_agents/usdc_perp_ai_grid/routines/compute_grid_features.py`
- `trading_agents/usdc_perp_ai_grid/routines/scan_usdc_universe.py`
- `trading_agents/usdc_perp_ai_grid/routines/build_grid_plan.py`
- `trading_agents/usdc_perp_ai_grid/routines/validate_grid_plan.py`
- `trading_agents/usdc_perp_ai_grid/routines/review_active_grids.py`
- `trading_agents/usdc_perp_ai_grid/routines/review_executor.py`
- `trading_agents/usdc_perp_ai_grid/routines/daily_grid_review.py`
- `trading_agents/usdc_perp_ai_grid/routines/promote_learnings.py`
- `mcp_servers/hummingbot_api/tools/usdc_ai_grid.py`
- `mcp_servers/hummingbot_api/server.py`

hummingbot-api:

- `models/usdc_perp_market.py`
- `services/usdc_perp_market_service.py`
- `routers/usdc_perp_market.py`
- `models/usdc_ai_grid.py`
- `services/usdc_ai_grid_plan_service.py`
- `routers/usdc_ai_grid.py`
- `services/grid_audit_service.py`
- `main.py`

Hummingbot Client:

- `scripts/backtest_usdc_ai_grid.py`
- `controllers/generic/ai_regime_grid.py`

## Dependency Note

`hummingbot-api/environment.yml` already includes `pydantic-settings`.

If `ModuleNotFoundError: No module named 'pydantic_settings'` appears, the active Python environment is incomplete. Activate or install the project environment before running the API.

## Deployment Intent

After code is pushed, connect to VPS by SSH and deploy the projects. The deployment will later be split across two VPS instances.

