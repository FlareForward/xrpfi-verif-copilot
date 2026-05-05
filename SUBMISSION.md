# ETHGlobal Open Agents 2026 — Submission

## Project Name
**XRPFi Verifiable Copilot**

## Tagline
A 2-agent AI system that helps XRP holders enter Flare DeFi — every decision verifiable on-chain.

## Description

XRPFi Verifiable Copilot is a production-ready 2-agent system built on the Flare Network ecosystem. It solves a real user problem: XRP holders want yield on their assets, but bridging to DeFi is complex, opaque, and error-prone. Our system automates the full flow — FXRP minting, yield routing, swap execution — while making every agent decision permanently verifiable via 0G storage and ERC-7857 iNFTs.

### The Flow

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
  ├── Persists both DecisionRecords to 0G Newton testnet storage
  └── Mints iNFT (ERC-7857) — permanent verifiable audit trail
         ↓
✅ chainscan-newton.0g.ai/tx/0x...
```

### Why This Matters

- **Verifiability**: Every agent decision — prices used, reasoning, action taken — is stored on 0G and minted as a non-fungible record. Users can audit exactly what the agent did and why.
- **Flare-native data**: Uses FTSO v2 for price feeds and FDC for cross-chain attestation — not external oracles.
- **Cross-agent communication**: Agent A and B are isolated processes communicating exclusively via Gensyn AXL topics, demonstrating real multi-agent coordination.
- **ENS identity**: Both agents have ENS names (`mint-helper.eth`, `yield-router.eth`) resolved dynamically — no hardcoded addresses.

---

## How It's Built

### Stack
- **Agent framework**: Google ADK (Gemini 2.0 Flash) with lightweight stub fallback
- **Flare data**: Flare AI Kit (`f29d0a7`) — FTSO v2 price feeds, FDC Payment attestation, FAssets v1.3 client
- **Inter-agent comms**: Gensyn AXL REST API with in-process async queue fallback
- **Storage**: 0G Newton testnet (`0g-storage-sdk` + HTTP fallback)
- **NFT**: ERC-7857 iNFT with `mint(address, encryptedURI, metadataHash)`
- **ENS**: web3.py + ENS middleware, dynamic resolution
- **Yield routing**: Uniswap Trading API v2 (`/v2/quote`, `/v2/swap`) for swap legs
- **Policy**: Deterministic pure-function rebalance policy (no LLM, reproducible)
- **Shared contract**: PR-0 `DecisionRecord` (Pydantic BaseModel, 76 LOC) — imported by both agents, never redeclared

### Architecture Decisions
- **PR-0 contract module**: Both agents share a single `src/contracts/decision_log.py` schema. This is enforced by test. No drift, no duplication.
- **Fallback-first**: Every external dependency (AXL, 0G, FTSO, ENS, Uniswap) has an in-process fallback. The system is demonstrable without any live credentials.
- **Deterministic policy**: Yield allocation is a pure function — same inputs always produce same outputs. LLM handles reasoning/summarization, not allocation math.
- **Concurrent isolation**: Built with a 3-surface parallel architecture (Orchestrator + Lane A + Lane B) using git worktrees.

---

## Sponsor Integrations

### 0G — Track B: AI + Decentralized Storage
Every `DecisionRecord` is serialized and uploaded to 0G Newton testnet via `ZeroGClient`. After upload, an ERC-7857 iNFT is minted with the storage URI embedded. The iNFT token ID and `chainscan-newton.0g.ai` explorer URL are stored back on the `DecisionRecord`.

**Key files:**
- `src/integrations/zero_g/client.py` — upload + root hash
- `src/integrations/zero_g/inft.py` — ERC-7857 mint
- `DEPLOYMENT_ADDRESSES.md` — deployed contract addresses

### ENS — Dynamic Agent Identity
Both agents resolve their ENS names dynamically via web3.py. No addresses are hardcoded. The resolver uses `w3.ens.address()` with a fallback map for testnet environments.

**Key files:**
- `src/integrations/ens/resolver.py` — mint-helper.eth
- `src/integrations/ens/resolver_b.py` — yield-router.eth

### Uniswap — Trading API v2
Agent B calls the Uniswap Trading API for swap calldata on the cross-venue routing leg. We also documented 10 developer experience friction points in `FEEDBACK.md`.

**Key files:**
- `src/integrations/uniswap/client.py` — `get_quote()`, `get_swap_calldata()`
- `FEEDBACK.md` — 10 devex notes for Uniswap Foundation

### Gensyn — AXL Cross-Node Communication
Agent A (mint-helper, AXL node 1) publishes to `xrpfi.mint.complete`. Agent B (yield-router, AXL node 2) subscribes and publishes `xrpfi.route.plan`. Topics are config-driven, endpoints are separate nodes. Fallback uses a shared in-process async queue that fully mirrors the AXL interface.

**Key files:**
- `src/gensyn/node_a/publisher.py` — node 1 publisher
- `src/gensyn/node_b/subscriber.py` — node 2 subscriber
- `src/gensyn/node_b/publisher.py` — node 2 publisher

---

## Demo

```bash
git clone <repo>
cd xrpfi-verif-copilot
cp .env.example .env
# Add GOOGLE_API_KEY to .env
pip install -e .
python demo/run_demo.py
```

Output ends with:
```
✅ Verifiable audit trail: https://chainscan-newton.0g.ai/tx/0x...
```

---

## Testing

```bash
pytest tests/ -v   # 151 tests, 0 failures
ruff check src/    # All checks passed
```

---

## Team
FlareForward — Steven Hudspeth

Built for ETHGlobal Open Agents 2026 in ~48h.
