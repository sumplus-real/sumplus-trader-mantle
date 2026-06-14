"""Turn a guardrail-approved Decision into a Maria swap call.

paper mode  → call Maria get_quote only (no broadcast), log the would-be trade.
live  mode  → call Maria execute_swap (Maria itself may still be in dry-run until its
              MARIA_SKILLS_TX_ENABLED flag is on; we surface whichever it returns).
"""
from __future__ import annotations

from agent.execution.maria_client import MariaClient
from agent.types import Decision, ExecutionResult


class Executor:
    def __init__(self, maria: MariaClient, mode: str = "paper", default_slippage_bps: int = 50):
        self.maria = maria
        self.mode = mode
        self.slippage_bps = default_slippage_bps

    async def execute(self, decision: Decision, amount_usd: float) -> ExecutionResult:
        amount = f"{amount_usd:g}"
        if self.mode == "paper":
            quote = await self.maria.get_quote(
                chain=decision.chain, from_token=decision.from_token,
                to_token=decision.to_token, amount=amount, slippage_bps=self.slippage_bps,
            )
            return ExecutionResult(executed=False, dry_run=True, detail={"mode": "paper", "quote": quote})

        return await self.maria.execute_swap(
            chain=decision.chain, from_token=decision.from_token,
            to_token=decision.to_token, amount=amount, slippage_bps=self.slippage_bps,
        )
