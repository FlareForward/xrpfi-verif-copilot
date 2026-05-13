from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_resolve_with_status_marks_fallback_as_not_live() -> None:
    from src.integrations.ens.resolver import TEST_ADDRESSES, EnsResolver

    resolver = EnsResolver()

    with patch.object(
        resolver, "_resolve_via_web3", new_callable=AsyncMock, return_value=None
    ), patch.object(
        resolver, "_resolve_via_rpc", new_callable=AsyncMock, return_value=None
    ):
        address, is_live = await resolver.resolve_with_status("mint-helper.eth")

    assert address == TEST_ADDRESSES["mint-helper.eth"]
    assert is_live is False


@pytest.mark.asyncio
async def test_resolve_with_status_marks_mocked_resolution_as_live() -> None:
    from src.integrations.ens.resolver import EnsResolver

    live_address = "0x71C7656EC7ab88b098defB751B7401B5f6d8976F"
    resolver = EnsResolver()

    with patch.object(
        resolver, "_resolve_via_web3", new_callable=AsyncMock, return_value=live_address
    ), patch.object(
        resolver, "_resolve_via_rpc", new_callable=AsyncMock, return_value=None
    ):
        address, is_live = await resolver.resolve_with_status("mint-helper.eth")

    assert address == live_address
    assert is_live is True


@pytest.mark.asyncio
async def test_resolve_preserves_address_only_api() -> None:
    from src.integrations.ens.resolver import EnsResolver

    live_address = "0x71C7656EC7ab88b098defB751B7401B5f6d8976F"
    resolver = EnsResolver()

    with patch.object(
        resolver, "_resolve_via_web3", new_callable=AsyncMock, return_value=None
    ), patch.object(
        resolver, "_resolve_via_rpc", new_callable=AsyncMock, return_value=live_address
    ):
        address = await resolver.resolve("mint-helper.eth")

    assert address == live_address
