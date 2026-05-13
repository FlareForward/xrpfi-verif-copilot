# XRPFi Verifiable Copilot — Agent Receipt Explorer

![CI](https://github.com/FlareForward/xrpfi-verif-copilot/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)

**The flight recorder for AI finance. Every agent decision leaves a verifiable receipt.**

## What It Does

AI agents making financial decisions need to leave an audit trail. XRPFi produces a structured, inspectable receipt for every agent action: inputs, identity, decision, risk notes, proof status, and on-chain link. The receipt is permanent and clickable on 0G's explorer. This is the infrastructure pattern that serious agentic finance requires. One live on-chain artifact today; the pattern generalises.

## Live Proof

- **0G iNFT:** token 1 — [chainscan.0g.ai](https://chainscan.0g.ai/tx/0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd)
- **FTSO prices:** live price data from `coston2-api.flare.network` on every run
- **Reality check:** See [REALITY_MATRIX.md](REALITY_MATRIX.md) for the exact live/fixture/planned state of every integration.

## Quick Start

```bash
pip install uv && uv pip install -e ".[dev]"
cp .env.example .env
uv run python demo/judge_demo.py
```

## Architecture

```text
User intent
   |
   v
AI agent evaluates inputs
   |
   v
DecisionRecord receipt
   |-- agent identity
   |-- FTSO price inputs
   |-- decision and risk notes
   |-- LIVE / FIXTURE / PLANNED proof status
   |
   v
0G iNFT link
   |
   v
chainscan.0g.ai
```

The product is the receipt: a compact record that lets a judge, user, or future protocol inspect what an AI agent saw, decided, and proved.

## Receipt Format

Each agent action produces a `DecisionRecord` shaped around auditability:

```json
{
  "session_id": "demo-session-001",
  "agent_name": "yield-router",
  "agent_ens": "yield-router.eth",
  "inputs": {
    "ftso_prices": ["FLR/USD [LIVE]", "XRP/USD [LIVE]"],
    "fdc_proof": "proof_hash=... [FIXTURE]",
    "route_amount": "100 XRP"
  },
  "decision": {
    "action_taken": "evaluate_yield_route",
    "result_summary": "60% SparkDEX / 40% Kinetic [FIXTURE]",
    "risk_notes": ["fixture route policy; no live DeFi call"]
  },
  "proof_status": {
    "ftso": "live",
    "zero_g_inft": "live",
    "fdc": "fixture",
    "zero_g_storage_upload": "planned"
  },
  "on_chain_link": "https://chainscan.0g.ai/tx/0xbe0cf7c8..."
}
```

## Sponsor Integrations

| Integration | State | Evidence | Notes |
|---|---|---|---|
| FTSO prices | live | hits `coston2-api.flare.network` on every run | Live data source for receipt inputs |
| 0G iNFT (token 1) | live | [`0xbe0cf7c8...`](https://chainscan.0g.ai/tx/0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd) on chainscan.0g.ai | Minted 2026-05-04 |
| 0G storage upload | planned | wallet `0x81e518...` has 0 OG | See [ZERO_G_STORAGE_STATUS.md](ZERO_G_STORAGE_STATUS.md) |
| ENS mint-helper.eth | planned | name unregistered; Sepolia wallet unfunded | Script ready in `scripts/register_ens.py` |
| ENS yield-router.eth | planned | name unregistered; Sepolia wallet unfunded | |
| FDC attestation | fixture | demo proof hash; not a real XRPL tx | |
| FAssets mint | fixture | stub tx params; no on-chain broadcast | |
| Uniswap WETH/USDC quote | fixture | no API key set; pair unrelated to FXRP | |
| Gensyn AXL | fixture | in-process `asyncio.Queue`; `force_fallback=True` | |
| Yield routing | fixture | deterministic 60/40 policy; no live DeFi calls | |

The same table is maintained as the dedicated [Reality Matrix](REALITY_MATRIX.md).

## FlareForward / Apex Bridge

This receipt pattern is directly relevant to FlareForward's work on Apex and agent-assisted DeFi. The primitive demonstrated here — structured, on-chain-linked agent receipts — is a building block for any system where AI agents manage real capital.

## Tests

```bash
uv run --extra dev pytest tests/ -q
uv run ruff check .
uv run mypy --strict src/
```

Expected baseline for this repositioning cycle: 163 tests passing, ruff clean, and mypy strict clean.

## Team

Built by **FlareForward** (Steven Hudspeth) for 0G APAC Hackathon 2026.

## License

MIT
