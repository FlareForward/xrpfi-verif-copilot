"""Tests for FTSO v2 price client.

Covers:
- FtsoPrice import from contracts.decision_log (not redeclared)
- get_price with mocked httpx response
- get_prices batch call
- Staleness flag
- Known feed catalogue
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.contracts.decision_log import FtsoPrice
from src.integrations.ftso.client import (
    COSTON2_RPC,
    FEED_IDS,
    FtsoClient,
    STALE_THRESHOLD_SECONDS,
)


# ---------------------------------------------------------------------------
# Regression pin — import guard
# ---------------------------------------------------------------------------
def test_ftso_price_imported_from_contracts_module() -> None:
    """Pin: FtsoPrice must come from contracts.decision_log, never redeclared."""
    import inspect

    import src.integrations.ftso.client as ftso_module

    source = inspect.getsource(ftso_module)
    assert "from src.contracts.decision_log import" in source
    assert "class FtsoPrice" not in source  # must not redeclare


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _encode_feed_result(value: int, decimals: int, timestamp: int) -> str:
    """Build a minimal ABI-encoded getFeedById result (3 x 32 bytes)."""
    # uint256 value, int8 decimals (zero-extended), uint64 timestamp
    val_hex = f"{value:064x}"
    dec_hex = f"{decimals & 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:064x}"
    ts_hex = f"{timestamp:064x}"
    return "0x" + val_hex + dec_hex + ts_hex


def _registry_result(address: str) -> str:
    """Encode address as 32-byte ABI result."""
    clean = address.lower().removeprefix("0x").zfill(64)
    return "0x" + clean


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestFtsoClientGetPrice:
    @pytest.mark.asyncio
    async def test_get_price_xrp_usd_happy_path(self) -> None:
        """get_price returns FtsoPrice with correct fields from mocked RPC."""
        client = FtsoClient()
        # Pre-seed cached FTSO address to skip registry call
        client._ftso_address = "0x3d893C53D9e8056135C26C8c638B76C8b60Df726"

        ts = int(datetime.now(timezone.utc).timestamp())
        # XRP/USD = 0.50 with 7 decimals → value = 5_000_000
        encoded = _encode_feed_result(5_000_000, 7, ts)

        with patch.object(client, "_eth_call", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = encoded
            price = await client.get_price("XRP/USD")

        assert isinstance(price, FtsoPrice)
        assert price.feed_name == "XRP/USD"
        assert price.feed_id == FEED_IDS["XRP/USD"]
        assert abs(price.price_usd - 0.5) < 0.0001
        assert price.decimals == 7
        assert isinstance(price.timestamp, datetime)
        assert not price.is_stale  # fresh timestamp

    @pytest.mark.asyncio
    async def test_get_price_flr_usd(self) -> None:
        client = FtsoClient()
        client._ftso_address = "0x3d893C53D9e8056135C26C8c638B76C8b60Df726"

        ts = int(datetime.now(timezone.utc).timestamp())
        # FLR/USD = 0.02 with 7 decimals → value = 200_000
        encoded = _encode_feed_result(200_000, 7, ts)

        with patch.object(client, "_eth_call", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = encoded
            price = await client.get_price("FLR/USD")

        assert price.feed_name == "FLR/USD"
        assert price.feed_id == FEED_IDS["FLR/USD"]
        assert abs(price.price_usd - 0.02) < 0.0001

    @pytest.mark.asyncio
    async def test_get_price_stale_when_old_timestamp(self) -> None:
        """is_stale = True when price timestamp is older than STALE_THRESHOLD_SECONDS."""
        client = FtsoClient()
        client._ftso_address = "0x3d893C53D9e8056135C26C8c638B76C8b60Df726"

        # Timestamp 60 seconds ago — should be stale
        old_ts = int(datetime.now(timezone.utc).timestamp()) - (STALE_THRESHOLD_SECONDS + 30)
        encoded = _encode_feed_result(5_000_000, 7, old_ts)

        with patch.object(client, "_eth_call", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = encoded
            price = await client.get_price("XRP/USD")

        assert price.is_stale

    @pytest.mark.asyncio
    async def test_get_price_unknown_feed_raises(self) -> None:
        client = FtsoClient()
        with pytest.raises(ValueError, match="Unknown feed"):
            await client.get_price("DOGE/USD")

    @pytest.mark.asyncio
    async def test_get_price_rpc_failure_returns_stub(self) -> None:
        """When RPC fails, get_price returns a stub price (is_stale=True)."""
        client = FtsoClient()
        client._ftso_address = "0x3d893C53D9e8056135C26C8c638B76C8b60Df726"

        with patch.object(
            client, "_eth_call", side_effect=RuntimeError("network error")
        ):
            price = await client.get_price("XRP/USD")

        assert isinstance(price, FtsoPrice)
        assert price.is_stale  # stub is always marked stale
        assert price.feed_id == FEED_IDS["XRP/USD"]

    @pytest.mark.asyncio
    async def test_get_prices_batch(self) -> None:
        """get_prices returns a list in the same order as the input."""
        client = FtsoClient()
        client._ftso_address = "0x3d893C53D9e8056135C26C8c638B76C8b60Df726"

        ts = int(datetime.now(timezone.utc).timestamp())
        xrp_result = _encode_feed_result(5_000_000, 7, ts)
        flr_result = _encode_feed_result(200_000, 7, ts)

        call_results = [xrp_result, flr_result]
        call_index = 0

        async def side_effect(_to: str, _data: str) -> str:
            nonlocal call_index
            result = call_results[call_index % len(call_results)]
            call_index += 1
            return result

        with patch.object(client, "_eth_call", side_effect=side_effect):
            prices = await client.get_prices(["XRP/USD", "FLR/USD"])

        assert len(prices) == 2
        assert prices[0].feed_name == "XRP/USD"
        assert prices[1].feed_name == "FLR/USD"

    def test_get_known_feeds_contains_required_ids(self) -> None:
        """FLR/USD and XRP/USD feed IDs match the spec."""
        client = FtsoClient()
        feeds = client.get_known_feeds()
        assert feeds["FLR/USD"]["feed_id"] == "0x014658522f555344000000000000000000000000000000000000000000"
        assert feeds["XRP/USD"]["feed_id"] == "0x015852502f555344000000000000000000000000000000000000000000"

    def test_ftso_price_always_has_feed_id_and_timestamp(self) -> None:
        """FtsoPrice model requires feed_id and timestamp (Flare-First Data Policy)."""
        import inspect
        from src.contracts.decision_log import FtsoPrice as FP

        fields = FP.model_fields
        assert "feed_id" in fields
        assert "timestamp" in fields
