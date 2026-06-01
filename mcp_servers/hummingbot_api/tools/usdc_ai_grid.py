from __future__ import annotations

from typing import Any


def _api_root(client: Any) -> str:
    base_url = getattr(client.executors, "base_url")
    return base_url.rsplit("/executors", 1)[0]


async def manage_usdc_ai_grid(
    client: Any,
    action: str,
    connector_name: str = "binance_perpetual",
    trading_pairs: list[str] | None = None,
    plan: dict[str, Any] | None = None,
    candidate: dict[str, Any] | None = None,
    account_name: str = "master_account",
    controller_id: str = "usdc_ai_grid",
    dry_run: bool = True,
    max_pairs: int = 32,
    min_24h_quote_volume: float = 0,
) -> dict[str, Any]:
    root = _api_root(client)
    session = client.executors.session

    if action == "scan":
        params = {
            "connector_name": connector_name,
            "quote_asset": "USDC",
            "max_pairs": max_pairs,
            "min_24h_quote_volume": min_24h_quote_volume,
        }
        universe_resp = await session.get(f"{root}/usdc-perp-market/universe", params=params)
        universe_resp.raise_for_status()
        universe = await universe_resp.json()
        pairs = trading_pairs or universe.get("trading_pairs", [])
        candidates_resp = await session.post(
            f"{root}/usdc-perp-market/candidates",
            json={"connector_name": connector_name, "trading_pairs": pairs},
        )
        candidates_resp.raise_for_status()
        candidates = await candidates_resp.json()
        return {"action": "scan", "universe": universe, "candidates": candidates}

    if action == "validate_plan":
        if not plan:
            return {"action": action, "error": "plan is required"}
        resp = await session.post(f"{root}/usdc-ai-grid/plan/validate", json={"plan": plan, "candidate": candidate})
        resp.raise_for_status()
        return {"action": action, "result": await resp.json()}

    if action == "preview":
        if not plan:
            return {"action": action, "error": "plan is required"}
        resp = await session.post(f"{root}/usdc-ai-grid/plan/preview", json={"plan": plan, "candidate": candidate})
        resp.raise_for_status()
        return {"action": action, "result": await resp.json()}

    if action == "deploy":
        if not plan:
            return {"action": action, "error": "plan is required"}
        payload = {
            "plan": plan,
            "candidate": candidate,
            "account_name": account_name,
            "controller_id": controller_id,
            "dry_run": dry_run,
        }
        resp = await session.post(f"{root}/usdc-ai-grid/plan/deploy", json=payload)
        resp.raise_for_status()
        return {"action": action, "result": await resp.json()}

    if action == "review":
        resp = await session.post(f"{root}/usdc-ai-grid/executors/review")
        resp.raise_for_status()
        return {"action": action, "result": await resp.json()}

    return {"action": action, "error": "Unknown action. Use scan, validate_plan, preview, deploy, or review."}

