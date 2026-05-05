# Submission Checklist — 0G APAC Hackathon
**Event:** 0G APAC Hackathon (hackquest.io)  
**Track:** Track 2 — Agentic Trading Arena / Verifiable Finance  
**Deadline:** 2026-05-16 23:59 UTC+8  
**Prize Pool:** $150k total | 1st $45k, 2nd $35k, 3rd $20k

---

## Submission Requirements

### ✅ Agent-completed items

| # | Requirement | Evidence | Status |
|---|-------------|----------|--------|
| 1 | Open source code with real progress | All source in `src/`, `tests/`, `demo/` | ✅ |
| 2 | README in English | `README.md` — updated for 0G APAC | ✅ |
| 3 | At least one 0G component used | `src/integrations/zero_g/` — storage client + iNFT mint | ✅ |
| 4 | Code quality | 151/151 tests, ruff clean | ✅ |
| 5 | X post draft ready | `X_POST_DRAFT.md` | ✅ |
| 6 | Demo script ready | `DEMO_SCRIPT.md` | ✅ |
| 7 | Environment vars externalized (no hardcoded mainnet) | `.env` + `src/config.py` | ✅ |
| 8 | iNFT contract deployable on mainnet | `contracts/deploy.py` — mainnet-ready | ✅ |

---

### ⏸ Operator-required items (action needed)

| # | Requirement | What to do | Status |
|---|-------------|-----------|--------|
| A | **Fund build wallet** | Send 0.5–1.0 OG mainnet tokens to `0x4d1EB41C0093A14c6c838a1C8fED6f79bc5Dc1AE` via Binance/KuCoin/OKX (ticker: OG). Then tell Claude "GO M" | ⏸ BLOCKING M4 |
| B | **Deploy iNFT contract** | After wallet funded, run: `cd ~/xrpfi-verif-copilot && uv run python contracts/deploy.py`. Copy the output contract address into `DEPLOYMENT_ADDRESSES.md` | ⏸ Waiting on A |
| C | **Run end-to-end demo** | After deploy: `uv run python demo/run_demo.py`. Capture the 0G tx hash + iNFT token ID. Add to `DEPLOYMENT_ADDRESSES.md` under "Demo Transaction" | ⏸ Waiting on B |
| D | **Make GitHub repo public** | GitHub → Settings → Danger Zone → Change visibility → Public. Repo path: `~/xrpfi-verif-copilot/` | ⏸ Required before submission |
| E | **Record demo video** | Follow `DEMO_SCRIPT.md`. Record ~3 min screen capture. Upload to Loom or YouTube (unlisted OK). | ⏸ Required |
| F | **Post on X** | Use content from `X_POST_DRAFT.md`. Replace `[ADD VIDEO LINK]` with your recording URL. Must include #0GHackathon #BuildOn0G | ⏸ Required |
| G | **Fill HackQuest submission form** | Go to hackquest.io/hackathons/0G-APAC-Hackathon (registered ✅). Fill in: GitHub URL, demo video URL, X post URL, contract address, project description | ⏸ Final step |

---

## What to Fill in the HackQuest Form

**Project name:** XRPFi Verifiable Copilot

**One-liner:** A 2-agent AI system that helps XRP holders enter Flare DeFi — every agent decision permanently verifiable on 0G storage and minted as an iNFT.

**GitHub repo:** https://github.com/flareforward/xrpfi-verif-copilot *(make public first)*

**Demo video:** [fill in after recording]

**X post URL:** [fill in after posting]

**0G contract address:** [fill in from DEPLOYMENT_ADDRESSES.md after deploy]

**Track:** Track 2 — Agentic Trading Arena

**0G components used:**
- 0G Storage: every DecisionRecord uploaded via `src/integrations/zero_g/client.py`
- ERC-7857 iNFT: minted on 0G mainnet via `src/integrations/zero_g/inft.py` + `contracts/XRPFiINFT.sol`
- Explorer proof: chainscan.0g.ai link in README and DEPLOYMENT_ADDRESSES.md

**Description:** *(use the content from SUBMISSION.md)*

---

## Quick Re-run Gate (run before submitting)

```bash
cd ~/xrpfi-verif-copilot
uv run pytest tests/ -q        # must show 151 passed
uv run ruff check src/ tests/ demo/  # must show "All checks passed"
```

---

## Judging Criteria Alignment

| Criterion | Our Evidence |
|-----------|-------------|
| Technical Implementation | 151 tests, real 0G mainnet deploy, 2 live agents, Flare FAssets/FTSO/FDC |
| Product Value & Market Potential | XRP = $35B+ market cap, millions of holders wanting DeFi yield |
| UX & Demo Quality | DEMO_SCRIPT.md + working `demo/run_demo.py` |
| Team & Documentation | README, SUBMISSION.md, docs/architecture.md, FEEDBACK.md |
