"""Gensyn AXL node B — subscriber for xrpfi.mint.complete topic.

Cross-node communication pattern:
- AXL node A (mint-helper): publishes to xrpfi.mint.complete
- AXL node B (yield-router): subscribes to xrpfi.mint.complete, then routes

Operation modes:
1. Primary: Gensyn AXL REST API at axl_node_b_endpoint (from config).
2. Fallback: Local async queue with _fallback_mode=True when AXL is unreachable.

Fallback mode is explicitly flagged and documented. Cross-node communication
is demonstrable in fallback mode via a shared in-process queue.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

import httpx

from src.config import get_settings
from src.contracts.decision_log import DecisionRecord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level fallback queue — shared with AxlPublisher in node_a (Lane A).
# In-process simulation: publisher.py in node_a writes here, subscriber reads.
# Key: topic name → asyncio.Queue[dict]
# ---------------------------------------------------------------------------
_FALLBACK_QUEUES: dict[str, asyncio.Queue[dict[str, Any]]] = {}  # noqa: RUF012


def get_fallback_queue(topic: str) -> asyncio.Queue[dict[str, Any]]:
    """Get or create the fallback queue for a given topic."""
    if topic not in _FALLBACK_QUEUES:
        _FALLBACK_QUEUES[topic] = asyncio.Queue()
    return _FALLBACK_QUEUES[topic]


class AxlSubscriber:
    """Subscribes to xrpfi.mint.complete on Gensyn AXL node B.

    Calls handler(record: DecisionRecord) for each received message.

    Primary mode: polls AXL REST API at axl_node_b_endpoint.
    Fallback mode: reads from in-process asyncio.Queue (_fallback_mode=True).

    AXL topic config is read from src.config — not hardcoded.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        force_fallback: bool = False,
    ) -> None:
        settings = get_settings()
        self._endpoint = settings.axl_node_b_endpoint.rstrip("/")
        self._topic = settings.axl_topic_mint_complete
        self._http = http_client
        self._owns_client = http_client is None
        self._fallback_mode = force_fallback
        self._running = False

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=5.0)
        return self._http

    async def _check_axl_available(self) -> bool:
        """Probe AXL node B to see if it's reachable."""
        try:
            client = await self._get_client()
            resp = await client.get(f"{self._endpoint}/health", timeout=2.0)
            return resp.status_code == 200
        except Exception as exc:
            logger.debug("AXL node B not reachable (%s) — falling back to queue mode", exc)
            return False

    async def subscribe_mint_complete(self, handler: Callable[[DecisionRecord], Any]) -> None:
        """Subscribe to xrpfi.mint.complete and call handler for each message.

        Args:
            handler: Async or sync callable that receives a DecisionRecord.
                     Called once per received message.

        This coroutine runs until cancelled. In fallback mode, it drains
        the in-process queue indefinitely (blocks on empty).
        """
        # Detect mode
        if not self._fallback_mode:
            available = await self._check_axl_available()
            if not available:
                self._fallback_mode = True
                logger.warning(
                    "AXL node B (%s) unreachable — switching to fallback queue mode",
                    self._endpoint,
                )

        self._running = True

        if self._fallback_mode:
            await self._subscribe_fallback(handler)
        else:
            await self._subscribe_axl(handler)

    async def _subscribe_axl(self, handler: Callable[[DecisionRecord], Any]) -> None:
        """Primary: poll AXL REST API for messages on the mint.complete topic."""
        logger.info(
            "AXL subscriber: polling %s for topic %s",
            self._endpoint,
            self._topic,
        )
        client = await self._get_client()

        while self._running:
            try:
                resp = await client.get(
                    f"{self._endpoint}/subscribe/{self._topic}",
                    headers={"Accept": "application/json"},
                    timeout=30.0,  # long-poll
                )
                if resp.status_code == 200:
                    data = resp.json()
                    messages = data.get("messages", [data])
                    for msg in messages:
                        record = _deserialize_record(msg)
                        await _call_handler(handler, record)
                elif resp.status_code == 204:
                    # No messages yet — wait briefly
                    await asyncio.sleep(0.5)
                else:
                    logger.warning("AXL poll unexpected status: %d", resp.status_code)
                    await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("AXL subscriber error: %s — retrying in 2s", exc)
                await asyncio.sleep(2.0)

    async def _subscribe_fallback(self, handler: Callable[[DecisionRecord], Any]) -> None:
        """Fallback: drain the in-process asyncio.Queue for the mint.complete topic."""
        logger.info(
            "AXL subscriber [FALLBACK MODE]: reading from in-process queue, topic=%s",
            self._topic,
        )
        queue = get_fallback_queue(self._topic)

        while self._running:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=1.0)
                record = _deserialize_record(msg)
                await _call_handler(handler, record)
                queue.task_done()
            except TimeoutError:
                # Normal — no messages yet; keep polling
                continue
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Fallback subscriber error: %s", exc)

    def stop(self) -> None:
        """Signal the subscription loop to stop."""
        self._running = False

    async def close(self) -> None:
        """Close the underlying HTTP client if we own it."""
        self.stop()
        if self._owns_client and self._http is not None:
            await self._http.aclose()
            self._http = None

    @property
    def fallback_mode(self) -> bool:
        """True when operating in local fallback queue mode."""
        return self._fallback_mode


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _deserialize_record(msg: dict[str, Any]) -> DecisionRecord:
    """Deserialize a raw AXL message payload to a DecisionRecord.

    Handles both wrapped payloads ({"payload": {...}}) and flat DecisionRecord dicts.
    """
    payload = msg.get("payload", msg)
    if isinstance(payload, str):
        # JSON-encoded payload
        payload = json.loads(payload)
    return DecisionRecord(**payload)


async def _call_handler(
    handler: Callable[[DecisionRecord], Any],
    record: DecisionRecord,
) -> None:
    """Call handler with record — supports both async and sync handlers."""
    import inspect

    if inspect.iscoroutinefunction(handler):
        await handler(record)
    else:
        handler(record)
