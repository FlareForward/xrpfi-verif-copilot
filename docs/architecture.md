# XRPFi Verifiable Copilot — Architecture

## System Overview

Two AI agents collaborate to help XRP holders enter Flare DeFi, with every decision
verified on-chain and stored as an iNFT on 0G.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        User (XRP Holder)                                │
│                   "I want to earn yield on my XRP"                      │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              Agent A — mint-helper.eth                                  │
│              (Gensyn AXL Node 1 | Google ADK | Gemini 2.0)              │
│                                                                         │
│  1. Resolves "mint-helper.eth" via ENS (not hardcoded)                  │
│  2. Reads FTSO prices: FLR/USD + XRP/USD (Flare-First Data Policy)      │
│  3. Attests XRP deposit via FDC Payment attestation (XRPL → Flare)      │
│  4. Estimates mint cost (collateral, lots, fee bips)                    │
│  5. Initiates FXRP mint via FAssets v1.3 on Songbird testnet            │
│  6. Produces DecisionRecord for every action                            │
│  7. Publishes "mint complete" to AXL topic via Gensyn AXL node 1        │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │
                    Gensyn AXL message
                    topic: xrpfi.mint.complete
                    (cross-node, node 1 → node 2)
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              Agent B — yield-router.eth                                 │
│              (Gensyn AXL Node 2 | Google ADK | Gemini 2.0)              │
│                                                                         │
│  1. Receives AXL message from Agent A (subscribes to xrpfi.mint.complete)│
│  2. Resolves "yield-router.eth" via ENS                                 │
│  3. Queries Flare DeFi venue catalog (SparkDEX, Kinetic, Cyclo)         │
│  4. Deterministic rebalance policy: allocates FXRP by risk preference  │
│  5. Calls Uniswap API for any swap legs needed                          │
│  6. Produces DecisionRecord with full route plan + reasoning            │
│  7. Publishes route plan to AXL topic xrpfi.route.plan                  │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              Verifiability Layer (Orchestrator)                         │
│                                                                         │
│  All DecisionRecords (from both agents):                                │
│  1. Serialized to canonical JSON                                        │
│  2. Uploaded to 0G decentralized storage (Newton testnet)               │
│  3. Minted as ERC-7857 iNFT on 0G Newton testnet                       │
│  4. Explorer URL: https://chainscan-newton.0g.ai/token/<tokenId>        │
│                                                                         │
│  Result: Any judge/user can click the iNFT URL and verify:              │
│    - Which FTSO prices the agent used (with feed_id + timestamp)        │
│    - Whether FDC payment attestation passed                             │
│    - The exact rebalance reasoning                                      │
│    - Every action taken and its result                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

## Sponsor Prize Alignment

| Sponsor | How We Satisfy the Requirement |
|---------|--------------------------------|
| **0G** | Every DecisionRecord → 0G storage → iNFT minted on 0G Newton testnet. Explorer URL in demo output. DEPLOYMENT_ADDRESSES.md has contract address. |
| **ENS** | `mint-helper.eth` and `yield-router.eth` resolved dynamically via ENS (web3.py + ENS middleware). ENS resolution is functional, not hardcoded. |
| **Uniswap** | Agent B calls Uniswap Trading API v2 for swap legs. `FEEDBACK.md` documents devex, bugs, and missing features. |
| **Gensyn** | AXL node 1 (Agent A) publishes to `xrpfi.mint.complete`; AXL node 2 (Agent B) subscribes. Cross-node communication demonstrated with separate endpoints. |

## Data Flow — DecisionRecord (PR-0 Contract)

Every agent action produces a `DecisionRecord` (Pydantic BaseModel from `src/contracts/decision_log.py`):

```python
DecisionRecord(
    agent_name="mint-helper",
    agent_ens="mint-helper.eth",
    action_type="mint",
    ftso_prices=[FtsoPrice(feed_id="0x01...", price_usd=0.50, timestamp=...)],
    fdc_proof=FdcProof(attestation_type="Payment", proof_hash="0x...", chain="XRPL"),
    reasoning="XRP/USD=0.50, FLR/USD=0.025. Mint economics favorable.",
    action_taken="Initiated FAssets mint for 100 XRP → ~99 FXRP",
    result_summary="Collateral reservation ID: ...",
    zero_g=ZeroGRecord(storage_tx_hash="0x...", inft_token_id="42")
)
```

Both agents import `DecisionRecord` from the shared `src/contracts/decision_log.py`
(Contract Enforcement Protocol — no local redeclaration permitted).

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent framework | Google ADK (google-adk ≥1.19.0) + Gemini 2.0 Flash |
| Flare AI Kit | flare-foundation/flare-ai-kit @ f29d0a7 (pinned) |
| Flare DeFi | FAssets v1.3 (Songbird testnet), FTSO v2 (Coston2), FDC |
| Inter-agent comms | Gensyn AXL (2 separate nodes) |
| Verifiability | 0G storage (0g-storage-sdk) + iNFT (ERC-7857) |
| Swap legs | Uniswap Trading API v2 |
| Name resolution | ENS (web3.py + eth-ens-namehash) |
| Language | Python 3.12 |
| Config | pydantic-settings + .env |

## Directory Structure

```
xrpfi-verif-copilot/
├── src/
│   ├── contracts/
│   │   └── decision_log.py          # PR-0 shared schema (both agents import from here)
│   ├── agents/
│   │   ├── mint_helper/             # Agent A (Lane A)
│   │   └── yield_router/            # Agent B (Lane B)
│   ├── integrations/
│   │   ├── fassets/                 # FAssets v1.3 client
│   │   ├── fdc/                     # FDC attestation client
│   │   ├── ftso/                    # FTSO v2 price feed client
│   │   ├── ens/                     # ENS resolution
│   │   ├── uniswap/                 # Uniswap API client
│   │   ├── defi_venues/             # Flare DeFi venue catalog
│   │   └── zero_g/                  # 0G storage + iNFT mint
│   ├── gensyn/
│   │   ├── node_a/                  # AXL publisher (mint-helper)
│   │   └── node_b/                  # AXL subscriber + publisher (yield-router)
│   ├── policies/
│   │   └── rebalance_policy.py      # Deterministic pure-function policy
│   └── config.py                    # Pydantic settings
├── demo/
│   └── run_demo.py                  # End-to-end demo script
├── tests/                           # Pytest test suite
├── README.md
├── FEEDBACK.md                      # Uniswap devex notes (prize gate)
└── DEPLOYMENT_ADDRESSES.md          # Contract addresses on testnets
```
