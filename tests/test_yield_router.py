"""Tests for the yield-router agent and DeFi venue catalog.

Covers:
- Agent instantiation and DecisionRecord import source
- DeFiVenueCatalog get_venues and get_yield_quote
- ENS resolver_b basic interface
- AXL subscriber/publisher in fallback mode
- DecisionRecord produced by yield-router imports from src.contracts.decision_log
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from src.contracts.decision_log import DecisionRecord, FtsoPrice

# ---------------------------------------------------------------------------
# DecisionRecord import invariant
# ---------------------------------------------------------------------------


class TestDecisionRecordImport:
    def test_decision_record_imported_from_contracts(self) -> None:
        """Pin: DecisionRecord must come from src.contracts.decision_log, not redeclared locally."""
        import src.contracts.decision_log as module
        assert hasattr(module, "DecisionRecord")
        assert DecisionRecord is module.DecisionRecord

    def test_yield_router_agent_uses_contracts_module(self) -> None:
        """The agent module imports DecisionRecord from the contract module."""
        import src.agents.yield_router.agent as agent_module
        import src.contracts.decision_log as contracts_module

        # Ensure the agent module references the same DecisionRecord class
        assert agent_module.DecisionRecord is contracts_module.DecisionRecord  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Agent shell
# ---------------------------------------------------------------------------


class TestYieldRouterAgent:
    def test_agent_instantiated(self) -> None:
        from src.agents.yield_router.agent import yield_router_agent
        assert yield_router_agent is not None
        assert yield_router_agent.name == "yield_router"

    def test_agent_has_correct_model(self) -> None:
        from src.agents.yield_router.agent import yield_router_agent
        assert yield_router_agent.model == "gemini-2.0-flash"

    def test_agent_has_five_tools(self) -> None:
        from src.agents.yield_router.agent import yield_router_agent
        assert len(yield_router_agent.tools) == 5

    def test_agent_tool_names(self) -> None:
        from src.agents.yield_router.agent import yield_router_agent
        names = {t.__name__ for t in yield_router_agent.tools}
        expected = {
            "get_defi_venues",
            "get_yield_quotes",
            "recommend_allocation",
            "execute_swap",
            "get_route_plan",
        }
        assert names == expected

    def test_system_prompt_mentions_yield_router_eth(self) -> None:
        from src.agents.yield_router.agent import SYSTEM_PROMPT
        assert "yield-router.eth" in SYSTEM_PROMPT

    def test_system_prompt_mentions_flare_first_data_policy(self) -> None:
        from src.agents.yield_router.agent import SYSTEM_PROMPT
        assert "feed_id" in SYSTEM_PROMPT or "FTSO" in SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# DeFi venue catalog
# ---------------------------------------------------------------------------


class TestDeFiVenueCatalog:
    @pytest.mark.asyncio
    async def test_get_venues_returns_list(self) -> None:
        from src.integrations.defi_venues.catalog import DeFiVenueCatalog
        catalog = DeFiVenueCatalog()
        venues = await catalog.get_venues()
        assert isinstance(venues, list)
        assert len(venues) >= 3

    @pytest.mark.asyncio
    async def test_get_venues_have_required_keys(self) -> None:
        from src.integrations.defi_venues.catalog import DeFiVenueCatalog
        catalog = DeFiVenueCatalog()
        venues = await catalog.get_venues()
        required = {"id", "name", "type", "apy_estimate", "risk"}
        for v in venues:
            missing = required - set(v.keys())
            assert not missing, f"venue {v.get('id')} missing keys: {missing}"

    @pytest.mark.asyncio
    async def test_sparkdex_in_catalog(self) -> None:
        from src.integrations.defi_venues.catalog import DeFiVenueCatalog
        catalog = DeFiVenueCatalog()
        venues = await catalog.get_venues()
        ids = {v["id"] for v in venues}
        assert "sparkdex-v2" in ids

    @pytest.mark.asyncio
    async def test_kinetic_in_catalog(self) -> None:
        from src.integrations.defi_venues.catalog import DeFiVenueCatalog
        catalog = DeFiVenueCatalog()
        venues = await catalog.get_venues()
        ids = {v["id"] for v in venues}
        assert "kinetic-lending" in ids

    @pytest.mark.asyncio
    async def test_cyclo_in_catalog(self) -> None:
        from src.integrations.defi_venues.catalog import DeFiVenueCatalog
        catalog = DeFiVenueCatalog()
        venues = await catalog.get_venues()
        ids = {v["id"] for v in venues}
        assert "cyclo-vault" in ids

    @pytest.mark.asyncio
    async def test_get_yield_quote_sparkdex(self) -> None:
        from src.integrations.defi_venues.catalog import DeFiVenueCatalog
        catalog = DeFiVenueCatalog()
        quote = await catalog.get_yield_quote("sparkdex-v2", "FXRP", 1000.0)
        assert quote["venue_id"] == "sparkdex-v2"
        assert quote["apy_estimate"] == pytest.approx(0.12)
        assert quote["annual_yield_usd"] == pytest.approx(120.0, rel=1e-4)
        assert "monthly_yield_usd" in quote

    @pytest.mark.asyncio
    async def test_get_yield_quote_kinetic(self) -> None:
        from src.integrations.defi_venues.catalog import DeFiVenueCatalog
        catalog = DeFiVenueCatalog()
        quote = await catalog.get_yield_quote("kinetic-lending", "FXRP", 500.0)
        assert quote["apy_estimate"] == pytest.approx(0.08)
        assert quote["annual_yield_usd"] == pytest.approx(40.0, rel=1e-4)

    @pytest.mark.asyncio
    async def test_get_yield_quote_unknown_venue_raises(self) -> None:
        from src.integrations.defi_venues.catalog import DeFiVenueCatalog
        catalog = DeFiVenueCatalog()
        with pytest.raises(ValueError, match="Unknown venue_id"):
            await catalog.get_yield_quote("nonexistent-venue", "FXRP", 100.0)

    @pytest.mark.asyncio
    async def test_get_venues_by_risk_low(self) -> None:
        from src.integrations.defi_venues.catalog import DeFiVenueCatalog
        catalog = DeFiVenueCatalog()
        venues = await catalog.get_venues_by_risk("low")
        for v in venues:
            assert v["risk"] == "low"

    @pytest.mark.asyncio
    async def test_get_venues_by_risk_medium(self) -> None:
        from src.integrations.defi_venues.catalog import DeFiVenueCatalog
        catalog = DeFiVenueCatalog()
        venues = await catalog.get_venues_by_risk("medium")
        allowed = {"low", "medium"}
        for v in venues:
            assert v["risk"] in allowed

    @pytest.mark.asyncio
    async def test_get_venues_returns_copy(self) -> None:
        """Mutations to returned list must not affect the catalog."""
        from src.integrations.defi_venues.catalog import DeFiVenueCatalog
        catalog = DeFiVenueCatalog()
        v1 = await catalog.get_venues()
        v1[0]["apy_estimate"] = 999.0
        v2 = await catalog.get_venues()
        assert v2[0]["apy_estimate"] != 999.0


# ---------------------------------------------------------------------------
# AXL node B: subscriber + publisher in fallback mode
# ---------------------------------------------------------------------------


class TestAxlFallback:
    @pytest.mark.asyncio
    async def test_publisher_returns_fallback_message_id(self) -> None:
        from src.gensyn.node_b.publisher import AxlPublisher
        pub = AxlPublisher(force_fallback=True)
        record = _make_route_record()
        msg_id = await pub.publish_route_plan(record)
        assert msg_id.startswith("fallback-"), f"Expected fallback- prefix, got: {msg_id}"

    @pytest.mark.asyncio
    async def test_publisher_message_id_increments(self) -> None:
        from src.gensyn.node_b.publisher import AxlPublisher
        pub = AxlPublisher(force_fallback=True)
        record = _make_route_record()
        id1 = await pub.publish_route_plan(record)
        id2 = await pub.publish_route_plan(record)
        assert id1 != id2

    @pytest.mark.asyncio
    async def test_subscriber_receives_from_publisher(self) -> None:
        """Cross-node: publisher pushes to queue; subscriber reads it."""
        from src.config import get_settings
        from src.gensyn.node_b.publisher import AxlPublisher
        from src.gensyn.node_b.subscriber import get_fallback_queue

        settings = get_settings()
        topic = settings.axl_topic_route_plan

        # Clear the queue first
        queue = get_fallback_queue(topic)
        while not queue.empty():
            queue.get_nowait()

        pub = AxlPublisher(force_fallback=True)
        record = _make_route_record()
        await pub.publish_route_plan(record)

        # Verify it's in the queue
        assert not queue.empty()
        msg = await queue.get()
        assert msg["topic"] == topic
        assert msg["payload"]["agent_name"] == "yield-router"

    @pytest.mark.asyncio
    async def test_subscriber_calls_handler(self) -> None:
        """Subscriber delivers a DecisionRecord to the handler."""
        from src.config import get_settings
        from src.gensyn.node_b.subscriber import AxlSubscriber, get_fallback_queue

        settings = get_settings()
        topic = settings.axl_topic_mint_complete

        queue = get_fallback_queue(topic)
        record = _make_mint_record()
        await queue.put({"topic": topic, "payload": record.model_dump(mode="json")})

        received: list[DecisionRecord] = []

        async def handler(r: DecisionRecord) -> None:
            received.append(r)

        sub = AxlSubscriber(force_fallback=True)

        # Run subscriber for a brief window
        async def run_sub() -> None:
            await sub.subscribe_mint_complete(handler)

        task = asyncio.create_task(run_sub())
        await asyncio.sleep(0.2)
        sub.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert len(received) >= 1
        assert received[0].agent_name == "mint-helper"
        assert received[0].action_type == "mint"

    def test_fallback_mode_flag_is_set(self) -> None:
        from src.gensyn.node_b.publisher import AxlPublisher
        pub = AxlPublisher(force_fallback=True)
        assert pub.fallback_mode is True

    def test_subscriber_fallback_mode_flag(self) -> None:
        from src.gensyn.node_b.subscriber import AxlSubscriber
        sub = AxlSubscriber(force_fallback=True)
        assert sub.fallback_mode is True


# ---------------------------------------------------------------------------
# ENS resolver_b
# ---------------------------------------------------------------------------


class TestEnsResolverB:
    def test_ens_name_constant(self) -> None:
        from src.integrations.ens.resolver_b import ENS_NAME
        assert ENS_NAME == "yield-router.eth"

    def test_resolver_instantiates(self) -> None:
        from src.integrations.ens.resolver_b import YieldRouterEnsResolver
        r = YieldRouterEnsResolver()
        assert r is not None

    def test_get_registration_info_has_ens_name(self) -> None:
        from src.integrations.ens.resolver_b import YieldRouterEnsResolver
        r = YieldRouterEnsResolver()
        info = r.get_registration_info()
        assert info["ens_name"] == "yield-router.eth"

    def test_get_registration_info_has_text_records(self) -> None:
        from src.integrations.ens.resolver_b import YieldRouterEnsResolver
        r = YieldRouterEnsResolver()
        info = r.get_registration_info()
        assert "text_records" in info
        assert info["text_records"]["agent_type"] == "yield-router"

    @pytest.mark.asyncio
    async def test_resolve_falls_back_to_address(self) -> None:
        """When ENS is unreachable, resolve() returns the fallback address."""
        from src.integrations.ens.resolver_b import FALLBACK_ADDRESS, YieldRouterEnsResolver
        # Use an invalid RPC URL to force fallback
        r = YieldRouterEnsResolver(rpc_url="http://localhost:1")
        addr = await r.resolve()
        assert addr == FALLBACK_ADDRESS
        assert r.is_fallback is True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_route_record() -> DecisionRecord:
    return DecisionRecord(
        agent_name="yield-router",
        agent_ens="yield-router.eth",
        action_type="route",
        input_summary="Route 500 FXRP USD, risk=medium",
        ftso_prices=[
            FtsoPrice(
                feed_id="0x015852502f555344",
                feed_name="XRP/USD",
                price_usd=0.50,
                decimals=6,
                timestamp=datetime.now(UTC),
            )
        ],
        reasoning="Deterministic policy applied.",
        action_taken="recommend_allocation",
        result_summary="Allocated across 2 venues.",
    )


def _make_mint_record() -> DecisionRecord:
    return DecisionRecord(
        agent_name="mint-helper",
        agent_ens="mint-helper.eth",
        action_type="mint",
        input_summary="Mint 100 XRP → FXRP",
        ftso_prices=[
            FtsoPrice(
                feed_id="0x015852502f555344",
                feed_name="XRP/USD",
                price_usd=0.50,
                decimals=6,
                timestamp=datetime.now(UTC),
            )
        ],
        reasoning="FAssets mint initiated.",
        action_taken="Initiated FAssets mint",
        result_summary="Mint complete. FXRP received.",
    )
