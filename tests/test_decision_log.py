"""Tests for the PR-0 DecisionRecord contract module.

These tests pin the invariants that must hold for all agent outputs.
DO NOT weaken or remove — per Silent Regression Protocol.
"""

from datetime import datetime, timezone

import pytest

from src.contracts.decision_log import DecisionRecord, FdcProof, FtsoPrice, ZeroGRecord


def make_ftso_price(feed_id: str = "0x014658522f555344", price: float = 0.025) -> FtsoPrice:
    return FtsoPrice(
        feed_id=feed_id,
        feed_name="FLR/USD",
        price_usd=price,
        decimals=7,
        timestamp=datetime.now(timezone.utc),
    )


def make_record(**kwargs) -> DecisionRecord:
    defaults = {
        "agent_name": "mint-helper",
        "agent_ens": "mint-helper.eth",
        "action_type": "mint",
        "input_summary": "User requests 100 XRP → FXRP mint",
        "ftso_prices": [make_ftso_price()],
        "reasoning": "FTSO XRP/USD = 0.50, FLR/USD = 0.025; mint economics favorable",
        "action_taken": "Initiated FAssets mint for 100 XRP",
        "result_summary": "Mint initiated, waiting for FDC Payment attestation",
    }
    defaults.update(kwargs)
    return DecisionRecord(**defaults)


class TestDecisionRecord:
    def test_record_id_auto_generated(self):
        r1 = make_record()
        r2 = make_record()
        assert r1.record_id != r2.record_id

    def test_record_id_is_uuid_string(self):
        r = make_record()
        assert len(r.record_id) == 36
        assert r.record_id.count("-") == 4

    def test_not_persisted_by_default(self):
        r = make_record()
        assert not r.is_persisted()
        assert not r.is_minted()

    def test_persisted_after_zero_g_hash(self):
        r = make_record()
        r.zero_g.storage_tx_hash = "0xabc123"
        assert r.is_persisted()
        assert not r.is_minted()

    def test_minted_after_inft_token_id(self):
        r = make_record()
        r.zero_g.storage_tx_hash = "0xabc123"
        r.zero_g.inft_token_id = "42"
        assert r.is_persisted()
        assert r.is_minted()

    def test_ftso_prices_required_field_populated(self):
        r = make_record()
        assert len(r.ftso_prices) > 0
        p = r.ftso_prices[0]
        assert p.feed_id.startswith("0x")
        assert p.price_usd > 0
        assert isinstance(p.timestamp, datetime)

    def test_stale_flag_defaults_false(self):
        p = make_ftso_price()
        assert not p.is_stale

    def test_fdc_proof_optional(self):
        r = make_record(fdc_proof=None)
        assert r.fdc_proof is None

    def test_fdc_proof_attached(self):
        proof = FdcProof(
            attestation_type="Payment",
            proof_hash="0xdeadbeef",
            chain="XRPL",
            round_id=12345,
            verified=True,
        )
        r = make_record(fdc_proof=proof)
        assert r.fdc_proof is not None
        assert r.fdc_proof.chain == "XRPL"
        assert r.fdc_proof.verified

    def test_action_type_enum_valid(self):
        for atype in ["mint", "route", "swap", "redeem", "report", "attest"]:
            r = make_record(action_type=atype)
            assert r.action_type == atype

    def test_action_type_invalid_rejected(self):
        with pytest.raises(Exception):
            make_record(action_type="hodl")

    def test_yield_router_record(self):
        r = make_record(
            agent_name="yield-router",
            agent_ens="yield-router.eth",
            action_type="route",
            ftso_prices=[
                make_ftso_price("0x014658522f555344", 0.025),
                make_ftso_price("0x015852502f555344", 0.50),
            ],
        )
        assert r.agent_name == "yield-router"
        assert len(r.ftso_prices) == 2

    def test_serialization_round_trip(self):
        r = make_record()
        data = r.model_dump()
        r2 = DecisionRecord(**data)
        assert r2.record_id == r.record_id
        assert r2.agent_ens == r.agent_ens
