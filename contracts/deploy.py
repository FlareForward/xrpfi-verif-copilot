"""Deploy XRPFiINFT to 0G Galileo Testnet.

Usage:
    cd /Users/stevenhudspeth/xrpfi-verif-copilot
    source .venv/bin/activate
    python contracts/deploy.py

Requires in .env:
    ZERO_G_PRIVATE_KEY=0x...your_rabby_private_key...

Writes deployed address to .env as ZERO_G_INFT_CONTRACT.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

PRIVATE_KEY = os.environ.get("ZERO_G_PRIVATE_KEY")
if not PRIVATE_KEY:
    print("ERROR: ZERO_G_PRIVATE_KEY not set in .env")
    print("Add this line to .env:")
    print("  ZERO_G_PRIVATE_KEY=0x<your_rabby_private_key>")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Compile + deploy
# ---------------------------------------------------------------------------
try:
    from web3 import Web3
    from solcx import compile_source, install_solc
except ImportError:
    print("Installing required packages...")
    os.system(f"{sys.executable} -m pip install web3 py-solc-x -q")
    from web3 import Web3
    from solcx import compile_source, install_solc

RPC_URL = "https://evmrpc-testnet.0g.ai"
CHAIN_ID = 80087

sol_file = Path(__file__).parent / "XRPFiINFT.sol"
source = sol_file.read_text()

print("Installing solc 0.8.20...")
install_solc("0.8.20", show_progress=False)

print("Compiling XRPFiINFT.sol...")
compiled = compile_source(
    source,
    output_values=["abi", "bin"],
    solc_version="0.8.20",
)
contract_id = "<stdin>:XRPFiINFT"
abi = compiled[contract_id]["abi"]
bytecode = compiled[contract_id]["bin"]

w3 = Web3(Web3.HTTPProvider(RPC_URL))
if not w3.is_connected():
    print(f"ERROR: Cannot connect to {RPC_URL}")
    sys.exit(1)

account = w3.eth.account.from_key(PRIVATE_KEY)
print(f"Deployer: {account.address}")
balance = w3.eth.get_balance(account.address)
print(f"Balance:  {w3.from_wei(balance, 'ether')} OG")

if balance == 0:
    print("ERROR: No OG balance. Get testnet tokens first.")
    sys.exit(1)

print("Deploying XRPFiINFT to Galileo testnet...")
Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
nonce = w3.eth.get_transaction_count(account.address)

tx = Contract.constructor().build_transaction({
    "from": account.address,
    "nonce": nonce,
    "gas": 1_500_000,
    "chainId": CHAIN_ID,
})

signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
print(f"Tx hash: 0x{tx_hash.hex()}")
print("Waiting for confirmation...")

receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
contract_address = receipt["contractAddress"]

print(f"\n✅ XRPFiINFT deployed at: {contract_address}")
print(f"   Explorer: https://chainscan-galileo.0g.ai/address/{contract_address}")

# ---------------------------------------------------------------------------
# Write address to .env
# ---------------------------------------------------------------------------
env_text = env_path.read_text()
if "ZERO_G_INFT_CONTRACT" in env_text:
    lines = []
    for line in env_text.splitlines():
        if line.startswith("ZERO_G_INFT_CONTRACT="):
            lines.append(f"ZERO_G_INFT_CONTRACT={contract_address}")
        else:
            lines.append(line)
    env_path.write_text("\n".join(lines) + "\n")
else:
    with env_path.open("a") as f:
        f.write(f"\nZERO_G_INFT_CONTRACT={contract_address}\n")

print(f"\n✅ Written to .env: ZERO_G_INFT_CONTRACT={contract_address}")
print("\nRun the demo now:")
print("   python demo/run_demo.py")
