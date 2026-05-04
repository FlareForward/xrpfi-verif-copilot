# Lane B — Uniswap API Developer Experience Notes

> Collected during XRPFi Verifiable Copilot build (2026-05-04).
> These notes are for the Uniswap Prize submission FEEDBACK.md.
> Orchestrator will merge this file into the root FEEDBACK.md.

## Source
`src/integrations/uniswap/client.py` — `DEVEX_NOTES` list (captured inline during build)

---

## Notes

1. **ENDPOINT DISCOVERY**: Tried `GET /v2/quote` first (mirroring v1 path) — 404.
   Correct path is `GET /v2/quote` with query params, not POST.
   Docs show the base URL but don't prominently show which HTTP verb to use per endpoint.
   **Improvement:** Add a quick-start table with `METHOD + PATH + required params` at the top of each endpoint section.

2. **AUTHENTICATION**: The v2 API requires an `x-api-key` header for production usage.
   However, the docs don't clearly state which endpoints require auth vs. which are public.
   Hit a 403 on `/v2/quote` without the header in testing.
   **Improvement:** Clearly mark authenticated vs. unauthenticated endpoints in the API reference.

3. **RATE LIMITS**: No rate limit headers (`X-RateLimit-*`) in responses during dev testing.
   Had to infer limits from the docs footnote.
   **Improvement:** Return standard rate-limit headers so clients can implement backoff automatically.

4. **TOKEN ADDRESS LOOKUP**: API requires checksummed ERC-20 addresses, not token symbols.
   No built-in symbol→address resolution — must maintain your own address map or use a token list.
   **Improvement:** Add an optional `tokenSymbol` convenience parameter that resolves to address internally.

5. **CHAIN SUPPORT**: Docs mention Ethereum mainnet and some L2s, but Flare/Coston2 is NOT listed.
   Cross-chain FXRP swaps require a bridging step before Uniswap can be invoked.
   Workaround: treat Uniswap as Ethereum-side router only; bridge FXRP→wFXRP first.
   **Improvement:** Document cross-chain flow explicitly for non-EVM-native tokens.

6. **CALLDATA ENDPOINT**: `/v2/swap` (for calldata) requires the full quote object as input.
   The quote object shape isn't fully documented — had to inspect example responses to determine required fields.
   **Improvement:** Provide a JSON schema for the quote object in the swap endpoint docs.

7. **AMOUNT PRECISION**: Amounts are in raw wei (no decimals). Easy to get wrong when passing
   float amounts — must multiply by 10^decimals before sending.
   **Improvement:** Accept a `humanReadable: true` flag that auto-applies decimal conversion.

8. **SDK vs REST**: The Uniswap v3/v4 SDK (TypeScript) is much better documented than the REST API.
   REST API docs feel like an afterthought vs. the SDK.
   **Improvement:** Bring REST API docs up to parity with SDK — especially for Python users.

9. **QUOTE FRESHNESS**: Quotes expire quickly (~15s). The expiry window isn't prominently surfaced.
   If you get a quote then wait before submitting, you get a stale-quote error.
   **Improvement:** Return a `valid_until` Unix timestamp in the quote response.

10. **MOCK MODE**: No sandbox or testnet mode documented for the Trading API.
    Had to build our own mock in tests (using `respx`).
    **Improvement:** Provide a public sandbox endpoint or example fixtures for CI testing.

---

## Summary

The Uniswap Trading API v2 is functional but has significant developer experience gaps compared
to the SDK. The top three quick wins for improving developer adoption:

1. A clear `METHOD + PATH + auth required` table at the top of each endpoint's docs page.
2. Standard `X-RateLimit-*` response headers.
3. A public sandbox endpoint (or documented fixture set) for CI/offline testing.

The REST API would especially benefit from Python code examples — the current docs are
TypeScript/JavaScript-centric, creating friction for Python-native DeFi builders.
