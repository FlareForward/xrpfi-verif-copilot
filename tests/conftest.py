"""Test configuration and fixtures for XRPFi Verifiable Copilot."""

import pytest


@pytest.fixture(autouse=True)
def clear_axl_fallback_queues():
    """Reset module-level AXL fallback queue registry between tests.

    The _FALLBACK_QUEUES dict in src.gensyn.node_b.subscriber is module-level
    and shared across tests. Each test gets its own asyncio event loop
    (asyncio_default_test_loop_scope=function), so Queue objects created in one
    test's loop become stale in subsequent tests. Clearing the registry ensures
    each test gets fresh Queue instances bound to its own event loop.
    """
    import sys

    yield

    # Post-test cleanup: clear the registry so next test creates fresh Queues
    if "src.gensyn.node_b.subscriber" in sys.modules:
        mod = sys.modules["src.gensyn.node_b.subscriber"]
        if hasattr(mod, "_FALLBACK_QUEUES"):
            mod._FALLBACK_QUEUES.clear()
