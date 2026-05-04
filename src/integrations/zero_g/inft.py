"""0G iNFT minter — mints ERC-7857 AI agent NFTs on 0G Newton testnet.

iNFT (intelligent NFT) is ERC-7857 on 0G. Each DecisionRecord history
is minted as an iNFT, giving the judge a clickable proof on 0G explorer.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from pydantic import BaseModel
from web3 import Web3
from web3.contract import Contract

from src.contracts.decision_log import DecisionRecord

logger = logging.getLogger(__name__)

ZERO_G_EVM_RPC = "https://evmrpc-testnet.0g.ai"
ZERO_G_EXPLORER = "https://chainscan-newton.0g.ai"
ZERO_G_CHAIN_ID = 16600

# ERC-7857 iNFT ABI — minimal interface for mint + tokenURI
INFT_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "string", "name": "encryptedURI", "type": "string"},
            {"internalType": "bytes32", "name": "metadataHash", "type": "bytes32"},
        ],
        "name": "mint",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
        "name": "tokenURI",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": True, "name": "tokenId", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    },
]


class MintResult(BaseModel):
    token_id: str
    tx_hash: str
    explorer_url: str
    minted_at: datetime
    metadata_hash: str


class INFTMinter:
    """Mints DecisionRecord audit logs as iNFTs on 0G Newton testnet.

    The iNFT encryptedURI points to the 0G storage tx_hash where the full
    DecisionRecord JSON is stored. The metadataHash is keccak256 of the JSON.
    """

    def __init__(
        self,
        contract_address: Optional[str] = None,
        rpc_url: str = ZERO_G_EVM_RPC,
        private_key: Optional[str] = None,
    ) -> None:
        self.rpc_url = rpc_url
        self.private_key = private_key
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.contract_address = contract_address
        self._contract: Optional[Contract] = None

        if contract_address:
            checksum = self.w3.to_checksum_address(contract_address)
            self._contract = self.w3.eth.contract(address=checksum, abi=INFT_ABI)

    def _build_metadata(self, records: list[DecisionRecord]) -> dict:
        """Build the iNFT metadata payload from a list of decision records."""
        return {
            "name": f"XRPFi Decision Log — {len(records)} actions",
            "description": "Verifiable AI agent decision audit log for XRPFi Copilot",
            "agent_names": list({r.agent_name for r in records}),
            "agent_ens_names": list({r.agent_ens for r in records}),
            "action_count": len(records),
            "action_types": [r.action_type for r in records],
            "first_action_at": records[0].timestamp.isoformat() if records else None,
            "last_action_at": records[-1].timestamp.isoformat() if records else None,
            "zero_g_storage_refs": [
                r.zero_g.storage_tx_hash for r in records if r.zero_g.storage_tx_hash
            ],
            "ftso_prices_used": sum(len(r.ftso_prices) for r in records),
            "fdc_proofs_used": sum(1 for r in records if r.fdc_proof is not None),
        }

    def _compute_metadata_hash(self, metadata: dict) -> bytes:
        """keccak256 of canonical JSON metadata."""
        canonical = json.dumps(metadata, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return bytes(self.w3.keccak(canonical))

    async def mint_decision_log(
        self,
        records: list[DecisionRecord],
        recipient_address: str,
        storage_uri: str,
    ) -> MintResult:
        """Mint an iNFT representing the full decision log.

        Args:
            records: All DecisionRecord instances to bundle into this iNFT.
            recipient_address: Ethereum address to mint the iNFT to.
            storage_uri: 0G storage reference URI (tx hash or CID).

        Returns:
            MintResult with token_id, tx_hash, and explorer URL.
        """
        metadata = self._build_metadata(records)
        metadata_hash = self._compute_metadata_hash(metadata)

        if self._contract and self.private_key:
            result = await self._mint_on_chain(
                recipient_address, storage_uri, metadata_hash
            )
        else:
            logger.warning(
                "No iNFT contract address or private key — using demo mint (no real tx). "
                "Set ZERO_G_PRIVATE_KEY and deploy iNFT contract for real mint."
            )
            result = self._demo_mint(storage_uri, metadata_hash)

        # Update all records with the iNFT token ID
        for record in records:
            record.zero_g.inft_token_id = result.token_id
            record.zero_g.inft_explorer_url = result.explorer_url

        logger.info(
            "iNFT minted",
            token_id=result.token_id,
            records=len(records),
            explorer=result.explorer_url,
        )
        return result

    async def _mint_on_chain(
        self, to: str, encrypted_uri: str, metadata_hash: bytes
    ) -> MintResult:
        """Submit a real mint transaction to the 0G testnet."""
        assert self._contract is not None
        assert self.private_key is not None

        account = self.w3.eth.account.from_key(self.private_key)
        nonce = self.w3.eth.get_transaction_count(account.address)

        tx = self._contract.functions.mint(
            self.w3.to_checksum_address(to),
            encrypted_uri,
            metadata_hash,
        ).build_transaction(
            {
                "from": account.address,
                "nonce": nonce,
                "gas": 200000,
                "chainId": ZERO_G_CHAIN_ID,
            }
        )

        signed = self.w3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        # Parse Transfer event to get token_id
        token_id = "0"
        if receipt.get("logs"):
            for log in receipt["logs"]:
                if len(log.get("topics", [])) >= 4:
                    token_id = str(int(log["topics"][3].hex(), 16))
                    break

        tx_hash_hex = "0x" + receipt["transactionHash"].hex()
        return MintResult(
            token_id=token_id,
            tx_hash=tx_hash_hex,
            explorer_url=f"{ZERO_G_EXPLORER}/tx/{tx_hash_hex}",
            minted_at=datetime.now(timezone.utc),
            metadata_hash="0x" + metadata_hash.hex(),
        )

    def _demo_mint(self, encrypted_uri: str, metadata_hash: bytes) -> MintResult:
        """Simulated mint for demo/development when no contract is deployed."""
        import hashlib
        demo_token_id = str(int(hashlib.md5(encrypted_uri.encode()).hexdigest()[:8], 16))
        demo_tx = "0xdemo" + hashlib.sha256(encrypted_uri.encode()).hexdigest()[:60]
        return MintResult(
            token_id=demo_token_id,
            tx_hash=demo_tx,
            explorer_url=f"{ZERO_G_EXPLORER}/tx/{demo_tx}",
            minted_at=datetime.now(timezone.utc),
            metadata_hash="0x" + metadata_hash.hex(),
        )
