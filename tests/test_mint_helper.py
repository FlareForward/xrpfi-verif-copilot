"""Tests for mint-helper agent.

Covers:
- REGRESSION PIN: DecisionRecord imported from contracts.decision_log, not redeclared
- Agent produces DecisionRecord with action_type == "mint" from initiate_mint tool
- ENS resolver returns non-hardcoded address (mock web3 call)
- AxlPublisher in fallback mode produces valid UUID message_id
- Individual tool functions produce DecisionRecord outputs
"""

from __future__ import annotations

import inspect
import re
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.contracts.decision_log import DecisionRecord, FtsoPrice


# ---------------------------------------------------------------------------
# REGRESSION PIN — must always pass per Silent Regression Protocol
# ---------------------------------------------------------------------------
def test_decision_record_import_from_contracts_module() -> None:
    """Pin: DecisionRecord must come from contracts.decision_log, never redeclared."""
    import src.agents.mint_helper.agent as agent_module

    source = inspect.getsource(agent_module)
    assert (
        "from src.contracts.decision_log import" in source
        or "from contracts.decision_log import" in source
    ), "agent.py must import from src.contracts.decision_log"
    assert "class DecisionRecord" not in source, (
        "agent.py must NOT redeclare DecisionRecord — import from contracts.decision_log"
    )


# ---------------------------------------------------------------------------
# Mint-helper tool: check_xrp_balance
# ---------------------------------------------------------------------------
class TestCheckXrpBalance:
    @pytest.mark.asyncio
    async def test_returns_decision_record(self) -> None:
        from src.agents.mint_helper.agent import check_xrp_balance

        result = await check_xrp_balance("rGWrZyax5eXbi5YpFV3xgMm1K9L3YSm1YV")

        assert "decision_record" in result
        record = result["decision_record"]
        assert isinstance(record, DecisionRecord)
        assert record.agent_name == "mint-helper"
        assert record.action_type == "report"

    @pytest.mark.asyncio
    async def test_returns_balance_xrp(self) -> None:
        from src.agents.mint_helper.agent import check_xrp_balance

        result = await check_xrp_balance("rGWrZyax5eXbi5YpFV3xgMm1K9L3YSm1YV")

        assert "balance_xrp" in result
        assert isinstance(result["balance_xrp"], (int, float))


# ---------------------------------------------------------------------------
# Mint-helper tool: get_ftso_price
# ---------------------------------------------------------------------------
class TestGetFtsoPrice:
    @pytest.mark.asyncio
    async def test_returns_ftso_price_with_feed_id(self) -> None:
        from src.agents.mint_helper.agent import get_ftso_price

        stub_price = FtsoPrice(
            feed_id="0x015852502f555344000000000000000000000000000000000000000000",
            feed_name="XRP/USD",
            price_usd=0.50,
            decimals=7,
            timestamp=datetime.now(UTC),
            is_stale=False,
        )

        with patch(
            "src.integrations.ftso.client.FtsoClient.get_price",
            new_callable=AsyncMock,
            return_value=stub_price,
        ):
            result = await get_ftso_price("XRP/USD")

        assert result["feed_name"] == "XRP/USD"
        assert result["feed_id"].startswith("0x")
        assert "timestamp" in result
        assert "decision_record" in result
        record = result["decision_record"]
        assert isinstance(record, DecisionRecord)
        assert len(record.ftso_prices) == 1
        assert record.ftso_prices[0].feed_id == stub_price.feed_id


# ---------------------------------------------------------------------------
# Mint-helper tool: estimate_mint_cost
# ---------------------------------------------------------------------------
class TestEstimateMintCost:
    @pytest.mark.asyncio
    async def test_returns_decision_record(self) -> None:
        from src.agents.mint_helper.agent import estimate_mint_cost

        mock_estimate = {
            "asset_symbol": "FXRP",
            "lots": 10,
            "fee_bips": 15,
            "estimated_fee_xrp": 0.015,
            "collateral_required_flr": 20.0,
            "asset_manager_address": "0xAAAA",
        }

        with patch(
            "src.integrations.fassets.client.FAssetsClient.estimate_mint_cost",
            new_callable=AsyncMock,
            return_value=mock_estimate,
        ):
            result = await estimate_mint_cost("FXRP", 10)

        assert "decision_record" in result
        record = result["decision_record"]
        assert isinstance(record, DecisionRecord)
        assert record.action_type == "report"


# ---------------------------------------------------------------------------
# Mint-helper tool: initiate_mint → action_type == "mint"
# ---------------------------------------------------------------------------
class TestInitiateMint:
    @pytest.mark.asyncio
    async def test_produces_mint_action_type(self) -> None:
        """Regression: initiate_mint must produce DecisionRecord with action_type='mint'."""
        from src.agents.mint_helper.agent import initiate_mint

        mock_result = {
            "agent_address": "0xAAAA",
            "lots": 5,
            "max_minting_fee": 100,
            "collateral_reservation_id": 42,
            "tx_params": {},
            "status": "pending_user_approval",
        }

        with patch(
            "src.integrations.fassets.client.FAssetsClient.initiate_mint",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await initiate_mint(
                agent_address="0xAAAA000000000000000000000000000000000000",
                lots=5,
                max_minting_fee_bips=100,
            )

        assert "decision_record" in result
        record = result["decision_record"]
        assert isinstance(record, DecisionRecord)
        assert record.action_type == "mint", (
            f"Expected action_type='mint', got {record.action_type!r}"
        )
        assert record.agent_name == "mint-helper"
        assert result["status"] == "pending_user_approval"

    @pytest.mark.asyncio
    async def test_initiate_mint_includes_crt_id(self) -> None:
        from src.agents.mint_helper.agent import initiate_mint

        mock_result = {
            "agent_address": "0xAAAA",
            "lots": 3,
            "max_minting_fee": 50,
            "collateral_reservation_id": 99,
            "tx_params": {},
            "status": "pending_user_approval",
        }

        with patch(
            "src.integrations.fassets.client.FAssetsClient.initiate_mint",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await initiate_mint("0xAAAA", 3, 50)

        assert result["collateral_reservation_id"] == 99


# ---------------------------------------------------------------------------
# ENS resolver — dynamic resolution (not hardcoded)
# ---------------------------------------------------------------------------
class TestEnsResolverDynamic:
    @pytest.mark.asyncio
    async def test_resolve_returns_non_hardcoded_address(self) -> None:
        """EnsResolver.resolve must use dynamic resolution, not a hardcoded constant.

        We mock _resolve_via_rpc to return a specific address and verify the
        resolver passes that value through unchanged.
        """
        from src.integrations.ens.resolver import EnsResolver

        dynamic_address = "0x71C7656EC7ab88b098defB751B7401B5f6d8976F"

        resolver = EnsResolver()

        with patch.object(
            resolver, "_resolve_via_web3", new_callable=AsyncMock, return_value=None
        ), patch.object(
            resolver,
            "_resolve_via_rpc",
            new_callable=AsyncMock,
            return_value=dynamic_address,
        ):
            address = await resolver.resolve("mint-helper.eth")

        assert address == dynamic_address
        # Verify the address did NOT come from a hardcoded constant
        # by checking that the resolver module source does not contain the address
        import src.integrations.ens.resolver as ens_module
        source = inspect.getsource(ens_module)
        assert dynamic_address not in source, (
            "Address must not be hardcoded in resolver.py — must use dynamic resolution"
        )

    @pytest.mark.asyncio
    async def test_resolve_uses_fallback_when_not_registered(self) -> None:
        """When live resolution fails, falls back to TEST_ADDRESSES and logs warning."""
        from src.integrations.ens.resolver import TEST_ADDRESSES, EnsResolver

        resolver = EnsResolver()

        with patch.object(
            resolver, "_resolve_via_web3", new_callable=AsyncMock, return_value=None
        ), patch.object(
            resolver, "_resolve_via_rpc", new_callable=AsyncMock, return_value=None
        ):
            address = await resolver.resolve("mint-helper.eth")

        # Must use fallback from TEST_ADDRESSES, not a bare hardcoded string
        assert address == TEST_ADDRESSES["mint-helper.eth"]

    @pytest.mark.asyncio
    async def test_resolve_unknown_name_raises(self) -> None:
        from src.integrations.ens.resolver import EnsResolver

        resolver = EnsResolver()

        with patch.object(
            resolver, "_resolve_via_web3", new_callable=AsyncMock, return_value=None
        ), patch.object(
            resolver, "_resolve_via_rpc", new_callable=AsyncMock, return_value=None
        ), pytest.raises(ValueError, match="could not resolve"):
            await resolver.resolve("nonexistent-unknown-name-xrpfi.eth")


# ---------------------------------------------------------------------------
# AXL publisher — fallback mode produces valid UUID message_id
# ---------------------------------------------------------------------------
class TestAxlPublisherFallbackMode:
    @pytest.mark.asyncio
    async def test_fallback_mode_produces_valid_uuid_message_id(self) -> None:
        """publish_mint_complete in fallback mode returns a valid UUID message_id."""
        from src.gensyn.node_a.publisher import AxlPublisher

        publisher = AxlPublisher()

        record = DecisionRecord(
            agent_name="mint-helper",
            agent_ens="mint-helper.eth",
            action_type="mint",
            input_summary="Test mint 10 XRP→FXRP",
            ftso_prices=[],
            reasoning="Test reasoning",
            action_taken="FAssetsClient.initiate_mint",
            result_summary="crt_id=42",
        )

        # Force fallback by making AXL node unreachable

        with patch.object(
            publisher,
            "_try_axl_publish",
            new_callable=AsyncMock,
            return_value=None,  # None = offline
        ):
            msg_id = await publisher.publish_mint_complete(record)

        # Must be a valid UUID
        assert isinstance(msg_id, str)
        assert len(msg_id) == 36
        # Validate UUID format: 8-4-4-4-12
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        )
        assert uuid_pattern.match(msg_id), f"Not a valid UUID: {msg_id}"

    @pytest.mark.asyncio
    async def test_fallback_mode_flag_set(self) -> None:
        from src.gensyn.node_a.publisher import AxlPublisher

        publisher = AxlPublisher()
        record = DecisionRecord(
            agent_name="mint-helper",
            agent_ens="mint-helper.eth",
            action_type="mint",
            input_summary="Test",
            ftso_prices=[],
            reasoning="Test",
            action_taken="test",
            result_summary="test",
        )

        with patch.object(
            publisher, "_try_axl_publish", new_callable=AsyncMock, return_value=None
        ):
            await publisher.publish_mint_complete(record)

        assert publisher.is_fallback_mode

    @pytest.mark.asyncio
    async def test_get_message_id_returns_last_published(self) -> None:
        from src.gensyn.node_a.publisher import AxlPublisher

        publisher = AxlPublisher()
        record = DecisionRecord(
            agent_name="mint-helper",
            agent_ens="mint-helper.eth",
            action_type="mint",
            input_summary="Test",
            ftso_prices=[],
            reasoning="Test",
            action_taken="test",
            result_summary="test",
        )

        with patch.object(
            publisher, "_try_axl_publish", new_callable=AsyncMock, return_value=None
        ):
            msg_id = await publisher.publish_mint_complete(record)

        last_id = await publisher.get_message_id()
        assert last_id == msg_id

    @pytest.mark.asyncio
    async def test_fallback_message_ends_up_in_queue(self) -> None:
        from src.gensyn.node_a.publisher import AXL_TOPIC, AxlPublisher

        publisher = AxlPublisher()
        record = DecisionRecord(
            agent_name="mint-helper",
            agent_ens="mint-helper.eth",
            action_type="report",
            input_summary="Queue test",
            ftso_prices=[],
            reasoning="Test",
            action_taken="test",
            result_summary="test",
        )

        with patch.object(
            publisher, "_try_axl_publish", new_callable=AsyncMock, return_value=None
        ):
            await publisher.publish_mint_complete(record)

        messages = await publisher.drain_fallback_queue()
        assert len(messages) == 1
        assert messages[0]["topic"] == AXL_TOPIC


# ---------------------------------------------------------------------------
# Agent module: mint_helper_agent exists and has correct name
# ---------------------------------------------------------------------------
def test_mint_helper_agent_name() -> None:
    from src.agents.mint_helper.agent import mint_helper_agent

    assert mint_helper_agent.name == "mint_helper"


def test_mint_helper_agent_has_all_tools() -> None:
    from src.agents.mint_helper.agent import mint_helper_agent

    # Tools stored as dict (stub) or list (real ADK)
    tools = mint_helper_agent.tools
    if isinstance(tools, dict):
        tool_names = set(tools.keys())
    else:
        tool_names = {t.__name__ for t in tools}

    expected = {
        "check_xrp_balance",
        "get_ftso_price",
        "verify_payment_fdc",
        "estimate_mint_cost",
        "initiate_mint",
    }
    assert expected.issubset(tool_names), f"Missing tools: {expected - tool_names}"
