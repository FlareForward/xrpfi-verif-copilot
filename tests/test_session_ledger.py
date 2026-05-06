import re

from src.contracts.decision_log import DecisionRecord
from src.session.ledger import load_sessions, save_session


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


def test_empty_ledger(tmp_path):
    assert load_sessions(path=tmp_path / "missing.json") == []


def test_session_id_format(tmp_path):
    saved = save_session([], [], path=tmp_path / "sessions.json")

    assert re.fullmatch(r"session_\d{8}T\d{6}Z_[a-f0-9]{8}", saved["session_id"])
