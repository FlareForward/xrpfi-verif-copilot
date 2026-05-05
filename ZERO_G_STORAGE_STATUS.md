# 0G Storage Mainnet Status

Date: 2026-05-05

## Summary

Mainnet storage upload now targets the documented 0G mainnet Flow contract:

- Chain ID: `16661`
- RPC: `https://0g-rpc.publicnode.com`
- Storage indexer: `https://indexer-storage-turbo.0g.ai`
- Flow contract: `0x62D4144dB0F0a6fBBaeb6296c785C71B3D57C526`

The previous Galileo/testnet Flow contract is no longer used by the upload helper. The helper now pins the mainnet Flow contract instead of trusting storage-node status metadata.

## Upload Test Result

Command:

```bash
uv run python demo/run_demo.py 2>&1 | grep -E "storage|tx_hash|0x|Upload|error|revert|0G"
```

Result: upload reached the correct mainnet Flow contract but did not produce a live storage transaction because the configured 0G wallet lacks enough OG for the storage fee plus gas.

Observed error:

```text
Upload error: Failed to submit transaction: insufficient funds for transfer
to: 0x62d4144db0f0a6fbbaeb6296c785c71b3d57c526
```

The HTTP `/upload` fallback on `https://indexer-storage-turbo.0g.ai` returned `HTTP 404`, so the client correctly fell back to explicit local proof hashes instead of claiming a fake live upload.

## What Was Changed

- `contracts/storage_upload/upload.mjs` now pins `ZERO_G_FLOW_CONTRACT` to the documented mainnet Flow contract.
- `src/integrations/zero_g/client.py` now passes the runtime RPC, indexer, explorer, chain ID, and Flow contract into the Node helper process.
- `src/config.py` now exposes `zero_g_flow_contract`.
- `.env.example` now documents mainnet 0G storage defaults instead of Galileo/testnet values.

## Remaining Blocker

Fund the configured 0G wallet on chain `16661`, then rerun:

```bash
uv run python demo/run_demo.py 2>&1 | grep -E "storage|tx_hash|0x"
```

Expected success signal:

```text
0G TS SDK upload success: root=0x... tx=0x...
```

Until the wallet is funded, judge-facing output should label storage as a fallback:

```text
0G storage: fallback (mainnet upload pending — see ZERO_G_STORAGE_STATUS.md)
```
