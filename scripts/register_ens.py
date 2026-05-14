"""Register XRPFi agent ENS names on Ethereum Sepolia.

This script performs the ENS .eth controller flow:

1. Generate or accept a bytes32 commitment secret.
2. Call ETHRegistrarController.makeCommitment(...).
3. Submit commit(commitment).
4. Wait for the controller's minimum commitment age.
5. Register the name with a PublicResolver addr(bytes32) setup call.
6. Verify resolver + addr records on-chain.

The script refuses to transact when the configured wallet has less than
0.05 Sepolia ETH unless --allow-low-balance is passed.
"""

from __future__ import annotations

import argparse
import secrets
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import Web3
from web3.contract.contract import Contract
from web3.types import TxParams, Wei

from src.config import get_settings
from src.integrations.ens.resolver import EnsResolver

ETH_REGISTRAR_CONTROLLER: Final = "0xfb3cE5D01e0f33f41DbB39035dB9745962F1f968"
PUBLIC_RESOLVER: Final = "0xE99638b40E4Fff0129D56f03b55b6bbC4BBE49b5"
REGISTRATION_DURATION_SECONDS: Final = 31_536_000
MIN_BALANCE_ETH: Final = Decimal("0.05")
NAMES: Final = ("mint-helper", "yield-router")
type PriceResponse = tuple[int, int] | list[int] | dict[str, int] | int

_REGISTRATION_STRUCT: Final[list[dict[str, object]]] = [
    {"internalType": "string", "name": "label", "type": "string"},
    {"internalType": "address", "name": "owner", "type": "address"},
    {"internalType": "uint256", "name": "duration", "type": "uint256"},
    {"internalType": "bytes32", "name": "secret", "type": "bytes32"},
    {"internalType": "address", "name": "resolver", "type": "address"},
    {"internalType": "bytes[]", "name": "data", "type": "bytes[]"},
    {"internalType": "uint8", "name": "reverseRecord", "type": "uint8"},
    {"internalType": "bytes32", "name": "referrer", "type": "bytes32"},
]

CONTROLLER_ABI: Final[list[dict[str, object]]] = [
    {
        "inputs": [{"internalType": "string", "name": "label", "type": "string"}],
        "name": "available",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "minCommitmentAge",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {
                "components": _REGISTRATION_STRUCT,
                "internalType": "struct IETHRegistrarController.Registration",
                "name": "registration",
                "type": "tuple",
            }
        ],
        "name": "makeCommitment",
        "outputs": [{"internalType": "bytes32", "name": "commitment", "type": "bytes32"}],
        "stateMutability": "pure",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "commitment", "type": "bytes32"}],
        "name": "commit",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "string", "name": "label", "type": "string"},
            {"internalType": "uint256", "name": "duration", "type": "uint256"},
        ],
        "name": "rentPrice",
        "outputs": [
            {
                "components": [
                    {"internalType": "uint256", "name": "base", "type": "uint256"},
                    {"internalType": "uint256", "name": "premium", "type": "uint256"},
                ],
                "internalType": "struct IPriceOracle.Price",
                "name": "price",
                "type": "tuple",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {
                "components": _REGISTRATION_STRUCT,
                "internalType": "struct IETHRegistrarController.Registration",
                "name": "registration",
                "type": "tuple",
            }
        ],
        "name": "register",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function",
    },
]

RESOLVER_ABI: Final[list[dict[str, object]]] = [
    {
        "inputs": [
            {"internalType": "bytes32", "name": "node", "type": "bytes32"},
            {"internalType": "address", "name": "a", "type": "address"},
        ],
        "name": "setAddr",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "node", "type": "bytes32"}],
        "name": "addr",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
]


@dataclass(frozen=True)
class RegistrationResult:
    """Transaction evidence for a registered ENS name."""

    name: str
    commitment: str
    commit_tx: str
    register_tx: str
    resolved_address: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--names",
        nargs="+",
        default=list(NAMES),
        help="ENS labels to register under .eth, without the .eth suffix.",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=REGISTRATION_DURATION_SECONDS,
        help="Registration duration in seconds.",
    )
    parser.add_argument(
        "--secret",
        help="Optional 0x-prefixed bytes32 secret. Reuse only for a known pending commitment.",
    )
    parser.add_argument(
        "--skip-wait",
        action="store_true",
        help="Do not sleep after commit. Use only if the commitment age has already elapsed.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print computed values and preflight checks without submitting transactions.",
    )
    parser.add_argument(
        "--allow-low-balance",
        action="store_true",
        help="Bypass the 0.05 Sepolia ETH balance guard.",
    )
    return parser.parse_args()


def require_prefixed_bytes32(value: str) -> bytes:
    if not value.startswith("0x") or len(value) != 66:
        raise ValueError("--secret must be a 0x-prefixed bytes32 value")
    return bytes.fromhex(value[2:])


def price_to_wei(price: PriceResponse) -> Wei:
    if isinstance(price, tuple | list):
        return Wei(int(price[0]) + int(price[1]))
    if isinstance(price, dict):
        return Wei(int(price["base"]) + int(price["premium"]))
    return Wei(int(price))


def namehash(name: str) -> bytes:
    return EnsResolver._namehash(name)  # noqa: SLF001


def build_web3() -> Web3:
    settings = get_settings()
    if not settings.eth_sepolia_rpc_url:
        raise RuntimeError("ETH_SEPOLIA_RPC_URL is not configured")
    return Web3(Web3.HTTPProvider(settings.eth_sepolia_rpc_url, request_kwargs={"timeout": 30}))


def build_account() -> LocalAccount:
    settings = get_settings()
    if not settings.agent_private_key:
        raise RuntimeError("AGENT_PRIVATE_KEY is not configured")
    return Account.from_key(settings.agent_private_key)


def transact(w3: Web3, account: LocalAccount, tx: TxParams) -> str:
    tx.setdefault("from", account.address)
    tx.setdefault("chainId", w3.eth.chain_id)
    tx.setdefault("nonce", w3.eth.get_transaction_count(account.address))

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    if receipt["status"] != 1:
        raise RuntimeError(f"transaction reverted: {tx_hash.hex()}")
    return Web3.to_hex(tx_hash)


def resolver_set_addr_data(resolver: Contract, full_name: str, owner: str) -> str:
    return resolver.encode_abi("setAddr", args=[namehash(full_name), owner])


def register_name(
    w3: Web3,
    account: LocalAccount,
    controller: Contract,
    resolver: Contract,
    label: str,
    duration: int,
    secret: bytes,
    skip_wait: bool,
) -> RegistrationResult:
    full_name = f"{label}.eth"
    owner = Web3.to_checksum_address(account.address)
    resolver_address = Web3.to_checksum_address(PUBLIC_RESOLVER)
    setup_data: list[bytes] = [bytes.fromhex(resolver_set_addr_data(resolver, full_name, owner)[2:])]

    available = bool(controller.functions.available(label).call())
    if not available:
        raise RuntimeError(f"{full_name} is not available on this controller")

    commitment = controller.functions.makeCommitment(
        (label, owner, duration, secret, resolver_address, setup_data, 0, b"\x00" * 32)
    ).call()
    commitment_hex = Web3.to_hex(commitment)

    print(f"{full_name}: commitment {commitment_hex}")
    commit_tx = transact(
        w3,
        account,
        controller.functions.commit(commitment).build_transaction({"gas": 120_000}),
    )
    print(f"{full_name}: commit tx {commit_tx}")

    min_age = int(controller.functions.minCommitmentAge().call())
    wait_seconds = max(min_age + 5, 65)
    if skip_wait:
        print(f"{full_name}: skipping {wait_seconds}s commitment wait")
    else:
        print(f"{full_name}: waiting {wait_seconds}s for ENS commitment age")
        time.sleep(wait_seconds)

    price = price_to_wei(controller.functions.rentPrice(label, duration).call())
    tx = controller.functions.register(
        (label, owner, duration, secret, resolver_address, setup_data, 0, b"\x00" * 32)
    ).build_transaction({"value": int(price * 110 // 100), "gas": 500_000})
    register_tx = transact(w3, account, tx)
    print(f"{full_name}: register tx {register_tx}")

    resolved_address = resolver.functions.addr(namehash(full_name)).call()
    resolved_checksum = Web3.to_checksum_address(resolved_address)
    if resolved_checksum != owner:
        raise RuntimeError(f"{full_name} resolved to {resolved_checksum}, expected {owner}")

    return RegistrationResult(
        name=full_name,
        commitment=commitment_hex,
        commit_tx=commit_tx,
        register_tx=register_tx,
        resolved_address=resolved_checksum,
    )


def main() -> None:
    args = parse_args()
    w3 = build_web3()
    account = build_account()
    balance_wei = w3.eth.get_balance(account.address)
    balance_eth = Decimal(str(w3.from_wei(balance_wei, "ether")))

    print(f"chain_id: {w3.eth.chain_id}")
    print(f"wallet:   {account.address}")
    print(f"balance:  {balance_eth} Sepolia ETH")

    if balance_eth < MIN_BALANCE_ETH and not args.allow_low_balance:
        raise SystemExit(
            "Sepolia wallet is below 0.05 ETH. Fund it via sepoliafaucet.com or "
            "https://www.alchemy.com/faucets/ethereum-sepolia, then rerun."
        )

    controller = w3.eth.contract(
        address=Web3.to_checksum_address(ETH_REGISTRAR_CONTROLLER),
        abi=CONTROLLER_ABI,
    )
    resolver = w3.eth.contract(address=Web3.to_checksum_address(PUBLIC_RESOLVER), abi=RESOLVER_ABI)
    secret = require_prefixed_bytes32(args.secret) if args.secret else secrets.token_bytes(32)
    print(f"secret:   0x{secret.hex()}")

    if args.dry_run:
        for label in args.names:
            full_name = f"{label}.eth"
            data = resolver_set_addr_data(resolver, full_name, account.address)
            print(f"{full_name}: available={controller.functions.available(label).call()}")
            print(f"{full_name}: setup_data={data}")
        return

    results = [
        register_name(
            w3=w3,
            account=account,
            controller=controller,
            resolver=resolver,
            label=label,
            duration=args.duration,
            secret=secret,
            skip_wait=args.skip_wait,
        )
        for label in args.names
    ]

    print("\nENS registration evidence")
    for result in results:
        print(
            f"- {result.name}: commit={result.commit_tx} register={result.register_tx} "
            f"resolved={result.resolved_address}"
        )


if __name__ == "__main__":
    main()
