# Deployment Addresses

## 0G Mainnet (Chain ID 16661)

| Contract | Address | Explorer |
|----------|---------|----------|
| XRPFi iNFT (ERC-7857) | `0x01fE5698a2448d0fc336295df9977796030C79C4` | [chainscan.0g.ai](https://chainscan.0g.ai/address/0x01fE5698a2448d0fc336295df9977796030C79C4) |

**Deploy tx:** `0xc44f334032243a996ea9221ce9888d157da7d3af2fc67ef437435b9b1ca26023`  
**Deploy block:** 32391100  
**Deployer:** `0x81e51856d72023490cF7DEc1A6717f4269028F95`  
**RPC used:** `https://0g-rpc.publicnode.com`  
**Explorer:** https://chainscan.0g.ai/

---

## Demo Transaction

| Item | Value |
|------|-------|
| iNFT mint tx | `0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd` |
| iNFT token ID | `1` |
| iNFT explorer URL | https://chainscan.0g.ai/tx/0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd |
| FTSO prices (live) | FLR/USD=0.0076298, XRP/USD=1.409773 (fetched live from Flare FTSO v2) |
| 0G Storage | `0x9128916bab7eb7cd7175ce1c201d76e06ec595655d7220b760c5963ceaa978b9` (https://chainscan.0g.ai/tx/0x9128916bab7eb7cd7175ce1c201d76e06ec595655d7220b760c5963ceaa978b9) |

---

## Flare Coston2 Testnet (Flare data — no deploy needed)

| Contract | Address |
|----------|---------|
| FlareContractRegistry | `0xaD67FE66660Fb8dFE9d6b1b4240d8650e30F6019` |
| FtsoV2 | via registry: `FtsoV2` |
| FdcHub | via registry: `FdcHub` |

**Explorer:** https://coston2-explorer.flare.network/

## Songbird Testnet — FAssets v1.3 (no deploy needed)

| Contract | Address |
|----------|---------|
| AssetManager (FXRP) | via registry: `AssetManager` |

**Explorer:** https://songbird-explorer.flare.network/

## ENS

| Name | Status |
|------|--------|
| `mint-helper.eth` | Sepolia registration prepared; blocked on funding wallet `0x6CC5C6dacdf110E40f30A4c8945CD5D0Cb1290Ab` (0 ETH at 2026-05-05 check) |
| `yield-router.eth` | Sepolia registration prepared; blocked on funding wallet `0x6CC5C6dacdf110E40f30A4c8945CD5D0Cb1290Ab` (0 ETH at 2026-05-05 check) |

**Registration target:** Sepolia for hackathon identity testing, mainnet before production.

**Resolver note:** The in-tree resolver now uses Ethereum Keccak namehash and no longer short-circuits web3 resolution into fallback mode.

**Repeatable registration script:** `scripts/register_ens.py`

**Funding blocker:** The configured Sepolia signing wallet currently has 0 ETH. Fund it with
at least 0.05 Sepolia ETH, then run:

```bash
uv run python scripts/register_ens.py
```

## 0G Storage

| Network | Value |
|---------|-------|
| Chain ID | `16661` |
| RPC | `https://0g-rpc.publicnode.com` |
| Storage indexer | `https://indexer-storage-turbo.0g.ai` |
| Flow contract | `0x62D4144dB0F0a6fBBaeb6296c785C71B3D57C526` |

The old Galileo/testnet Flow contract `0x22E03a6A89B950F1c82ec5e74F8eCa321a105296` is not used for mainnet uploads.
