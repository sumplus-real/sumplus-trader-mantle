# Submission — Mantle Turing Test Hackathon 2026

> Project: **Sumplus Trader**. Tracks: **Trading & Strategy** + **Agentic Economy**.

## One-liner

An autonomous on-chain trading agent that decides and executes entirely on its own, yet is
structurally incapable of exceeding its leash.

## The problem

Most "AI trading agent" demos are a bot with a hot private key and a prompt. They can trade, but
nothing stops them from going all-in, chasing a shilled token, or blowing past a drawdown. The
thing standing between an autonomous agent and the chain is exactly what nobody shows. That trust
gap is why autonomous on-chain agents are not taken seriously yet.

## What we built

A trading agent split into honest layers:

- **Brain** — a DeepSeek-driven strategy that reads a market snapshot and proposes one decision
  (buy / sell / hold, pair, size, rationale). The strategy harness is ours; the model is the engine.
- **Guardrail** — a deterministic policy layer that allows, clamps, or hard-rejects every decision
  against a whitelist, size caps, a drawdown circuit-breaker, and a rate limit.
- **Secure execution** — approved trades route to a separate execution layer (Maria) that enforces
  the same policy server-side, signs with a server wallet, and broadcasts the swap.
- **DEX routing** — on Mantle the swap is routed through Agni Finance (chain 5000) via our Arsenal
  routing layer.
- **Conversational surface** — a built-in web chat: a user can ask the agent its status, ask why it
  made a decision, and pause / resume / adjust caps in plain language. No human approves trades; the
  human supervises.

The pitch is not "look at my returns." It is **safe autonomy** — the agent runs by itself, and the
leash holds. Defence in depth: the guardrail self-limits the brain, and the execution layer enforces
the same policy independently, so the safety property does not depend on the model behaving.

## Why it fits the tracks

- **Trading & Strategy** — a real strategy engine deciding and executing spot swaps on Mantle, with
  risk management (drawdown breaker, position caps) built into the trade path, not bolted on.
- **Agentic Economy** — an autonomous agent that acts on-chain under a delegated, enforceable policy.
  This is what makes agent-driven on-chain activity safe enough to scale.

## Deployed on Mantle — live proof

The agent executed a real swap on Mantle (chain 5000) through Agni Finance (Uniswap V3 fork): the
agent's wallet swapped 4 MNT into 2.2344 USDC, broadcast and confirmed on-chain.

- **Tx:** `0x889c64321833c1f27c87cacf4d455cfcdf840b14f4deaf49dab915726495cd45`
- **Mantlescan:** https://mantlescan.xyz/tx/0x889c64321833c1f27c87cacf4d455cfcdf840b14f4deaf49dab915726495cd45
- **Wallet (on-chain actor):** `0x5B9687e2F0BF34BBB9e7937488a513BD82A12dD3`
- **Router:** Agni SwapRouter `0x319B69888b0d11cEC22caA5034e25FfFBDc88421` · **In:** 4 MNT (WMNT) · **Out:** 2.2344 USDC

Token registry and router are verified on-chain (WMNT / USDC / USDT). An ERC-8004 identity ties the
agent's wallet to a registered agent id.

## Run it (no keys, no network)

```bash
python -m agent.cli demo     # guardrail enforcement: allow / clamp / reject
python -m agent.cli web      # web chat + live status panel  →  http://127.0.0.1:8800
python -m agent.cli tick     # one autonomous decision cycle
```

Ships with an offline mock brain and mock execution backend so anyone can run the full agent with
nothing installed. Add keys to switch to the real DeepSeek brain and live Mantle execution.

## Demo script (90 seconds)

1. `python -m agent.cli demo` — show three decisions: an in-policy buy is **allowed**, an oversized
   buy is **clamped** to the cap, a shilled off-whitelist token is **rejected**. "No human approved
   any of this. The leash held."
2. `python -m agent.cli web` — open the page. Type `tick`: the agent makes a real decision, the
   status panel updates (portfolio, drawdown vs cap, recent decisions with allow/blocked badges).
3. Type `set cap max_single_trade_usd 10`, then `tick` again — watch the agent's next size get
   clamped live. Type `pause` — the agent stops opening trades. This is supervised autonomy.

## Tech

DeepSeek (decision) · custom guardrail · Maria secure execution layer · Arsenal DEX routing
(Agni Finance on Mantle) · ERC-8004 identity · Python / FastAPI. Open-source agent; the execution
and routing layers run as hosted services behind a clean API boundary.

## Open-source boundary

This repo is the agent. The execution layer (Maria) and DEX router (Arsenal) are hosted services
behind `ExecutionBackend`; the repo ships only an API client plus an offline mock, so the full agent
is runnable and auditable without exposing backend source.

## What's next

Live execution against a funded Mantle wallet; the same chain-agnostic engine extends to BSC for
live-PnL autonomous trading.
