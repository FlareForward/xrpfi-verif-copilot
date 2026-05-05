"""Gensyn AXL receipt proof tests for the judge demo."""

from __future__ import annotations

import asyncio
import contextlib
import re
from uuid import UUID

import pytest

from demo.judge_demo import fallback_mint_record, run_axl_receipt
from src.gensyn.node_a.publisher import AXL_TOPIC, AxlPublisher
from src.gensyn.node_b.subscriber import AxlSubscriber


@pytest.mark.asyncio
async def test_node_a_publish_is_received_by_node_b_fallback_queue() -> None:
    """Node A fallback publish lands on Node B's subscribed topic queue."""
    publisher = AxlPublisher()
    subscriber = AxlSubscriber(force_fallback=True)
    record = fallback_mint_record([])
    received = asyncio.get_running_loop().create_future()

    async def handler(received_record):
        if not received.done():
            received.set_result(received_record)

    task = asyncio.create_task(subscriber.subscribe_mint_complete(handler))
    await asyncio.sleep(0)

    try:
        msg_id = await publisher.publish_mint_complete(record)
        received_record = await asyncio.wait_for(received, timeout=1.0)
    finally:
        subscriber.stop()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await subscriber.close()

    assert UUID(msg_id)
    assert received_record.axl_message_id == msg_id
    assert received_record.record_id == record.record_id


@pytest.mark.asyncio
async def test_judge_demo_axl_receipt_includes_message_topic_and_payload() -> None:
    """Step [8] returns the judge-facing Node A -> Node B receipt proof."""
    receipt, warning = await run_axl_receipt(fallback_mint_record([]), fxrp_amount=99.0)

    assert warning is None
    assert f"Node A → Node B: {AXL_TOPIC} ✓" in receipt
    assert f"topic={AXL_TOPIC}" in receipt
    assert "payload={\"fxrp\":99.0}" in receipt

    msg_id_match = re.search(r"msg_id=([0-9a-f-]{36})", receipt)
    assert msg_id_match is not None
    assert UUID(msg_id_match.group(1))
