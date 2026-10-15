"""Structured logging with secret scrubbing (ADR-009).

Configures ``structlog`` on top of the stdlib logging module so that:

- Every log line is a single JSON object (C-45: control characters are
  escaped by the JSON renderer).
- Output goes to both stdout and ``logs/app.jsonl`` (rotating 10 MB x 5).
- A scrubber processor redacts secret-looking strings before they are
  rendered (C-07, C-15): API keys, ``Bearer`` tokens, PEM private-key
  markers, and the values of environment variables whose names contain
  ``KEY``, ``TOKEN``, ``SECRET``, or ``PEM``.
- Noisy third-party loggers (httpx, httpcore, kaleido) are capped at
  WARNING.

Exports :func:`configure_logging` and :func:`get_logger`.
"""

from __future__ import annotations

import logging
import logging.handlers
import re
from pathlib import Path
from typing import Any

import structlog

from compliance_runtime.config.loader import sensitive_env_values

_LOG_DIR = Path("logs")
_LOG_FILE = _LOG_DIR / "app.jsonl"
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
_BACKUP_COUNT = 5
_NOISY_LOGGERS = ("httpx", "httpcore", "kaleido")

_REDACTED = "[REDACTED]"
_REDACTED_PEM = "[REDACTED_PEM]"

# Secret-looking token patterns. sk- covers sk-, sk-or-, sk-ant-.
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9\-_]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9\-_.=]+"),
)
_PEM_MARKERS = (
    "-----BEGIN PRIVATE KEY-----",
    "-----BEGIN OPENSSH PRIVATE KEY-----",
    "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN EC PRIVATE KEY-----",
)

_configured = False


def _scrub_string(value: str, env_secrets: frozenset[str]) -> str:
    """Redact secret material from a single string."""
    if any(marker in value for marker in _PEM_MARKERS):
        return _REDACTED_PEM
    for secret in env_secrets:
        if secret and secret in value:
            value = value.replace(secret, _REDACTED)
    for pattern in _SECRET_PATTERNS:
        value = pattern.sub(_REDACTED, value)
    return value


def _scrub(obj: Any, env_secrets: frozenset[str]) -> Any:
    """Recursively scrub secrets from an event-dict value."""
    if isinstance(obj, str):
        return _scrub_string(obj, env_secrets)
    if isinstance(obj, dict):
        return {k: _scrub(v, env_secrets) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return type(obj)(_scrub(v, env_secrets) for v in obj)
    return obj


def _make_scrubber() -> Any:
    """Build a structlog processor that redacts secrets in every event."""
    env_secrets = frozenset(sensitive_env_values())

    def processor(
        logger: Any, method_name: str, event_dict: dict[str, Any]
    ) -> dict[str, Any]:
        return {k: _scrub(v, env_secrets) for k, v in event_dict.items()}

    return processor


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog + stdlib logging. Idempotent.

    Safe to call more than once: repeated calls replace the handler set
    rather than stacking duplicate handlers.
    """
    global _configured

    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, log_level.upper(), logging.INFO)

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        _make_scrubber(),
    ]

    # Renderer for records coming through the stdlib handlers. The JSON
    # renderer escapes newlines and control characters (C-45).
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    file_handler = logging.handlers.RotatingFileHandler(
        _LOG_FILE,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    # Idempotency: drop any handlers we installed on a previous call.
    for handler in list(root.handlers):
        root.removeHandler(handler)
    root.addHandler(stream_handler)
    root.addHandler(file_handler)
    root.setLevel(level)

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    _configured = True


def get_logger(name: str | None = None) -> Any:
    """Return a bound structlog logger, configuring logging if needed."""
    if not _configured:
        configure_logging()
    return structlog.get_logger(name)


def _self_test() -> None:
    """Configure logging, emit an event, and read it back from the file."""
    import json

    configure_logging()
    configure_logging()  # idempotent: must not duplicate handlers

    log = get_logger("selftest")
    log.info("selftest_event", answer=42, note="line1\nline2")

    for handler in logging.getLogger().handlers:
        handler.flush()

    last = _LOG_FILE.read_text(encoding="utf-8").strip().splitlines()[-1]
    record = json.loads(last)  # must be valid JSON
    assert record["event"] == "selftest_event", record
    assert record["answer"] == 42, record
    # C-45: the embedded newline is escaped, so the line holds one record.
    assert "\n" not in last
    print("logging self-test: PASS")


if __name__ == "__main__":
    _self_test()
