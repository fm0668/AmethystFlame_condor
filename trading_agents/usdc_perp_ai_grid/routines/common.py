from __future__ import annotations

import asyncio
import json
import math
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import aiohttp
import yaml


AGENT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = AGENT_DIR / "data"
CONFIG_PATH = AGENT_DIR / "config.yml"
BINANCE_FAPI_URL = "https://fapi.binance.com"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ensure_data_dirs() -> None:
    for child in [
        "universe",
        "market_snapshots",
        "perp_pressure",
        "perp_pressure/history",
        "candidates",
        "grid_plans",
        "validation",
        "reviews/daily",
        "reviews/executors",
    ]:
        (DATA_DIR / child).mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) if CONFIG_PATH.exists() else {}
    data.setdefault("connector_name", "binance_perpetual")
    data.setdefault("quote_asset", "USDC")
    data.setdefault("max_pairs", 32)
    data.setdefault("api", {})
    data["api"]["url"] = os.getenv("HUMMINGBOT_API_URL", data["api"].get("url", "http://localhost:8000"))
    data["api"]["username"] = os.getenv("HUMMINGBOT_API_USERNAME", data["api"].get("username", "admin"))
    data["api"]["password"] = os.getenv("HUMMINGBOT_API_PASSWORD", data["api"].get("password", "admin"))
    return data


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_json_file(directory: Path) -> Path:
    latest = directory / "latest.json"
    if latest.exists():
        return latest
    files = sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError(f"No JSON files found in {directory}")
    return files[0]


def write_versioned_json(directory: Path, payload: Any) -> Path:
    ensure_data_dirs()
    output_path = directory / f"{timestamp_slug()}.json"
    write_json(output_path, payload)
    write_json(directory / "latest.json", payload)
    return output_path


def hb_pair_to_binance_symbol(trading_pair: str) -> str:
    return trading_pair.replace("-", "").upper()


def binance_symbol_to_hb_pair(symbol: str, quote_asset: str = "USDC") -> str:
    symbol = symbol.upper()
    quote_asset = quote_asset.upper()
    if not symbol.endswith(quote_asset):
        raise ValueError(f"{symbol} does not end with {quote_asset}")
    return f"{symbol[:-len(quote_asset)]}-{quote_asset}"


def safe_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def pct_change(new: float | None, old: float | None) -> float | None:
    if new is None or old in (None, 0):
        return None
    return (new - old) / old * 100


def zscore(value: float | None, values: list[float]) -> float | None:
    clean_values = [v for v in values if v is not None and not math.isnan(v)]
    if value is None or len(clean_values) < 5:
        return None
    stdev = statistics.pstdev(clean_values)
    if stdev == 0:
        return 0.0
    return (value - statistics.mean(clean_values)) / stdev


async def fetch_json(session: aiohttp.ClientSession, url: str, **kwargs: Any) -> Any:
    async with session.get(url, **kwargs) as response:
        text = await response.text()
        if response.status >= 400:
            raise RuntimeError(f"GET {url} failed with {response.status}: {text[:300]}")
        return json.loads(text)


class HummingbotAPI:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.auth = aiohttp.BasicAuth(username, password)
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "HummingbotAPI":
        self.session = aiohttp.ClientSession(auth=self.auth, timeout=aiohttp.ClientTimeout(total=60))
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self.session:
            await self.session.close()

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        assert self.session is not None
        url = f"{self.base_url}{path}"
        if params:
            params = {k: v for k, v in params.items() if v is not None}
            url = f"{url}?{urlencode(params, doseq=True)}"
        async with self.session.get(url) as response:
            return await self._decode_response("GET", url, response)

    async def post(self, path: str, payload: dict[str, Any]) -> Any:
        assert self.session is not None
        url = f"{self.base_url}{path}"
        async with self.session.post(url, json=payload) as response:
            return await self._decode_response("POST", url, response)

    async def _decode_response(self, method: str, url: str, response: aiohttp.ClientResponse) -> Any:
        text = await response.text()
        if response.status >= 400:
            raise RuntimeError(f"{method} {url} failed with {response.status}: {text[:500]}")
        if not text:
            return None
        return json.loads(text)


async def gather_limited(limit: int, coros: list[Any]) -> list[Any]:
    semaphore = asyncio.Semaphore(limit)

    async def run(coro: Any) -> Any:
        async with semaphore:
            return await coro

    return await asyncio.gather(*(run(coro) for coro in coros))


def candle_close(candle: dict[str, Any]) -> float | None:
    return safe_float(candle.get("close"))


def candle_high(candle: dict[str, Any]) -> float | None:
    return safe_float(candle.get("high"))


def candle_low(candle: dict[str, Any]) -> float | None:
    return safe_float(candle.get("low"))


def candle_volume(candle: dict[str, Any]) -> float | None:
    return safe_float(candle.get("volume") or candle.get("quote_asset_volume"))


def now_ts() -> float:
    return time.time()

