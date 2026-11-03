"""Tests for the local OpenCode assistant endpoints."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fresh_urban_forest.service import _parse_agent_events, create_app
from tests.fixtures import make_dataset


def _events(reply: str = "The canopy cover is a raster estimate.") -> str:
    """Build a minimal JSON-lines event stream."""
    events = [
        {"type": "text", "sessionID": "ses_test", "part": {"text": reply}},
        {
            "type": "tool_use",
            "sessionID": "ses_test",
            "part": {
                "tool": "bash",
                "state": {"title": "inspect", "input": {"command": "fresh-urban-forest info"}},
            },
        },
    ]
    return "\n".join(json.dumps(event) for event in events) + "\n"


def test_agent_info_is_disabled_by_default(tmp_path: Path) -> None:
    """The assistant is off unless the service explicitly enables it."""
    dataset = make_dataset(tmp_path)
    client = TestClient(create_app(dataset, runtime_dir=tmp_path / "runtime"))
    info = client.get("/api/agent").json()
    assert info["enabled"] is False
    response = client.post("/api/agent/chat", json={"message": "hello"})
    assert response.status_code == 403


def test_agent_chat_runs_opencode_and_parses_events(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An enabled assistant runs the CLI and returns reply, session, and actions."""
    dataset = make_dataset(tmp_path)
    client = TestClient(
        create_app(
            dataset,
            runtime_dir=tmp_path / "runtime",
            allow_agent=True,
            agent_model="test/model",
            workspace=tmp_path,
        )
    )
    monkeypatch.setattr(
        "fresh_urban_forest.service.shutil.which", lambda _name: "/usr/bin/opencode"
    )

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        command = args[0]
        assert isinstance(command, list)
        assert command[0] == "/usr/bin/opencode"
        assert "run" in command
        assert "test/model" in command
        return subprocess.CompletedProcess(command, 0, stdout=_events(), stderr="")

    monkeypatch.setattr("fresh_urban_forest.service.subprocess.run", fake_run)
    response = client.post(
        "/api/agent/chat",
        json={"message": "What is canopy cover?", "context": {"view": "map"}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "raster estimate" in payload["reply"]
    assert payload["session"] == "ses_test"
    assert payload["actions"][0]["tool"] == "bash"


def test_agent_chat_reports_missing_opencode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing executable is a clear 503."""
    dataset = make_dataset(tmp_path)
    client = TestClient(create_app(dataset, runtime_dir=tmp_path / "runtime", allow_agent=True))
    monkeypatch.setattr("fresh_urban_forest.service.shutil.which", lambda _name: None)
    response = client.post("/api/agent/chat", json={"message": "hello"})
    assert response.status_code == 503
    assert "opencode" in response.json()["detail"]


def test_agent_chat_reports_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A slow assistant becomes a 504 rather than hanging the request."""
    dataset = make_dataset(tmp_path)
    client = TestClient(
        create_app(
            dataset,
            runtime_dir=tmp_path / "runtime",
            allow_agent=True,
            agent_timeout=0.01,
        )
    )
    monkeypatch.setattr(
        "fresh_urban_forest.service.shutil.which", lambda _name: "/usr/bin/opencode"
    )

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired("opencode", 0.01)

    monkeypatch.setattr("fresh_urban_forest.service.subprocess.run", fake_run)
    response = client.post("/api/agent/chat", json={"message": "hello"})
    assert response.status_code == 504


def test_agent_chat_reports_empty_reply(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty event stream is a 502 with the stderr detail."""
    dataset = make_dataset(tmp_path)
    client = TestClient(create_app(dataset, runtime_dir=tmp_path / "runtime", allow_agent=True))
    monkeypatch.setattr(
        "fresh_urban_forest.service.shutil.which", lambda _name: "/usr/bin/opencode"
    )
    monkeypatch.setattr(
        "fresh_urban_forest.service.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, stdout="", stderr="no text"),
    )
    response = client.post("/api/agent/chat", json={"message": "hello"})
    assert response.status_code == 502
    assert "no text" in response.json()["detail"]


def test_parse_agent_events_extracts_errors() -> None:
    """Errors and text are extracted from the event stream."""
    stream = "\n".join(
        [
            json.dumps({"type": "text", "part": {"text": "hello"}}),
            json.dumps({"type": "error", "error": {"message": "bad tool"}}),
            "not json",
        ]
    )
    reply, session, actions, errors = _parse_agent_events(stream)
    assert reply == "hello"
    assert session is None
    assert actions == []
    assert errors == ["bad tool"]
