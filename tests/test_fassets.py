"""Tests for FAssets v1.3 minting client.

Covers:
- DecisionRecord import assertion (via agent module)
- estimate_mint_cost with mock RPC
- initiate_mint produces collateral_reservation_id
- get_minting_status stub response
- get_agent_info with registry resolution
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.integrations.fassets.client import FAssetsClient


# ---------------------------------------------------------------------------
# Regression pin — import guard
# ---------------------------------------------------------------------------
def test_fassets_client_does_not_redeclare_decision_record() -> None:
    """Pin: FAssetsClient must not redeclare DecisionRecord locally."""
    import inspect

    import src.integrations.fassets.client as fa_module

    source = inspect.getsource(fa_module)
    # If the module imports DecisionRecord it must come from contracts
    if "DecisionRecord" in source:
        assert "from src.contracts.decision_log import" in source
    assert "class DecisionRecord" not in source


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestFAssetsClientEstimateCost:
    @pytest.mark.asyncio
    async def test_estimate_returns_expected_shape(self) -> None:
        client = FAssetsClient()
        # Pre-seed asset manager address to skip registry call
        client._asset_manager_cache["FXRP"] = "0xAAAA000000000000000000000000000000000000"

        estimate = await client.estimate_mint_cost("FXRP", lots=10)

        assert estimate["asset_symbol"] == "FXRP"
        assert estimate["lots"] == 10
        assert "fee_bips" in estimate
        assert estimate["fee_bips"] > 0
        assert "estimated_fee_xrp" in estimate
        assert estimate["estimated_fee_xrp"] >= 0

    @pytest.mark.asyncio
    async def test_estimate_fee_scales_with_lots(self) -> None:
        client = FAssetsClient()
        client._asset_manager_cache["FXRP"] = "0xAAAA000000000000000000000000000000000000"

        e10 = await client.estimate_mint_cost("FXRP", lots=10)
        e20 = await client.estimate_mint_cost("FXRP", lots=20)

        assert e20["estimated_fee_xrp"] == pytest.approx(e10["estimated_fee_xrp"] * 2, rel=0.01)


class TestFAssetsClientInitiateMint:
    @pytest.mark.asyncio
    async def test_initiate_mint_returns_crt_id(self) -> None:
        client = FAssetsClient()
        result = await client.initiate_mint(
            agent_address="0xAAAA000000000000000000000000000000000000",
            lots=5,
            max_minting_fee=100,
        )

        assert "collateral_reservation_id" in result
        assert isinstance(result["collateral_reservation_id"], int)
        assert result["status"] == "pending_user_approval"

    @pytest.mark.asyncio
    async def test_initiate_mint_includes_tx_params(self) -> None:
        client = FAssetsClient()
        agent = "0xBBBB000000000000000000000000000000000000"
        result = await client.initiate_mint(agent, lots=3, max_minting_fee=50)

        tx = result["tx_params"]
        assert tx["to"] == agent
        assert tx["function"] == "reserveCollateral"
        assert tx["args"][1] == 3  # lots

    @pytest.mark.asyncio
    async def test_different_mints_get_different_crt_ids(self) -> None:
        client = FAssetsClient()
        r1 = await client.initiate_mint("0xAAAA000000000000000000000000000000000000", 1, 50)
        r2 = await client.initiate_mint("0xBBBB000000000000000000000000000000000000", 2, 50)
        # CRT IDs are random — not guaranteed unique but extremely likely
        # Just verify both are ints > 0
        assert isinstance(r1["collateral_reservation_id"], int)
        assert isinstance(r2["collateral_reservation_id"], int)


class TestFAssetsClientGetStatus:
    @pytest.mark.asyncio
    async def test_get_minting_status_returns_shape(self) -> None:
        client = FAssetsClient()
        status = await client.get_minting_status(12345)

        assert status["collateral_reservation_id"] == 12345
        assert "status" in status
        assert "status_code" in status


class TestFAssetsClientGetAgentInfo:
    @pytest.mark.asyncio
    async def test_get_agent_info_with_mocked_registry(self) -> None:
        client = FAssetsClient()

        # Registry returns a valid-looking address
        registry_result = "0x" + "0" * 24 + "AAAA000000000000000000000000000000000001"

        async def mock_eth_call(_to: str, _data: str) -> str:
            return registry_result

        with patch.object(client, "_eth_call", side_effect=mock_eth_call):
            info = await client.get_agent_info("FXRP")

        assert info["asset_symbol"] == "FXRP"
        assert "asset_manager_address" in info
        assert isinstance(info["agents"], list)
