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
| 0G Storage | Simulated hashes (0G mainnet storage node returning 503 at time of demo) |

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

## ENS (Ethereum Mainnet)

| Name | Status |
|------|--------|
| `mint-helper.eth` | Fallback to test address when unregistered (see `resolver.py`) |
| `yield-router.eth` | Fallback to test address when unregistered (see `resolver_b.py`) |
