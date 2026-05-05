"""Tests for the deterministic rebalance policy.

Regression pin: rebalance_policy must be deterministic — same inputs always
produce the same outputs. Silent Regression Protocol: do NOT weaken these tests.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest

from src.contracts.decision_log import FtsoPrice
from src.policies.rebalance_policy import recommend_allocation

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_ftso() -> list[FtsoPrice]:
    return [
        FtsoPrice(
            feed_id="0x015852502f555344",
            feed_name="XRP/USD",
            price_usd=0.50,
            decimals=6,
            timestamp=datetime.now(UTC),
        ),
        FtsoPrice(
            feed_id="0x014658522f555344",
            feed_name="FLR/USD",
            price_usd=0.025,
            decimals=7,
            timestamp=datetime.now(UTC),
        ),
    ]


VENUES_MIXED = [
    {"id": "sparkdex-v2", "name": "SparkDEX v2", "type": "dex_lp", "apy_estimate": 0.12, "risk": "medium"},
    {"id": "kinetic-lending", "name": "Kinetic Lending", "type": "lending", "apy_estimate": 0.08, "risk": "low"},
    {"id": "cyclo-vault", "name": "Cyclo Yield Vault", "type": "yield_vault", "apy_estimate": 0.15, "risk": "medium-high"},
]

VENUES_LOW_ONLY = [
    {"id": "kinetic-lending", "name": "Kinetic Lending", "type": "lending", "apy_estimate": 0.08, "risk": "low"},
]

VENUES_HIGH_RISK_ONLY = [
    {"id": "high-risk-venue", "name": "High Risk", "type": "yield_vault", "apy_estimate": 0.25, "risk": "high"},
]


# ---------------------------------------------------------------------------
# Regression pin: determinism
# ---------------------------------------------------------------------------


def test_rebalance_policy_is_deterministic() -> None:
    """Pin: rebalance policy must be deterministic — same inputs always produce same outputs."""
    ftso = [
        FtsoPrice(
            feed_id="0x01",
            feed_name="FLR/USD",
            price_usd=0.025,
            decimals=7,
            timestamp=datetime.now(UTC),
        )
    ]
    venues = [
        {"id": "sparkdex-v2", "type": "dex_lp", "apy_estimate": 0.12, "risk": "medium"},
        {"id": "kinetic-lending", "type": "lending", "apy_estimate": 0.08, "risk": "low"},
    ]
    results = [recommend_allocation(1000.0, venues, "medium", ftso) for _ in range(10)]
    assert all(r == results[0] for r in results), "rebalance_policy must be deterministic"


# ---------------------------------------------------------------------------
# Allocation sums to 1.0
# ---------------------------------------------------------------------------


class TestAllocationSum:
    def test_medium_risk_sums_to_one(self) -> None:
        result = recommend_allocation(1000.0, VENUES_MIXED, "medium", make_ftso())
        total = sum(a["allocation_pct"] for a in result)
        assert math.isclose(total, 1.0, rel_tol=1e-6), f"allocation_pct total={total}"

    def test_low_risk_sums_to_one(self) -> None:
        result = recommend_allocation(500.0, VENUES_MIXED, "low", make_ftso())
        total = sum(a["allocation_pct"] for a in result)
        assert math.isclose(total, 1.0, rel_tol=1e-6), f"allocation_pct total={total}"

    def test_high_risk_sums_to_one(self) -> None:
        result = recommend_allocation(2000.0, VENUES_MIXED, "high", make_ftso())
        total = sum(a["allocation_pct"] for a in result)
        assert math.isclose(total, 1.0, rel_tol=1e-6), f"allocation_pct total={total}"

    def test_single_venue_sums_to_one(self) -> None:
        result = recommend_allocation(100.0, VENUES_LOW_ONLY, "low", make_ftso())
        assert len(result) == 1
        assert math.isclose(result[0]["allocation_pct"], 1.0, rel_tol=1e-6)

    def test_amount_usd_sum_matches_input(self) -> None:
        amount = 1234.56
        result = recommend_allocation(amount, VENUES_MIXED, "medium", make_ftso())
        total_usd = sum(a["amount_usd"] for a in result)
        # Allow small floating point delta
        assert math.isclose(total_usd, amount, rel_tol=1e-4), (
            f"total_usd={total_usd} != input={amount}"
        )


# ---------------------------------------------------------------------------
# Risk filtering: never allocate to venue with risk > preference
# ---------------------------------------------------------------------------


class TestRiskFiltering:
    def test_low_preference_excludes_medium_risk(self) -> None:
        result = recommend_allocation(1000.0, VENUES_MIXED, "low", make_ftso())
        for alloc in result:
            assert alloc["risk"] == "low", (
                f"venue {alloc['venue_id']} has risk={alloc['risk']} but preference=low"
            )

    def test_medium_preference_excludes_medium_high(self) -> None:
        result = recommend_allocation(1000.0, VENUES_MIXED, "medium", make_ftso())
        allowed = {"low", "medium"}
        for alloc in result:
            assert alloc["risk"] in allowed, (
                f"venue {alloc['venue_id']} risk={alloc['risk']} exceeds medium preference"
            )

    def test_high_preference_allows_all_risk_tiers(self) -> None:
        result = recommend_allocation(1000.0, VENUES_MIXED, "high", make_ftso())
        venue_ids = {a["venue_id"] for a in result}
        # All three venues should be eligible
        assert "sparkdex-v2" in venue_ids
        assert "kinetic-lending" in venue_ids
        assert "cyclo-vault" in venue_ids

    def test_low_preference_cannot_allocate_high_risk_only_catalog(self) -> None:
        """When catalog has only high-risk venues and preference is low, must raise."""
        with pytest.raises(ValueError, match="No venues eligible"):
            recommend_allocation(1000.0, VENUES_HIGH_RISK_ONLY, "low", make_ftso())

    def test_medium_preference_cannot_allocate_medium_high_only(self) -> None:
        venues = [{"id": "cyclo-vault", "apy_estimate": 0.15, "risk": "medium-high"}]
        with pytest.raises(ValueError, match="No venues eligible"):
            recommend_allocation(500.0, venues, "medium", make_ftso())


# ---------------------------------------------------------------------------
# Invalid input handling
# ---------------------------------------------------------------------------


class TestInvalidInputs:
    def test_invalid_risk_preference_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid risk_preference"):
            recommend_allocation(1000.0, VENUES_MIXED, "ultra-safe", make_ftso())

    def test_empty_venues_raises(self) -> None:
        with pytest.raises((ValueError, IndexError)):
            recommend_allocation(1000.0, [], "medium", make_ftso())

    def test_ftso_prices_must_be_list(self) -> None:
        with pytest.raises(TypeError):
            recommend_allocation(1000.0, VENUES_MIXED, "medium", "not-a-list")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Allocation correctness
# ---------------------------------------------------------------------------


class TestAllocationCorrectness:
    def test_low_risk_concentrates_in_kinetic(self) -> None:
        """Low risk preference should concentrate 100% in the only low-risk venue."""
        result = recommend_allocation(1000.0, VENUES_MIXED, "low", make_ftso())
        assert len(result) == 1
        assert result[0]["venue_id"] == "kinetic-lending"
        assert math.isclose(result[0]["allocation_pct"], 1.0)

    def test_medium_risk_includes_both_eligible_venues(self) -> None:
        result = recommend_allocation(1000.0, VENUES_MIXED, "medium", make_ftso())
        ids = {a["venue_id"] for a in result}
        assert "kinetic-lending" in ids
        assert "sparkdex-v2" in ids

    def test_higher_apy_gets_more_allocation_in_medium(self) -> None:
        """APY-weighted allocation: higher APY venue gets more share."""
        result = recommend_allocation(1000.0, VENUES_MIXED, "medium", make_ftso())
        alloc_by_id = {a["venue_id"]: a["allocation_pct"] for a in result}
        # sparkdex-v2 (12% APY) should get more than kinetic-lending (8% APY)
        assert alloc_by_id["sparkdex-v2"] > alloc_by_id["kinetic-lending"]

    def test_all_allocations_have_required_keys(self) -> None:
        result = recommend_allocation(500.0, VENUES_MIXED, "high", make_ftso())
        required = {"venue_id", "allocation_pct", "amount_usd", "expected_apy", "risk"}
        for alloc in result:
            missing = required - set(alloc.keys())
            assert not missing, f"allocation missing keys: {missing}"

    def test_allocation_pct_values_non_negative(self) -> None:
        result = recommend_allocation(1000.0, VENUES_MIXED, "high", make_ftso())
        for alloc in result:
            assert alloc["allocation_pct"] >= 0.0

    def test_amount_usd_values_non_negative(self) -> None:
        result = recommend_allocation(1000.0, VENUES_MIXED, "high", make_ftso())
        for alloc in result:
            assert alloc["amount_usd"] >= 0.0

    def test_determinism_across_risk_levels(self) -> None:
        """Each risk level is deterministic independently."""
        ftso = make_ftso()
        for risk in ("low", "medium", "high"):
            r1 = recommend_allocation(750.0, VENUES_MIXED, risk, ftso)
            r2 = recommend_allocation(750.0, VENUES_MIXED, risk, ftso)
            assert r1 == r2, f"Non-deterministic for risk={risk}"
