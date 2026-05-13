# XRPFi Verifiable Copilot — Judge Proof Sheet

**0G APAC Hackathon 2026 | FlareForward**

## Quick Start

```bash
pip install uv && uv pip install -e ".[dev]"
cp .env.example .env
uv run python demo/judge_demo.py
```

Browser UI alternative:

```bash
uv run python web/server.py
```

## Live On-Chain Proof

The live anchors are intentionally narrow: a real 0G iNFT and live FTSO price reads. Other integrations are visible in the demo, but they are labeled fixture or planned unless the reality matrix says otherwise.

| Proof Element | State | Value | Explorer Link |
|---|---|---|---|
| 0G iNFT Contract (ERC-7857) | live | `0x01fE5698a2448d0fc336295df9977796030C79C4` | [chainscan.0g.ai/address/0x01fE5698...](https://chainscan.0g.ai/address/0x01fE5698a2448d0fc336295df9977796030C79C4) |
| iNFT Mint Tx | live | `0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd` | [chainscan.0g.ai/tx/0xbe0cf7c8...](https://chainscan.0g.ai/tx/0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd) |
| Token ID | live | `1` | [chainscan.0g.ai/tx/0xbe0cf7c8...](https://chainscan.0g.ai/tx/0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd) |
| FTSO price reads | live | `FLR/USD`, `XRP/USD` from `coston2-api.flare.network` | Runtime output |
| Reality Matrix | source of truth | [REALITY_MATRIX.md](../REALITY_MATRIX.md) | Exact live/fixture/planned state |

## Expected Receipt Output

The demo should read as a receipt, not as proof that every sponsor integration is live:

```text
Agent Receipt — XRPFi Verifiable Copilot

Receipt ID:    <session_id>
Timestamp:     <ISO timestamp>
Agent:         mint-helper.eth -> yield-router.eth

Data Inputs
FTSO FLR/USD:  <price> [LIVE]
FTSO XRP/USD:  <price> [LIVE]
FDC proof:     proof_hash=<sha256> [FIXTURE — demo attestation, not live XRPL]

Decision
Action:        Evaluate yield route for 100 XRP
Route:         60% SparkDEX / 40% Kinetic [FIXTURE — policy rule]
FAssets mint:  Stub params returned [FIXTURE — no broadcast]

Proof Artifacts
0G storage:    [PLANNED — wallet unfunded; see ZERO_G_STORAGE_STATUS.md]
0G iNFT:       token=1 https://chainscan.0g.ai/tx/0xbe0cf7c8... [LIVE]
```

## Reality Matrix

| Integration | State | Evidence | Notes |
|---|---|---|---|
| FTSO prices | live | hits `coston2-api.flare.network` on every run | |
| 0G iNFT (token 1) | live | [`0xbe0cf7c8...`](https://chainscan.0g.ai/tx/0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd) on chainscan.0g.ai | minted 2026-05-04 |
| 0G storage upload | planned | wallet `0x81e518...` has 0 OG | see `ZERO_G_STORAGE_STATUS.md` |
| ENS mint-helper.eth | planned | name unregistered; Sepolia wallet unfunded | script ready in `scripts/register_ens.py` |
| ENS yield-router.eth | planned | name unregistered; Sepolia wallet unfunded | |
| FDC attestation | fixture | demo proof hash; not a real XRPL tx | |
| FAssets mint | fixture | stub tx params; no on-chain broadcast | |
| Uniswap WETH/USDC quote | fixture | no API key set; pair unrelated to FXRP | |
| Gensyn AXL | fixture | in-process `asyncio.Queue`; `force_fallback=True` | |
| Yield routing | fixture | deterministic 60/40 policy; no live DeFi calls | |

## Common Fallbacks

| Condition | Label Shown | Resolution |
|---|---|---|
| `GOOGLE_API_KEY` not set | deterministic reasoning fallback | Add key to `.env` |
| 0G wallet unfunded | `[PLANNED — wallet unfunded]` | Top up `0x81e518...` on Chain 16661 |
| `UNISWAP_API_KEY` not set | `[FIXTURE — no API key]` | Add key to `.env` |
| ENS not registered | `[PLANNED — name unregistered]` | Register on Sepolia with `scripts/register_ens.py` |
| Gensyn node not connected | `[FIXTURE — local AXL-compatible fallback]` | Connect a real Gensyn node |

## Quality Check

```bash
uv run --extra dev pytest tests/ -q
uv run ruff check .
uv run mypy --strict src/
```

Expected baseline: 163 tests passing, ruff clean, and mypy strict clean.

## Links

- [0G iNFT token 1 transaction](https://chainscan.0g.ai/tx/0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd)
- [Reality Matrix](../REALITY_MATRIX.md)
- [Submission](../SUBMISSION.md)
- [GitHub](https://github.com/FlareForward/xrpfi-verif-copilot)
