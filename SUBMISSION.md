# XRPFi Verifiable Copilot

**0G APAC Hackathon 2026 — Track 2: Agentic Trading Arena | by FlareForward**

## What It Does

XRPFi Verifiable Copilot helps XRP holders move toward Flare DeFi without asking them to understand every bridge, oracle, or routing step. Two agents work together: `mint-helper.eth` prepares the FXRP mint path, and `yield-router.eth` chooses a yield route after the mint event is received. Each agent decision is saved as a verifiable record so a judge can inspect what happened and why. 0G provides the proof layer: decision records are designed for decentralized storage, and the demo iNFT on 0G mainnet points to the verifiable agent history. The result is a click-through audit trail for an AI-assisted XRP-to-DeFi flow.

## Live Proof

- **0G iNFT:** token 1 — [chainscan.0g.ai](https://chainscan.0g.ai/tx/0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd)
- **0G Storage:** implemented — mainnet upload pending (see `ZERO_G_STORAGE_STATUS.md`)
- **ENS:** mint-helper.eth + yield-router.eth (Sepolia registration script ready; live tx pending funded wallet)
- **Uniswap:** WETH→USDC live quote via Trading API v2 (see `demo/judge_demo.py` step [7])
- **Gensyn AXL:** cross-node message node A → node B (see `demo/judge_demo.py` step [8])

## Sponsor Integrations

| Sponsor | What was built | Key files | Evidence |
|---------|---------------|-----------|----------|
| 0G | Decentralized storage path for every DecisionRecord + ERC-7857 iNFT on mainnet | `src/integrations/zero_g/` | [chainscan.0g.ai token 1 tx](https://chainscan.0g.ai/tx/0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd) |
| ENS | Dynamic forward/reverse resolution for both agents (no hardcoding) | `src/integrations/ens/` | `mint-helper.eth`, `yield-router.eth` |
| Uniswap | Trading API v2 swap quotes for yield routing leg | `src/integrations/uniswap/` | `FEEDBACK.md` |
| Gensyn | AXL cross-node messaging between mint-helper (node 1) and yield-router (node 2) | `src/gensyn/` | `demo/judge_demo.py` step [8] |

## How to Run

```bash
pip install uv && uv pip install -e ".[dev]"
cp .env.example .env  # add GOOGLE_API_KEY
uv run python demo/judge_demo.py
```

See [docs/JUDGES_CHECKLIST.md](docs/JUDGES_CHECKLIST.md) for expected output, fallback explanations, and sponsor integration evidence.

## Demo Video

Demo video: pending final capture.

## GitHub

https://github.com/flareforward/xrpfi-verif-copilot
