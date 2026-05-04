# Developer Feedback — XRPFi Verifiable Copilot

> **Uniswap Prize Gate:** This file is required for Uniswap Foundation prize eligibility.
> It documents our developer experience building on top of Uniswap integrations.

---

## About This Project

XRPFi Verifiable Copilot is a 2-agent system that helps XRP holders enter Flare DeFi
end-to-end: FXRP minting via FAssets v1.3 → yield routing via Uniswap API + Flare DeFi venues.
Every agent decision is persisted to 0G storage and minted as an iNFT for verifiability.

Built for **ETHGlobal Open Agents 2026** in ~48h.

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
<!-- Lane B: append your devex notes here during T13 -->
- **Auth ambiguity**: The v2 API documentation is unclear about whether an API key is
  required for testnet vs mainnet. We attempted unauthenticated requests and received
  401 on some endpoints but not others. A clear "auth required: yes/no per endpoint" table
  in the docs would help.
- **Flare/Coston2 not in chain list**: Uniswap API does not support Flare Network or
  Coston2 testnet as a destination chain. We route swap legs through Ethereum mainnet/
  Sepolia as an intermediary. A Flare integration would enable direct FXRP/FLR swaps
  without bridging.
- **Quote TTL not documented**: Quote objects include a deadline field but the TTL
  (how long a quote is valid) is not documented. We assume 30s based on experimentation.
- **Missing FXRP token address in routing**: FXRP is not indexed in Uniswap's default
  token list. We had to manually specify token addresses. An auto-index of Flare-bridged
  tokens would improve DX for Flare DeFi builders.

#### Missing features (wishlist)
- Cross-chain quote: given a Flare DeFi route, return the optimal bridge + swap path
  automatically rather than requiring builders to compose it manually
- Testnet parity: Uniswap v4 hooks are mainnet-only; testnet versions for hackathon development
  would reduce the friction of building with real code but safe economics
- SDK streaming quotes: a subscribe-to-price endpoint for agents that need live quote updates
  rather than polling

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

- Python SDK (`0g-storage-sdk 0.2.1`) uploads work via the SDK; HTTP fallback also works
- iNFT (ERC-7857) minting requires a deployed iNFT contract on 0G Newton testnet — we
  deploy one for the demo; the contract address is in `DEPLOYMENT_ADDRESSES.md`
- Newton testnet faucet provides 0.1 OG/day — sufficient for hackathon demo transactions

---

## Gensyn AXL Notes

- AXL cross-node communication between `mint-helper` (node A) and `yield-router` (node B)
  is implemented using the Gensyn AXL REST API with a local async queue fallback
- The AXL topic-based message passing (`xrpfi.mint.complete` → `xrpfi.route.plan`) clearly
  demonstrates cross-agent communication via separate AXL nodes
- For production: replace localhost endpoints with real Gensyn network node addresses

---

*Last updated: 2026-05-04 by XRPFi Verifiable Copilot team*
