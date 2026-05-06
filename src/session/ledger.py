"""Persistent session ledger for judge demo runs."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

DEFAULT_LEDGER_PATH = Path.home() / ".xrpfi" / "sessions.json"


def save_session(
    steps: Sequence[dict[str, Any]],
    records: Sequence[Any],
    *,
    path: Path | None = None,
) -> dict[str, Any]:
    """Append one completed judge demo run to the session ledger."""
    ledger_path = path or DEFAULT_LEDGER_PATH
    sessions = load_sessions(path=ledger_path)
    serialized_records = [_serialize_record(record) for record in records]
    session: dict[str, Any] = {
        "session_id": _new_session_id(),
        "timestamp": datetime.now(UTC).isoformat(),
        "steps": list(steps),
        "records": serialized_records,
    }
    session["inft"] = _extract_inft(steps, serialized_records)
    sessions.insert(0, session)
    _write_sessions(ledger_path, sessions)
    return session


def load_sessions(*, path: Path | None = None) -> list[dict[str, Any]]:
    """Return persisted judge demo sessions, newest first."""
    ledger_path = path or DEFAULT_LEDGER_PATH
    if not ledger_path.exists():
        return []

    try:
        raw = json.loads(ledger_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    if not isinstance(raw, list):
        return []

    return [cast(dict[str, Any], session) for session in raw if isinstance(session, dict)]


def _write_sessions(path: Path, sessions: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_text(json.dumps(sessions, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _new_session_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"session_{timestamp}_{uuid4().hex[:8]}"


def _serialize_record(record: object) -> dict[str, Any]:
    if hasattr(record, "model_dump"):
        dumped = record.model_dump(mode="json")
        return cast(dict[str, Any], dict(dumped)) if isinstance(dumped, dict) else {"value": dumped}
    if isinstance(record, dict):
        return cast(dict[str, Any], record)
    return {"value": str(record)}


def _extract_inft(
    steps: Sequence[dict[str, Any]],
    records: Sequence[dict[str, Any]],
) -> dict[str, str] | None:
    for record in records:
        zero_g = record.get("zero_g")
        if not isinstance(zero_g, dict):
            continue
        token_id = zero_g.get("inft_token_id")
        explorer_url = zero_g.get("inft_explorer_url")
        if token_id or explorer_url:
            return {
                "token_id": str(token_id or "1"),
                "explorer_url": str(explorer_url or ""),
            }

    for step in steps:
        value = str(step.get("value", ""))
        if step.get("step") != 10 and "token=" not in value:
            continue
        token_match = re.search(r"token=([^\s]+)", value)
        url_match = re.search(r"https?://\S+", value)
        if token_match or url_match:
            return {
                "token_id": token_match.group(1) if token_match else "1",
                "explorer_url": url_match.group(0) if url_match else "",
            }
    return None
