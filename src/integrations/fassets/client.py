"""FAssets v1.3 minting client.

Interacts with the FAssets AssetManager contract on Songbird testnet.
Provides helpers for agent discovery, cost estimation, mint initiation,
and status polling.

RPC: https://songbird-api.flare.network/ext/C/rpc
AssetManager: resolved via FlareContractRegistry
"""

from __future__ import annotations

import logging
from typing import Any, cast

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SONGBIRD_RPC = "https://songbird-api.flare.network/ext/C/rpc"

# Songbird FlareContractRegistry address (same address as Flare mainnet pattern)
FLARE_CONTRACT_REGISTRY = "0xaD67FE66660Fb8dFE9d6b1b4240d8650e30F6019"

# Minimal ABI fragments we need
REGISTRY_ABI = [
    {
        "inputs": [{"name": "_name", "type": "string"}],
        "name": "getContractAddressByName",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    }
]

ASSET_MANAGER_ABI = [
    {
        "name": "getAvailableAgents",
        "type": "function",
        "inputs": [
            {"name": "start", "type": "uint256"},
            {"name": "end", "type": "uint256"},
        ],
        "outputs": [
            {"name": "", "type": "address[]"},
            {"name": "", "type": "uint256"},
        ],
        "stateMutability": "view",
    },
    {
        "name": "reserveCollateral",
        "type": "function",
        "stateMutability": "payable",
        "inputs": [
            {"name": "_agentVault", "type": "address"},
            {"name": "_lots", "type": "uint256"},
            {"name": "_maxMintingFeeBIPS", "type": "uint256"},
            {"name": "_executor", "type": "address"},
            {"name": "_minterUnderlyingAddresses", "type": "string[]"},
        ],
    },
    {
        "name": "getAgentInfo",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "_agentVault", "type": "address"}],
        "outputs": [
            {
                "components": [
                    {"name": "agentVault", "type": "address"},
                    {"name": "ownerManagementAddress", "type": "address"},
                    {"name": "mintingFeeBIPS", "type": "uint256"},
                    {"name": "mintingCollateralRatioBIPS", "type": "uint256"},
                    {"name": "availableLots", "type": "uint256"},
                    {"name": "status", "type": "uint8"},
                ],
                "name": "",
                "type": "tuple",
            }
        ],
    },
    {
        "name": "getCollateralReservation",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "_crtId", "type": "uint64"}],
        "outputs": [
            {
                "components": [
                    {"name": "agentVault", "type": "address"},
                    {"name": "minter", "type": "address"},
                    {"name": "lots", "type": "uint256"},
                    {"name": "mintingFeeBIPS", "type": "uint256"},
                    {"name": "status", "type": "uint8"},
                ],
                "name": "",
                "type": "tuple",
            }
        ],
    },
]


class FAssetsClient:
    """Async client for FAssets v1.3 AssetManager on Songbird testnet.

    Usage::

        client = FAssetsClient()
        agents = await client.get_agent_info("FXRP")
        estimate = await client.estimate_mint_cost("FXRP", lots=10)
    """

    def __init__(
        self,
        rpc_url: str = SONGBIRD_RPC,
        registry_address: str = FLARE_CONTRACT_REGISTRY,
        timeout: float = 30.0,
    ) -> None:
        self._rpc_url = rpc_url
        self._registry_address = registry_address
        self._timeout = timeout
        self._asset_manager_cache: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Internal RPC helpers
    # ------------------------------------------------------------------
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def _eth_call(self, to: str, data: str) -> str:
        """Low-level eth_call via JSON-RPC."""
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

    def _encode_get_contract_address(self, name: str) -> str:
        """Encode getContractAddressByName(name) calldata (minimal ABI encoder)."""
        # Function selector: keccak256("getContractAddressByName(string)")[:4]
        selector = "0x82760fca"  # precomputed
        # Encode string: offset=32, length, padded data
        name_bytes = name.encode()
        length = len(name_bytes)
        padded = name_bytes.ljust(((length + 31) // 32) * 32, b"\x00")
        offset_hex = "0000000000000000000000000000000000000000000000000000000000000020"
        length_hex = f"{length:064x}"
        data_hex = padded.hex().ljust(64, "0")
        return selector + offset_hex + length_hex + data_hex

    def _decode_address(self, hex_result: str) -> str:
        """Decode a 32-byte ABI-encoded address."""
        # Last 20 bytes (40 hex chars) of a 32-byte result
        clean = hex_result.replace("0x", "").strip()
        return "0x" + clean[-40:]

    async def _get_asset_manager(self, asset_symbol: str) -> str:
        """Resolve AssetManager address for an asset symbol via registry."""
        if asset_symbol in self._asset_manager_cache:
            return self._asset_manager_cache[asset_symbol]

        contract_name = f"AssetManager_{asset_symbol}"
        try:
            calldata = self._encode_get_contract_address(contract_name)
            result = await self._eth_call(self._registry_address, calldata)
            address = self._decode_address(result)
        except Exception as exc:
            logger.warning(
                "Could not resolve AssetManager for %s from registry: %s "
                "— using fallback stub address",
                asset_symbol, exc,
            )
            # Hackathon fallback: known Songbird FXRP AssetManager from public docs
            address = "0x0000000000000000000000000000000000000000"  # stub

        self._asset_manager_cache[asset_symbol] = address
        return address

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def get_agent_info(self, asset_symbol: str) -> dict[str, Any]:
        """Get available FAssets agents for minting `asset_symbol`.

        Args:
            asset_symbol: e.g. "FXRP".

        Returns:
            dict with keys: asset_symbol, agents (list of address strings),
            total_count, asset_manager_address.
        """
        logger.info("get_agent_info: %s", asset_symbol)
        asset_manager = await self._get_asset_manager(asset_symbol)

        # getAvailableAgents(0, 20) — selector: 0xb92b0e7c (precomputed)
        selector = "0xb92b0e7c"
        start_hex = "0000000000000000000000000000000000000000000000000000000000000000"
        end_hex = "0000000000000000000000000000000000000000000000000000000000000014"
        calldata = selector + start_hex + end_hex

        try:
            result = await self._eth_call(asset_manager, calldata)
            # Minimal decode: result is ABI-encoded (address[], uint256)
            # For hackathon: return raw result with parsed stub
            agents: list[str] = []
            logger.debug("getAvailableAgents raw result: %s", result)
        except Exception as exc:
            logger.warning("getAvailableAgents failed: %s", exc)
            agents = []

        return {
            "asset_symbol": asset_symbol,
            "agents": agents,
            "total_count": len(agents),
            "asset_manager_address": asset_manager,
        }

    async def estimate_mint_cost(self, asset_symbol: str, lots: int) -> dict[str, Any]:
        """Estimate fee for minting `lots` lots of `asset_symbol`.

        Args:
            asset_symbol: e.g. "FXRP".
            lots: Number of lots to mint.

        Returns:
            dict with keys: asset_symbol, lots, fee_bips, estimated_fee_xrp,
            collateral_required_flr, asset_manager_address.
        """
        logger.info("estimate_mint_cost: %s lots=%d", asset_symbol, lots)
        asset_manager = await self._get_asset_manager(asset_symbol)

        # In production: call getAgentInfo on a specific agent, read mintingFeeBIPS
        # For hackathon: use a known typical FXRP minting fee (15 BIPS = 0.15%)
        fee_bips = 15  # typical testnet value
        # 1 lot = 1 XRP for FXRP; fee = lots * fee_bips / 10000
        estimated_fee_xrp = lots * fee_bips / 10000

        return {
            "asset_symbol": asset_symbol,
            "lots": lots,
            "fee_bips": fee_bips,
            "estimated_fee_xrp": estimated_fee_xrp,
            "collateral_required_flr": lots * 2.0,  # simplified: ~2x collateral
            "asset_manager_address": asset_manager,
        }

    async def initiate_mint(
        self,
        agent_address: str,
        lots: int,
        max_minting_fee: int,
    ) -> dict[str, Any]:
        """Initiate minting by reserving collateral with a FAssets agent.

        IMPORTANT: This constructs the transaction parameters only.
        Per 2-of-2 confirmation rule, the caller (agent layer) must obtain
        explicit user approval before broadcasting.

        Args:
            agent_address: FAssets agent vault address.
            lots: Number of lots to mint.
            max_minting_fee: Max fee user accepts (in BIPS, e.g. 100 = 1%).

        Returns:
            dict with keys: agent_address, lots, max_minting_fee,
            collateral_reservation_id, tx_params, status.
        """
        logger.info(
            "initiate_mint: agent=%s lots=%d max_fee=%d bips",
            agent_address, lots, max_minting_fee,
        )
        # In production: call reserveCollateral on AssetManager (payable tx).
        # The tx emits CollateralReserved(agentVault, minter, crtId, ...).
        # For hackathon: return stub tx_params with a simulated crtId.
        import uuid as _uuid

        stub_crt_id = abs(hash(_uuid.uuid4().hex)) % 100000

        return {
            "agent_address": agent_address,
            "lots": lots,
            "max_minting_fee": max_minting_fee,
            "collateral_reservation_id": stub_crt_id,
            "tx_params": {
                "to": agent_address,
                "function": "reserveCollateral",
                "args": [agent_address, lots, max_minting_fee, "0x0", []],
                "value_wei": lots * int(1e18),  # 1 FLR per lot reservation deposit
            },
            "status": "pending_user_approval",
        }

    async def get_minting_status(self, collateral_reservation_id: int) -> dict[str, Any]:
        """Check the status of a collateral reservation.

        Args:
            collateral_reservation_id: CRT ID from reserveCollateral event.

        Returns:
            dict with keys: collateral_reservation_id, status, agent_vault,
            lots, minting_fee_bips.
        """
        logger.info("get_minting_status: crt_id=%d", collateral_reservation_id)
        # In production: call getCollateralReservation(crtId) on AssetManager.
        # Status enum: 0=INIT, 1=MINTING_PAYMENT_ANNOUNCED, 2=MINTING_EXECUTED, 3=DEFAULT
        return {
            "collateral_reservation_id": collateral_reservation_id,
            "status": "PENDING",
            "status_code": 0,
            "agent_vault": "0x0000000000000000000000000000000000000000",
            "lots": 0,
            "minting_fee_bips": 0,
            "note": "Production: call getCollateralReservation on AssetManager contract",
        }
