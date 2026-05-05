"""Gensyn AXL Node A publisher.

Publishes DecisionRecord events to the AXL topic ``xrpfi.mint.complete``
for consumption by Lane B (yield-router agent on AXL Node 2).

AXL cross-node communication:
- Node 1 (this file) publishes mint completion events.
- Node 2 (Lane B) subscribes and triggers yield routing.

Deployment note (from project README):
  AXL nodes run on ``localhost:8765`` (Node 1) and ``localhost:8766`` (Node 2)
  for demo purposes. Production deployment uses separate Gensyn nodes with
  distinct node IDs on the Gensyn network.

Fallback mode:
  When the AXL REST API is unavailable (no Gensyn node running), the publisher
  operates in ``_fallback_mode = True``. Messages are queued in an async in-
  memory queue that fully mimics the AXL interface. A valid UUID axl_message_id
  is always produced and logged. The fallback ensures the cross-node communication
  code path is demonstrable without a running Gensyn cluster.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

from src.contracts.decision_log import DecisionRecord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
AXL_NODE_1_BASE = "http://localhost:8765"
AXL_NODE_2_BASE = "http://localhost:8766"

AXL_TOPIC = "xrpfi.mint.complete"

# HTTP timeout for AXL API calls (fast — local service)
AXL_TIMEOUT = 5.0


class AxlPublisher:
    """Gensyn AXL Node 1 publisher for mint completion events.

    Attempts to use the Gensyn AXL REST API first. Falls back to an
    in-memory async queue that reproduces the same interface when the
    node is not running (common during dev / hackathon demo).

    Usage::

        publisher = AxlPublisher()
        msg_id = await publisher.publish_mint_complete(decision_record)
        # msg_id is a UUID str, always set regardless of fallback mode
    """

    def __init__(
        self,
        node_base: str = AXL_NODE_1_BASE,
        topic: str = AXL_TOPIC,
        timeout: float = AXL_TIMEOUT,
    ) -> None:
        self._node_base = node_base
        self._topic = topic
        self._timeout = timeout

        # Fallback state
        self._fallback_mode: bool = False
        self._fallback_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._last_message_id: str = ""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _try_axl_publish(self, payload: dict[str, Any]) -> str | None:
        """Try to POST the payload to the AXL REST API.

        Returns the message_id string on success, None if the node is unreachable.
        """
        url = f"{self._node_base}/api/v1/publish"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as http:
                resp = await http.post(url, json=payload)
                resp.raise_for_status()
                body = resp.json()
                msg_id: str = body.get("messageId", str(uuid.uuid4()))
                logger.info(
                    "AXL Node 1: published to %s → messageId=%s", self._topic, msg_id
                )
                return msg_id
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            logger.debug("AXL Node 1 unreachable: %s", exc)
            return None

    def _make_axl_payload(self, record: DecisionRecord) -> dict[str, Any]:
        """Serialise a DecisionRecord into an AXL message payload."""
        return {
            "topic": self._topic,
            "nodeId": "xrpfi-node-1",
            "publishedAt": datetime.now(UTC).isoformat(),
            "message": {
                "record_id": record.record_id,
                "agent_name": record.agent_name,
                "agent_ens": record.agent_ens,
                "action_type": record.action_type,
                "input_summary": record.input_summary,
                "result_summary": record.result_summary,
                "reasoning": record.reasoning,
                "timestamp": record.timestamp.isoformat(),
                "ftso_prices": [
                    {
                        "feed_id": p.feed_id,
                        "feed_name": p.feed_name,
                        "price_usd": p.price_usd,
                        "timestamp": p.timestamp.isoformat(),
                    }
                    for p in record.ftso_prices
                ],
                "fdc_proof": (
                    {
                        "attestation_type": record.fdc_proof.attestation_type,
                        "proof_hash": record.fdc_proof.proof_hash,
                        "chain": record.fdc_proof.chain,
                        "round_id": record.fdc_proof.round_id,
                        "verified": record.fdc_proof.verified,
                    }
                    if record.fdc_proof
                    else None
                ),
                "zero_g": {
                    "storage_tx_hash": record.zero_g.storage_tx_hash,
                    "inft_token_id": record.zero_g.inft_token_id,
                },
            },
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def publish_mint_complete(self, record: DecisionRecord) -> str:
        """Publish a mint completion DecisionRecord to the AXL topic.

        Tries AXL REST API first. If unavailable, uses the in-memory fallback
        queue. Always returns a valid UUID axl_message_id.

        The message_id is also written back to record.axl_message_id so the
        orchestrator can persist it with the DecisionRecord.

        Args:
            record: DecisionRecord from the mint-helper agent.

        Returns:
            axl_message_id as a UUID string.
        """
        payload = self._make_axl_payload(record)

        # Attempt live AXL publish
        msg_id = await self._try_axl_publish(payload)

        if msg_id is None:
            # Fallback: in-memory queue
            self._fallback_mode = True
            msg_id = str(uuid.uuid4())

            if record.model_config.get("frozen"):
                object.__setattr__(record, "axl_message_id", msg_id)
            else:
                record.axl_message_id = msg_id

            fallback_payload = {
                "messageId": msg_id,
                "topic": self._topic,
                "nodeId": "xrpfi-node-1",
                "publishedAt": datetime.now(UTC).isoformat(),
                "payload": record.model_dump(mode="json"),
            }
            await self._fallback_queue.put(fallback_payload)

            from src.gensyn.node_b.subscriber import get_fallback_queue

            await get_fallback_queue(self._topic).put(fallback_payload)
            logger.warning(
                "AXL fallback mode active — message queued locally. "
                "messageId=%s topic=%s record_id=%s",
                msg_id, self._topic, record.record_id,
            )
        else:
            self._fallback_mode = False
            if record.model_config.get("frozen"):
                object.__setattr__(record, "axl_message_id", msg_id)
            else:
                record.axl_message_id = msg_id

        self._last_message_id = msg_id
        return msg_id

    async def get_message_id(self) -> str:
        """Return the last published message ID.

        Returns:
            UUID string of the last publish call, or empty string if no
            message has been published yet.
        """
        return self._last_message_id

    @property
    def is_fallback_mode(self) -> bool:
        """True if the publisher is operating in fallback (offline) mode."""
        return self._fallback_mode

    async def drain_fallback_queue(self) -> list[dict[str, Any]]:
        """Return all messages currently in the fallback queue (non-destructive peek).

        Useful for testing and diagnostics.
        """
        messages: list[dict[str, Any]] = []
        # Copy without consuming
        temp: list[dict[str, Any]] = []
        while not self._fallback_queue.empty():
            msg = self._fallback_queue.get_nowait()
            messages.append(msg)
            temp.append(msg)
        for msg in temp:
            await self._fallback_queue.put(msg)
        return messages

    def get_topic(self) -> str:
        """Return the AXL topic name (needed by Lane B to subscribe)."""
        return self._topic
