#!/usr/bin/env python
"""Dashboard smoke test — cross-thread repro (Lesson 2c).

Streamlit re-runs app.py on a fresh thread per widget interaction, and the
pipeline is cached across reruns. This smoke test reproduces that in-process
without launching a browser: it builds the pipeline on the main thread and
then queries it from a separate thread, asserting no
``sqlite3.ProgrammingError`` is raised. Hermetic (temp DB + temp key dir);
no network, no new deps.
"""

from __future__ import annotations

import sys
import tempfile
import threading
from pathlib import Path

from compliance_runtime.config.keys import set_keys_dir
from compliance_runtime.interception.models import ToolCallRequest
from compliance_runtime.interception.pipeline import build_pipeline


def main() -> int:
    passed = 0
    with tempfile.TemporaryDirectory() as tmp:
        set_keys_dir(tmp)
        try:
            pipeline, _ = build_pipeline("configs/runtime.yaml", db_path=f"{tmp}/d.db")
            pipeline.execute(ToolCallRequest(
                action="issue_refund", parameters={"amount": 250},
                agent_id="a", session_id="s",
            ))

            # Thread A (main): the connection was created here.
            assert len(pipeline.all_action_records()) == 1
            passed += 1

            # Thread B (fresh): simulates a Streamlit rerun on a new thread.
            result: dict[str, object] = {}

            def worker() -> None:
                try:
                    result["count"] = len(pipeline.all_action_records())
                except Exception as exc:  # noqa: BLE001 - capture to re-raise in main
                    result["error"] = exc

            thread = threading.Thread(target=worker)
            thread.start()
            thread.join()

            if "error" in result:
                raise AssertionError(
                    f"cross-thread query failed: {result['error']!r}"
                )
            assert result["count"] == 1, result
            passed += 1

            pipeline.close()
        finally:
            set_keys_dir(None)

    print(f"PASS: all {passed} assertions passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
