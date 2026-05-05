# XRPFi Verifiable Copilot — Judge Handout

**Hackathon:** 0G APAC Hackathon 2026  
**Track:** Track 2 — Agentic Trading Arena / Verifiable Finance  
**Team:** FlareForward  
**Repository:** https://github.com/flareforward/xrpfi-verif-copilot

## What Judges Should Verify First

| Proof | Link |
|---|---|
| 0G mainnet iNFT contract | https://chainscan.0g.ai/address/0x01fE5698a2448d0fc336295df9977796030C79C4 |
| Demo iNFT mint transaction | https://chainscan.0g.ai/tx/0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd |
| Contract deployment transaction | https://chainscan.0g.ai/tx/0xc44f334032243a996ea9221ce9888d157da7d3af2fc67ef437435b9b1ca26023 |
| Deployment record | ../DEPLOYMENT_ADDRESSES.md |
| Architecture | architecture.md |

## Quickstart

```bash
pip install uv && uv pip install -e ".[dev]"
cp .env.example .env
uv run python demo/judge_demo.py
```

Add `GOOGLE_API_KEY` to `.env` for the agent demo. The 0G iNFT proof above is already live on 0G mainnet, so judges can verify the receipt even before rerunning locally.

## Architecture

```text
User request
  -> mint-helper.eth
     -> FTSO v2 prices + FDC payment proof path + FAssets mint decision
  -> Gensyn AXL topic: xrpfi.mint.complete
  -> yield-router.eth
     -> Flare venue catalog + deterministic rebalance policy + Uniswap quote path
  -> DecisionRecord bundle
  -> 0G proof layer
  -> ERC-7857 iNFT on 0G mainnet
  -> Chainscan receipt for judges and auditors
```

## Sponsor Integration Table

| Sponsor / Protocol | Integration | Evidence |
|---|---|---|
| 0G | ERC-7857 iNFT contract on 0G mainnet; decision records are anchored into the verifiable receipt flow | Contract `0x01fE5698a2448d0fc336295df9977796030C79C4`, token ID `1` |
| Flare | FTSO v2 price reads, FDC payment attestation path, FAssets v1.3 mint flow | `DEPLOYMENT_ADDRESSES.md`, `demo/judge_demo.py`, `src/integrations/ftso/`, `src/integrations/fdc/`, `src/integrations/fassets/` |
| ENS | Agent identities resolve through `mint-helper.eth` and `yield-router.eth` paths | `src/integrations/ens/`, `scripts/register_ens.py` |
| Uniswap | Trading API v2 quote path for route evaluation | `src/integrations/uniswap/`, `FEEDBACK.md` |
| Gensyn AXL | Cross-node handoff from mint-helper to yield-router | `src/gensyn/`, `demo/judge_demo.py` |

## Why It Fits Track 2

XRPFi Verifiable Copilot is an agentic trading assistant for the XRP-to-Flare-DeFi path. The product value is not only automation; it is verifiable automation. Each agent action produces a structured `DecisionRecord` containing prices, reasoning, action, result, and proof references. 0G turns that decision history into a judge-clickable receipt, closing the trust gap around AI-assisted financial routing.
