# XRPFi Receipt Explorer Reality Matrix

This table is the source of truth for the live, fixture, and planned state of every integration claim in the XRPFi Receipt Explorer repositioning pass.

| Integration | State | Evidence | Notes |
|---|---|---|---|
| FTSO prices | live | hits coston2-api.flare.network on every run | |
| 0G iNFT (token 1) | live | 0xbe0cf7c8... on chainscan.0g.ai | minted 2026-05-04 |
| 0G storage upload | planned | wallet 0x81e518... has 0 OG | see ZERO_G_STORAGE_STATUS.md |
| ENS mint-helper.eth | code-ready | script ready; Sepolia wallet needs 0.05 ETH | script ready in scripts/register_ens.py |
| ENS yield-router.eth | code-ready | script ready; Sepolia wallet needs 0.05 ETH | |
| FDC attestation | fixture | demo proof hash; not a real XRPL tx | |
| FAssets mint | fixture | stub tx params; no on-chain broadcast | |
| Uniswap WETH/USDC quote | fixture | no API key set; pair unrelated to FXRP | |
| Gensyn AXL | fixture | in-process asyncio.Queue; force_fallback=True | |
| Yield routing | fixture | deterministic 60/40 policy; no live DeFi calls | |
