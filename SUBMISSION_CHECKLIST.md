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
| 4 | Code quality | 157/157 tests, ruff clean | ✅ |
| 5 | X post draft ready | `X_POST_DRAFT.md` | ✅ |
| 6 | Demo script ready | `DEMO_SCRIPT.md` | ✅ |
| 7 | Environment vars externalized (no hardcoded mainnet) | `.env` + `src/config.py` | ✅ |
| 8 | iNFT contract deployable on mainnet | `contracts/deploy.py` — mainnet-ready | ✅ |
| 9 | Judge-facing handout ready | `docs/JUDGE_HANDOUT.md` | ✅ |
| 10 | 0G mainnet proof captured | Contract `0x01fE5698a2448d0fc336295df9977796030C79C4`; token ID `1`; tx `0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd` | ✅ |

---

### ✅ Completed operator/deploy items

| # | Requirement | What to do | Status |
|---|-------------|-----------|--------|
| A | Fund build wallet | Completed; 0G mainnet deployment exists | ✅ |
| B | Deploy iNFT contract | Contract deployed at `0x01fE5698a2448d0fc336295df9977796030C79C4` | ✅ |
| C | Run end-to-end demo proof | Demo iNFT token ID `1`; mint tx `0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd` | ✅ |

### ⏸ Remaining operator-required items

| # | Requirement | What to do | Status |
|---|-------------|-----------|--------|
| D | **Make GitHub repo public** | GitHub → Settings → Danger Zone → Change visibility → Public. Repo path: `~/xrpfi-verif-copilot/` | ⏸ Required before submission |
| E | **Record demo video** | Follow `DEMO_SCRIPT.md`. Record under 3 minutes. Upload to Loom or YouTube as a public or unlisted link. | ⏸ Required |
| F | **Post on X** | Use `X_POST_DRAFT.md`. Attach the demo video or screenshot. Include #0GHackathon and #BuildOn0G. | ⏸ Required |
| G | **Fill HackQuest submission form** | Go to `https://www.hackquest.io/en/hackathons/0G-APAC-Hackathon`. Fill in GitHub URL, demo video URL, X post URL, 0G contract address, and project description. | ⏸ Final step |

---

## What to Fill in the HackQuest Form

**Project name:** XRPFi Verifiable Copilot

**One-liner:** A 2-agent AI system that helps XRP holders enter Flare DeFi — every agent decision permanently verifiable on 0G storage and minted as an iNFT.

**GitHub repo:** https://github.com/flareforward/xrpfi-verif-copilot *(make public first)*

**Demo video:** Add the Loom or YouTube URL after recording.

**X post URL:** Add the public X URL after posting.

**0G contract address:** `0x01fE5698a2448d0fc336295df9977796030C79C4`

**0G explorer proof:** https://chainscan.0g.ai/tx/0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd

**Track:** Track 2 — Agentic Trading Arena

**0G components used:**
- 0G Storage: every DecisionRecord uploaded via `src/integrations/zero_g/client.py`
- ERC-7857 iNFT: minted on 0G mainnet via `src/integrations/zero_g/inft.py` + `contracts/XRPFiINFT.sol`
- Explorer proof: chainscan.0g.ai link in README and DEPLOYMENT_ADDRESSES.md
- Judge handout: `docs/JUDGE_HANDOUT.md`

**Description:** *(use the content from SUBMISSION.md)*

---

## Quick Re-run Gate (run before submitting)

```bash
cd ~/xrpfi-verif-copilot
uv run pytest tests/ -q
uv run ruff check src/ tests/ demo/ scripts/ web/
```

---

## Judging Criteria Alignment

| Criterion | Our Evidence |
|-----------|-------------|
| Technical Implementation | 157 tests, real 0G mainnet deploy, 2 live agents, Flare FAssets/FTSO/FDC |
| Product Value & Market Potential | XRP = $35B+ market cap, millions of holders wanting DeFi yield |
| UX & Demo Quality | DEMO_SCRIPT.md + working `demo/run_demo.py` |
| Team & Documentation | README, SUBMISSION.md, docs/architecture.md, docs/JUDGE_HANDOUT.md, FEEDBACK.md |
