"""Deterministic rebalance policy for FXRP yield allocation.

This is a PURE FUNCTION — no randomness, no LLM calls, no side effects.
Same inputs ALWAYS produce the same outputs (regression-pinned in tests).

LLM reasoning in the agent is ADVISORY only; this function is the source of truth
for all allocation decisions.

Risk tier ordering:
  low < medium < medium-high < high
"""

from __future__ import annotations

import math
from typing import Any

from src.contracts.decision_log import FtsoPrice

# ---------------------------------------------------------------------------
# Risk tier ordering
# ---------------------------------------------------------------------------
_RISK_ORDER: dict[str, int] = {
    "low": 0,
    "medium": 1,
    "medium-high": 2,
    "high": 3,
}

# ---------------------------------------------------------------------------
# Allocation strategy parameters per risk preference
# These are deterministic constants — do not introduce randomness.
# ---------------------------------------------------------------------------
_STRATEGY: dict[str, dict[str, Any]] = {
    "low": {
        # Prefer lowest-risk venues; only allocate to risk <= "low"
        "max_risk": "low",
        "diversify": False,       # concentrate in safest venue
        "top_n": 1,
    },
    "medium": {
        # Allocate to risk <= "medium"; diversify across eligible venues
        "max_risk": "medium",
        "diversify": True,
        "top_n": 3,
    },
    "high": {
        # Allocate to all venues; weight by APY
        "max_risk": "high",
        "diversify": True,
        "top_n": 10,  # effectively "all"
    },
}


def recommend_allocation(
    fxrp_amount_usd: float,
    venues: list[dict[str, Any]],
    risk_preference: str,
    ftso_prices: list[FtsoPrice],
) -> list[dict[str, Any]]:
    """Recommend allocation split across Flare DeFi venues.

    Pure function: deterministic given same inputs. No randomness, no LLM calls.
    Total allocation_pct ALWAYS sums to 1.0.
    Never allocates to a venue with risk tier > risk_preference.

    FTSO prices are accepted for future live-APY computation (v2). In v1 they are
    validated (must be a list) but APY remains from the static catalog.
    Per Flare-First Data Policy: feed_id + timestamp are required on each FtsoPrice.

    Args:
        fxrp_amount_usd: Total FXRP principal in USD to allocate.
        venues: List of venue dicts from DeFiVenueCatalog.get_venues().
        risk_preference: One of 'low', 'medium', 'high'.
        ftso_prices: FTSO price readings at decision time (feed_id + timestamp required).

    Returns:
        List of allocation dicts: [{"venue_id": str, "allocation_pct": float,
        "amount_usd": float, "expected_apy": float}]
        Total allocation_pct sums to 1.0.

    Raises:
        ValueError: If risk_preference is not one of 'low', 'medium', 'high'.
        ValueError: If no eligible venues match the risk preference.
    """
    # Validate risk preference
    if risk_preference not in _STRATEGY:
        raise ValueError(
            f"Invalid risk_preference {risk_preference!r}. "
            f"Must be one of: {list(_STRATEGY.keys())}"
        )

    # Validate FTSO prices (must be a list; individual items validated by type)
    if not isinstance(ftso_prices, list):
        raise TypeError("ftso_prices must be a list of FtsoPrice instances")

    strategy = _STRATEGY[risk_preference]
    max_risk = strategy["max_risk"]
    max_tier = _RISK_ORDER[max_risk]
    top_n: int = strategy["top_n"]
    diversify: bool = strategy["diversify"]

    # Filter venues by risk tier
    eligible = [
        v for v in venues
        if _RISK_ORDER.get(v.get("risk", "high"), 999) <= max_tier
    ]

    if not eligible:
        raise ValueError(
            f"No venues eligible for risk_preference={risk_preference!r}. "
            f"All venues exceed max_risk={max_risk!r}."
        )

    # Sort deterministically: primary=APY descending, secondary=id ascending
    # Secondary sort on id ensures determinism when APYs are equal.
    eligible_sorted = sorted(
        eligible,
        key=lambda v: (-v.get("apy_estimate", 0.0), v.get("id", "")),
    )

    # Take top_n
    selected = eligible_sorted[:top_n]

    # Compute weights
    if not diversify or len(selected) == 1:
        # Concentrate 100% in top venue
        weights = [1.0] + [0.0] * (len(selected) - 1)
    else:
        # Weight proportional to APY (APY-weighted allocation)
        apy_values = [v.get("apy_estimate", 0.0) for v in selected]
        total_apy = sum(apy_values)

        if total_apy <= 0.0:
            # Uniform distribution as fallback (deterministic)
            n = len(selected)
            weights = [1.0 / n] * n
        else:
            weights = [a / total_apy for a in apy_values]

    # Normalize weights to exactly sum to 1.0 (floating point safety)
    total_weight = sum(weights)
    if total_weight > 0:
        weights = [w / total_weight for w in weights]

    # Build allocation list
    allocations: list[dict[str, Any]] = []
    remaining_usd = fxrp_amount_usd
    remaining_pct = 1.0

    for i, venue in enumerate(selected):
        is_last = i == len(selected) - 1

        if is_last:
            # Last allocation absorbs rounding residual
            pct = remaining_pct
            amount = remaining_usd
        else:
            pct = _round6(weights[i])
            amount = _round4(fxrp_amount_usd * pct)
            remaining_pct -= pct
            remaining_usd -= amount

        allocations.append({
            "venue_id": venue["id"],
            "venue_name": venue.get("name", venue["id"]),
            "allocation_pct": pct,
            "amount_usd": amount,
            "expected_apy": venue.get("apy_estimate", 0.0),
            "risk": venue.get("risk", "unknown"),
        })

    # Guarantee: total allocation_pct == 1.0
    _assert_sums_to_one(allocations)

    return allocations


def _round6(x: float) -> float:
    """Round to 6 decimal places."""
    return round(x, 6)


def _round4(x: float) -> float:
    """Round to 4 decimal places."""
    return round(x, 4)


def _assert_sums_to_one(allocations: list[dict[str, Any]]) -> None:
    """Raise AssertionError if allocation_pct doesn't sum to ~1.0."""
    total = sum(a["allocation_pct"] for a in allocations)
    if not math.isclose(total, 1.0, rel_tol=1e-6, abs_tol=1e-9):
        raise AssertionError(
            f"BUG: allocation_pct total={total:.8f} != 1.0. "
            "This is a policy invariant violation."
        )
