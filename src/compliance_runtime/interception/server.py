"""FastAPI HTTP server (ADR-010, 09_RUNTIME_DESIGN §10).

Exposes the runtime pipeline over HTTP. Endpoints are ``async`` so every DB
access runs on the event-loop thread that created the connection (SQLite
connections are thread-affine). Errors are returned as a JSON envelope with no
traceback.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from compliance_runtime import __version__
from compliance_runtime.exceptions import ComplianceRuntimeError
from compliance_runtime.interception.models import ToolCallRequest
from compliance_runtime.interception.openai_compat import (
    parse_openai_tool_call,
    to_openai_tool_response,
    tool_call_id_of,
)
from compliance_runtime.interception.pipeline import RuntimePipeline, build_pipeline

_DEFAULT_CONFIG = "configs/runtime.yaml"


def _error_response(status: int, code: str, message: str) -> JSONResponse:
    """Return a traceback-free JSON error envelope."""
    return JSONResponse(
        status_code=status, content={"error": {"code": code, "message": message}}
    )


def create_app(
    config_path: str | Path = _DEFAULT_CONFIG,
    db_path: str | Path | None = None,
) -> FastAPI:
    """Build the FastAPI app, wiring the pipeline in the lifespan."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        pipeline, conn = build_pipeline(config_path, db_path=db_path)
        app.state.pipeline = pipeline
        app.state.conn = conn
        try:
            yield
        finally:
            pipeline.close()

    app = FastAPI(title="AI Compliance Runtime", version=__version__, lifespan=lifespan)

    @app.exception_handler(ComplianceRuntimeError)
    async def _runtime_error(request: Request, exc: ComplianceRuntimeError):
        return _error_response(422, type(exc).__name__, str(exc))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        # No traceback in the response (C-37 pattern).
        return _error_response(500, "RUNTIME_INTERNAL_ERROR", "internal error")

    def _pipeline(request: Request) -> RuntimePipeline:
        return request.app.state.pipeline

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "version": __version__, "git_sha": "unknown"}

    @app.post("/v1/tools/execute")
    async def execute(request: ToolCallRequest, http: Request):
        return _pipeline(http).execute(request)

    @app.post("/v1/tools/execute-openai")
    async def execute_openai(payload: dict[str, Any], http: Request):
        parsed = parse_openai_tool_call(payload)
        response = _pipeline(http).execute(parsed)
        return to_openai_tool_response(response, tool_call_id_of(payload))

    @app.get("/v1/approvals")
    async def list_approvals(http: Request, role: str | None = None):
        return _pipeline(http).list_pending_approvals(role)

    @app.get("/v1/approvals/{request_id}")
    async def get_approval(request_id: str, http: Request):
        found = _pipeline(http).get_approval(request_id)
        if found is None:
            return _error_response(404, "NOT_FOUND", "approval request not found")
        return found

    @app.post("/v1/approvals/{request_id}/decide")
    async def decide(request_id: str, body: dict[str, Any], http: Request):
        return _pipeline(http).decide_approval(
            request_id,
            actor_id=body["actor_id"],
            actor_role=body["actor_role"],
            decision=body["decision"],
            rationale=body.get("rationale"),
            edits=body.get("edits"),
        )

    @app.get("/v1/evidence/{action_id}")
    async def get_evidence(action_id: str, http: Request):
        record = _pipeline(http).get_action_record(action_id)
        if record is None:
            return _error_response(404, "NOT_FOUND", "action record not found")
        return record

    @app.post("/v1/evidence/verify")
    async def verify(http: Request):
        return _pipeline(http).verify_chain()

    return app


# Module-level app for `uvicorn compliance_runtime.interception.server:app`.
app = create_app()
