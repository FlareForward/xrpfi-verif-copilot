# 0G APAC Hackathon 2026 — Submission

**Event:** 0G APAC Hackathon (hackquest.io/hackathons/0G-APAC-Hackathon)  
**Track:** Track 2 — Agentic Trading Arena / Verifiable Finance  
**Deadline:** 2026-05-16 23:59 UTC+8  
**Team:** FlareForward — Steven Hudspeth

---

## Project Name
**XRPFi Verifiable Copilot**

## Tagline
A 2-agent AI system that helps XRP holders enter Flare DeFi — every decision verifiable on-chain via 0G.

## Description

XRPFi Verifiable Copilot is a production-ready 2-agent system built on 0G + Flare Network. It solves a real user problem: XRP holders want yield on their assets, but bridging to DeFi is complex, opaque, and error-prone. Our system automates the full flow — FXRP minting, yield routing, swap execution — while making every agent decision permanently verifiable via 0G storage and ERC-7857 iNFTs.

### Why 0G Is the Right Trust Layer

Traditional AI agents are black boxes. Users have no way to verify what the agent actually did — which prices it used, what reasoning it applied, whether it executed what it said it would.

We use 0G as the verifiability layer: every `DecisionRecord` (prices, reasoning, actions, timestamps) is serialized and uploaded to 0G decentralized storage. After upload, an ERC-7857 iNFT is minted on 0G mainnet with the storage URI embedded. The iNFT token ID and `chainscan.0g.ai` explorer URL are stored back on the record.

The result: any judge, any auditor, any user can click a link and see exactly what the AI agent decided — on-chain, permanent, tamper-proof.

### The Agent Flow

```
XRP holder
    ↓
mint-helper.eth (Agent A)
  ├── Checks XRP/USD + FLR/USD prices via FTSO v2 (Flare-native oracle)
  ├── Attests XRP payment via FDC (Flare Data Connector)
  ├── Initiates FXRP mint via FAssets v1.3 on Songbird
  └── Publishes mint.complete event via Gensyn AXL (node 1 → node 2)
         ↓
yield-router.eth (Agent B)
  ├── Receives AXL message from Agent A
  ├── Fetches Flare DeFi venue yields (SparkDEX, Kinetic, Cyclo)
  ├── Runs deterministic rebalance policy (pure function, no LLM randomness)
  ├── Calls Uniswap Trading API v2 for cross-venue swap leg
  └── Publishes route.plan event via Gensyn AXL
         ↓
Orchestrator
  ├── Persists both DecisionRecords to 0G mainnet storage
  └── Mints iNFT (ERC-7857) — permanent verifiable audit trail
         ↓
✅ chainscan.0g.ai — clickable proof for every judge
```

---

## How It's Built

### Stack
- **Agent framework**: Google ADK (Gemini 2.0 Flash) with lightweight stub fallback
- **Flare data**: Flare AI Kit — FTSO v2 price feeds, FDC Payment attestation, FAssets v1.3
- **Inter-agent comms**: Gensyn AXL REST API with in-process async queue fallback
- **Storage**: 0G mainnet (Chain ID 16661) — `ZeroGClient` + TS SDK helper
- **NFT**: ERC-7857 iNFT — `mint(address, encryptedURI, metadataHash)` on 0G
- **ENS**: web3.py dynamic resolution — no hardcoded addresses
- **Yield routing**: Uniswap Trading API v2 for cross-venue swap legs
- **Policy**: Deterministic pure-function rebalance policy (reproducible, auditable)
- **Shared contract**: PR-0 `DecisionRecord` Pydantic model — single source of truth for both agents

### Architecture Decisions
- **PR-0 contract module**: Both agents share `src/contracts/decision_log.py`. Enforced by test. No drift.
- **Fallback-first**: Every external dependency (AXL, 0G, FTSO, ENS, Uniswap) has an in-process fallback. Demonstrable without live credentials.
- **Deterministic policy**: Same inputs, same outputs. LLM handles reasoning/summarization, not allocation math.

---

## 0G Integration Details

**Key files:**
- `src/integrations/zero_g/client.py` — upload DecisionRecord JSON to 0G storage
- `src/integrations/zero_g/inft.py` — mint ERC-7857 iNFT on 0G mainnet
- `contracts/XRPFiINFT.sol` — Solidity contract (deployed to 0G mainnet)
- `contracts/deploy.py` — deploy script (mainnet-ready, reads from .env)

**Network:** 0G mainnet (Chain ID 16661), RPC `https://evmrpc-mainnet.0g.ai`  
**Explorer:** https://chainscan.0g.ai/  
**Contract:** See `DEPLOYMENT_ADDRESSES.md`

---

## Quick Start

```bash
git clone https://github.com/flareforward/xrpfi-verif-copilot
cd xrpfi-verif-copilot
pip install uv
uv sync --extra dev
cp .env.example .env
# Add GOOGLE_API_KEY to .env
uv run python demo/run_demo.py
```

---

## Tests

```bash
uv run pytest tests/ -q        # 151 passed
uv run ruff check src/ tests/ demo/  # All checks passed
```

---

## Team
FlareForward — Steven Hudspeth  
Built for 0G APAC Hackathon 2026.
