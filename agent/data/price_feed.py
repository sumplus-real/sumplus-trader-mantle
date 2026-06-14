"""Market snapshot for the brain.

Two sources, both honest:
  - CMC spot prices for context (trend / 24h change).
  - A live on-chain quote from Maria.get_quote for the actual executable price on the target
    DEX (this is the price the agent would really get, fees + slippage included).
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from agent.execution.maria_client import MariaClient


async def cmc_prices(symbols: list[str]) -> dict[str, Any]:
    api_key = os.environ.get("CMC_API_KEY", "")
    if not api_key:
        return {"_note": "CMC_API_KEY not set; spot prices unavailable"}
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(url, headers={"X-CMC_PRO_API_KEY": api_key},
                        params={"symbol": ",".join(symbols)})
    r.raise_for_status()
    data = r.json().get("data", {})
    out = {}
    for s in symbols:
        q = (data.get(s, {}) or {}).get("quote", {}).get("USD", {})
        out[s] = {"price": q.get("price"), "pct_24h": q.get("percent_change_24h")}
    return out


async def build_snapshot(maria: MariaClient, chain: str, pair: dict, probe_amount: str = "10") -> dict[str, Any]:
    """pair = {'from': 'USDC', 'to': 'MNT'}. Returns a snapshot dict for the brain."""
    snapshot: dict[str, Any] = {"chain": chain, "pair": pair}
    snapshot["spot"] = await cmc_prices(sorted({pair["from"], pair["to"]}))
    try:
        snapshot["live_quote"] = await maria.get_quote(
            chain=chain, from_token=pair["from"], to_token=pair["to"], amount=probe_amount,
        )
    except Exception as e:  # quote failures must not crash the loop
        snapshot["live_quote"] = {"error": str(e)}
    return snapshot
