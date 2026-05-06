import re

from src.contracts.decision_log import DecisionRecord
from src.session.ledger import load_sessions, save_session
from web.server import _build_gallery_entries


def make_record() -> DecisionRecord:
    return DecisionRecord(
        agent_name="mint-helper",
        agent_ens="mint-helper.eth",
        action_type="mint",
        input_summary="Mint 100 XRP into FXRP",
        reasoning="Fixture reasoning for the session ledger.",
        action_taken="Minted fixture FXRP",
        result_summary="Fixture mint complete",
    )


def test_save_load_roundtrip(tmp_path):
    ledger_path = tmp_path / "sessions.json"
    steps = [{"index": 1, "label": "FTSO live prices", "status": "complete"}]

    saved = save_session(steps, [make_record()], path=ledger_path)
    loaded = load_sessions(path=ledger_path)

    assert loaded == [saved]
    assert loaded[0]["steps"] == steps
    assert loaded[0]["records"][0]["agent_ens"] == "mint-helper.eth"
    assert loaded[0]["started_at"]
    assert loaded[0]["finished_at"]


def test_empty_ledger(tmp_path):
    assert load_sessions(path=tmp_path / "missing.json") == []


def test_session_id_format(tmp_path):
    saved = save_session([], [], path=tmp_path / "sessions.json")

    assert re.fullmatch(r"session_\d{8}T\d{6}Z_[a-f0-9]{8}", saved["session_id"])


def test_save_session_accepts_started_at(tmp_path):
    ledger_path = tmp_path / "sessions.json"
    started_at = "2026-05-05T16:00:00+00:00"

    saved = save_session([], [], path=ledger_path, started_at=started_at)

    assert saved["started_at"] == started_at
    assert saved["finished_at"] >= started_at


def test_gallery_entry_shape_from_sessions():
    sessions = [
        {
            "session_id": "session_new",
            "timestamp": "2026-05-05T16:00:14+00:00",
            "started_at": "2026-05-05T16:00:00+00:00",
            "finished_at": "2026-05-05T16:00:14+00:00",
            "steps": [
                {"step": 1, "label": "FTSO live prices", "status": "ok"},
                {
                    "step": 9,
                    "label": "0G storage",
                    "status": "ok",
                    "value": "tx=0xabc123 https://chainscan.0g.ai/tx/0xabc123",
                },
                {"step": 10, "label": "iNFT minted", "status": "warn"},
            ],
            "records": [
                {
                    "zero_g": {
                        "storage_tx_hash": "0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd",
                    }
                }
            ],
            "inft": {
                "token_id": "1",
                "explorer_url": "https://chainscan.0g.ai/tx/0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd",
            },
        }
    ]

    gallery = _build_gallery_entries(sessions)

    assert gallery == [
        {
            "session_id": "session_new",
            "timestamp": "2026-05-05T16:00:14+00:00",
            "steps_completed": 2,
            "steps_total": 10,
            "inft_token_id": "1",
            "inft_explorer_url": "https://chainscan.0g.ai/tx/0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd",
            "storage_tx_hash": "0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd",
            "storage_is_real": True,
            "duration_seconds": 14,
        }
    ]


def test_gallery_entry_marks_local_storage_fallback():
    gallery = _build_gallery_entries(
        [
            {
                "session_id": "session_local",
                "timestamp": "2026-05-05T16:00:00+00:00",
                "steps": [
                    {
                        "step": 9,
                        "label": "0G storage",
                        "status": "warn",
                        "value": "tx=0xlocal_proof_abc123",
                    }
                ],
                "records": [],
                "inft": None,
            }
        ]
    )

    assert gallery[0]["storage_tx_hash"] == "0xlocal_proof_abc123"
    assert gallery[0]["storage_is_real"] is False
    assert gallery[0]["duration_seconds"] is None
