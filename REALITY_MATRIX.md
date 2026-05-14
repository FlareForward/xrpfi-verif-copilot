# XRPFi Receipt Explorer Reality Matrix

This table is the source of truth for the live, fixture, and planned state of every integration claim in the XRPFi Receipt Explorer repositioning pass.

| Integration | State | Evidence | Notes |
|---|---|---|---|
| FTSO prices | live | hits coston2-api.flare.network on every run | |
| 0G iNFT (token 1) | live | 0xbe0cf7c8... on chainscan.0g.ai | minted 2026-05-04 |
| 0G storage upload | live | 0x9128916b... on chainscan.0g.ai | confirmed 2026-05-13; see ZERO_G_STORAGE_STATUS.md |
| ENS mint-helper.eth | live | commit 0x3877a7d0... register 0x19b841ec... resolved 0x5373...6118 on Sepolia | registered 2026-05-14; resolves in judge receipt |
| ENS yield-router.eth | live | commit 0xa0ff5cb2... register 0xee881d94... resolved 0x5373...6118 on Sepolia | registered 2026-05-14; resolves in judge receipt |
| FDC attestation | fixture | demo proof hash; not a real XRPL tx | |
| FAssets mint | fixture | stub tx params; no on-chain broadcast | |
| Uniswap WETH/USDC quote | fixture | no API key set; pair unrelated to FXRP | |
| Gensyn AXL | fixture | in-process asyncio.Queue; force_fallback=True | |
| Yield routing | fixture | deterministic 60/40 policy; no live DeFi calls | |
