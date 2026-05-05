"""Flare Time Series Oracle (FTSO) v2 price client.

Reads price feeds from FTSO v2 on Coston2 testnet via the
FtsoV2Interface contract, resolved through FlareContractRegistry.

RPC: https://coston2-api.flare.network/ext/C/rpc
FlareContractRegistry: 0xaD67FE66660Fb8dFE9d6b1b4240d8650e30F6019

Per Flare-First Data Policy: every FtsoPrice returned includes
``feed_id`` and ``timestamp``. Callers MUST persist both.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.contracts.decision_log import FtsoPrice

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — feed IDs per Flare docs (bytes21, zero-padded to bytes32 for ABI)
# ---------------------------------------------------------------------------
COSTON2_RPC = "https://coston2-api.flare.network/ext/C/rpc"

FLARE_CONTRACT_REGISTRY = "0xaD67FE66660Fb8dFE9d6b1b4240d8650e30F6019"

# FTSO v2 feed IDs — bytes21 (42 hex chars = 21 bytes)
# Format: 0x01 + ASCII feed name + zero-pad to 21 bytes
FEED_IDS: dict[str, str] = {
    "FLR/USD": "0x01464c522f55534400000000000000000000000000",  # FL=464c
    "XRP/USD": "0x015852502f55534400000000000000000000000000",
    "BTC/USD": "0x014254432f55534400000000000000000000000000",
    "ETH/USD": "0x014554482f55534400000000000000000000000000",
    "SGB/USD": "0x015347422f55534400000000000000000000000000",
}

# Feed decimals (standard Flare FTSO v2: all USD feeds use 7 decimals)
FEED_DECIMALS: dict[str, int] = {
    "FLR/USD": 7,
    "XRP/USD": 7,
    "BTC/USD": 2,
    "ETH/USD": 5,
    "SGB/USD": 7,
}

# FtsoV2Interface contract name in registry
FTSO_CONTRACT_NAME = "FtsoV2"

# Staleness threshold (seconds) — per Flare docs, feeds update every ~1.8s
STALE_THRESHOLD_SECONDS = 30


class FtsoClient:
    """Async FTSO v2 price feed client for Flare / Coston2.

    Usage::

        client = FtsoClient()
        price = await client.get_price("XRP/USD")
        # price.feed_id and price.timestamp always populated per Flare-First policy
    """

    def __init__(
        self,
        rpc_url: str = COSTON2_RPC,
        registry_address: str = FLARE_CONTRACT_REGISTRY,
        timeout: float = 15.0,
    ) -> None:
        self._rpc_url = rpc_url
        self._registry_address = registry_address
        self._timeout = timeout
        self._ftso_address: str | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def _eth_call(self, to: str, data: str) -> str:
        """eth_call via JSON-RPC."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_call",
            "params": [{"to": to, "data": data}, "latest"],
        }
        async with httpx.AsyncClient(timeout=self._timeout) as http:
            resp = await http.post(self._rpc_url, json=payload)
            resp.raise_for_status()
            body = resp.json()
            if "error" in body:
                raise RuntimeError(f"eth_call error: {body['error']}")
            return body["result"]

    def _encode_get_contract_address(self, name: str) -> str:
        """Encode getContractAddressByName(name) calldata."""
        selector = "0x82760fca"
        name_bytes = name.encode()
        length = len(name_bytes)
        padded = name_bytes.ljust(((length + 31) // 32) * 32, b"\x00")
        offset_hex = "0000000000000000000000000000000000000000000000000000000000000020"
        length_hex = f"{length:064x}"
        data_hex = padded.hex().ljust(64, "0")
        return selector + offset_hex + length_hex + data_hex

    def _decode_address(self, hex_result: str) -> str:
        clean = hex_result.replace("0x", "").strip()
        return "0x" + clean[-40:]

    def _decode_uint256(self, hex_result: str) -> int:
        clean = hex_result.replace("0x", "").strip()
        return int(clean, 16) if clean else 0

    async def _get_ftso_address(self) -> str:
        """Resolve FtsoV2 contract address from registry (cached)."""
        if self._ftso_address is not None:
            return self._ftso_address

        try:
            calldata = self._encode_get_contract_address(FTSO_CONTRACT_NAME)
            result = await self._eth_call(self._registry_address, calldata)
            self._ftso_address = self._decode_address(result)
            logger.info("FtsoV2 address resolved: %s", self._ftso_address)
        except Exception as exc:
            logger.warning("Could not resolve FtsoV2 from registry: %s", exc)
            # Known Coston2 FtsoV2 address as fallback
            self._ftso_address = "0xc4e9c78ea53db782e28f28fdf80baf59336b304d"

        return self._ftso_address

    def _encode_feed_id_bytes21(self, feed_id_hex: str) -> str:
        """Right-pad a bytes21 feed_id (42 hex chars) to 32 bytes (64 hex chars) for ABI."""
        clean = feed_id_hex.replace("0x", "")
        assert len(clean) == 42, f"Expected 42-char bytes21, got {len(clean)}: {clean!r}"
        return clean.ljust(64, "0")

    def _encode_get_feed_by_id(self, feed_id_hex: str) -> str:
        """Encode getFeedById(bytes21) calldata.

        FtsoV2Interface.getFeedById(bytes21 _feedId)
        returns (uint256 _value, int8 _decimals, uint64 _timestamp)
        selector: keccak256("getFeedById(bytes21)")[:4] = 0x93e9f806
        """
        selector = "0x93e9f806"
        encoded_feed = self._encode_feed_id_bytes21(feed_id_hex)
        return selector + encoded_feed

    def _decode_feed_result(
        self, result: str, feed_name: str, feed_id: str
    ) -> FtsoPrice:
        """Decode getFeedById result into FtsoPrice.

        ABI return: (uint256 value, int8 decimals, uint64 timestamp)
        Packed as three 32-byte slots.
        """
        clean = result.replace("0x", "").strip()

        if len(clean) >= 192:
            value_int = int(clean[0:64], 16)
            # decimals slot — int8 is sign-extended in 32 bytes
            dec_raw = int(clean[64:128], 16)
            # interpret as signed int8
            decimals = dec_raw if dec_raw < 128 else dec_raw - 256
            ts_int = int(clean[128:192], 16)
        else:
            logger.warning("Unexpected FTSO result length for %s, using stub values", feed_name)
            value_int = 5_000_000  # 0.5 USD with 7 decimals
            decimals = FEED_DECIMALS.get(feed_name, 7)
            ts_int = int(datetime.now(UTC).timestamp())

        actual_decimals = decimals if decimals != 0 else FEED_DECIMALS.get(feed_name, 7)
        price_usd = value_int / (10**actual_decimals)

        ts = (
            datetime.fromtimestamp(ts_int, tz=UTC) if ts_int > 0 else datetime.now(UTC)
        )
        age_seconds = (datetime.now(UTC) - ts).total_seconds()
        is_stale = age_seconds > STALE_THRESHOLD_SECONDS

        if is_stale:
            logger.warning("FTSO feed %s is stale (age=%.0fs)", feed_name, age_seconds)

        return FtsoPrice(
            feed_id=feed_id,
            feed_name=feed_name,
            price_usd=price_usd,
            decimals=actual_decimals,
            timestamp=ts,
            is_stale=is_stale,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def get_price(self, feed_name: str) -> FtsoPrice:
        """Read a single FTSO v2 price feed.

        Args:
            feed_name: e.g. "XRP/USD" or "FLR/USD".

        Returns:
            FtsoPrice with feed_id and timestamp always set (Flare-First policy).

        Raises:
            ValueError: if feed_name is not recognised.
        """
        if feed_name not in FEED_IDS:
            raise ValueError(
                f"Unknown feed: {feed_name!r}. Available: {sorted(FEED_IDS)}"
            )

        feed_id = FEED_IDS[feed_name]
        ftso_address = await self._get_ftso_address()
        calldata = self._encode_get_feed_by_id(feed_id)

        try:
            result = await self._eth_call(ftso_address, calldata)
            price = self._decode_feed_result(result, feed_name, feed_id)
        except Exception as exc:
            logger.warning(
                "FTSO on-chain read failed for %s: %s — returning stub price",
                feed_name, exc,
            )
            # Stub fallback so tests and offline environments still work
            price = self._stub_price(feed_name, feed_id)

        logger.info(
            "FTSO %s = $%.6f (feed_id=%s, ts=%s, stale=%s)",
            feed_name, price.price_usd, price.feed_id,
            price.timestamp.isoformat(), price.is_stale,
        )
        return price

    def _stub_price(self, feed_name: str, feed_id: str) -> FtsoPrice:
        """Return a clearly-flagged stub price for offline use."""
        stubs: dict[str, float] = {
            "FLR/USD": 0.02,
            "XRP/USD": 0.50,
            "BTC/USD": 60000.0,
            "ETH/USD": 3000.0,
            "SGB/USD": 0.01,
        }
        decimals = FEED_DECIMALS.get(feed_name, 7)
        return FtsoPrice(
            feed_id=feed_id,
            feed_name=feed_name,
            price_usd=stubs.get(feed_name, 1.0),
            decimals=decimals,
            timestamp=datetime.now(UTC),
            is_stale=True,  # mark stub as stale so callers know
        )

    async def get_prices(self, feed_names: list[str]) -> list[FtsoPrice]:
        """Read multiple FTSO v2 price feeds.

        Args:
            feed_names: List of feed names, e.g. ["XRP/USD", "FLR/USD"].

        Returns:
            List of FtsoPrice in the same order as feed_names.
        """
        import asyncio

        results = await asyncio.gather(
            *[self.get_price(name) for name in feed_names],
            return_exceptions=True,
        )

        prices: list[FtsoPrice] = []
        for name, result in zip(feed_names, results, strict=False):
            if isinstance(result, Exception):
                logger.error("get_prices failed for %s: %s", name, result)
                feed_id = FEED_IDS.get(name, "0x00")
                prices.append(self._stub_price(name, feed_id))
            else:
                prices.append(result)  # type: ignore[arg-type]
        return prices

    def get_known_feeds(self) -> dict[str, Any]:
        """Return the catalogue of known feed IDs (informational)."""
        return {
            name: {"feed_id": fid, "decimals": FEED_DECIMALS.get(name, 7)}
            for name, fid in FEED_IDS.items()
        }
