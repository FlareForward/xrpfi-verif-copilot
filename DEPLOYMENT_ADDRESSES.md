# Deployment Addresses

## 0G Mainnet (Chain ID 16661)

| Contract | Address | Notes |
|----------|---------|-------|
| XRPFi iNFT (ERC-7857) | `TBD — run contracts/deploy.py after wallet funding` | iNFT contract for decision log minting |

**Explorer:** https://chainscan.0g.ai/  
**Deployer wallet:** `0x4d1EB41C0093A14c6c838a1C8fED6f79bc5Dc1AE`  
**Deploy command:**
```bash
cd ~/xrpfi-verif-copilot
uv run python contracts/deploy.py
```

> **Operator action required:** Fund deployer wallet with ~0.5 OG on 0G mainnet
> (Binance: OG/USDT, KuCoin, or OKX), then run the deploy command above.

---

## Demo Transaction

| Item | Value |
|------|-------|
| 0G Storage tx | *(fill in after `uv run python demo/run_demo.py`)* |
| iNFT token ID | *(fill in after demo run)* |
| iNFT explorer URL | *(fill in — format: https://chainscan.0g.ai/tx/<hash>)* |

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

## ENS (Ethereum Mainnet / Sepolia)

| Name | Status |
|------|--------|
| `mint-helper.eth` | Fallback to test address when unregistered (see `resolver.py`) |
| `yield-router.eth` | Fallback to test address when unregistered (see `resolver_b.py`) |

---

*Fill in 0G mainnet contract address and demo tx hash after Phase M4 completes.*
