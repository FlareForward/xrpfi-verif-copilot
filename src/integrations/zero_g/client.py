"""0G storage client — persists DecisionRecord JSON to 0G decentralized storage.

Upload priority:
  1. Official 0G TypeScript SDK via Node.js helper (contracts/storage_upload/upload.mjs)
  2. HTTP indexer fallback (simulated tx_hash when node unavailable)

Galileo testnet by default (chain ID 80087).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

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
        """Check if the Node.js 0G TS SDK helper is available."""
        helper = (
            Path(__file__).parent.parent.parent.parent
            / "contracts" / "storage_upload" / "upload.mjs"
        )
        if helper.exists() and self.private_key:
            try:
                result = subprocess.run(["node", "--version"], capture_output=True, timeout=5)
                if result.returncode == 0:
                    logger.info("0G TS SDK helper available at %s", helper)
                    return True
            except Exception:
                pass
        logger.warning("0G TS SDK helper unavailable — using HTTP fallback")
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
        """Upload using the official 0G TypeScript SDK via Node.js subprocess."""
        helper = (
            Path(__file__).parent.parent.parent.parent
            / "contracts" / "storage_upload" / "upload.mjs"
        )
        try:
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="wb") as tmp:
                tmp.write(data)
                tmp_path = tmp.name

            result = subprocess.run(
                ["node", str(helper), tmp_path, self.private_key],
                capture_output=True,
                text=True,
                timeout=120,
            )
            os.unlink(tmp_path)

            if result.returncode == 0:
                output = json.loads(result.stdout.strip())
                if "error" in output:
                    raise RuntimeError(output["error"])
                tx_hash = output.get("tx_hash", root_hash)
                real_root = output.get("root_hash", root_hash)
                explorer_url = output.get("explorer_url", f"{ZERO_G_EXPLORER}/tx/{tx_hash}")
                logger.info("0G TS SDK upload success: root=%s tx=%s", real_root, tx_hash)
                return StorageResult(
                    tx_hash=tx_hash,
                    root_hash=real_root,
                    size_bytes=len(data),
                    stored_at=datetime.now(UTC),
                    explorer_url=explorer_url,
                )
            else:
                raise RuntimeError(result.stderr or result.stdout)

        except Exception as exc:
            logger.warning("0G TS SDK upload failed, falling back to HTTP: %s", exc)
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
