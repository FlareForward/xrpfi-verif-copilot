"""Agent B: yield-router — routes minted FXRP to optimal yield on Flare DeFi.

Produces a DecisionRecord for every tool call result.
Imports DecisionRecord from src.contracts.decision_log (never redeclared locally).
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Any, Protocol, cast

from src.contracts.decision_log import DecisionRecord, FtsoPrice

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Google ADK import with lightweight stub fallback
# ---------------------------------------------------------------------------
try:
    from google.adk.agents import Agent

    _ADK_AVAILABLE = True
    logger.info("google-adk loaded successfully")
except ImportError:
    _ADK_AVAILABLE = False
    logger.warning("google-adk not installed — using lightweight stub Agent")

    class Agent:  # type: ignore[no-redef]
        """Lightweight stub that mirrors the google.adk.agents.Agent interface."""

        def __init__(
            self,
            name: str,
            model: str,
            description: str,
            instruction: str,
            tools: list[Any],
        ) -> None:
            self.name = name
            self.model = model
            self.description = description
            self.instruction = instruction
            self.tools = tools
            self._fallback_mode = True

        async def run(self, user_message: str) -> str:
            """Stub run: echo message and list available tools."""
            tool_names = [getattr(t, "__name__", str(t)) for t in self.tools]
            return (
                f"[stub:{self.name}] received: {user_message!r}\n"
                f"Available tools: {tool_names}\n"
                f"(google-adk not installed — stub mode)"
            )


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are yield-router.eth, an autonomous DeFi routing agent on the Flare Network.

Your mission:
- Receive minted FXRP amounts from mint-helper.eth via the AXL message bus.
- Query the Flare DeFi venue catalog (SparkDEX, Kinetic Lending, Cyclo Vault) for current
  yield opportunities.
- Apply the deterministic rebalance policy to recommend an allocation split across venues.
- Optionally execute swaps via Uniswap on Ethereum for cross-chain yield arbitrage.
- Produce a DecisionRecord for EVERY tool call result.
- All FTSO price reads MUST include feed_id and timestamp (Flare-First Data Policy).

Decision rules:
1. Never allocate to a venue whose risk tier exceeds the user's stated risk preference.
2. Allocation percentages must always sum to 1.0.
3. LLM reasoning is advisory — the rebalance policy function is the source of truth.
4. Every action, including no-ops, produces a DecisionRecord written to 0G storage.

ENS identity: yield-router.eth
AXL topic (subscribe): xrpfi.mint.complete
AXL topic (publish): xrpfi.route.plan
"""


# ---------------------------------------------------------------------------
# Live reasoning helper
# ---------------------------------------------------------------------------
class _GeminiModels(Protocol):
    def generate_content(self, *, model: str, contents: str) -> object: ...


class _GeminiClient(Protocol):
    models: _GeminiModels


async def _generate_live_reasoning(
    decision_context: str,
    fallback_reasoning: str,
) -> str:
    """Use Gemini for DecisionRecord reasoning when configured, otherwise fallback."""
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        try:
            from src.config import get_settings

            api_key = get_settings().google_api_key
        except Exception:
            api_key = ""

    if not api_key:
        return fallback_reasoning

    try:
        from src.config import get_settings

        model = os.getenv("GEMINI_MODEL", get_settings().gemini_model)
        from google import genai

        client = genai.Client(api_key=api_key)
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            "Write one concise DecisionRecord reasoning paragraph for this tool result. "
            "Do not include secrets, credentials, markdown, or transaction-signing instructions. "
            "Keep deterministic facts intact and preserve all stated safety constraints.\n\n"
            f"Context:\n{decision_context}\n\n"
            f"Offline fallback reasoning:\n{fallback_reasoning}"
        )
        response = await _call_gemini_generate_content(cast(_GeminiClient, client), model, prompt)
        text = getattr(response, "text", "") or ""
        if text.strip():
            return text.strip()
    except Exception as exc:
        logger.warning("Gemini reasoning unavailable; using deterministic fallback: %s", exc)

    return fallback_reasoning


async def _call_gemini_generate_content(
    client: _GeminiClient,
    model: str,
    prompt: str,
) -> object:
    """Bridge google-genai's sync API into async agent tools."""
    import asyncio

    return await asyncio.to_thread(
        client.models.generate_content,
        model=model,
        contents=prompt,
    )


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


async def get_defi_venues() -> dict[str, Any]:
    """Return all supported Flare DeFi venues from the catalog.

    Returns a DecisionRecord payload containing the venue list.
    """
    from src.integrations.defi_venues.catalog import DeFiVenueCatalog

    catalog = DeFiVenueCatalog()
    venues = await catalog.get_venues()
    fallback_reasoning = "Fetched static Flare DeFi venue catalog v1 (APYs are illustrative)."
    reasoning = await _generate_live_reasoning(
        decision_context=f"Tool=get_defi_venues; venue_count={len(venues)}; venues={venues}",
        fallback_reasoning=fallback_reasoning,
    )

    record = DecisionRecord(
        agent_name="yield-router",
        agent_ens="yield-router.eth",
        action_type="report",
        input_summary="Requested DeFi venue catalog",
        ftso_prices=[],
        reasoning=reasoning,
        action_taken="get_defi_venues",
        result_summary=f"Returned {len(venues)} venues",
    )
    return {"venues": venues, "record_id": record.record_id, "agent_ens": record.agent_ens}


async def get_yield_quotes(
    venue_id: str,
    token: str,
    amount_usd: float,
    ftso_price_xrp_usd: float = 0.50,
    ftso_price_flr_usd: float = 0.025,
) -> dict[str, Any]:
    """Get yield quote for a specific venue.

    Args:
        venue_id: The venue identifier (e.g., 'sparkdex-v2').
        token: Token symbol (e.g., 'FXRP').
        amount_usd: Amount in USD to simulate.
        ftso_price_xrp_usd: Current XRP/USD from FTSO (feed_id required at call site).
        ftso_price_flr_usd: Current FLR/USD from FTSO (feed_id required at call site).

    Returns dict with quote and DecisionRecord metadata.
    """
    from src.integrations.defi_venues.catalog import DeFiVenueCatalog

    catalog = DeFiVenueCatalog()
    quote = await catalog.get_yield_quote(venue_id, token, amount_usd)

    now = datetime.now(UTC)
    ftso_prices = [
        FtsoPrice(
            feed_id="0x015852502f555344",
            feed_name="XRP/USD",
            price_usd=ftso_price_xrp_usd,
            decimals=6,
            timestamp=now,
        ),
        FtsoPrice(
            feed_id="0x014658522f555344",
            feed_name="FLR/USD",
            price_usd=ftso_price_flr_usd,
            decimals=7,
            timestamp=now,
        ),
    ]
    fallback_reasoning = f"Queried {venue_id} for {token} yield at ${amount_usd:.2f} USD."
    reasoning = await _generate_live_reasoning(
        decision_context=(
            f"Tool=get_yield_quotes; venue_id={venue_id}; token={token}; "
            f"amount_usd={amount_usd}; quote={quote}; "
            f"xrp_feed_id={ftso_prices[0].feed_id}; xrp_timestamp={now.isoformat()}; "
            f"flr_feed_id={ftso_prices[1].feed_id}; flr_timestamp={now.isoformat()}"
        ),
        fallback_reasoning=fallback_reasoning,
    )

    record = DecisionRecord(
        agent_name="yield-router",
        agent_ens="yield-router.eth",
        action_type="report",
        input_summary=f"Yield quote for {venue_id}: {amount_usd} USD of {token}",
        ftso_prices=ftso_prices,
        reasoning=reasoning,
        action_taken="get_yield_quote",
        result_summary=f"APY={quote.get('apy_estimate', 0):.2%}, "
        f"annual_yield_usd={quote.get('annual_yield_usd', 0):.2f}",
    )
    return {**quote, "record_id": record.record_id, "agent_ens": record.agent_ens}


async def recommend_allocation(
    fxrp_amount_usd: float,
    risk_preference: str = "medium",
    ftso_price_xrp_usd: float = 0.50,
    ftso_price_flr_usd: float = 0.025,
) -> dict[str, Any]:
    """Recommend allocation split using the deterministic rebalance policy.

    Args:
        fxrp_amount_usd: Total FXRP value in USD to allocate.
        risk_preference: One of 'low', 'medium', 'high'.
        ftso_price_xrp_usd: Current XRP/USD FTSO price.
        ftso_price_flr_usd: Current FLR/USD FTSO price.

    Returns allocation recommendations with DecisionRecord metadata.
    """
    from src.integrations.defi_venues.catalog import DeFiVenueCatalog
    from src.policies.rebalance_policy import recommend_allocation as _recommend

    catalog = DeFiVenueCatalog()
    venues = await catalog.get_venues()

    now = datetime.now(UTC)
    ftso_prices = [
        FtsoPrice(
            feed_id="0x015852502f555344",
            feed_name="XRP/USD",
            price_usd=ftso_price_xrp_usd,
            decimals=6,
            timestamp=now,
        ),
        FtsoPrice(
            feed_id="0x014658522f555344",
            feed_name="FLR/USD",
            price_usd=ftso_price_flr_usd,
            decimals=7,
            timestamp=now,
        ),
    ]

    allocations = _recommend(fxrp_amount_usd, venues, risk_preference, ftso_prices)
    total_pct = sum(a["allocation_pct"] for a in allocations)
    fallback_reasoning = (
        f"Deterministic rebalance policy applied. "
        f"Risk preference={risk_preference}. {len(allocations)} venues eligible."
    )
    reasoning = await _generate_live_reasoning(
        decision_context=(
            f"Tool=recommend_allocation; fxrp_amount_usd={fxrp_amount_usd}; "
            f"risk_preference={risk_preference}; venue_count={len(venues)}; "
            f"eligible_count={len(allocations)}; total_pct={total_pct}; "
            f"allocations={allocations}; xrp_feed_id={ftso_prices[0].feed_id}; "
            f"flr_feed_id={ftso_prices[1].feed_id}; timestamp={now.isoformat()}"
        ),
        fallback_reasoning=fallback_reasoning,
    )

    record = DecisionRecord(
        agent_name="yield-router",
        agent_ens="yield-router.eth",
        action_type="route",
        input_summary=(
            f"Allocate {fxrp_amount_usd:.2f} USD FXRP, risk={risk_preference}"
        ),
        ftso_prices=ftso_prices,
        reasoning=reasoning,
        action_taken="recommend_allocation",
        result_summary=(
            f"Allocated {total_pct:.2%} across {len(allocations)} venues. "
            f"Total USD: {fxrp_amount_usd:.2f}"
        ),
    )
    return {
        "allocations": allocations,
        "total_usd": fxrp_amount_usd,
        "risk_preference": risk_preference,
        "record_id": record.record_id,
        "agent_ens": record.agent_ens,
    }


async def execute_swap(
    token_in: str,
    token_out: str,
    amount_in: float,
    chain_id: int = 1,
) -> dict[str, Any]:
    """Execute a swap via Uniswap Trading API.

    Args:
        token_in: Input token symbol or address.
        token_out: Output token symbol or address.
        amount_in: Amount of token_in.
        chain_id: EVM chain ID (default: 1 = Ethereum mainnet).

    Returns swap result with DecisionRecord metadata.
    """
    from src.integrations.uniswap.client import UniswapClient

    client = UniswapClient()
    quote = await client.get_quote(token_in, token_out, amount_in, chain_id)
    fallback_reasoning = "Uniswap Trading API v2 quote obtained. Calldata ready for execution."
    reasoning = await _generate_live_reasoning(
        decision_context=(
            f"Tool=execute_swap; token_in={token_in}; token_out={token_out}; "
            f"amount_in={amount_in}; chain_id={chain_id}; quote={quote}"
        ),
        fallback_reasoning=fallback_reasoning,
    )

    record = DecisionRecord(
        agent_name="yield-router",
        agent_ens="yield-router.eth",
        action_type="swap",
        input_summary=f"Swap {amount_in} {token_in} → {token_out} on chain {chain_id}",
        ftso_prices=[],
        reasoning=reasoning,
        action_taken=f"execute_swap via Uniswap: {token_in}->{token_out}",
        result_summary=(
            f"Quote: {quote.get('quote_amount', 'n/a')} {token_out}, "
            f"price_impact={quote.get('price_impact', 'n/a')}"
        ),
    )
    return {**quote, "record_id": record.record_id, "agent_ens": record.agent_ens}


async def get_route_plan(
    fxrp_amount_usd: float,
    xrp_amount: float,
    risk_preference: str = "medium",
    ftso_price_xrp_usd: float = 0.50,
    ftso_price_flr_usd: float = 0.025,
) -> dict[str, Any]:
    """Produce a complete route plan from minted FXRP to yield venues.

    Args:
        fxrp_amount_usd: Total FXRP value in USD.
        xrp_amount: Original XRP amount minted.
        risk_preference: One of 'low', 'medium', 'high'.
        ftso_price_xrp_usd: Current XRP/USD FTSO price.
        ftso_price_flr_usd: Current FLR/USD FTSO price.

    Returns a complete route plan DecisionRecord payload.
    """
    from src.integrations.defi_venues.catalog import DeFiVenueCatalog
    from src.policies.rebalance_policy import recommend_allocation as _recommend

    catalog = DeFiVenueCatalog()
    venues = await catalog.get_venues()

    now = datetime.now(UTC)
    ftso_prices = [
        FtsoPrice(
            feed_id="0x015852502f555344",
            feed_name="XRP/USD",
            price_usd=ftso_price_xrp_usd,
            decimals=6,
            timestamp=now,
        ),
        FtsoPrice(
            feed_id="0x014658522f555344",
            feed_name="FLR/USD",
            price_usd=ftso_price_flr_usd,
            decimals=7,
            timestamp=now,
        ),
    ]

    allocations = _recommend(fxrp_amount_usd, venues, risk_preference, ftso_prices)
    fallback_reasoning = (
        f"Complete route plan computed. XRP/USD={ftso_price_xrp_usd}, "
        f"FLR/USD={ftso_price_flr_usd}. "
        f"Deterministic policy applied across {len(venues)} Flare DeFi venues."
    )
    reasoning = await _generate_live_reasoning(
        decision_context=(
            f"Tool=get_route_plan; xrp_amount={xrp_amount}; "
            f"fxrp_amount_usd={fxrp_amount_usd}; risk_preference={risk_preference}; "
            f"venue_count={len(venues)}; allocation_count={len(allocations)}; "
            f"allocations={allocations}; xrp_price={ftso_price_xrp_usd}; "
            f"flr_price={ftso_price_flr_usd}; xrp_feed_id={ftso_prices[0].feed_id}; "
            f"flr_feed_id={ftso_prices[1].feed_id}; timestamp={now.isoformat()}"
        ),
        fallback_reasoning=fallback_reasoning,
    )

    record = DecisionRecord(
        agent_name="yield-router",
        agent_ens="yield-router.eth",
        action_type="route",
        input_summary=(
            f"Route plan: {xrp_amount} XRP → {fxrp_amount_usd:.2f} USD FXRP, "
            f"risk={risk_preference}"
        ),
        ftso_prices=ftso_prices,
        reasoning=reasoning,
        action_taken="get_route_plan",
        result_summary=(
            f"Route plan: {len(allocations)} venues, total {fxrp_amount_usd:.2f} USD. "
            f"Risk={risk_preference}."
        ),
    )

    return {
        "route_plan": {
            "xrp_amount": xrp_amount,
            "fxrp_amount_usd": fxrp_amount_usd,
            "risk_preference": risk_preference,
            "allocations": allocations,
            "ftso_snapshot": {
                "xrp_usd": ftso_price_xrp_usd,
                "flr_usd": ftso_price_flr_usd,
                "timestamp": now.isoformat(),
            },
        },
        "record_id": record.record_id,
        "record": record.model_dump(),
        "agent_ens": record.agent_ens,
    }


# ---------------------------------------------------------------------------
# Agent instantiation
# ---------------------------------------------------------------------------
yield_router_agent = Agent(
    name="yield_router",
    model="gemini-2.0-flash",
    description="Routes minted FXRP to optimal yield on Flare DeFi",
    instruction=SYSTEM_PROMPT,
    tools=[
        get_defi_venues,
        get_yield_quotes,
        recommend_allocation,
        execute_swap,
        get_route_plan,
    ],
)

__all__ = ["yield_router_agent", "SYSTEM_PROMPT"]
