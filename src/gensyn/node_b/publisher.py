"""Gensyn AXL node B — publisher for xrpfi.route.plan topic.

Cross-node communication pattern:
- AXL node B (yield-router): subscribes to xrpfi.mint.complete (from node A)
- AXL node B (yield-router): publishes route plan to xrpfi.route.plan

Operation modes:
1. Primary: Gensyn AXL REST API at axl_node_b_endpoint (from config).
2. Fallback: In-process asyncio.Queue with _fallback_mode=True when AXL is unreachable.

Fallback mode produces deterministic, incrementing message IDs prefixed with 'fallback-'.
AXL topic config is read from src.config — not hardcoded.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx

from src.config import get_settings
from src.contracts.decision_log import DecisionRecord

# Re-export fallback queue from subscriber for cross-node in-process communication
from src.gensyn.node_b.subscriber import get_fallback_queue

logger = logging.getLogger(__name__)


class AxlPublisher:
    """Publishes route plans to xrpfi.route.plan on Gensyn AXL node B.

    Primary mode: POST to AXL REST API at axl_node_b_endpoint.
    Fallback mode: Push to in-process asyncio.Queue (_fallback_mode=True).

    AXL topic config is read from src.config — not hardcoded.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        force_fallback: bool = False,
    ) -> None:
        settings = get_settings()
        self._endpoint = settings.axl_node_b_endpoint.rstrip("/")
        self._topic = settings.axl_topic_route_plan
        self._http = http_client
        self._owns_client = http_client is None
        self._fallback_mode = force_fallback
        self._fallback_counter = 0

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=10.0)
        return self._http

    async def _check_axl_available(self) -> bool:
        """Probe AXL node B to see if it's reachable."""
        try:
            client = await self._get_client()
            resp = await client.get(f"{self._endpoint}/health", timeout=2.0)
            return resp.status_code == 200
        except Exception as exc:
            logger.debug("AXL node B not reachable (%s) — using fallback publish mode", exc)
            return False

    async def publish_route_plan(self, record: DecisionRecord) -> str:
        """Publish a route plan DecisionRecord to xrpfi.route.plan.

        Args:
            record: The DecisionRecord produced by the yield-router after computing
                    the allocation plan.

        Returns:
            AXL message ID string (real ID from AXL, or 'fallback-<n>' in fallback mode).

        In fallback mode, the message is pushed to the in-process asyncio.Queue for
        xrpfi.route.plan, allowing the Orchestrator or downstream consumers to read it.
        """
        if not self._fallback_mode:
            available = await self._check_axl_available()
            if not available:
                self._fallback_mode = True
                logger.warning(
                    "AXL node B (%s) unreachable — switching to fallback publish mode",
                    self._endpoint,
                )

        if self._fallback_mode:
            return await self._publish_fallback(record)
        return await self._publish_axl(record)

    async def _publish_axl(self, record: DecisionRecord) -> str:
        """Primary: POST record to AXL REST API."""
        payload = {
            "topic": self._topic,
            "payload": record.model_dump(mode="json"),
            "message_id": str(uuid.uuid4()),
        }

        logger.info(
            "AXL publisher: posting to %s topic=%s record_id=%s",
            self._endpoint,
            self._topic,
            record.record_id,
        )

        client = await self._get_client()
        resp = await client.post(
            f"{self._endpoint}/publish",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        resp.raise_for_status()

        data: dict[str, Any] = resp.json()
        message_id: str = data.get("message_id", payload["message_id"])
        logger.info("AXL publish OK: message_id=%s", message_id)
        return message_id

    async def _publish_fallback(self, record: DecisionRecord) -> str:
        """Fallback: push to in-process asyncio.Queue for xrpfi.route.plan."""
        self._fallback_counter += 1
        message_id = f"fallback-{self._fallback_counter:06d}"

        queue = get_fallback_queue(self._topic)
        await queue.put({
            "message_id": message_id,
            "topic": self._topic,
            "payload": record.model_dump(mode="json"),
        })

        logger.info(
            "AXL publisher [FALLBACK MODE]: queued message_id=%s topic=%s record_id=%s",
            message_id,
            self._topic,
            record.record_id,
        )
        return message_id

    async def close(self) -> None:
        """Close the underlying HTTP client if we own it."""
        if self._owns_client and self._http is not None:
            await self._http.aclose()
            self._http = None

    @property
    def fallback_mode(self) -> bool:
        """True when operating in local fallback queue mode."""
        return self._fallback_mode
