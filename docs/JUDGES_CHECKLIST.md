# XRPFi Verifiable Copilot — Judge Proof Sheet

**0G APAC Hackathon 2026 | FlareForward | Track 2: Agentic Trading Arena**

---

## Quick Start (3 commands)

```bash
pip install uv && uv pip install -e ".[dev]"
cp .env.example .env       # add GOOGLE_API_KEY (optional — graceful fallback if absent)
uv run python demo/judge_demo.py
```

Browser UI alternative:
```bash
uv run python web/server.py   # open http://localhost:8088
# or
docker compose up xrpfi
```

---

## Live On-Chain Proof

| Proof Element | Value | Explorer Link |
|---|---|---|
| iNFT Contract (ERC-7857) | `0x01fE5698a2448d0fc336295df9977796030C79C4` | [chainscan.0g.ai/address/0x01fE5698...](https://chainscan.0g.ai/address/0x01fE5698a2448d0fc336295df9977796030C79C4) |
| Deploy Tx | `0xc44f334032243a996ea9221ce9888d157da7d3af2fc67ef437435b9b1ca26023` | [chainscan.0g.ai/tx/0xc44f33...](https://chainscan.0g.ai/tx/0xc44f334032243a996ea9221ce9888d157da7d3af2fc67ef437435b9b1ca26023) |
| iNFT Mint Tx | `0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd` | [chainscan.0g.ai/tx/0xbe0cf7c8...](https://chainscan.0g.ai/tx/0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd) |
| Token ID | `1` | [chainscan.0g.ai/tx/0xbe0cf7c8...](https://chainscan.0g.ai/tx/0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd) |
| Chain | 0G Mainnet (ID 16661) | https://chainscan.0g.ai |
| Deployer | `0x81e51856d72023490cF7DEc1A6717f4269028F95` | — |

---

## Expected `judge_demo.py` Output

```
============================================================
  XRPFi Verifiable Copilot — Judge Demo
  0G APAC Hackathon 2026 | FlareForward
============================================================

[1] FTSO prices      FLR/USD=0.0076  XRP/USD=1.41          ✓
[2] ENS resolved     mint-helper.eth → 0x81e518...          ✓
[3] ENS resolved     yield-router.eth → 0x81e518...         ✓
[4] FDC attestation  XRP payment attested (proof_hash=0x...) ✓
[5] FXRP minted      100 XRP → 99.00 FXRP (Songbird testnet) ✓
[6] Yield routed     60% SparkDEX / 40% Kinetic             ✓
[7] Uniswap quote    WETH→USDC: 1.0 WETH = 2,341 USDC      ⚠ (API key not set — fixture)
[8] Gensyn AXL       Node A → Node B: xrpfi.mint.complete ✓  ✓
[9] 0G storage       ⚠ storage fallback (0G wallet unfunded — see ZERO_G_STORAGE_STATUS.md)
[10] iNFT minted     token=1 https://chainscan.0g.ai/tx/0xbe0cf7c8...  ✓

============================================================
  Verifiable audit trail: https://chainscan.0g.ai/tx/0xbe0cf7c8...
  GitHub: https://github.com/FlareForward/xrpfi-verif-copilot
============================================================
```

---

## Common Fallbacks (not bugs)

| Condition | Fallback Shown | Fix |
|---|---|---|
| `GOOGLE_API_KEY` not set | Deterministic reasoning string (labeled in output) | Add key to `.env` |
| 0G wallet unfunded | `⚠ storage fallback` + `ZERO_G_STORAGE_STATUS.md` link | Top up `0x81e518...` on Chain 16661 |
| `UNISWAP_API_KEY` not set | Fixture quote (labeled `API key not set`) | Add key to `.env` |
| ENS not registered | Fallback address map | Register on Sepolia (see `scripts/register_ens.py`) |

Fallbacks are **transparent** — every one prints a labeled `⚠` rather than silently faking data.

---

## Sponsor Integration Evidence

| Sponsor | What Was Built | Code Location | Proof |
|---|---|---|---|
| **0G** | ERC-7857 iNFT contract on 0G mainnet; every `DecisionRecord` uploaded via `ZeroGClient` | `src/integrations/zero_g/` | iNFT mint tx above; `ZERO_G_STORAGE_STATUS.md` |
| **ENS** | Dynamic agent resolution — `mint-helper.eth` + `yield-router.eth` via Web3 keccak namehash | `src/integrations/ens/resolver.py` | `judge_demo.py` steps [2][3] |
| **Uniswap** | Trading API v2 WETH→USDC live quote (fixture fallback when key absent) | `src/integrations/uniswap/client.py` | `judge_demo.py` step [7]; `FEEDBACK.md` devex notes |
| **Gensyn** | AXL cross-node pub/sub: Node A (port 8765) publishes `xrpfi.mint.complete`; Node B subscribes | `src/gensyn/node_a/`, `src/gensyn/node_b/` | `judge_demo.py` step [8] |

---

## Test Suite

```bash
uv run --extra dev pytest tests/ -q   # 160 tests, all pass
uv run ruff check .                    # ruff clean
uv run mypy --strict src/              # mypy --strict clean, 36 files
```

---

## GitHub

https://github.com/FlareForward/xrpfi-verif-copilot

See also: [DEPLOYMENT_ADDRESSES.md](../DEPLOYMENT_ADDRESSES.md) | [ZERO_G_STORAGE_STATUS.md](../ZERO_G_STORAGE_STATUS.md) | [SUBMISSION.md](../SUBMISSION.md)
