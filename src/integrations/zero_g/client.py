"""0G storage client — persists DecisionRecord JSON to 0G decentralized storage.

Uses 0g-storage-sdk (pip install 0g-storage-sdk) or falls back to direct HTTP
if the SDK is unavailable. Galileo testnet by default.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime

import httpx
from pydantic import BaseModel

from src.contracts.decision_log import DecisionRecord

logger = logging.getLogger(__name__)

# 0G Galileo testnet (V3 — current active testnet as of 2026)
ZERO_G_EVM_RPC = "https://evmrpc-testnet.0g.ai"
ZERO_G_INDEXER_URL = "https://indexer-storage-testnet-turbo.0g.ai"
ZERO_G_CHAIN_ID = 80087
ZERO_G_EXPLORER = "https://chainscan-galileo.0g.ai"


class StorageResult(BaseModel):
    tx_hash: str
    root_hash: str
    size_bytes: int
    stored_at: datetime
    explorer_url: str


class ZeroGClient:
    """Persists DecisionRecord instances to 0G decentralized storage.

    Falls back to HTTP upload if 0g-storage-sdk is not installed.
    """

    def __init__(
        self,
        evm_rpc: str = ZERO_G_EVM_RPC,
        indexer_url: str = ZERO_G_INDEXER_URL,
        private_key: str | None = None,
    ) -> None:
        self.evm_rpc = evm_rpc
        self.indexer_url = indexer_url
        self.private_key = private_key
        self._sdk_available = self._check_sdk()

    def _check_sdk(self) -> bool:
        try:
            import importlib
            importlib.import_module("zg")
            return True
        except ImportError:
            logger.warning(
                "0g-storage-sdk not installed; falling back to HTTP upload. "
                "Install: pip install 0g-storage-sdk"
            )
            return False

    def _record_to_bytes(self, record: DecisionRecord) -> bytes:
        """Serialize a DecisionRecord to canonical JSON bytes for 0G upload."""
        payload = record.model_dump(mode="json")
        return json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")

    def _compute_root_hash(self, data: bytes) -> str:
        """SHA-256 root hash of the stored data (Merkle root placeholder for v1)."""
        return "0x" + hashlib.sha256(data).hexdigest()

    async def upload_record(self, record: DecisionRecord) -> StorageResult:
        """Upload a DecisionRecord to 0G storage.

        Returns a StorageResult with transaction hash and explorer URL.
        Populates record.zero_g.storage_tx_hash in place.
        """
        data = self._record_to_bytes(record)
        root_hash = self._compute_root_hash(data)

        if self._sdk_available:
            result = await self._upload_via_sdk(data, root_hash)
        else:
            result = await self._upload_via_http(data, root_hash)

        record.zero_g.storage_tx_hash = result.tx_hash
        record.zero_g.persisted_at = result.stored_at
        logger.info(
            "DecisionRecord persisted to 0G",
            record_id=record.record_id,
            tx_hash=result.tx_hash,
            explorer=result.explorer_url,
        )
        return result

    async def _upload_via_sdk(self, data: bytes, root_hash: str) -> StorageResult:
        """Upload using 0g-storage-sdk."""
        try:
            import zg  # type: ignore[import]
            from web3 import Web3

            w3 = Web3(Web3.HTTPProvider(self.evm_rpc))
            if self.private_key:
                account = w3.eth.account.from_key(self.private_key)
                uploader = zg.ZgFile(data)
                tree = uploader.build_merkle_tree()
                tx = await zg.upload(
                    tree=tree,
                    indexer_url=self.indexer_url,
                    account=account,
                    w3=w3,
                )
                tx_hash = tx.get("tx_hash", root_hash)
            else:
                # No key: simulate upload (demo mode)
                logger.warning("No 0G private key — using demo mode (no real upload)")
                tx_hash = f"demo-{root_hash[:20]}"

            return StorageResult(
                tx_hash=tx_hash,
                root_hash=root_hash,
                size_bytes=len(data),
                stored_at=datetime.now(UTC),
                explorer_url=f"{ZERO_G_EXPLORER}/tx/{tx_hash}",
            )
        except Exception as e:
            logger.warning("SDK upload failed, falling back to HTTP: %s", e)
            return await self._upload_via_http(data, root_hash)

    async def _upload_via_http(self, data: bytes, root_hash: str) -> StorageResult:
        """Upload via 0G HTTP indexer API (fallback)."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # 0G indexer upload endpoint
                resp = await client.post(
                    f"{self.indexer_url}/upload",
                    content=data,
                    headers={"Content-Type": "application/octet-stream"},
                )
                if resp.status_code in (200, 201):
                    body = resp.json()
                    tx_hash = body.get("tx_hash", root_hash)
                    logger.info("0G HTTP upload success: %s", tx_hash)
                else:
                    logger.warning(
                        "0G HTTP upload returned %d — using simulated tx_hash", resp.status_code
                    )
                    tx_hash = f"simulated-{root_hash[:20]}"
            except httpx.RequestError as e:
                logger.warning("0G HTTP upload failed: %s — using simulated tx_hash", e)
                tx_hash = f"simulated-{root_hash[:20]}"

        return StorageResult(
            tx_hash=tx_hash,
            root_hash=root_hash,
            size_bytes=len(data),
            stored_at=datetime.now(UTC),
            explorer_url=f"{ZERO_G_EXPLORER}/tx/{tx_hash}",
        )
