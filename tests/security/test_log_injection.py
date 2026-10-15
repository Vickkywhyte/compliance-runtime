"""Log-injection tests (C-45, C-46).

A crafted parameter value containing a newline and fake JSON must appear as
a single log line with the control characters escaped, so line-by-line log
parsers cannot be tricked into seeing a forged event.
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


def test_newline_in_log_value_is_escaped() -> None:
    configure_logging()
    get_logger("inj").info("newline_event", note="before\nafter")
    _flush()
    line = _last_line()
    assert "\n" not in line
    assert json.loads(line)["note"] == "before\nafter"


def test_fake_json_in_log_value_stays_one_line() -> None:
    configure_logging()
    payload = '\n{"event": "fake_admin_grant", "level": "info"}'
    get_logger("inj").info("real_event", note=payload)
    _flush()
    line = _last_line()
    # The injected newline is escaped: one physical line, one real event.
    assert line.count("\n") == 0
    record = json.loads(line)
    assert record["event"] == "real_event"
    assert record["note"] == payload
