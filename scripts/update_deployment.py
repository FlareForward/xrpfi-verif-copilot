"""Update or preview DEPLOYMENT_ADDRESSES.md post-funding evidence.

By default the script reads the current file, applies any supplied contract,
deployment, and demo transaction values, then prints a unified diff. Use
--write to persist the changes.
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

DEFAULT_DEPLOYMENT_FILE: Final = "DEPLOYMENT_ADDRESSES.md"
DEFAULT_EXPLORER: Final = "https://chainscan.0g.ai"
ADDRESS_RE: Final = re.compile(r"^0x[a-fA-F0-9]{40}$")
TX_RE: Final = re.compile(r"^0x[a-fA-F0-9]{64}$")


@dataclass(frozen=True)
class DeploymentUpdate:
    """Values that can be written into the deployment address document."""

    contract_address: str | None
    deploy_tx: str | None
    deploy_block: str | None
    deployer: str | None
    rpc_url: str | None
    explorer: str
    mint_tx: str | None
    token_id: str | None
    storage_tx: str | None

    @property
    def has_changes(self) -> bool:
        return any(
            (
                self.contract_address,
                self.deploy_tx,
                self.deploy_block,
                self.deployer,
                self.rpc_url,
                self.mint_tx,
                self.token_id,
                self.storage_tx,
            )
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default=DEFAULT_DEPLOYMENT_FILE, help="Deployment markdown file.")
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Dotenv file to read for ZERO_G_* values.",
    )
    parser.add_argument("--contract-address")
    parser.add_argument("--deploy-tx")
    parser.add_argument("--deploy-block")
    parser.add_argument("--deployer")
    parser.add_argument("--rpc-url")
    parser.add_argument("--explorer")
    parser.add_argument("--mint-tx")
    parser.add_argument("--token-id")
    parser.add_argument("--storage-tx")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing. This is the default unless --write is passed.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write changes to the deployment file. Without this flag, only print the diff.",
    )
    parser.add_argument(
        "--allow-noop",
        action="store_true",
        help="Exit 0 even when no replacement values were supplied.",
    )
    return parser.parse_args()


def strip_inline_comment(value: str) -> str:
    if " #" in value:
        value = value.split(" #", 1)[0]
    return value.strip().strip('"').strip("'")


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), strip_inline_comment(value))


def validate_address(value: str | None, label: str) -> str | None:
    if value is None or value == "":
        return None
    if not ADDRESS_RE.fullmatch(value):
        raise ValueError(f"{label} must be a 0x-prefixed 20-byte address")
    return value


def validate_tx(value: str | None, label: str) -> str | None:
    if value is None or value == "":
        return None
    if not TX_RE.fullmatch(value):
        raise ValueError(f"{label} must be a 0x-prefixed 32-byte transaction hash")
    return value


def optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def build_update(args: argparse.Namespace) -> DeploymentUpdate:
    rpc_url = optional_string(args.rpc_url) or optional_string(os.environ.get("ZERO_G_RPC_URL"))
    return DeploymentUpdate(
        contract_address=validate_address(
            args.contract_address or os.environ.get("ZERO_G_INFT_CONTRACT"),
            "--contract-address",
        ),
        deploy_tx=validate_tx(args.deploy_tx, "--deploy-tx"),
        deploy_block=str(args.deploy_block) if args.deploy_block else None,
        deployer=validate_address(args.deployer, "--deployer"),
        rpc_url=rpc_url,
        explorer=str(args.explorer or os.environ.get("ZERO_G_EXPLORER", DEFAULT_EXPLORER)).rstrip(
            "/"
        ),
        mint_tx=validate_tx(args.mint_tx, "--mint-tx"),
        token_id=str(args.token_id) if args.token_id else None,
        storage_tx=validate_tx(args.storage_tx, "--storage-tx"),
    )


def replace_line(text: str, pattern: str, replacement: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"could not find deployment line matching {pattern!r}")
    return updated


def apply_update(text: str, update: DeploymentUpdate) -> str:
    if update.contract_address:
        explorer_url = f"{update.explorer}/address/{update.contract_address}"
        text = replace_line(
            text,
            r"^\| XRPFi iNFT \(ERC-7857\) \| `0x[a-fA-F0-9]{40}` \| \[[^\]]+\]\([^)]+\) \|$",
            (
                "| XRPFi iNFT (ERC-7857) | "
                f"`{update.contract_address}` | [chainscan.0g.ai]({explorer_url}) |"
            ),
        )

    if update.deploy_tx:
        text = replace_line(
            text,
            r"^\*\*Deploy tx:\*\* `0x[a-fA-F0-9]{64}`  $",
            f"**Deploy tx:** `{update.deploy_tx}`  ",
        )
    if update.deploy_block:
        text = replace_line(
            text,
            r"^\*\*Deploy block:\*\* .+$",
            f"**Deploy block:** {update.deploy_block}  ",
        )
    if update.deployer:
        text = replace_line(
            text,
            r"^\*\*Deployer:\*\* `0x[a-fA-F0-9]{40}`  $",
            f"**Deployer:** `{update.deployer}`  ",
        )
    if update.rpc_url:
        text = replace_line(
            text,
            r"^\*\*RPC used:\*\* `[^`]+`  $",
            f"**RPC used:** `{update.rpc_url}`  ",
        )
    if update.mint_tx:
        mint_url = f"{update.explorer}/tx/{update.mint_tx}"
        text = replace_line(
            text,
            r"^\| iNFT mint tx \| `0x[a-fA-F0-9]{64}` \|$",
            f"| iNFT mint tx | `{update.mint_tx}` |",
        )
        text = replace_line(
            text,
            r"^\| iNFT explorer URL \| https://[^ ]+ \|$",
            f"| iNFT explorer URL | {mint_url} |",
        )
    if update.token_id:
        text = replace_line(
            text,
            r"^\| iNFT token ID \| `[^`]+` \|$",
            f"| iNFT token ID | `{update.token_id}` |",
        )
    if update.storage_tx:
        storage_url = f"{update.explorer}/tx/{update.storage_tx}"
        text = replace_line(
            text,
            r"^\| 0G Storage \| .+ \|$",
            f"| 0G Storage | `{update.storage_tx}` ({storage_url}) |",
        )

    return text


def print_diff(path: Path, before: str, after: str) -> None:
    diff = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"{path} (current)",
        tofile=f"{path} (updated)",
    )
    print("".join(diff), end="")


def main() -> int:
    args = parse_args()
    path = Path(args.file)
    load_env_file(Path(args.env_file))
    update = build_update(args)

    if not update.has_changes:
        print("No deployment values supplied; nothing to change.")
        return 0 if args.allow_noop else 1

    before = path.read_text(encoding="utf-8")
    after = apply_update(before, update)
    if before == after:
        print("Deployment file already matches supplied values.")
        return 0

    print_diff(path, before, after)
    if args.write:
        path.write_text(after, encoding="utf-8")
        print(f"\nUpdated {path}")
    else:
        print("\nDry run only; rerun with --write to update the file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
