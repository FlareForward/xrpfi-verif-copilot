"""Tests for 0G storage client and iNFT minter.

Regression pins — per Silent Regression Protocol, do NOT weaken these tests.
"""

from __future__ import annotations

import json
from base64 import b64decode
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
import respx
from httpx import Response

from src.config import Settings
from src.contracts.decision_log import DecisionRecord, FtsoPrice
from src.integrations.zero_g.client import StorageResult, ZeroGClient
from src.integrations.zero_g.inft import INFTMinter


def make_record(agent_name: str = "mint-helper") -> DecisionRecord:
    return DecisionRecord(
        agent_name=agent_name,
        agent_ens=f"{agent_name}.eth",
        action_type="mint" if agent_name == "mint-helper" else "route",
        input_summary="Test record",
        ftso_prices=[
            FtsoPrice(
                feed_id="0x014658522f555344",
                feed_name="FLR/USD",
                price_usd=0.025,
                decimals=7,
                timestamp=datetime.now(UTC),
            )
        ],
        reasoning="Test reasoning",
        action_taken="Test action",
        result_summary="Test result",
    )


class TestZeroGClient:
    def setup_method(self):
        self.client = ZeroGClient(private_key=None)

    def test_record_to_bytes_is_valid_json(self):
        record = make_record()
        data = self.client._record_to_bytes(record)
        parsed = json.loads(data.decode("utf-8"))
        assert parsed["agent_name"] == "mint-helper"
        assert parsed["action_type"] == "mint"

    def test_compute_root_hash_starts_0x(self):
        data = b"test data"
        root = self.client._compute_root_hash(data)
        assert root.startswith("0x")
        assert len(root) == 66  # 0x + 64 hex chars

    def test_compute_root_hash_deterministic(self):
        data = b"same data"
        h1 = self.client._compute_root_hash(data)
        h2 = self.client._compute_root_hash(data)
        assert h1 == h2

    @pytest.mark.asyncio
    async def test_upload_record_populates_zero_g_fields(self):
        record = make_record()
        assert record.zero_g.storage_tx_hash is None

        with patch.object(
            self.client,
            "_upload_via_http",
            new=AsyncMock(
                return_value=StorageResult(
                    tx_hash="0xabc123",
                    root_hash="0xdeadbeef",
                    size_bytes=100,
                    stored_at=datetime.now(UTC),
                    explorer_url="https://chainscan-newton.0g.ai/tx/0xabc123",
                )
            ),
        ):
            self.client._sdk_available = False
            result = await self.client.upload_record(record)

        assert record.zero_g.storage_tx_hash == "0xabc123"
        assert record.is_persisted()
        assert result.tx_hash == "0xabc123"

    @pytest.mark.asyncio
    async def test_upload_http_fallback_handles_error(self):
        """Pin: upload must not raise even if 0G endpoint is unreachable."""
        record = make_record()
        self.client = ZeroGClient(indexer_url="https://indexer-storage-turbo.0g.ai/", private_key=None)
        self.client._sdk_available = False

        with respx.mock(assert_all_called=True) as router:
            router.post("https://indexer-storage-turbo.0g.ai/file/segment").mock(
                return_value=Response(600, json={"code": 600, "message": "storage unavailable"})
            )
            result = await self.client.upload_record(record)

        assert result.tx_hash.startswith("local://sha256/") or result.tx_hash.startswith("0x")
        assert result.tx_hash.startswith("simulated-") is False
        assert result.live is result.tx_hash.startswith("0x")
        assert record.is_persisted()

    @pytest.mark.asyncio
    async def test_upload_http_fallback_posts_documented_segment_gateway(self):
        data = b'{"hello":"0g"}'
        root_hash = self.client._compute_root_hash(data)
        tx_hash = "0x" + "a" * 64

        with respx.mock(assert_all_called=True) as router:
            route = router.post("https://indexer-storage-turbo.0g.ai/file/segment").mock(
                return_value=Response(
                    200,
                    json={
                        "code": 0,
                        "data": {
                            "txHash": tx_hash,
                            "rootHash": root_hash,
                        },
                    },
                )
            )
            result = await self.client._upload_via_http(data, root_hash)

        request = route.calls.last.request
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["root"] == root_hash
        assert payload["index"] == 0
        assert b64decode(payload["data"]) == data
        assert payload["proof"] == {}
        assert payload["expectedReplica"] == 1
        assert result.tx_hash == tx_hash
        assert result.root_hash == root_hash
        assert result.backend == "0g-indexer-http"
        assert result.live is True

    @pytest.mark.asyncio
    async def test_upload_http_fallback_requires_tx_hash_for_live_result(self):
        data = b'{"hello":"0g"}'
        root_hash = self.client._compute_root_hash(data)

        with respx.mock(assert_all_called=True) as router:
            router.post("https://indexer-storage-turbo.0g.ai/file/segment").mock(
                return_value=Response(200, json={"code": 0, "data": {"rootHash": root_hash}})
            )
            result = await self.client._upload_via_http(data, root_hash)

        assert result.tx_hash.startswith("local://sha256/")
        assert result.live is False
        assert result.error == "HTTP upload response did not include a transaction hash"

    @pytest.mark.asyncio
    async def test_upload_http_fallback_handles_malformed_json_response(self):
        data = b'{"hello":"0g"}'
        root_hash = self.client._compute_root_hash(data)

        with respx.mock(assert_all_called=True) as router:
            router.post("https://indexer-storage-turbo.0g.ai/file/segment").mock(
                return_value=Response(200, text="not json")
            )
            result = await self.client._upload_via_http(data, root_hash)

        assert result.tx_hash.startswith("local://sha256/")
        assert result.live is False
        assert result.error is not None

    def test_zero_g_storage_url_defaults_to_mainnet_turbo_indexer(self):
        settings = Settings()
        assert settings.zero_g_storage_url == "https://indexer-storage-turbo.0g.ai"


class TestINFTMinter:
    def setup_method(self):
        self.minter = INFTMinter(contract_address=None, private_key=None)

    def test_build_metadata_has_required_fields(self):
        records = [make_record("mint-helper"), make_record("yield-router")]
        meta = self.minter._build_metadata(records)
        assert meta["action_count"] == 2
        assert "mint-helper" in meta["agent_names"]
        assert "yield-router" in meta["agent_names"]
        assert meta["ftso_prices_used"] == 2

    def test_compute_metadata_hash_is_32_bytes(self):
        meta = {"test": "data"}
        h = self.minter._compute_metadata_hash(meta)
        assert len(h) == 32

    def test_compute_metadata_hash_deterministic(self):
        meta = {"a": 1, "b": 2}
        h1 = self.minter._compute_metadata_hash(meta)
        h2 = self.minter._compute_metadata_hash(meta)
        assert h1 == h2

    @pytest.mark.asyncio
    async def test_demo_mint_returns_valid_result(self):
        """Pin: demo mint must always return a MintResult even without contract."""
        records = [make_record()]
        result = await self.minter.mint_decision_log(
            records=records,
            recipient_address="0x1234567890123456789012345678901234567890",
            storage_uri="0xdeadbeef",
        )
        assert result.token_id is not None
        assert result.tx_hash.startswith("0x")
        assert "0g.ai" in result.explorer_url or "chainscan-newton" in result.explorer_url
        # Records must be updated
        assert records[0].zero_g.inft_token_id == result.token_id
        assert records[0].is_minted()

    def test_demo_mint_token_id_deterministic(self):
        """Pin: demo mint must produce same token ID for same URI."""
        h = self.minter._compute_metadata_hash({"test": "meta"})
        r1 = self.minter._demo_mint("same-uri", h)
        r2 = self.minter._demo_mint("same-uri", h)
        assert r1.token_id == r2.token_id
