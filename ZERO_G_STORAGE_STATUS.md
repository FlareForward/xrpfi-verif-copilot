# 0G Storage Mainnet Status

Date: 2026-05-13

## Summary

Mainnet storage upload is in the final live-fix cycle. The previous blocker
was an unfunded wallet, but the configured 0G wallet is now funded and ready
for an end-to-end storage transaction.

- Chain ID: `16661`
- RPC: `https://0g-rpc.publicnode.com`
- Wallet: `0x53730993203f21b9ac8d10a8CA5CA5d92b036118`
- Wallet balance: `8.75 OG`
- Flow contract: `0x62D4144dB0F0a6fBBaeb6296c785C71B3D57C526`

Storage is not marked live until the current cycle records a real mainnet
storage transaction hash from `make judge`.

## Current Root Cause

Two independent blockers were identified on 2026-05-13:

1. The Node upload helper passes `fee: 0n` into the 0G TypeScript SDK. The
   FixedPriceFlow contract requires `msg.value >= price`, so the submit
   transaction reverts during gas estimation.
2. The HTTP fallback points at `https://indexer-storage-turbo.0g.ai`, which
   returns `HTTP 404` for the mainnet upload path.

## Fix In Progress

- Lane A owns the SDK/Flow-contract fee calculation in
  `contracts/storage_upload/upload.mjs`.
- Lane B owns the correct mainnet storage indexer URL and Python HTTP fallback
  path.
- The orchestrator owns this status file, `REALITY_MATRIX.md`, final
  integration, and the `v2.6.0-storage-live` tag.

## Live Acceptance Criteria

Storage becomes live only when all of the following are true:

```bash
uv run pytest tests/ -q
make judge
```

The judge run must produce a real storage transaction hash matching
`0x` plus 64 hex characters, not a `local://` fallback or fixture hash.

## Pending Evidence

The real transaction hash will be recorded here after Lane A and Lane B merge
and the orchestrator reruns the integration flow.
