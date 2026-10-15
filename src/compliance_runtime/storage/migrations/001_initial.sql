-- 001_initial — initial schema for the AI Compliance Runtime.
-- Verbatim DDL from claude_chat/05_DATA_SPEC.md §7. Pure DDL; no Python.
-- Applied by src/compliance_runtime/storage/migrate.py (tracked in
-- schema_migrations). Append-only guarantees per ADR-015 / C-10.

CREATE TABLE tool_calls (
    call_id TEXT PRIMARY KEY,
    correlation_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    action TEXT NOT NULL,
    parameters TEXT NOT NULL,           -- JSON
    received_at TEXT NOT NULL,
    metadata TEXT
);
CREATE INDEX idx_calls_correlation ON tool_calls(correlation_id);
CREATE INDEX idx_calls_agent ON tool_calls(agent_id);

CREATE TABLE policy_evaluations (
    evaluation_id TEXT PRIMARY KEY,
    call_id TEXT NOT NULL,
    matched_rule_id TEXT,
    matched_rule_priority INTEGER,
    policy_version TEXT NOT NULL,
    disposition TEXT NOT NULL,
    reason TEXT NOT NULL,
    evidence TEXT NOT NULL,             -- JSON
    evaluated_at TEXT NOT NULL,
    evaluation_duration_ms INTEGER NOT NULL,
    FOREIGN KEY (call_id) REFERENCES tool_calls(call_id)
);

CREATE TABLE action_records (
    action_id TEXT PRIMARY KEY,
    call_id TEXT NOT NULL,
    evaluation_id TEXT NOT NULL,
    disposition TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    action TEXT NOT NULL,
    parameters_hash TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    current_hash TEXT NOT NULL,
    signature TEXT NOT NULL,
    signing_key_id TEXT NOT NULL,
    runtime_version TEXT NOT NULL,
    FOREIGN KEY (call_id) REFERENCES tool_calls(call_id),
    FOREIGN KEY (evaluation_id) REFERENCES policy_evaluations(evaluation_id)
);
CREATE INDEX idx_records_timestamp ON action_records(timestamp);

-- Append-only enforcement (ADR-015)
CREATE TRIGGER action_records_no_update
BEFORE UPDATE ON action_records
BEGIN
    SELECT RAISE(ABORT, 'action_records is append-only');
END;
CREATE TRIGGER action_records_no_delete
BEFORE DELETE ON action_records
BEGIN
    SELECT RAISE(ABORT, 'action_records is append-only');
END;

CREATE TABLE approval_requests (
    request_id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL,
    call_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    matched_rule_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    assignee_role TEXT NOT NULL,
    ttl_seconds INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    state TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (action_id) REFERENCES action_records(action_id)
);
CREATE INDEX idx_approvals_state_role ON approval_requests(state, assignee_role);

CREATE TABLE approval_decisions (
    decision_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    decision TEXT NOT NULL,
    edits TEXT,                          -- JSON, nullable
    rationale TEXT,
    decided_at TEXT NOT NULL,
    FOREIGN KEY (request_id) REFERENCES approval_requests(request_id)
);

CREATE TRIGGER approval_decisions_no_update
BEFORE UPDATE ON approval_decisions
BEGIN
    SELECT RAISE(ABORT, 'approval_decisions is append-only');
END;
CREATE TRIGGER approval_decisions_no_delete
BEFORE DELETE ON approval_decisions
BEGIN
    SELECT RAISE(ABORT, 'approval_decisions is append-only');
END;

CREATE TABLE audit_events (
    event_id TEXT PRIMARY KEY,
    occurred_at TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    payload TEXT NOT NULL                -- JSON
);
CREATE INDEX idx_audit_entity ON audit_events(entity_type, entity_id);
CREATE INDEX idx_audit_correlation ON audit_events(correlation_id);

CREATE TRIGGER audit_events_no_update
BEFORE UPDATE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events is append-only');
END;
CREATE TRIGGER audit_events_no_delete
BEFORE DELETE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events is append-only');
END;
