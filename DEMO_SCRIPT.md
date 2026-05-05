# Demo Script — XRPFi Verifiable Copilot

**Target:** 3-minute 0G APAC Hackathon demo video
**Track:** Track 2 — Agentic Trading Arena / Verifiable Finance
**Recording goal:** Prove the working agent flow, then land on the 0G mainnet receipt.

---

## Setup Before Recording

- Browser tab 1: `http://localhost:8088`
- Browser tab 2: `https://chainscan.0g.ai/tx/0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd`
- Browser tab 3: `https://chainscan.0g.ai/address/0x01fE5698a2448d0fc336295df9977796030C79C4`
- Terminal: `~/xrpfi-verif-copilot`, font 18pt or larger
- Command ready, but not yet run:

```bash
uv run python demo/judge_demo.py
```

Keep the mouse still during proof shots. Zoom browser to 110-125% if Chainscan text is small.

---

## 3-Minute Shooting Guide

### 0:00-0:12 — Title + Product Promise

**Screen state:** Browser UI at `http://localhost:8088`, full window. Show the top status area and the agent flow if visible.

**Voiceover/caption:**

> "This is XRPFi Verifiable Copilot: two AI agents that help XRP holders move toward Flare DeFi yield, with every agent decision preserved as a verifiable receipt on 0G."

**Shot note:** Do not explain the whole architecture yet. Let the UI establish that this is a working product, not a slide deck.

### 0:12-0:32 — Problem in One Pass

**Screen state:** Stay on the UI. Hover or point at the flow from XRP to FXRP to routing if the page exposes it.

**Voiceover/caption:**

> "The hard part is not just finding yield. XRP holders have to reason across bridge steps, FAssets minting, FTSO prices, attestations, routing choices, and auditability. The copilot handles the flow and leaves proof behind."

### 0:32-0:58 — Agent A: Mint Helper

**Screen state:** Switch to terminal. Run:

```bash
uv run python demo/judge_demo.py
```

**Voiceover/caption:**

> "Agent A is mint-helper.eth. It resolves identity, reads live Flare FTSO prices, checks the XRP deposit proof path, and prepares the FAssets mint decision record."

**Capture target:** Let the terminal show the mint-helper step, FTSO prices, and any decision-record summary before moving on.

### 0:58-1:22 — Cross-Agent Handoff

**Screen state:** Terminal continues. Keep the Gensyn AXL message or route handoff lines centered.

**Voiceover/caption:**

> "When the mint step completes, Agent A publishes the event over Gensyn AXL. Agent B wakes up from the topic message, not from a hardcoded function call."

**Capture target:** Show node A to node B communication, topic name, or message ID if printed.

### 1:22-1:48 — Agent B: Yield Router

**Screen state:** Terminal continues. Center the routing output.

**Voiceover/caption:**

> "Agent B is yield-router.eth. It evaluates the Flare venue catalog and applies a deterministic rebalance policy, so the allocation is reproducible from the same inputs."

**Capture target:** Show allocation, venue names such as SparkDEX/Kinetic/Cyclo, and the Uniswap quote step if present.

### 1:48-2:14 — 0G Verification Layer

**Screen state:** Terminal continues. Center the 0G/iNFT output: contract, token ID, tx hash, or explorer URL.

**Voiceover/caption:**

> "The important part is the receipt. The decision records are bundled into the 0G proof layer and minted as an ERC-7857 iNFT on 0G mainnet. Judges do not have to trust the terminal output."

**Capture target:** Keep token ID `1` and tx hash `0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd` visible long enough to read.

### 2:14-2:38 — Chainscan Transaction Proof

**Screen state:** Switch to browser tab 2:

`https://chainscan.0g.ai/tx/0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd`

**Voiceover/caption:**

> "Here is the public 0G mainnet transaction. This is the clickable audit trail for the demo session, not a local log file."

**Capture target:** Show transaction status, hash, and network branding.

### 2:38-2:53 — Contract Proof

**Screen state:** Switch to browser tab 3:

`https://chainscan.0g.ai/address/0x01fE5698a2448d0fc336295df9977796030C79C4`

**Voiceover/caption:**

> "And this is the deployed XRPFi iNFT contract on 0G mainnet. The contract is the permanent anchor for the verifiable agent-history receipts."

**Capture target:** Show contract address and any visible transaction/token activity.

### 2:53-3:00 — Closing Line

**Screen state:** Return to the UI or leave the contract proof visible.

**Voiceover/caption:**

> "XRPFi Verifiable Copilot: XRP to DeFi yield, with receipts an auditor can click."

---

## Recording Checks

- Keep the final export under 3 minutes.
- Show the UI, terminal run, transaction proof, and contract proof.
- Avoid saying "simulated" unless the terminal explicitly shows the 0G storage fallback. If it appears, say: "storage upload fallback used during the run; the iNFT proof is live on 0G mainnet."
- Use the exact Chainscan links above in the video description.
