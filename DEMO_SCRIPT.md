# Demo Script — XRPFi Verifiable Copilot
**Target:** 3-minute demo video for 0G APAC Hackathon submission  
**Track:** Track 2 — Agentic Trading Arena / Verifiable Finance

---

## Before You Record

1. Open two terminal windows side by side (or use a split terminal)
2. Navigate both to `~/xrpfi-verif-copilot/`
3. Make sure `.env` has your real `GOOGLE_API_KEY` and funded `ZERO_G_PRIVATE_KEY`
4. Have your browser open to `https://chainscan.0g.ai/` (0G mainnet explorer)
5. Have `DEPLOYMENT_ADDRESSES.md` open — you'll read the contract address aloud

---

## Script (3 minutes)

### 0:00–0:30 — The Problem (voiceover, no typing)

> "XRP holders sit on billions in idle capital. Moving it into DeFi means:
> bridge to Flare, mint FXRP via FAssets, navigate a dozen yield venues,
> manage collateral ratios — all while trusting the AI black box.
>
> XRPFi Verifiable Copilot automates the entire flow and makes every agent
> decision permanently verifiable on 0G — so you can prove exactly what the
> AI did and why."

*Show the architecture diagram in `docs/architecture.md` on screen.*

---

### 0:30–1:30 — Live Demo: Mint Helper Agent

In terminal:
```bash
uv run python demo/run_demo.py
```

Narrate as output appears:

> "Step 1: mint-helper.eth resolves dynamically via ENS — no hardcoded address."

*(Wait for ENS resolution output)*

> "Step 2: FTSO v2 prices — Flare-native oracle. Every price includes the
> feed ID and timestamp, locked into the decision record."

*(Wait for FTSO price output)*

> "Step 3: FDC Payment attestation — cross-chain proof that the XRP deposit
> actually happened on the XRPL ledger."

*(Wait for FDC output)*

> "Step 4: FAssets v1.3 mint initiated on Songbird. Reservation ID confirmed."

*(Wait for mint output)*

> "Agent A is done. It publishes a 'mint.complete' event to yield-router via
> Gensyn AXL — cross-node, topic-based. Watch Agent B wake up."

---

### 1:30–2:30 — Live Demo: Yield Router + 0G Storage

*(Demo continues in same terminal)*

> "Agent B — yield-router.eth — picks up the AXL message."

*(Wait for yield-router output)*

> "Deterministic rebalance policy: same inputs, same output, every time.
> No LLM randomness in the allocation math. 60% SparkDEX LP, 40% Kinetic."

*(Wait for allocation output)*

> "Both decision records — every price used, every action taken, all
> the reasoning — are now being uploaded to 0G decentralized storage."

*(Wait for 0G storage output — shows tx hash)*

> "And now the iNFT mint. ERC-7857. This is the verifiable audit trail."

*(Wait for iNFT output — shows token ID and explorer URL)*

---

### 2:30–3:00 — On-Chain Proof

Switch to browser. Navigate to the explorer URL shown in the terminal output:
`https://chainscan.0g.ai/tx/<tx_hash>`

> "Here it is — on the 0G mainnet explorer. A real on-chain transaction
> proving the AI agent's decision log."

Navigate to the contract:
`https://chainscan.0g.ai/address/<INFT_CONTRACT_ADDRESS>`

> "The iNFT contract. Any judge, any auditor, any user can click here and
> see exactly what the agent did. Not a log file. Not a database.
> On-chain. Permanent. Verifiable."

*(Final beat)*

> "XRPFi Verifiable Copilot. XRP to DeFi yield — with a receipt."

---

## Tips

- Keep the terminal font large (18pt+) so it's readable in the recording
- Screenflow or QuickTime screen recording work well on Mac
- Aim for 2:50 — leave 10 seconds of breathing room
- If the live 0G upload is slow, the demo script has a fallback that still shows a tx hash — explain that as "simulated for dev, real tx on mainnet after funding"
- Loom is fine for upload (unlisted link is acceptable for hackathon)
