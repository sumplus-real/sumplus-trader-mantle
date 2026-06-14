"""Autonomous tick loop: snapshot -> brain decides -> guardrail -> execute -> log.

No human approval anywhere in the path. The only thing standing between the brain and the
chain is the guardrail (local) + Maria's policy gate (server). That is the whole point.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from agent.brain.deepseek_strategy import DeepSeekBrain
from agent.data.price_feed import build_snapshot
from agent.execution.executor import Executor
from agent.execution.maria_client import MariaClient
from agent.guardrail.policy import Guardrail
from agent import ledger

STRATEGY_CFG = json.loads((Path(__file__).resolve().parent.parent / "config" / "strategy.json").read_text())


def _policy_summary(cfg: dict) -> dict:
    return {
        "allowed_pairs": cfg["allowed_pairs"],
        "allowed_tokens": cfg["allowed_tokens"],
        "max_single_trade_usd": cfg["risk"]["max_single_trade_usd"],
        "max_drawdown_pct": cfg["risk"]["max_drawdown_pct"],
    }


async def tick(brain: DeepSeekBrain, maria: MariaClient, guard: Guardrail, execu: Executor,
               *, portfolio_value_usd: float, drawdown_pct: float) -> None:
    cfg = STRATEGY_CFG
    enabled = [c for c, v in cfg["chains"].items() if v.get("enabled")]
    for pair in cfg["allowed_pairs"]:
        if pair["chain"] not in enabled:
            continue
        snapshot = await build_snapshot(maria, pair["chain"], pair)
        decision = await brain.decide(snapshot, _policy_summary(cfg))
        ledger.record("decision", {"decision": decision.to_dict()})

        verdict = guard.check(
            decision, portfolio_value_usd=portfolio_value_usd,
            drawdown_pct=drawdown_pct, trades_last_hour=ledger.trades_last_hour(),
        )
        ledger.record("guardrail", {"allowed": verdict.allowed, "reason": verdict.reason})
        if not verdict.allowed or not decision.is_trade():
            continue

        amount = verdict.clamped_amount_usd or decision.amount_usd
        result = await execu.execute(decision, amount)
        ledger.record("executed" if result.executed else "execute_attempt",
                      {"amount_usd": amount, "result": result.detail, "error": result.error})


async def run_forever(portfolio_value_usd: float = 1000.0) -> None:
    brain = DeepSeekBrain()
    maria = MariaClient()
    guard = Guardrail(STRATEGY_CFG)
    execu = Executor(maria, mode=STRATEGY_CFG.get("mode", "paper"),
                     default_slippage_bps=STRATEGY_CFG["risk"]["default_slippage_bps"])
    interval = STRATEGY_CFG["loop"]["tick_seconds"]
    while True:
        try:
            await tick(brain, maria, guard, execu,
                       portfolio_value_usd=portfolio_value_usd, drawdown_pct=0.0)
        except Exception as e:  # a bad tick must not kill the agent
            ledger.record("tick_error", {"error": str(e)})
        await asyncio.sleep(interval)


if __name__ == "__main__":
    asyncio.run(run_forever())
