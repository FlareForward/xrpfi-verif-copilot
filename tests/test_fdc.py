"""Tests for FDC payment attestation client.

Covers:
- FdcProof import from contracts.decision_log (not redeclared)
- request_payment_attestation with mock fixtures
- verify_payment on-chain call
- Offline fallback behaviour
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.contracts.decision_log import FdcProof
from src.integrations.fdc.client import PAYMENT_TYPE, XRPL_CHAIN_ID, FdcClient


# ---------------------------------------------------------------------------
# Regression pin — import guard
# ---------------------------------------------------------------------------
def test_fdc_proof_imported_from_contracts_module() -> None:
    """Pin: FdcProof must come from contracts.decision_log, never redeclared."""
    import inspect

    import src.integrations.fdc.client as fdc_module

    source = inspect.getsource(fdc_module)
    assert "from src.contracts.decision_log import" in source
    assert "class FdcProof" not in source


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
SAMPLE_TX_HASH = "A" * 64
SAMPLE_FROM = "rGWrZyax5eXbi5YpFV3xgMm1K9L3YSm1YV"
SAMPLE_TO = "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh"
SAMPLE_AMOUNT = 100.0


@pytest.fixture()
def client() -> FdcClient:
    return FdcClient()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestFdcClientRequestAttestation:
    @pytest.mark.asyncio
    async def test_request_returns_fdc_proof(self, client: FdcClient) -> None:
        """request_payment_attestation returns FdcProof with correct fields."""
        relay_response = {"roundId": 42, "status": "SUBMITTED"}

        with patch.object(client, "_post_relay", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = relay_response
            proof = await client.request_payment_attestation(
                SAMPLE_TX_HASH, SAMPLE_FROM, SAMPLE_TO, SAMPLE_AMOUNT
            )

        assert isinstance(proof, FdcProof)
        assert proof.attestation_type == PAYMENT_TYPE
        assert proof.chain == XRPL_CHAIN_ID
        assert proof.round_id == 42
        assert proof.proof_hash.startswith("0x")
        assert not proof.verified  # not verified yet

    @pytest.mark.asyncio
    async def test_request_relay_offline_fallback(self, client: FdcClient) -> None:
        """Falls back gracefully when relay is offline, still returns FdcProof."""
        with patch.object(
            client, "_post_relay", side_effect=Exception("connection refused")
        ):
            proof = await client.request_payment_attestation(
                SAMPLE_TX_HASH, SAMPLE_FROM, SAMPLE_TO, SAMPLE_AMOUNT
            )

        assert isinstance(proof, FdcProof)
        assert proof.round_id > 0  # stub round_id derived from tx hash
        assert not proof.verified

    @pytest.mark.asyncio
    async def test_proof_hash_is_deterministic(self, client: FdcClient) -> None:
        """Same tx hash + round_id always produces the same proof hash."""
        with patch.object(
            client, "_post_relay", new_callable=AsyncMock, return_value={"roundId": 7}
        ):
            p1 = await client.request_payment_attestation(
                SAMPLE_TX_HASH, SAMPLE_FROM, SAMPLE_TO, SAMPLE_AMOUNT
            )
        with patch.object(
            client, "_post_relay", new_callable=AsyncMock, return_value={"roundId": 7}
        ):
            p2 = await client.request_payment_attestation(
                SAMPLE_TX_HASH, SAMPLE_FROM, SAMPLE_TO, SAMPLE_AMOUNT
            )

        assert p1.proof_hash == p2.proof_hash


class TestFdcClientVerifyPayment:
    @pytest.mark.asyncio
    async def test_verify_payment_with_valid_root(self, client: FdcClient) -> None:
        """verify_payment returns True when StateConnector returns a non-zero root."""
        proof = FdcProof(
            attestation_type=PAYMENT_TYPE,
            proof_hash="0x" + "ab" * 32,
            chain=XRPL_CHAIN_ID,
            round_id=100,
            verified=False,
        )

        # Return a non-zero Merkle root
        non_zero_root = "0x" + "cd" * 32
        with patch.object(client, "_eth_call", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = non_zero_root
            result = await client.verify_payment(proof)

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_payment_offline_fallback(self, client: FdcClient) -> None:
        """Falls back to demo-verify when round_id > 0 and StateConnector fails."""
        proof = FdcProof(
            attestation_type=PAYMENT_TYPE,
            proof_hash="0x" + "aa" * 32,
            chain=XRPL_CHAIN_ID,
            round_id=50,
            verified=False,
        )

        with patch.object(
            client, "_eth_call", side_effect=RuntimeError("no connection")
        ):
            result = await client.verify_payment(proof)

        # Offline fallback: round_id > 0 → demo-verified
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_payment_round_zero_not_verified(self, client: FdcClient) -> None:
        """round_id == 0 with failed RPC → not verified."""
        proof = FdcProof(
            attestation_type=PAYMENT_TYPE,
            proof_hash="0x" + "00" * 32,
            chain=XRPL_CHAIN_ID,
            round_id=0,
            verified=False,
        )

        with patch.object(
            client, "_eth_call", side_effect=RuntimeError("no connection")
        ):
            result = await client.verify_payment(proof)

        assert result is False

    @pytest.mark.asyncio
    async def test_attestation_status_offline(self, client: FdcClient) -> None:
        """get_attestation_status returns OFFLINE status when relay unreachable."""
        proof = FdcProof(
            attestation_type=PAYMENT_TYPE,
            proof_hash="0x" + "aa" * 32,
            chain=XRPL_CHAIN_ID,
            round_id=99,
            verified=False,
        )

        with patch.object(
            client, "_get_relay", side_effect=Exception("connection refused")
        ):
            status = await client.get_attestation_status(proof)

        assert status["round_id"] == 99
        assert status["status"] == "OFFLINE"
        assert not status["finalised"]
