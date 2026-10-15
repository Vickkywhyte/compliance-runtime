"""Logging read-back tests (Lesson 5, C-45).

These assert observable behavior: the event is written to ``logs/app.jsonl``
and can be read back as valid JSON with the expected fields.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from compliance_runtime.utils.logging import configure_logging, get_logger

_LOG_FILE = Path("logs/app.jsonl")


def _flush() -> None:
    for handler in logging.getLogger().handlers:
        handler.flush()


def _last_line() -> str:
    return _LOG_FILE.read_text(encoding="utf-8").strip().splitlines()[-1]


def test_configure_logging_creates_log_file() -> None:
    configure_logging()
    get_logger("test").info("create_file_event")
    _flush()
    assert _LOG_FILE.exists()


def test_log_event_is_valid_json() -> None:
    configure_logging()
    get_logger("test").info("json_event", k="v")
    _flush()
    record = json.loads(_last_line())
    assert isinstance(record, dict)


def test_log_event_contains_expected_fields() -> None:
    configure_logging()
    get_logger("test").info("fields_event", answer=42)
    _flush()
    record = json.loads(_last_line())
    assert record["event"] == "fields_event"
    assert record["answer"] == 42
    assert record["level"] == "info"
    assert "timestamp" in record


def test_control_characters_are_escaped() -> None:
    configure_logging()
    get_logger("test").info("ctrl_event", payload="line1\nline2")
    _flush()
    line = _last_line()
    # The embedded newline must be escaped so the record is a single line.
    assert line.count("\n") == 0
    record = json.loads(line)
    assert record["payload"] == "line1\nline2"


def test_idempotent_configure() -> None:
    configure_logging()
    configure_logging()
    root = logging.getLogger()
    # Exactly the stream + rotating-file handler, no duplicates.
    assert len(root.handlers) == 2
