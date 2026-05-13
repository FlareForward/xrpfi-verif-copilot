# 0G Storage Mainnet Status

Date: 2026-05-13

## Summary

0G mainnet storage upload is live for the XRPFi judge receipt.

- Chain ID: `16661`
- RPC: `https://0g-rpc.publicnode.com`
- Storage indexer: `https://indexer-storage-turbo.0g.ai`
- Wallet: `0x53730993203f21b9ac8d10a8CA5CA5d92b036118`
- Flow contract: `0x62D4144dB0F0a6fBBaeb6296c785C71B3D57C526`
- Storage transaction:
  `0x9128916bab7eb7cd7175ce1c201d76e06ec595655d7220b760c5963ceaa978b9`
- Explorer:
  `https://chainscan.0g.ai/tx/0x9128916bab7eb7cd7175ce1c201d76e06ec595655d7220b760c5963ceaa978b9`

Receipt verification confirmed the transaction succeeded on 0G mainnet in
block `33162228`, from wallet `0x53730993203f21b9ac8d10a8CA5CA5d92b036118`
to the Flow contract.

## Root Cause Fixed

Two independent blockers were fixed:

1. The upload helper previously sent `fee: 0n`. It now queries the Flow market
   price and sends a positive storage fee with the transaction.
2. The bundled TypeScript SDK expected the older Flow ABI. The helper now uses
   the live Flow ABI with the `data` plus `submitter` submission wrapper, while
   keeping the SDK's file, indexer, and uploader flow.

The Python HTTP fallback also now posts to the mainnet indexer's `/file/segment`
path and returns explicit local proof only when live upload is unavailable.

## Verification

```bash
node --check contracts/storage_upload/upload.mjs
uv run ruff check src/ tests/ demo/
uv run mypy src/ --strict
uv run pytest tests/ -q
make update-deployment UPDATE_DEPLOYMENT_ARGS='--storage-tx 0x9128916bab7eb7cd7175ce1c201d76e06ec595655d7220b760c5963ceaa978b9 --write'
```

Observed gate result: `170 passed`.

Live transaction receipt:

```text
tx:     0x9128916bab7eb7cd7175ce1c201d76e06ec595655d7220b760c5963ceaa978b9
status: 1
block:  33162228
gas:    339202
```
