"""Preflight the 0G storage wallet balance."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Final

from web3 import Web3

DEFAULT_RPC_URL: Final = "https://0g-rpc.publicnode.com"
DEFAULT_CHAIN_ID: Final = 16661
DEFAULT_MIN_BALANCE_OG: Final = Decimal("0.1")
DEPLOYER_ADDRESS: Final = "0x53730993203f21b9ac8d10a8CA5CA5d92b036118"
EXPLORER_URL: Final = f"https://chainscan.0g.ai/address/{DEPLOYER_ADDRESS}"


@dataclass(frozen=True)
class BalanceCheck:
    """Funding preflight result."""

    address: str
    chain_id: int
    balance_og: Decimal
    minimum_og: Decimal
    rpc_url: str

    @property
    def funded(self) -> bool:
        return self.balance_og > self.minimum_og


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to the dotenv file containing ZERO_G_PRIVATE_KEY and ZERO_G_RPC_URL.",
    )
    parser.add_argument(
        "--rpc-url",
        default=None,
        help="Override ZERO_G_RPC_URL for this check.",
    )
    parser.add_argument(
        "--chain-id",
        type=int,
        default=None,
        help="Expected 0G chain ID. Defaults to ZERO_G_CHAIN_ID or 16661.",
    )
    parser.add_argument(
        "--min-og",
        default=str(DEFAULT_MIN_BALANCE_OG),
        help="Minimum OG balance required for a passing funding check.",
    )
    parser.add_argument(
        "--allow-missing-key",
        action="store_true",
        help="Exit 0 when ZERO_G_PRIVATE_KEY is absent; useful for documentation-only runs.",
    )
    return parser.parse_args()


def load_env_file(path: Path) -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv = None

    if load_dotenv is not None:
        load_dotenv(path)
        return

    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), strip_inline_comment(value).strip())


def strip_inline_comment(value: str) -> str:
    if " #" in value:
        value = value.split(" #", 1)[0]
    return value.strip().strip('"').strip("'")


def parse_decimal(value: str, label: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{label} must be a decimal value, got {value!r}") from exc


def require_private_key(allow_missing_key: bool) -> str | None:
    private_key = strip_inline_comment(os.environ.get("ZERO_G_PRIVATE_KEY", ""))
    if private_key:
        return private_key

    message = "ZERO_G_PRIVATE_KEY is not configured; cannot derive the 0G funding wallet."
    if allow_missing_key:
        print(f"SKIP: {message}")
        return None
    raise RuntimeError(message)


def run_check(args: argparse.Namespace) -> BalanceCheck | None:
    load_env_file(Path(args.env_file))
    private_key = require_private_key(bool(args.allow_missing_key))
    if private_key is None:
        return None

    minimum_og = parse_decimal(str(args.min_og), "--min-og")
    rpc_url = args.rpc_url or os.environ.get("ZERO_G_RPC_URL") or DEFAULT_RPC_URL
    expected_chain_id = args.chain_id or int(os.environ.get("ZERO_G_CHAIN_ID", DEFAULT_CHAIN_ID))

    address = Web3.to_checksum_address(DEPLOYER_ADDRESS)
    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 15}))

    if not w3.is_connected():
        raise RuntimeError(f"cannot connect to 0G RPC: {rpc_url}")

    chain_id = int(w3.eth.chain_id)
    if chain_id != expected_chain_id:
        raise RuntimeError(f"unexpected chain ID {chain_id}; expected {expected_chain_id}")

    balance_wei = w3.eth.get_balance(address)
    balance_og = Decimal(str(w3.from_wei(balance_wei, "ether")))
    return BalanceCheck(
        address=address,
        chain_id=chain_id,
        balance_og=balance_og,
        minimum_og=minimum_og,
        rpc_url=rpc_url,
    )


def print_result(result: BalanceCheck | None) -> int:
    if result is None:
        return 0

    print("0G Wallet Balance Check")
    print(f"Address: {result.address}")
    print(f"Balance: {result.balance_og:.6f} OG")
    print("Chain: 0G Mainnet (ID 16661)")
    print(f"RPC: {result.rpc_url}")
    print()
    if result.funded:
        print("Status: ✅ Funded (ready for storage upload)")
    else:
        print("Status: ⚠ Unfunded — send at least 0.5 OG to enable real storage tx hashes")
    print(f"Explorer: {EXPLORER_URL}")
    return 0 if result.funded else 1


def main() -> int:
    args = parse_args()
    try:
        return print_result(run_check(args))
    except Exception as exc:
        print(f"0G funding check: ERROR - {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
