"""Autonomous tick loop: snapshot -> brain decides -> guardrail -> execute -> log.

No human approval anywhere. The only thing between the brain and the chain is the guardrail
(local) plus the execution layer's own policy gate (server). The loop honours the shared
runtime state, so the chat layer can pause it or adjust caps live.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from agent import ledger, runtime
from agent.brain.base import Brain
from agent.brain.factory import make_brain
from agent.data.price_feed import build_snapshot
from agent.execution.backend import ExecutionBackend
from agent.execution.executor import Executor
from agent.execution.factory import make_backend
from agent.guardrail.policy import Guardrail

CFG_PATH = Path(__file__).resolve().parent.parent / "config" / "strategy.json"
STRATEGY_CFG = json.loads(CFG_PATH.read_text())


def _effective_cfg() -> dict[str, Any]:
    """Strategy config with live overrides from runtime state merged into risk caps."""
    cfg = json.loads(json.dumps(STRATEGY_CFG))  # deep copy
    overrides = runtime.load().get("overrides", {})
    for k, v in overrides.items():
        if k in cfg["risk"]:
            cfg["risk"][k] = v
    return cfg


def _policy_summary(cfg: dict) -> dict:
    return {
        "allowed_pairs": cfg["allowed_pairs"],
        "allowed_tokens": cfg["allowed_tokens"],
        "max_single_trade_usd": cfg["risk"]["max_single_trade_usd"],
        "max_drawdown_pct": cfg["risk"]["max_drawdown_pct"],
    }


async def tick(brain: Brain, backend: ExecutionBackend, execu: Executor,
               *, portfolio_value_usd: float, drawdown_pct: float = 0.0) -> list[dict]:
    cfg = _effective_cfg()
    guard = Guardrail(cfg)
    enabled = [c for c, v in cfg["chains"].items() if v.get("enabled")]
    results: list[dict] = []
    for pair in cfg["allowed_pairs"]:
        if pair["chain"] not in enabled:
            continue
        snapshot = await build_snapshot(backend, pair["chain"], pair)
        decision = await brain.decide(snapshot, _policy_summary(cfg))
        ledger.record("decision", {"decision": decision.to_dict()})

        verdict = guard.check(
            decision, portfolio_value_usd=portfolio_value_usd,
            drawdown_pct=drawdown_pct, trades_last_hour=ledger.trades_last_hour(),
        )
        ledger.record("guardrail", {"decision": decision.to_dict(), "allowed": verdict.allowed, "reason": verdict.reason})
        step = {"decision": decision.to_dict(), "verdict": verdict.reason, "allowed": verdict.allowed}

        if verdict.allowed and decision.is_trade():
            amount = verdict.clamped_amount_usd or decision.amount_usd
            result = await execu.execute(decision, amount)
            ledger.record("executed" if result.executed else "execute_attempt",
                          {"amount_usd": amount, "result": result.detail, "error": result.error})
            step["execution"] = result.detail
        results.append(step)
    return results


async def run_forever() -> None:
    brain = make_brain()
    mode = _effective_cfg().get("mode", "mock")
    backend = make_backend(mode)
    execu = Executor(backend, mode=mode, default_slippage_bps=STRATEGY_CFG["risk"]["default_slippage_bps"])
    interval = STRATEGY_CFG["loop"]["tick_seconds"]
    while True:
        state = runtime.load()
        if state.get("paused"):
            ledger.record("paused", {})
        else:
            try:
                await tick(brain, backend, execu, portfolio_value_usd=state["portfolio_value_usd"])
            except Exception as e:
                ledger.record("tick_error", {"error": str(e)})
        await asyncio.sleep(interval)


if __name__ == "__main__":
    asyncio.run(run_forever())
