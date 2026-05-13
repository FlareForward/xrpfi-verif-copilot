# XRPFi Verifiable Copilot — Agent Receipt Explorer

**0G APAC Hackathon 2026 | FlareForward**

## Submission Summary

XRPFi is the flight recorder for AI finance: every agent decision leaves a structured, inspectable receipt. The demo shows an AI-assisted finance flow producing a `DecisionRecord` with inputs, agent identity, decision details, risk notes, proof status, and an on-chain-linked artifact. The strongest proof today is focused and honest: one real 0G iNFT and live FTSO price reads. Everything else is labeled as fixture or planned so judges can see both what works now and what the architecture is prepared to support.

## Live Proof

- **0G iNFT:** token 1 — [chainscan.0g.ai](https://chainscan.0g.ai/tx/0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd)
- **FTSO prices:** live data from `coston2-api.flare.network` on every run
- **ENS identities:** code-ready for Sepolia; live registration is pending
  0.05 Sepolia ETH funding to `0x53730993203f21b9ac8d10a8CA5CA5d92b036118`,
  then `uv run python scripts/register_ens.py`.

See [REALITY_MATRIX.md](REALITY_MATRIX.md) for exact live/fixture/planned state.

## Sponsor Integrations

| Integration | State | Evidence | Notes |
|---|---|---|---|
| FTSO prices | live | hits `coston2-api.flare.network` on every run | Receipt input data |
| 0G iNFT (token 1) | live | [`0xbe0cf7c8...`](https://chainscan.0g.ai/tx/0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd) on chainscan.0g.ai | Minted 2026-05-04 |
| 0G storage upload | planned | wallet `0x81e518...` has 0 OG | See `ZERO_G_STORAGE_STATUS.md` |
| ENS mint-helper.eth | code-ready | registration script ready; Sepolia wallet needs 0.05 ETH | Public Sepolia RPC: `https://rpc.sepolia.org`; fund `0x5373...6118`, dry-run, then register |
| ENS yield-router.eth | code-ready | registration script ready; Sepolia wallet needs 0.05 ETH | Same `scripts/register_ens.py` run as `mint-helper.eth` |
| FDC attestation | fixture | demo proof hash; not a real XRPL tx | |
| FAssets mint | fixture | stub tx params; no on-chain broadcast | |
| Uniswap WETH/USDC quote | fixture | no API key set; pair unrelated to FXRP | |
| Gensyn AXL | fixture | in-process `asyncio.Queue`; `force_fallback=True` | |
| Yield routing | fixture | deterministic 60/40 policy; no live DeFi calls | |

## How to Run

```bash
pip install uv && uv pip install -e ".[dev]"
cp .env.example .env
uv run python demo/judge_demo.py
```

## Demo Video

Demo video: pending final capture.

## Why It Matters

AI-assisted finance needs receipts before it needs bigger promises. A structured receipt lets users, judges, and builders inspect the data used, the agent identity, the decision made, and the proof status behind each claim. XRPFi demonstrates that pattern with a real 0G iNFT anchor today and a clear path for turning fixture and planned fields into stronger integrations later.

## GitHub

https://github.com/FlareForward/xrpfi-verif-copilot
