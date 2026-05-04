"""ENS resolver for yield-router.eth — Agent B identity.

Resolves yield-router.eth to an Ethereum address using the ENS public resolver.
Falls back to a cached address in offline/testnet mode.

Pattern: mirrors Lane A's resolver.py (for mint-helper.eth) but scoped to yield-router.eth.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ENS name and fallback address
# ---------------------------------------------------------------------------
ENS_NAME = "yield-router.eth"

# Fallback address used when ENS is unavailable or in testnet/offline mode.
# Replace with the actual deployed address once yield-router.eth is registered.
FALLBACK_ADDRESS = "0x0000000000000000000000000000000000000002"

# ENS NameHash of "yield-router.eth" (computed per EIP-137)
# Python: eth_ens_namehash.main.ENS.namehash("yield-router.eth")
ENS_NAMEHASH = "0x0000000000000000000000000000000000000000000000000000000000000000"  # placeholder

# Uniswap prize context: ENS registration for yield-router.eth demonstrates
# on-chain identity for autonomous DeFi agents — a key primitive for agent accountability.
ENS_REGISTRATION_NOTE = (
    "yield-router.eth should be registered on ENS (Ethereum Sepolia testnet for hackathon). "
    "Steps: (1) fund address with SepoliaETH, (2) call ENSRegistrarController.register(), "
    "(3) set text records: description, url, agent_type=yield-router. "
    "ENS registry: 0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e (mainnet/Sepolia shared)."
)


class YieldRouterEnsResolver:
    """Resolves yield-router.eth to an on-chain address via ENS.

    Two operation modes:
    - Online: Uses Web3.py + ENS public resolver on Ethereum mainnet or Sepolia.
    - Offline/fallback: Returns FALLBACK_ADDRESS with a warning log.

    The fallback is explicitly flagged so callers can distinguish resolved vs. cached addresses.
    """

    def __init__(self, rpc_url: str | None = None) -> None:
        from src.config import get_settings

        settings = get_settings()
        self._rpc_url = rpc_url or settings.eth_rpc_url
        self._resolved_address: str | None = None
        self._fallback_mode = False

    async def resolve(self) -> str:
        """Resolve yield-router.eth to an Ethereum address.

        Returns:
            Checksummed Ethereum address string.

        Resolution order:
            1. Cached address (if already resolved this session).
            2. Live ENS resolution via Web3.
            3. Fallback address (if ENS resolution fails).
        """
        if self._resolved_address is not None:
            return self._resolved_address

        try:
            address = await self._resolve_via_web3()
            self._resolved_address = address
            self._fallback_mode = False
            logger.info("ENS resolved %s -> %s", ENS_NAME, address)
            return address
        except Exception as exc:
            logger.warning(
                "ENS resolution failed for %s (%s) — using fallback address %s",
                ENS_NAME,
                exc,
                FALLBACK_ADDRESS,
            )
            self._resolved_address = FALLBACK_ADDRESS
            self._fallback_mode = True
            return FALLBACK_ADDRESS

    async def _resolve_via_web3(self) -> str:
        """Attempt live ENS resolution via Web3.py.

        Raises:
            Exception: If Web3 or ENS resolution fails.
        """
        try:
            from web3 import AsyncWeb3
            from web3.middleware import ExtraDataToPOAMiddleware  # type: ignore[attr-defined]
        except ImportError as exc:
            raise ImportError("web3 not installed — run: pip install web3") from exc

        w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(self._rpc_url))

        # ENS resolution via web3.py ns module
        try:
            address = await w3.ens.address(ENS_NAME)  # type: ignore[attr-defined]
        except AttributeError:
            # Older web3.py versions use different API
            address = await w3.eth.resolve_address(ENS_NAME)  # type: ignore[attr-defined]

        if address is None:
            raise ValueError(f"ENS name {ENS_NAME!r} not registered or has no address record")

        return str(address)

    @property
    def is_fallback(self) -> bool:
        """True if the last resolve() call used the fallback address."""
        return self._fallback_mode

    def get_registration_info(self) -> dict[str, Any]:
        """Return ENS registration guidance for yield-router.eth.

        Useful for building the submission packet or README.
        """
        return {
            "ens_name": ENS_NAME,
            "ens_namehash": ENS_NAMEHASH,
            "fallback_address": FALLBACK_ADDRESS,
            "registration_note": ENS_REGISTRATION_NOTE,
            "testnet": "sepolia",
            "mainnet_registry": "0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e",
            "text_records": {
                "description": "Autonomous yield routing agent for Flare DeFi (XRPFi Copilot)",
                "url": "https://github.com/flare-forward/xrpfi-verif-copilot",
                "agent_type": "yield-router",
                "version": "0.1.0",
            },
        }
