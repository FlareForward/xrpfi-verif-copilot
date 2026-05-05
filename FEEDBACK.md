# Developer Feedback — XRPFi Verifiable Copilot

> **Uniswap Prize Gate:** This file is required for Uniswap Foundation prize eligibility.
> It documents our developer experience building on top of Uniswap integrations.
> Built for **0G APAC Hackathon 2026 — Track 2: Agentic Trading Arena**.

---

## About This Project

XRPFi Verifiable Copilot is a 2-agent system that helps XRP holders enter Flare DeFi
end-to-end: FXRP minting via FAssets v1.3 → yield routing via Uniswap API + Flare DeFi venues.
Every agent decision is persisted through the 0G storage path and represented by an iNFT for verifiability.

Built for **0G APAC Hackathon 2026** in ~48h.

## Why 0G?

0G is the core trust layer for this project, not a badge added at the end. XRPFi Verifiable Copilot asks users to trust AI agents with sensitive DeFi routing decisions, so every material decision needs an external proof surface that judges and users can inspect. 0G storage gives each `DecisionRecord` a decentralized home once uploaded, while the ERC-7857 iNFT gives the session a durable, clickable ownership and audit object on 0G mainnet. Without 0G, the demo would be another opaque agent flow; with 0G, the agent's reasoning and actions become verifiable artifacts.

---

## Uniswap Integration Notes

### What we built
Agent B (`yield-router.eth`) uses the Uniswap Trading API to execute swap legs when
routing FXRP across yield venues. The agent calls `GET /v2/quote` and `POST /v2/swap`
from `https://api.uniswap.org/v2`.

### Developer Experience

#### What worked well
- The Trading API v2 endpoint structure is clean and RESTful
- Quote response includes all fields needed for downstream execution
- TypeScript types in the SDK are thorough and help with payload construction

#### Friction points and bugs encountered

1. **Endpoint discovery**: Tried `GET /v2/quote` first — 404. Correct path uses query params,
   not a POST body. Docs show base URL but don't prominently state HTTP verb per endpoint.
   *Fix: add a `METHOD + PATH + required params` table at the top of each endpoint section.*

2. **Authentication ambiguity**: `x-api-key` header required for production, but docs don't
   clearly state which endpoints need auth vs. which are public. Hit 403 on `/v2/quote`
   without the header. *Fix: mark authenticated/unauthenticated endpoints explicitly.*

3. **No rate-limit headers**: No `X-RateLimit-*` in responses — had to infer limits from a
   footnote. *Fix: return standard rate-limit headers for automatic client backoff.*

4. **Token address lookup**: API requires checksummed ERC-20 addresses — no symbol→address
   resolution built in. *Fix: optional `tokenSymbol` convenience param.*

5. **Flare/Coston2 missing from chain list**: Uniswap does not support Flare or Coston2.
   Cross-chain FXRP swaps require a bridge step first. *Fix: document cross-chain flow for
   non-EVM-native tokens; consider Flare as a supported chain.*

6. **Calldata endpoint underdocumented**: `/v2/swap` requires a full quote object as input
   but the schema isn't defined — had to inspect example responses.
   *Fix: provide JSON schema for the quote object in swap docs.*

7. **Amount precision gotcha**: Amounts in raw wei (no decimals). Easy to get wrong with
   float inputs. *Fix: optional `humanReadable: true` flag with auto decimal conversion.*

8. **REST vs SDK documentation gap**: TypeScript SDK docs are far more complete than the REST
   API docs. *Fix: bring REST docs to parity — especially for Python users.*

9. **Quote freshness (~15s) not surfaced**: No `valid_until` timestamp in the quote response.
   Stale-quote errors appear only at submit time. *Fix: return `valid_until` Unix timestamp.*

10. **No sandbox/mock endpoint**: Had to build our own respx mock for CI.
    *Fix: provide a public sandbox endpoint or documented fixture set for offline testing.*

#### Missing features (wishlist)
- **Cross-chain quote**: given a Flare DeFi route, return the optimal bridge + swap path
  automatically rather than requiring builders to compose it manually
- **Testnet parity**: Uniswap v4 hooks are mainnet-only; testnet versions would reduce friction
  for hackathon development with real code + safe economics
- **SDK streaming quotes**: a subscribe-to-price endpoint for agents needing live quote updates
  rather than polling
- **Flare support**: Adding Flare/Coston2 as a supported chain would directly unblock
  FXRP/FLR swaps without bridging

#### Documentation gaps
- The distinction between Uniswap v2 and v4 APIs in the Trading API docs is not clear
  when both are available — a migration guide or "start here" table would help
- Error codes are not documented — we received numeric error codes in some 4xx responses
  with no reference table to look them up

---

## Flare AI Kit Notes (for team)

- Flare AI Kit alpha (`f29d0a7`) works for FTSO price reads and FAssets client scaffolding
- `google-adk` dependency (`>=1.19.0`) is the main constraint — Gemini 2.0 Flash is the
  default model and works well for agent reasoning loops
- FDC attestation round IDs require a running Flare DA Layer connection; for testnet demos
  we fall back to fixture proof hashes

---

## 0G Integration Notes

- Python SDK (`0g-storage-sdk 0.2.1`) integration is implemented through `src/integrations/zero_g/`
- iNFT (ERC-7857) minting uses a deployed iNFT contract on 0G mainnet; the contract address
  and token 1 transaction are in `DEPLOYMENT_ADDRESSES.md`
- Mainnet storage upload is implemented, with current status tracked transparently in
  `ZERO_G_STORAGE_STATUS.md` when an upload transaction is unavailable

---

## Gensyn AXL Notes

- AXL cross-node communication between `mint-helper` (node A) and `yield-router` (node B)
  is implemented using the Gensyn AXL REST API with a local async queue fallback
- The AXL topic-based message passing (`xrpfi.mint.complete` → `xrpfi.route.plan`) clearly
  demonstrates cross-agent communication via separate AXL nodes
- For production: replace localhost endpoints with real Gensyn network node addresses

---

*Last updated: 2026-05-05 by XRPFi Verifiable Copilot team*
