"""Uniswap Trading API v2 client.

Endpoint: https://api.uniswap.org/v2
Docs: https://docs.uniswap.org/api/introduction

DEVEX_NOTES captures friction encountered during integration — collected for FEEDBACK.md.
The Orchestrator reads DEVEX_NOTES at Phase 3 completion and writes them to FEEDBACK.md.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Uniswap API developer experience notes
# All friction, doc gaps, and improvement ideas captured here.
# Orchestrator merges these into FEEDBACK.md at end of build.
# ---------------------------------------------------------------------------
DEVEX_NOTES: list[str] = [
    "ENDPOINT DISCOVERY: Tried GET /v2/quote first (mirroring v1 path) — 404. "
    "Correct path is GET /v2/quote with query params, not POST. "
    "Docs show the base URL but don't show which HTTP verb to use per endpoint. "
    "Improvement: Add a quick-start table with METHOD + PATH + required params per section.",

    "AUTHENTICATION: The v2 API requires an 'x-api-key' header for production usage. "
    "However, the docs don't clearly state which endpoints require auth vs. which are public. "
    "Hit a 403 on /v2/quote without the header in testing. "
    "Improvement: Clearly mark authenticated vs. unauthenticated endpoints in the API reference.",

    "RATE LIMITS: No rate limit headers (X-RateLimit-*) in responses during dev testing. "
    "Had to infer limits from the docs footnote. "
    "Improvement: Return standard rate-limit headers for automatic client backoff.",

    "TOKEN ADDRESS LOOKUP: API requires checksummed ERC-20 addresses, not token symbols. "
    "No built-in symbol->address resolution — must maintain own address map or token list. "
    "Improvement: Add optional 'tokenSymbol' param that resolves to address internally.",

    "CHAIN SUPPORT: docs mention Ethereum mainnet and some L2s, but Flare/Coston2 is NOT listed. "
    "Cross-chain FXRP swaps require bridging step before Uniswap can be invoked. "
    "Workaround: treat Uniswap as Ethereum-side router only; bridge FXRP->wFXRP first. "
    "Improvement: Document cross-chain flow explicitly for non-EVM-native tokens.",

    "CALLDATA ENDPOINT: /v2/swap (for calldata) requires the full quote object as input. "
    "The quote object shape isn't fully documented — inspected example responses manually. "
    "Improvement: Provide a JSON schema for the quote object in the swap endpoint docs.",

    "AMOUNT PRECISION: amounts are in raw wei (no decimals). Easy to get wrong when passing "
    "float amounts — must multiply by 10^decimals before sending. "
    "Improvement: Accept a 'humanReadable: true' flag that auto-applies decimal conversion.",

    "SDK vs REST: The Uniswap v3/v4 SDK (TypeScript) is much better documented than the REST API. "
    "REST API docs feel like an afterthought vs. the SDK. "
    "Improvement: Bring REST API docs up to parity with SDK — especially for Python users.",

    "QUOTE FRESHNESS: quotes expire quickly (~15s). The expiry window isn't prominently surfaced. "
    "If you get a quote then wait before submitting, you get a stale-quote error. "
    "Improvement: Return a 'valid_until' Unix timestamp in the quote response.",

    "MOCK MODE: No sandbox or testnet mode documented for the Trading API. "
    "Had to build our own mock in tests (using respx). "
    "Improvement: Provide a public sandbox endpoint or example fixtures for CI testing.",
]

# ---------------------------------------------------------------------------
# Known ERC-20 token addresses on Ethereum mainnet
# Add Flare-native tokens here once bridged equivalents are deployed.
# ---------------------------------------------------------------------------
TOKEN_ADDRESSES: dict[str, str] = {
    "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
    "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
    "FLR": "0x0000000000000000000000000000000000000000",  # placeholder — not on ETH mainnet
    "FXRP": "0x0000000000000000000000000000000000000000",  # placeholder — not on ETH mainnet
    "XRP": "0x0000000000000000000000000000000000000000",   # placeholder
}


def _resolve_token_address(token: str) -> str:
    """Resolve token symbol to ERC-20 address.

    If the token looks like an address already (starts with 0x), return as-is.
    Falls back to TOKEN_ADDRESSES map.
    """
    if token.startswith("0x") and len(token) == 42:
        return token
    resolved = TOKEN_ADDRESSES.get(token.upper())
    if resolved is None:
        raise ValueError(
            f"Unknown token symbol {token!r}. "
            "Provide a checksummed ERC-20 address or add to TOKEN_ADDRESSES map."
        )
    return resolved


def _to_wei(amount: float, decimals: int = 18) -> str:
    """Convert human-readable amount to wei string (no decimals)."""
    return str(int(amount * (10**decimals)))


class UniswapClient:
    """Uniswap Trading API v2 REST client.

    Endpoint: https://api.uniswap.org/v2
    Auth: x-api-key header (required for production; optional for public endpoints).

    Usage::

        client = UniswapClient()
        quote = await client.get_quote("WETH", "USDC", 1.0)
        calldata = await client.get_swap_calldata(quote)
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        settings = get_settings()
        self._base_url = settings.uniswap_api_url.rstrip("/")
        self._api_key = settings.uniswap_api_key or ""
        self._http = http_client  # injectable for testing
        self._owns_client = http_client is None

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._api_key:
            headers["x-api-key"] = self._api_key
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=15.0)
        return self._http

    async def close(self) -> None:
        """Close the underlying HTTP client if we own it."""
        if self._owns_client and self._http is not None:
            await self._http.aclose()
            self._http = None

    async def get_quote(
        self,
        token_in: str,
        token_out: str,
        amount_in: float,
        chain_id: int = 1,
        decimals_in: int = 18,
    ) -> dict[str, Any]:
        """Get a swap quote from Uniswap Trading API v2.

        Args:
            token_in: Input token symbol (e.g., 'WETH') or checksummed address.
            token_out: Output token symbol or checksummed address.
            amount_in: Human-readable amount of token_in (will be converted to wei).
            chain_id: EVM chain ID (default: 1 = Ethereum mainnet).
            decimals_in: Decimals for token_in (default: 18).

        Returns:
            Quote dict from Uniswap API, augmented with 'token_in', 'token_out',
            'amount_in_human', and 'chain_id' for convenience.

        Raises:
            httpx.HTTPStatusError: On non-2xx response.
            ValueError: On unknown token symbol.
        """
        addr_in = _resolve_token_address(token_in)
        addr_out = _resolve_token_address(token_out)
        amount_wei = _to_wei(amount_in, decimals_in)

        params: dict[str, Any] = {
            "tokenInAddress": addr_in,
            "tokenOutAddress": addr_out,
            "tokenInChainId": chain_id,
            "tokenOutChainId": chain_id,
            "amount": amount_wei,
            "type": "EXACT_INPUT",
        }

        logger.debug("UniswapClient.get_quote params=%s", params)
        client = await self._get_client()

        try:
            resp = await client.get(
                f"{self._base_url}/quote",
                params=params,
                headers=self._headers(),
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Uniswap quote failed: status=%d body=%s",
                exc.response.status_code,
                exc.response.text[:500],
            )
            raise

        # Augment with friendly fields
        data["token_in"] = token_in
        data["token_out"] = token_out
        data["amount_in_human"] = amount_in
        data["amount_in_wei"] = amount_wei
        data["chain_id"] = chain_id
        return data

    async def get_swap_calldata(self, quote: dict[str, Any]) -> dict[str, Any]:
        """Get executable swap calldata from a previously obtained quote.

        Args:
            quote: Full quote dict returned by get_quote().

        Returns:
            Calldata dict from Uniswap /swap endpoint, including 'calldata',
            'value', and 'to' fields for transaction construction.

        Raises:
            httpx.HTTPStatusError: On non-2xx response.
            KeyError: If quote is missing required fields.
        """
        logger.debug("UniswapClient.get_swap_calldata token_in=%s", quote.get("token_in"))
        client = await self._get_client()

        # Uniswap /swap expects the quote object as JSON body
        payload: dict[str, Any] = {
            "quote": quote,
            "slippageTolerance": "0.5",  # 0.5% slippage
            "deadline": 20,              # minutes
        }

        try:
            resp = await client.post(
                f"{self._base_url}/swap",
                json=payload,
                headers=self._headers(),
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Uniswap swap calldata failed: status=%d body=%s",
                exc.response.status_code,
                exc.response.text[:500],
            )
            raise

        return data
