"""Flare DeFi venue catalog — hardcoded v1 with illustrative APYs.

For v2: replace static APY estimates with live FTSO feed reads (FXRP/USD)
and on-chain liquidity pool data via Web3.

Venues: SparkDEX v2, Kinetic Lending, Cyclo Yield Vault.
All addresses are Coston2 testnet placeholders until live deployment.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static venue catalog (v1)
# APY estimates are illustrative — not live data.
# For live data: read FXRP/USD via FTSO and compute yield in USD terms.
# ---------------------------------------------------------------------------
FLARE_DEFI_VENUES: list[dict[str, Any]] = [
    {
        "id": "sparkdex-v2",
        "name": "SparkDEX v2",
        "type": "dex_lp",
        "pair": "FXRP/FLR",
        "token": "FXRP",
        "apy_estimate": 0.12,
        "risk": "medium",
        "testnet_address": "0x0000000000000000000000000000000000000001",
        "chain": "flare-coston2",
        "description": "Automated market maker LP on SparkDEX — FXRP/FLR pair earns trading fees.",
        "docs_url": "https://docs.sparkdex.io",
    },
    {
        "id": "kinetic-lending",
        "name": "Kinetic Lending",
        "type": "lending",
        "token": "FXRP",
        "pair": None,
        "apy_estimate": 0.08,
        "risk": "low",
        "testnet_address": "0x0000000000000000000000000000000000000002",
        "chain": "flare-coston2",
        "description": "Supply FXRP to Kinetic lending pool — earn variable interest rate.",
        "docs_url": "https://docs.kinetic.market",
    },
    {
        "id": "cyclo-vault",
        "name": "Cyclo Yield Vault",
        "type": "yield_vault",
        "token": "FXRP",
        "pair": None,
        "apy_estimate": 0.15,
        "risk": "medium-high",
        "testnet_address": "0x0000000000000000000000000000000000000003",
        "chain": "flare-coston2",
        "description": "Automated yield optimizer — compounds FXRP rewards across strategies.",
        "docs_url": "https://cyclo.fi/docs",
    },
]

# ---------------------------------------------------------------------------
# Risk tier ordering for filtering
# ---------------------------------------------------------------------------
_RISK_ORDER: dict[str, int] = {
    "low": 0,
    "medium": 1,
    "medium-high": 2,
    "high": 3,
}


class DeFiVenueCatalog:
    """Catalog of supported Flare DeFi yield venues.

    v1: static APY estimates.
    v2 path: inject live FtsoPrice reads for FXRP/USD to estimate real yield.
    """

    def __init__(self, venues: list[dict[str, Any]] | None = None) -> None:
        self._venues = venues if venues is not None else copy.deepcopy(FLARE_DEFI_VENUES)

    async def get_venues(self) -> list[dict[str, Any]]:
        """Return all supported Flare DeFi venues.

        Returns:
            List of venue dicts with id, name, type, apy_estimate, risk, etc.
        """
        logger.debug("DeFiVenueCatalog.get_venues: returning %d venues", len(self._venues))
        return copy.deepcopy(self._venues)

    async def get_venue(self, venue_id: str) -> dict[str, Any] | None:
        """Return a single venue by ID, or None if not found."""
        for v in self._venues:
            if v["id"] == venue_id:
                return copy.deepcopy(v)
        return None

    async def get_yield_quote(
        self,
        venue_id: str,
        token: str,
        amount_usd: float,
    ) -> dict[str, Any]:
        """Return APY estimate and projected annual yield for a given venue.

        Args:
            venue_id: Venue identifier (e.g., 'sparkdex-v2').
            token: Token symbol (e.g., 'FXRP').
            amount_usd: Principal amount in USD.

        Returns:
            dict with venue_id, token, amount_usd, apy_estimate, annual_yield_usd,
            monthly_yield_usd, risk, and a note that APY is illustrative in v1.

        Raises:
            ValueError: If venue_id is not found in catalog.
        """
        venue = await self.get_venue(venue_id)
        if venue is None:
            raise ValueError(f"Unknown venue_id: {venue_id!r}")

        apy = venue["apy_estimate"]
        annual_yield = amount_usd * apy
        monthly_yield = annual_yield / 12.0

        logger.debug(
            "get_yield_quote: venue=%s token=%s amount=%.2f apy=%.2%",
            venue_id,
            token,
            amount_usd,
            apy,
        )

        return {
            "venue_id": venue_id,
            "venue_name": venue["name"],
            "token": token,
            "amount_usd": amount_usd,
            "apy_estimate": apy,
            "annual_yield_usd": round(annual_yield, 4),
            "monthly_yield_usd": round(monthly_yield, 4),
            "risk": venue["risk"],
            "chain": venue["chain"],
            "note": "APY is illustrative (v1 static). Live data requires FTSO FXRP/USD feed.",
            "ftso_required_feed": "0x014658522f555344",  # FXRP/USD feed_id placeholder
        }

    async def get_venues_by_risk(self, max_risk: str) -> list[dict[str, Any]]:
        """Return venues whose risk level does not exceed max_risk.

        Args:
            max_risk: Maximum risk tier: 'low', 'medium', 'medium-high', 'high'.

        Returns:
            Filtered list of venues ordered by APY descending.
        """
        max_tier = _RISK_ORDER.get(max_risk, 999)
        eligible = [
            v for v in self._venues if _RISK_ORDER.get(v["risk"], 999) <= max_tier
        ]
        return sorted(eligible, key=lambda v: v["apy_estimate"], reverse=True)
