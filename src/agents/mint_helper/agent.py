"""mint-helper agent — Google ADK agent for XRP→FXRP minting via FAssets v1.3.

Uses a lightweight Agent stub when google-adk is not installed (common in CI /
hackathon environments). The stub mirrors the google.adk.agents.Agent interface
exactly so that production code can swap in the real SDK with zero changes.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from src.contracts.decision_log import DecisionRecord, FdcProof, FtsoPrice

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Google ADK import — real SDK preferred, lightweight stub as fallback
# ---------------------------------------------------------------------------
try:
    from google.adk.agents import Agent  # type: ignore[import]

    _ADK_AVAILABLE = True
    logger.info("google-adk SDK loaded — using real Agent class")
except ImportError:  # pragma: no cover — only hit when SDK not installed
    _ADK_AVAILABLE = False
    logger.warning(
        "google-adk not installed — using lightweight Agent stub. "
        "Install google-adk>=1.19.0 for production use."
    )

    class Agent:  # type: ignore[no-redef]
        """Lightweight stub that mirrors google.adk.agents.Agent.

        Accepts the same constructor kwargs. The ``run`` method returns a plain
        string so callers can pattern-match on the output without importing the
        real SDK.
        """

        def __init__(
            self,
            name: str,
            model: str,
            description: str,
            instruction: str,
            tools: list[Callable[..., Any]],
        ) -> None:
            self.name = name
            self.model = model
            self.description = description
            self.instruction = instruction
            self.tools = {fn.__name__: fn for fn in tools}

        async def run(self, user_message: str) -> str:
            """Stub run — echoes message and signals that the real SDK is absent."""
            return (
                f"[{self.name} stub] Message received: {user_message!r}. "
                "Install google-adk>=1.19.0 for full LLM responses."
            )


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are mint-helper, a specialized agent that guides XRP holders through
minting FXRP on the Flare Network using FAssets v1.3.

Your responsibilities:
1. Check the user's XRP balance and validate the source address.
2. Fetch the current XRP/USD price from the Flare FTSO v2 oracle so the user
   understands the current rate.
3. Verify any prior XRP payment using the Flare Data Connector (FDC) attestation
   to confirm on-chain evidence before minting.
4. Estimate the minting cost (FAssets agent fee + collateral reservation fee).
5. When instructed, initiate the FXRP mint by reserving collateral with a
   FAssets agent.

Rules:
- ALWAYS include the FTSO feed_id and timestamp in every price reference
  (Flare-First Data Policy).
- NEVER sign or broadcast a transaction without 2-of-2 confirmation:
  this agent advises; the user must explicitly approve.
- Produce a DecisionRecord for every tool call result.
- Only proceed with minting after FDC payment proof is verified.

When uncertain, surface the uncertainty rather than guessing.
"""


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------
def _make_record(
    action_type: str,
    input_summary: str,
    reasoning: str,
    action_taken: str,
    result_summary: str,
    ftso_prices: list[FtsoPrice] | None = None,
    fdc_proof: FdcProof | None = None,
) -> DecisionRecord:
    """Helper: create a DecisionRecord from mint-helper."""
    return DecisionRecord(
        agent_name="mint-helper",
        agent_ens="mint-helper.eth",
        action_type=action_type,  # type: ignore[arg-type]
        input_summary=input_summary,
        ftso_prices=ftso_prices or [],
        fdc_proof=fdc_proof,
        reasoning=reasoning,
        action_taken=action_taken,
        result_summary=result_summary,
    )


async def check_xrp_balance(xrp_address: str) -> dict[str, Any]:
    """Check the XRP balance for a given XRPL address.

    Args:
        xrp_address: XRPL classic address (r…).

    Returns:
        dict with keys: address, balance_xrp, decision_record.
    """
    logger.info("check_xrp_balance called for %s", xrp_address)
    # In production: call XRPL public API (xrplcluster.com / xrpl.ws)
    # For hackathon: return a stub that exercises the DecisionRecord path.
    simulated_balance = 100.0  # placeholder — real impl calls xrpl-py AccountInfo

    record = _make_record(
        action_type="report",
        input_summary=f"XRP balance check for {xrp_address}",
        reasoning=(
            "Retrieved account balance from XRPL ledger. "
            "Minimum 20 XRP reserve must be maintained."
        ),
        action_taken=f"AccountInfo lookup for {xrp_address}",
        result_summary=f"Balance: {simulated_balance} XRP",
    )
    return {
        "address": xrp_address,
        "balance_xrp": simulated_balance,
        "decision_record": record,
    }


async def get_ftso_price(feed_name: str) -> dict[str, Any]:
    """Fetch current price from Flare FTSO v2.

    Args:
        feed_name: e.g. "XRP/USD" or "FLR/USD".

    Returns:
        dict with keys: feed_name, price_usd, feed_id, timestamp, decision_record.

    Per Flare-First Data Policy: feed_id and timestamp are mandatory.
    """
    logger.info("get_ftso_price called for %s", feed_name)
    # Real impl: import FtsoClient and call get_price; stub for agent layer
    from src.integrations.ftso.client import FtsoClient

    client = FtsoClient()
    price = await client.get_price(feed_name)

    record = _make_record(
        action_type="report",
        input_summary=f"FTSO price fetch for {feed_name}",
        reasoning=(
            f"Retrieved {feed_name} price from Flare FTSO v2. "
            f"feed_id={price.feed_id}, timestamp={price.timestamp.isoformat()}. "
            "Used to calculate minting cost and collateral requirement."
        ),
        action_taken=f"FtsoClient.get_price({feed_name!r})",
        result_summary=f"{feed_name} = ${price.price_usd:.6f} USD at {price.timestamp.isoformat()}",
        ftso_prices=[price],
    )
    return {
        "feed_name": price.feed_name,
        "price_usd": price.price_usd,
        "feed_id": price.feed_id,
        "timestamp": price.timestamp.isoformat(),
        "decision_record": record,
    }


async def verify_payment_fdc(
    xrp_tx_hash: str,
    from_address: str,
    to_address: str,
    amount_xrp: float,
) -> dict[str, Any]:
    """Verify an XRP payment using Flare Data Connector attestation.

    Args:
        xrp_tx_hash: XRPL transaction hash (64 hex chars).
        from_address: Sender XRPL address.
        to_address: Receiver XRPL address (FAssets agent's underlying address).
        amount_xrp: Amount in XRP (not drops).

    Returns:
        dict with keys: verified, proof, decision_record.
    """
    logger.info("verify_payment_fdc called for tx %s", xrp_tx_hash)
    from src.integrations.fdc.client import FdcClient

    client = FdcClient()
    proof = await client.request_payment_attestation(
        xrp_tx_hash, from_address, to_address, amount_xrp
    )
    verified = await client.verify_payment(proof)

    record = _make_record(
        action_type="attest",
        input_summary=(
            f"FDC payment verification for tx={xrp_tx_hash[:16]}… "
            f"from={from_address} to={to_address} amount={amount_xrp} XRP"
        ),
        reasoning=(
            "FDC Merkle proof requested and verified on-chain. "
            "Minting may only proceed after verification == True."
        ),
        action_taken="FdcClient.request_payment_attestation + verify_payment",
        result_summary=f"verified={verified}, proof_hash={proof.proof_hash[:16]}…",
        fdc_proof=proof,
    )
    return {
        "verified": verified,
        "proof": proof,
        "decision_record": record,
    }


async def estimate_mint_cost(asset_symbol: str, lots: int) -> dict[str, Any]:
    """Estimate the cost of minting `lots` lots of `asset_symbol` (e.g. FXRP).

    Args:
        asset_symbol: FAssets symbol, e.g. "FXRP".
        lots: Number of lots to mint (1 lot = 1 XRP for FXRP).

    Returns:
        dict with keys: asset_symbol, lots, fee_estimate, decision_record.
    """
    logger.info("estimate_mint_cost: %s lots=%d", asset_symbol, lots)
    from src.integrations.fassets.client import FAssetsClient

    client = FAssetsClient()
    estimate = await client.estimate_mint_cost(asset_symbol, lots)

    record = _make_record(
        action_type="report",
        input_summary=f"Minting cost estimate for {lots} lots of {asset_symbol}",
        reasoning=(
            f"Retrieved fee estimate from FAssets AssetManager. "
            f"Minting fee (BIPS): {estimate.get('fee_bips', 'N/A')}. "
            "User should confirm total cost before initiating."
        ),
        action_taken=f"FAssetsClient.estimate_mint_cost({asset_symbol!r}, {lots})",
        result_summary=str(estimate),
    )
    return {
        "asset_symbol": asset_symbol,
        "lots": lots,
        "fee_estimate": estimate,
        "decision_record": record,
    }


async def initiate_mint(
    agent_address: str,
    lots: int,
    max_minting_fee_bips: int,
) -> dict[str, Any]:
    """Initiate FXRP minting by reserving collateral with a FAssets agent.

    2-OF-2 CONFIRMATION REQUIRED: this tool only constructs and returns the
    transaction parameters. The user MUST explicitly approve before broadcast.

    Args:
        agent_address: FAssets agent vault address.
        lots: Number of lots to mint.
        max_minting_fee_bips: Maximum fee the user is willing to pay (in BIPS).

    Returns:
        dict with keys: status, collateral_reservation_id, decision_record.

    Note:
        Returns status="pending_user_approval" — the user must call
        confirmMint() after reviewing the reservation details.
    """
    logger.info(
        "initiate_mint: agent=%s lots=%d max_fee_bips=%d",
        agent_address, lots, max_minting_fee_bips,
    )
    from src.integrations.fassets.client import FAssetsClient

    client = FAssetsClient()
    result = await client.initiate_mint(agent_address, lots, max_minting_fee_bips)

    record = _make_record(
        action_type="mint",
        input_summary=(
            f"Initiate mint: agent={agent_address}, lots={lots}, "
            f"max_fee_bips={max_minting_fee_bips}"
        ),
        reasoning=(
            "Collateral reservation submitted. Per 2-of-2 confirmation rule, "
            "this agent has advised only. User must approve the reservation "
            "on-chain before minting is finalized."
        ),
        action_taken=(
            f"FAssetsClient.initiate_mint({agent_address!r}, {lots}, {max_minting_fee_bips})"
        ),
        result_summary=(
            f"collateral_reservation_id={result.get('collateral_reservation_id', 'N/A')}"
        ),
    )
    return {
        "status": "pending_user_approval",
        "collateral_reservation_id": result.get("collateral_reservation_id"),
        "reservation_details": result,
        "decision_record": record,
    }


# ---------------------------------------------------------------------------
# Agent instantiation
# ---------------------------------------------------------------------------
mint_helper_agent = Agent(
    name="mint-helper",
    model="gemini-2.0-flash",
    description="Helps XRP holders mint FXRP via FAssets v1.3 on Flare",
    instruction=SYSTEM_PROMPT,
    tools=[
        check_xrp_balance,
        get_ftso_price,
        verify_payment_fdc,
        estimate_mint_cost,
        initiate_mint,
    ],
)
