"""Tests for the FastAPI server (ADR-010) via TestClient."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from compliance_runtime.config.keys import set_keys_dir
from compliance_runtime.interception.server import create_app


@pytest.fixture()
def client(tmp_path: Path) -> Iterator[TestClient]:
    set_keys_dir(tmp_path)
    app = create_app("configs/runtime.yaml", db_path=tmp_path / "t.db")
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        set_keys_dir(None)


def _exec_body(amount, entity=None) -> dict:
    body = {
        "action": "issue_refund",
        "parameters": {"amount": amount, "currency": "EUR"},
        "agent_id": "a",
        "session_id": "s",
    }
    if entity is not None:
        body["entity_context"] = entity
    return body


def test_health_endpoint(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_execute_endpoint_allow(client: TestClient) -> None:
    resp = client.post("/v1/tools/execute", json=_exec_body(250))
    assert resp.status_code == 200
    assert resp.json()["disposition"] == "allow"


def test_execute_endpoint_deny(client: TestClient) -> None:
    resp = client.post("/v1/tools/execute",
                       json=_exec_body(250, entity={"fraud_flags": ["x"]}))
    assert resp.json()["disposition"] == "deny"


def test_execute_endpoint_approval(client: TestClient) -> None:
    resp = client.post("/v1/tools/execute", json=_exec_body(850))
    data = resp.json()
    assert data["disposition"] == "require_approval"
    assert data["request_id"]


def test_execute_openai_endpoint(client: TestClient) -> None:
    payload = {
        "tool_calls": [
            {"id": "call_1", "type": "function",
             "function": {"name": "issue_refund", "arguments": '{"amount": 250}'}}
        ],
        "agent_id": "a", "session_id": "s",
    }
    resp = client.post("/v1/tools/execute-openai", json=payload)
    assert resp.status_code == 200
    assert resp.json()["role"] == "tool"


def test_list_approvals_endpoint(client: TestClient) -> None:
    client.post("/v1/tools/execute", json=_exec_body(850))
    resp = client.get("/v1/approvals", params={"role": "compliance_officer"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_decide_endpoint(client: TestClient) -> None:
    created = client.post("/v1/tools/execute", json=_exec_body(850)).json()
    resp = client.post(
        f"/v1/approvals/{created['request_id']}/decide",
        json={"actor_id": "u", "actor_role": "compliance_officer",
              "decision": "approve", "rationale": "ok"},
    )
    assert resp.status_code == 200
    assert resp.json()["decision"] == "approve"


def test_get_evidence_endpoint(client: TestClient) -> None:
    created = client.post("/v1/tools/execute", json=_exec_body(250)).json()
    resp = client.get(f"/v1/evidence/{created['action_id']}")
    assert resp.status_code == 200
    assert resp.json()["action_id"] == created["action_id"]


def test_verify_endpoint(client: TestClient) -> None:
    client.post("/v1/tools/execute", json=_exec_body(250))
    resp = client.post("/v1/evidence/verify")
    assert resp.status_code == 200
    body = resp.json()
    assert body["chain_integrity"] is True
    assert body["signature_validity"] is True


def test_error_envelope_shape(client: TestClient) -> None:
    resp = client.post(
        "/v1/approvals/nonexistent/decide",
        json={"actor_id": "u", "actor_role": "compliance_officer",
              "decision": "approve"},
    )
    assert resp.status_code >= 400
    body = resp.json()
    assert "error" in body
    assert "code" in body["error"] and "message" in body["error"]


def test_no_traceback_in_error_response(tmp_path: Path) -> None:
    set_keys_dir(tmp_path)
    app = create_app("configs/runtime.yaml", db_path=tmp_path / "t.db")
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            def _boom(*args, **kwargs):
                raise RuntimeError("kaboom with secret stack")

            client.app.state.pipeline.execute = _boom  # type: ignore[assignment]
            resp = client.post("/v1/tools/execute", json=_exec_body(250))
            assert resp.status_code == 500
            text = resp.text
            assert "Traceback" not in text and "kaboom" not in text
            assert resp.json()["error"]["code"] == "RUNTIME_INTERNAL_ERROR"
    finally:
        set_keys_dir(None)
