"""ENS (Ethereum Name Service) resolver.

Performs forward and reverse ENS resolution using web3.py against
Ethereum mainnet. Resolution is always dynamic — addresses are never
hardcoded. If a name is not registered (e.g. during hackathon dev),
the resolver falls back to a configurable test address and logs a
prominent warning so the team is always aware.

Note: ``mint-helper.eth`` may not be registered on mainnet during the
hackathon. The fallback address is used in that case (see TEST_ADDRESSES).
The fallback path MUST still exercise the resolution code path (no
short-circuit to a constant).
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, cast

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ETH_MAINNET_RPC = "https://eth.llamarpc.com"

# ENS Registry on Ethereum mainnet (canonical, never changes)
ENS_REGISTRY_ADDRESS = "0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e"

# Well-known test addresses to use as fallback when a name is not registered.
# These are public Ethereum addresses with no private keys — safe for tests.
TEST_ADDRESSES: dict[str, str] = {
    "mint-helper.eth": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",  # vitalik.eth
    "yield-router.eth": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",  # public placeholder
}

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


class EnsResolver:
    """Dynamic ENS name resolver using direct ENS contract calls.

    Uses web3.py's ENS module when available, falls back to direct
    JSON-RPC eth_call for maximum portability.

    Usage::

        resolver = EnsResolver()
        address = await resolver.resolve("mint-helper.eth")
        name = await resolver.reverse_resolve("0xd8dA6BF...")
    """

    def __init__(
        self,
        rpc_url: str = ETH_MAINNET_RPC,
        timeout: float = 15.0,
        sepolia_rpc_url: str | None = None,
    ) -> None:
        self._rpc_url = rpc_url
        self._timeout = timeout
        # Sepolia fallback: if set, live resolution is attempted there too.
        # Names registered on Sepolia count as is_live=True for hackathon demos.
        self._sepolia_rpc_url = sepolia_rpc_url
        self._w3: object | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_web3(self) -> object | None:
        """Lazy-init web3 with ENS middleware if available."""
        if self._w3 is not None:
            return self._w3

        try:
            from web3 import Web3
            from web3.middleware import ExtraDataToPOAMiddleware

            w3 = Web3(Web3.HTTPProvider(self._rpc_url))
            # Inject POA middleware for compatibility
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            self._w3 = w3
            logger.debug("web3 initialised with provider %s", self._rpc_url)
        except ImportError:
            logger.warning("web3 not installed — ENS resolution will use JSON-RPC stub")
            self._w3 = None
        return self._w3

    @staticmethod
    def _namehash(name: str) -> bytes:
        """Compute ENS namehash for a given name.

        Implements EIP-137: namehash(name) = keccak256(namehash(parent) + keccak256(label))
        """
        from web3 import Web3
        node = b"\x00" * 32
        if not name:
            return node
        labels = name.split(".")
        for label in reversed(labels):
            label_hash = Web3.keccak(text=label)
            node = Web3.keccak(node + label_hash)
        return node

    def _namehash_hex(self, name: str) -> str:
        """Return namehash as 0x-prefixed hex string."""
        return "0x" + self._namehash(name).hex()

    async def _eth_call(self, to: str, data: str) -> str:
        """Direct JSON-RPC eth_call."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_call",
            "params": [{"to": to, "data": data}, "latest"],
        }
        async with httpx.AsyncClient(timeout=self._timeout) as http:
            resp = await http.post(self._rpc_url, json=payload)
            resp.raise_for_status()
            body = cast(dict[str, Any], resp.json())
            if "error" in body:
                raise RuntimeError(f"eth_call error: {body['error']}")
            return str(body["result"])

    async def _resolve_via_web3(self, name: str) -> str | None:
        """Attempt ENS resolution via web3.py ENS module."""
        w3 = self._get_web3()
        if w3 is None:
            return None

        try:
            # Use web3.py's built-in ENS lookup
            ens = w3.ens  # type: ignore[attr-defined]
            if ens is None:
                return None
            maybe_address = ens.address(name)
            address = cast(
                str | None,
                await maybe_address if inspect.isawaitable(maybe_address) else maybe_address,
            )
            return address if address and address != ZERO_ADDRESS else None
        except Exception as exc:
            logger.debug("web3 ENS resolution failed for %s: %s", name, exc)
            return None

    async def _resolve_via_rpc(self, name: str) -> str | None:
        """Resolve ENS name via direct JSON-RPC call to ENS Registry.

        Two-step: (1) registry.resolver(node) → resolver address,
        (2) resolver.addr(node) → address.
        """
        node_hex = self._namehash_hex(name)
        node_bytes = node_hex[2:].ljust(64, "0")  # pad to 32 bytes

        # Step 1: ENS Registry resolver(bytes32 node) — selector: 0x0178b8bf
        try:
            resolver_result = await self._eth_call(
                ENS_REGISTRY_ADDRESS,
                "0x0178b8bf" + node_bytes,
            )
            resolver_address = "0x" + resolver_result.replace("0x", "")[-40:]

            if resolver_address == ZERO_ADDRESS or resolver_address == "0x" + "0" * 40:
                logger.debug("No resolver set for %s", name)
                return None

            # Step 2: PublicResolver addr(bytes32 node) — selector: 0x3b3b57de
            addr_result = await self._eth_call(
                resolver_address,
                "0x3b3b57de" + node_bytes,
            )
            address = "0x" + addr_result.replace("0x", "")[-40:]
            if address == ZERO_ADDRESS or address == "0x" + "0" * 40:
                return None
            return address

        except Exception as exc:
            logger.debug("RPC ENS resolution failed for %s: %s", name, exc)
            return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def resolve_with_status(self, name: str) -> tuple[str, bool]:
        """Resolve an ENS name and report whether the result is live.

        Resolution order:
        1. Try web3.py ENS module (if web3 installed).
        2. Try direct JSON-RPC calls to ENS Registry + Resolver contracts.
        3. If name is in TEST_ADDRESSES fallback map and neither resolved,
           use the test address and log a warning.
        4. Raise ValueError if no resolution is possible.

        Args:
            name: ENS name, e.g. "mint-helper.eth".

        Returns:
            Tuple of (checksummed Ethereum address, is_live). ``is_live`` is
            False only when the returned address came from TEST_ADDRESSES.

        Raises:
            ValueError: if name cannot be resolved and no fallback exists.
        """
        logger.info("ENS: resolve_with_status(%s)", name)

        # Attempt live resolution (mainnet)
        address = await self._resolve_via_web3(name)

        if address is None:
            address = await self._resolve_via_rpc(name)

        if address is not None:
            logger.info("ENS: %s → %s (live, mainnet)", name, address)
            return address, True

        # Try Sepolia if configured — names registered on testnet count as live
        # for hackathon / pre-production demos.
        if self._sepolia_rpc_url:
            try:
                sepolia_resolver = EnsResolver(rpc_url=self._sepolia_rpc_url, timeout=self._timeout)
                address = await sepolia_resolver._resolve_via_rpc(name)
                if address is not None:
                    logger.info("ENS: %s → %s (live, sepolia)", name, address)
                    return address, True
            except Exception as exc:
                logger.debug("ENS: Sepolia resolution failed for %s: %s", name, exc)

        # Fallback for unregistered hackathon names
        if name in TEST_ADDRESSES:
            fallback = TEST_ADDRESSES[name]
            logger.warning(
                "ENS: %s not registered on mainnet — using test fallback %s. "
                "Register the name before production deployment.",
                name, fallback,
            )
            return fallback, False

        raise ValueError(
            f"ENS: could not resolve {name!r} — not registered and no test fallback defined."
        )

    async def resolve(self, name: str) -> str:
        """Resolve an ENS name to an Ethereum address (forward resolution).

        See ``resolve_with_status`` for the status-aware form.
        """
        address, _is_live = await self.resolve_with_status(name)
        return address

    async def reverse_resolve(self, address: str) -> str:
        """Reverse-resolve an Ethereum address to an ENS name.

        Looks up the <address>.addr.reverse ENS record.

        Args:
            address: Checksummed or lowercase Ethereum address.

        Returns:
            ENS name if reverse record is set, empty string otherwise.
        """
        logger.info("ENS: reverse_resolve(%s)", address)

        # Reverse node: <address without 0x>.addr.reverse
        addr_lower = address.lower().removeprefix("0x")
        reverse_name = f"{addr_lower}.addr.reverse"

        w3 = self._get_web3()
        if w3 is not None:
            try:
                ens = w3.ens  # type: ignore[attr-defined]
                if ens is not None:
                    maybe_name = ens.name(address)
                    name: str | None = (
                        await maybe_name if inspect.isawaitable(maybe_name) else maybe_name
                    )
                    if name:
                        logger.info("ENS reverse: %s → %s", address, name)
                        return name
            except Exception as exc:
                logger.debug("web3 reverse resolve failed: %s", exc)

        # Direct RPC fallback: resolve reverse node to get name
        try:
            node_hex = self._namehash_hex(reverse_name)
            node_bytes = node_hex[2:].ljust(64, "0")

            # Step 1: get resolver
            resolver_result = await self._eth_call(
                ENS_REGISTRY_ADDRESS,
                "0x0178b8bf" + node_bytes,
            )
            resolver_address = "0x" + resolver_result.replace("0x", "")[-40:]

            if resolver_address == ZERO_ADDRESS or resolver_address == "0x" + "0" * 40:
                logger.debug("No reverse record set for %s", address)
                return ""

            # Step 2: call name(bytes32) — selector: 0x691f3431
            name_result = await self._eth_call(
                resolver_address,
                "0x691f3431" + node_bytes,
            )
            # Decode ABI-encoded string: offset(32) + length(32) + data
            clean = name_result.replace("0x", "")
            if len(clean) > 128:
                name_len = int(clean[64:128], 16)
                name_hex = clean[128: 128 + name_len * 2]
                resolved_name = bytes.fromhex(name_hex).decode("utf-8", errors="replace")
                if resolved_name:
                    logger.info("ENS reverse (RPC): %s → %s", address, resolved_name)
                    return resolved_name
        except Exception as exc:
            logger.debug("RPC reverse resolve failed for %s: %s", address, exc)

        return ""

    def get_test_addresses(self) -> dict[str, str]:
        """Return the configured fallback test addresses (informational)."""
        return dict(TEST_ADDRESSES)
