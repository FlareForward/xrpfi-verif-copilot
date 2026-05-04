"""PR-0 Contract Module — DecisionRecord schema shared by all agents.

No local redeclaration. Import: from contracts.decision_log import DecisionRecord
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class FtsoPrice(BaseModel):
    """FTSO price feed reading. Per Flare-First Data Policy: feed_id + timestamp required."""

    feed_id: str = Field(description="FTSO v2 bytes21 feed ID, e.g. '0x014658522f555344'")
    feed_name: str = Field(description="Human-readable name, e.g. 'FLR/USD'")
    price_usd: float
    decimals: int
    timestamp: datetime
    is_stale: bool = Field(default=False, description="True if data age > 30s at use")


class FdcProof(BaseModel):
    """FDC attestation proof — XRP payment verification in mint flow."""

    attestation_type: str = Field(description="'Payment', 'EVMTransaction', etc.")
    proof_hash: str
    chain: str = Field(description="'XRPL', 'BTC', 'ETH', etc.")
    round_id: int
    verified: bool = Field(default=False)


class ZeroGRecord(BaseModel):
    """0G storage + iNFT references, populated after Orchestrator persists the record."""

    storage_tx_hash: Optional[str] = None
    inft_token_id: Optional[str] = None
    inft_explorer_url: Optional[str] = None
    persisted_at: Optional[datetime] = None


class DecisionRecord(BaseModel):
    """Shared decision record produced by every agent action.

    Both mint-helper and yield-router produce DecisionRecord instances.
    The Orchestrator collects them, writes to 0G storage, and mints iNFTs.

    IMPORT RULE: always import from contracts.decision_log, never redeclare locally.
    """

    record_id: str = Field(default_factory=lambda: str(uuid4()), description="UUID for this record")
    agent_name: str = Field(description="Agent identifier: 'mint-helper' or 'yield-router'")
    agent_ens: str = Field(description="ENS name: 'mint-helper.eth' or 'yield-router.eth'")
    axl_message_id: Optional[str] = Field(default=None, description="Gensyn AXL message ID if inter-agent")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    action_type: Literal["mint", "route", "swap", "redeem", "report", "attest"] = Field(
        description="Category of agent action"
    )
    input_summary: str = Field(description="Brief human-readable description of inputs")
    ftso_prices: list[FtsoPrice] = Field(default_factory=list, description="FTSO prices at decision time")
    fdc_proof: Optional[FdcProof] = Field(default=None, description="FDC attestation if cross-chain")
    reasoning: str = Field(description="LLM advisory or policy reasoning (one paragraph max)")
    action_taken: str = Field(description="Exact action executed (or 'none' if advisory only)")
    result_summary: str = Field(description="Outcome: success/failure + key metrics")
    zero_g: ZeroGRecord = Field(default_factory=ZeroGRecord, description="0G persistence metadata")

    def is_persisted(self) -> bool:
        """True when this record has been written to 0G storage."""
        return self.zero_g.storage_tx_hash is not None

    def is_minted(self) -> bool:
        """True when this record has been minted as an iNFT on 0G."""
        return self.zero_g.inft_token_id is not None
