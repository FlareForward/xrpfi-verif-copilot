"""Tests for the Uniswap Trading API v2 client.

Uses respx to mock httpx calls — no real network required.
Tests: get_quote with mock response, token resolution, error handling.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

# ---------------------------------------------------------------------------
# Mock response fixtures
# ---------------------------------------------------------------------------

MOCK_QUOTE_RESPONSE: dict[str, Any] = {
    "quoteId": "q-abc123",
    "blockNumber": "19000000",
    "amount": "1000000000000000000",
    "amountDecimals": "1.0",
    "quote": "1850000000",
    "quoteDecimals": "1850.0",
    "quoteGasAdjusted": "1849900000",
    "quoteGasAdjustedDecimals": "1849.9",
    "gasUseEstimateQuote": "100000",
    "gasUseEstimate": "150000",
    "gasPriceWei": "20000000000",
    "route": [],
    "routeString": "WETH -- 0.3% --> USDC",
    "tokenInAddress": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    "tokenOutAddress": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "methodParameters": {},
    "price_impact": "0.01%",
    "quote_amount": "1850.0",
}

MOCK_SWAP_RESPONSE: dict[str, Any] = {
    "calldata": "0xdeadbeef",
    "value": "0x0",
    "to": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
    "gasLimit": "200000",
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUniswapClient:
    @pytest.mark.asyncio
    async def test_get_quote_success(self) -> None:
        """get_quote returns augmented quote dict on 200 response."""
        from src.integrations.uniswap.client import UniswapClient

        with respx.mock(base_url="https://api.uniswap.org/v2") as mock:
            mock.get("/quote").mock(
                return_value=httpx.Response(200, json=MOCK_QUOTE_RESPONSE)
            )

            client = UniswapClient()
            quote = await client.get_quote("WETH", "USDC", 1.0, chain_id=1)

        assert quote["token_in"] == "WETH"
        assert quote["token_out"] == "USDC"
        assert quote["amount_in_human"] == 1.0
        assert quote["chain_id"] == 1
        assert "amount_in_wei" in quote

    @pytest.mark.asyncio
    async def test_get_quote_includes_original_response(self) -> None:
        """get_quote merges original API fields into the result."""
        from src.integrations.uniswap.client import UniswapClient

        with respx.mock(base_url="https://api.uniswap.org/v2") as mock:
            mock.get("/quote").mock(
                return_value=httpx.Response(200, json=MOCK_QUOTE_RESPONSE)
            )

            client = UniswapClient()
            quote = await client.get_quote("WETH", "USDC", 1.0)

        assert "quoteId" in quote
        assert "routeString" in quote

    @pytest.mark.asyncio
    async def test_get_quote_sends_correct_params(self) -> None:
        """get_quote sends correct query parameters to the API."""
        from src.integrations.uniswap.client import UniswapClient

        captured_request = None

        with respx.mock(base_url="https://api.uniswap.org/v2") as mock:
            def capture(request: httpx.Request) -> httpx.Response:
                nonlocal captured_request
                captured_request = request
                return httpx.Response(200, json=MOCK_QUOTE_RESPONSE)

            mock.get("/quote").mock(side_effect=capture)
            client = UniswapClient()
            await client.get_quote("WETH", "USDC", 2.5)

        assert captured_request is not None
        params = dict(captured_request.url.params)
        assert params["type"] == "EXACT_INPUT"
        assert params["protocols"] == "v3"
        assert "tokenInAddress" in params
        assert "tokenOutAddress" in params
        assert "amount" in params

    @pytest.mark.asyncio
    async def test_get_quote_amount_in_wei_conversion(self) -> None:
        """Amount is correctly converted to wei (18 decimals)."""
        from src.integrations.uniswap.client import UniswapClient

        captured_request = None

        with respx.mock(base_url="https://api.uniswap.org/v2") as mock:
            def capture(request: httpx.Request) -> httpx.Response:
                nonlocal captured_request
                captured_request = request
                return httpx.Response(200, json=MOCK_QUOTE_RESPONSE)

            mock.get("/quote").mock(side_effect=capture)
            client = UniswapClient()
            quote = await client.get_quote("WETH", "USDC", 1.5)

        # 1.5 ETH = 1.5 * 10^18 wei
        assert quote["amount_in_wei"] == "1500000000000000000"

    @pytest.mark.asyncio
    async def test_get_quote_404_raises(self) -> None:
        """get_quote raises HTTPStatusError on 404."""
        from src.integrations.uniswap.client import UniswapClient

        with respx.mock(base_url="https://api.uniswap.org/v2") as mock:
            mock.get("/quote").mock(
                return_value=httpx.Response(404, json={"error": "not found"})
            )

            client = UniswapClient()
            with pytest.raises(httpx.HTTPStatusError):
                await client.get_quote("WETH", "USDC", 1.0)

    @pytest.mark.asyncio
    async def test_get_quote_403_raises(self) -> None:
        """get_quote raises HTTPStatusError on 403 (missing API key)."""
        from src.integrations.uniswap.client import UniswapClient

        with respx.mock(base_url="https://api.uniswap.org/v2") as mock:
            mock.get("/quote").mock(
                return_value=httpx.Response(403, json={"error": "forbidden"})
            )

            client = UniswapClient()
            with pytest.raises(httpx.HTTPStatusError):
                await client.get_quote("WETH", "USDC", 1.0)

    @pytest.mark.asyncio
    async def test_get_swap_calldata_success(self) -> None:
        """get_swap_calldata returns calldata dict on 200 response."""
        from src.integrations.uniswap.client import UniswapClient

        with respx.mock(base_url="https://api.uniswap.org/v2") as mock:
            mock.post("/swap").mock(
                return_value=httpx.Response(200, json=MOCK_SWAP_RESPONSE)
            )

            client = UniswapClient()
            calldata = await client.get_swap_calldata(MOCK_QUOTE_RESPONSE)

        assert "calldata" in calldata
        assert "to" in calldata

    @pytest.mark.asyncio
    async def test_get_swap_calldata_sends_quote_as_body(self) -> None:
        """get_swap_calldata posts the quote object as JSON body."""
        from src.integrations.uniswap.client import UniswapClient

        captured_body: dict[str, Any] = {}

        with respx.mock(base_url="https://api.uniswap.org/v2") as mock:
            def capture(request: httpx.Request) -> httpx.Response:
                captured_body.update(json.loads(request.content))
                return httpx.Response(200, json=MOCK_SWAP_RESPONSE)

            mock.post("/swap").mock(side_effect=capture)
            client = UniswapClient()
            await client.get_swap_calldata(MOCK_QUOTE_RESPONSE)

        assert "quote" in captured_body
        assert "slippageTolerance" in captured_body
        assert "deadline" in captured_body


class TestTokenResolution:
    def test_resolve_known_symbol(self) -> None:
        from src.integrations.uniswap.client import _resolve_token_address
        addr = _resolve_token_address("WETH")
        assert addr == "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

    def test_resolve_checksummed_address_passthrough(self) -> None:
        from src.integrations.uniswap.client import _resolve_token_address
        addr = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
        assert _resolve_token_address(addr) == addr

    def test_resolve_unknown_symbol_raises(self) -> None:
        from src.integrations.uniswap.client import _resolve_token_address
        with pytest.raises(ValueError, match="Unknown token symbol"):
            _resolve_token_address("UNKNOWNCOIN")

    def test_to_wei_one_eth(self) -> None:
        from src.integrations.uniswap.client import _to_wei
        assert _to_wei(1.0) == "1000000000000000000"

    def test_to_wei_fractional(self) -> None:
        from src.integrations.uniswap.client import _to_wei
        assert _to_wei(0.5) == "500000000000000000"


class TestDevexNotes:
    def test_devex_notes_is_list(self) -> None:
        """DEVEX_NOTES must be a list for Orchestrator to collect."""
        from src.integrations.uniswap.client import DEVEX_NOTES
        assert isinstance(DEVEX_NOTES, list)

    def test_devex_notes_non_empty(self) -> None:
        """Must have captured at least some devex friction."""
        from src.integrations.uniswap.client import DEVEX_NOTES
        assert len(DEVEX_NOTES) >= 5, "Expected at least 5 devex notes"

    def test_devex_notes_are_strings(self) -> None:
        from src.integrations.uniswap.client import DEVEX_NOTES
        for note in DEVEX_NOTES:
            assert isinstance(note, str)
