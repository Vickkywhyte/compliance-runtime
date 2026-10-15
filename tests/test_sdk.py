"""Tests for the Python SDK (ADR-011)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from compliance_runtime.config.keys import set_keys_dir
from compliance_runtime.interception.sdk import ToolExecutor


@pytest.fixture()
def executor(tmp_path: Path) -> Iterator[ToolExecutor]:
    set_keys_dir(tmp_path)
    ex = ToolExecutor.from_config("configs/runtime.yaml", db_path=tmp_path / "t.db")
    try:
        yield ex
    finally:
        ex.close()
        set_keys_dir(None)


def test_sdk_execute_allow(executor: ToolExecutor) -> None:
    resp = executor.execute("issue_refund", {"amount": 250}, agent_id="a",
                            session_id="s")
    assert resp.disposition == "allow"


def test_sdk_execute_deny(executor: ToolExecutor) -> None:
    resp = executor.execute("issue_refund", {"amount": 250}, agent_id="a",
                            session_id="s", entity_context={"fraud_flags": ["x"]})
    assert resp.disposition == "deny"


def test_sdk_execute_approval(executor: ToolExecutor) -> None:
    resp = executor.execute("issue_refund", {"amount": 850}, agent_id="a",
                            session_id="s")
    assert resp.disposition == "require_approval"
    assert resp.request_id is not None


def test_sdk_execute_openai_tool_call(executor: ToolExecutor) -> None:
    payload = {
        "tool_calls": [
            {"id": "call_1", "type": "function",
             "function": {"name": "issue_refund", "arguments": '{"amount": 250}'}}
        ],
        "agent_id": "a", "session_id": "s",
    }
    tool = executor.execute_openai_tool_call(payload)
    assert tool.role == "tool"
    assert tool.tool_call_id == "call_1"
    assert json.loads(tool.content)["disposition"] == "allow"


def test_sdk_from_config_uses_isolated_db(tmp_path: Path) -> None:
    set_keys_dir(tmp_path)
    db = tmp_path / "isolated.db"
    try:
        with ToolExecutor.from_config("configs/runtime.yaml", db_path=db) as ex:
            ex.execute("issue_refund", {"amount": 250}, agent_id="a", session_id="s")
        assert db.exists()  # the executor wrote to the isolated DB file
    finally:
        set_keys_dir(None)


def test_sdk_context_manager_closes_connection(tmp_path: Path) -> None:
    import sqlite3

    set_keys_dir(tmp_path)
    try:
        with ToolExecutor.from_config(
            "configs/runtime.yaml", db_path=tmp_path / "t.db"
        ) as ex:
            conn = ex.pipeline._tool_calls._conn
        # After __exit__, the connection is closed.
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")
    finally:
        set_keys_dir(None)
