"""0G storage client — persists DecisionRecord JSON to 0G decentralized storage.

Upload priority:
  1. Official 0G TypeScript SDK via Node.js helper (contracts/storage_upload/upload.mjs)
  2. HTTP indexer health check + explicit local proof when live storage is unavailable

Network defaults read from environment variables (mainnet by default).
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

# 0G mainnet defaults — override via env vars
ZERO_G_EVM_RPC = os.environ.get("ZERO_G_RPC_URL", "https://0g-rpc.publicnode.com")
ZERO_G_INDEXER_URL = os.environ.get("ZERO_G_STORAGE_URL", "https://indexer-storage-turbo.0g.ai")
ZERO_G_CHAIN_ID = int(os.environ.get("ZERO_G_CHAIN_ID", "16661"))
ZERO_G_EXPLORER = os.environ.get("ZERO_G_EXPLORER", "https://chainscan.0g.ai")


class StorageResult(BaseModel):
    tx_hash: str
    root_hash: str
    size_bytes: int
    stored_at: datetime
    explorer_url: str
    backend: str = "unknown"
    live: bool = False
    error: str | None = None


class ZeroGClient:
    """Persists DecisionRecord instances to 0G decentralized storage.

    Returns an explicit non-live local proof if 0G storage is unavailable.
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
        logger.warning("0G TS SDK helper unavailable — checking HTTP indexer only")
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
        tmp_path: str | None = None
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
            if result.returncode == 0:
                output = self._parse_helper_output(result.stdout)
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
                    backend="0g-ts-sdk",
                    live=True,
                )
            else:
                raise RuntimeError(result.stderr or result.stdout)

        except Exception as exc:
            logger.warning("0G TS SDK upload failed, checking HTTP indexer: %s", exc)
            return await self._upload_via_http(data, root_hash)
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)

    def _parse_helper_output(self, stdout: str) -> dict[str, object]:
        """Parse the helper's JSON even when the SDK prints progress lines first."""
        for line in reversed([item.strip() for item in stdout.splitlines() if item.strip()]):
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        raise RuntimeError(f"0G helper did not emit JSON: {stdout[-500:]}")

    async def _upload_via_http(self, data: bytes, root_hash: str) -> StorageResult:
        """Upload via 0G HTTP indexer API or return an explicit local proof."""
        error: str | None = None
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(
                    f"{self.indexer_url}/upload",
                    content=data,
                    headers={"Content-Type": "application/octet-stream"},
                )
                if resp.status_code in (200, 201):
                    body = resp.json()
                    tx_hash = body.get("tx_hash", root_hash)
                    logger.info("0G HTTP upload success: %s", tx_hash)
                    return StorageResult(
                        tx_hash=tx_hash,
                        root_hash=root_hash,
                        size_bytes=len(data),
                        stored_at=datetime.now(UTC),
                        explorer_url=f"{ZERO_G_EXPLORER}/tx/{tx_hash}",
                        backend="0g-indexer-http",
                        live=True,
                    )
                else:
                    error = f"HTTP {resp.status_code}: {resp.text[:160]}"
                    logger.warning("0G HTTP upload unavailable: %s", error)
            except httpx.RequestError as e:
                error = str(e)
                logger.warning("0G HTTP upload failed: %s", e)

        tx_hash = f"local://sha256/{root_hash.removeprefix('0x')}"
        return StorageResult(
            tx_hash=tx_hash,
            root_hash=root_hash,
            size_bytes=len(data),
            stored_at=datetime.now(UTC),
            explorer_url="",
            backend="local-proof",
            live=False,
            error=error or "0G storage endpoint unavailable",
        )
