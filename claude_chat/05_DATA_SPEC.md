# Data Specification — AI Compliance Runtime

> **READ THIS FIRST (for Claude Code):**
> Every schema in the system is defined here. If code needs a new field,
> it is added here first, then in Pydantic models, then in code. Enums
> are locked; extending requires updating this doc and any config.
>
> **Dependencies:** `02_PRD.md` · `03_ARCHITECTURE.md` ·
> `04_TECH_DECISIONS.md` (ADR-003, ADR-004, ADR-005, ADR-006, ADR-008,
> ADR-015)
> **Depended on by:** `06_EVAL_SPEC.md` · `07_SECURITY_MODEL.md` ·
> `08_ROADMAP.md` · `09_RUNTIME_DESIGN.md`

---

## 1. Conventions

- **Pydantic v2** for every model crossing a module boundary
- **Timestamps:** timezone-aware UTC (`datetime.now(timezone.utc)`)
- **IDs:** ULIDs for new entities; deterministic hashes for chained
  artifacts
- **Enums:** `Literal` types in Pydantic; validated against controlled
  vocabulary
- **SQLite:** column names `snake_case`; row shape mirrors Pydantic
- **`extra="forbid"`** on configs; **`extra="ignore"`** on I/O models

## 2. Controlled vocabularies

```python
Disposition = Literal["allow", "deny", "require_approval", "allow_with_flag"]

ApprovalState = Literal["pending", "approved", "denied", "modified_approved", "expired"]

ApprovalDecision = Literal["approve", "deny", "modify_approve"]

Operator = Literal[
    "equals", "not_equals",
    "greater_than", "less_than", "greater_or_equal", "less_or_equal",
    "in", "not_in", "matches_regex",
]

ActorType = Literal["agent", "human", "system"]

AuditEntityType = Literal[
    "tool_call", "policy_evaluation", "action_record",
    "approval_request", "approval_decision", "audit_event",
]

ErrorCode = Literal[
    "POLICY_DENIED",
    "POLICY_APPROVAL_REQUIRED",
    "POLICY_VALIDATION_FAILED",
    "POLICY_LOAD_FAILED",
    "EVIDENCE_CHAIN_BROKEN",
    "EVIDENCE_SIGNATURE_INVALID",
    "APPROVAL_EXPIRED",
    "APPROVAL_CONFLICT",
    "RUNTIME_INTERNAL_ERROR",
]
```

## 3. Core entities

### 3.1 ToolCall

```python
class ToolCall(BaseModel):
    model_config = {"extra": "ignore"}

    call_id: str                        # ULID; unique per tool call
    correlation_id: str                 # groups calls from one agent session
    agent_id: str                       # identifier of the calling agent
    session_id: str                     # agent session ID
    action: str                         # tool name (e.g., "issue_refund")
    parameters: dict[str, Any]          # tool arguments
    received_at: datetime
    metadata: dict[str, Any] = {}       # optional caller-supplied metadata
```

**Persistence:** `tool_calls` table, primary key `call_id`.

### 3.2 PolicyEvaluation

```python
class PolicyEvaluation(BaseModel):
    model_config = {"extra": "ignore"}

    evaluation_id: str                  # ULID
    call_id: str                        # FK to ToolCall
    matched_rule_id: str | None         # None if no rule matched
    matched_rule_priority: int | None
    policy_version: str                 # version of the policy set evaluated
    disposition: Disposition
    reason: str                         # human-readable
    evidence: dict[str, Any]            # fields that matched
    evaluated_at: datetime
    evaluation_duration_ms: int
```

**Persistence:** `policy_evaluations` table, primary key `evaluation_id`.

### 3.3 ActionRecord

```python
class ActionRecord(BaseModel):
    model_config = {"extra": "ignore"}

    action_id: str                      # ULID
    call_id: str                        # FK to ToolCall
    evaluation_id: str                  # FK to PolicyEvaluation
    disposition: Disposition
    agent_id: str
    session_id: str
    action: str
    parameters_hash: str                # sha256 of parameters (not raw; may contain PII)
    timestamp: datetime

    previous_hash: str                  # hash of previous record (or GENESIS)
    current_hash: str                   # sha256 of this record's canonical form
    signature: str                      # Ed25519 signature (base64) of current_hash
    signing_key_id: str                 # identifier for the key that signed

    runtime_version: str
```

**Persistence:** `action_records` table, primary key `action_id`,
**append-only** (repository + SQLite triggers enforce).

### 3.4 ApprovalRequest

```python
class ApprovalRequest(BaseModel):
    model_config = {"extra": "ignore"}

    request_id: str                     # ULID
    action_id: str                      # FK to ActionRecord
    call_id: str                        # FK to ToolCall
    reason: str                         # why approval is required
    matched_rule_id: str
    severity: Literal["low", "medium", "high", "critical"]
    assignee_role: str                  # who should review
    ttl_seconds: int                    # time before auto-deny
    created_at: datetime
    expires_at: datetime
    state: ApprovalState                # starts as "pending"
    version: int                        # optimistic locking
```

**Persistence:** `approval_requests` table, primary key `request_id`,
index on `(state, assignee_role)`.

### 3.5 ApprovalDecision

```python
class ApprovalDecision(BaseModel):
    model_config = {"extra": "ignore"}

    decision_id: str                    # ULID
    request_id: str                     # FK to ApprovalRequest
    actor_id: str
    actor_role: str
    decision: ApprovalDecision
    edits: dict[str, Any] | None        # for modify_approve
    rationale: str | None               # for deny or modify_approve
    decided_at: datetime
```

**Persistence:** `approval_decisions` table, primary key `decision_id`,
**append-only**.

### 3.6 AuditEvent

```python
class AuditEvent(BaseModel):
    model_config = {"extra": "ignore"}

    event_id: str                       # ULID
    occurred_at: datetime
    actor_type: ActorType
    actor_id: str                       # agent_id, user_id, or "system"
    action: str                         # e.g., "action_recorded"
    entity_type: AuditEntityType
    entity_id: str
    correlation_id: str
    payload: dict[str, Any]
```

**Persistence:** `audit_events` table, primary key `event_id`,
**append-only**.

### 3.7 Policy (defined in YAML, loaded into memory)

```python
class PolicyCondition(BaseModel):
    model_config = {"extra": "forbid"}

    field: str                          # e.g., "action", "parameters.amount"
    operator: Operator
    value: Any

class PolicyRule(BaseModel):
    model_config = {"extra": "forbid"}

    id: str
    priority: int                       # ascending; first match wins
    description: str
    when: list[PolicyCondition]         # ALL must be true
    enforce: PolicyEnforcement

class PolicyEnforcement(BaseModel):
    model_config = {"extra": "forbid"}

    disposition: Disposition
    reason: str
    require_role: str | None = None     # for require_approval
    severity: Literal["low", "medium", "high", "critical"] | None = None
    ttl_seconds: int | None = None      # for require_approval

class Policy(BaseModel):
    model_config = {"extra": "forbid"}

    name: str
    version: str
    rules: list[PolicyRule]
```

## 4. Configuration schemas

### 4.1 `configs/runtime.yaml`

```yaml
runtime:
  version: "0.1.0"
  default_disposition: "allow_with_flag"   # used when no rule matches
  evidence_store_path: "data/runtime.db"
  keys_dir: "~/.compliance-runtime/keys"
  log_level: "INFO"

http:
  host: "0.0.0.0"
  port: 8000
  request_timeout_seconds: 30

approvals:
  default_ttl_seconds: 900
  max_pending_per_role: 500

evidence:
  hash_algorithm: "sha256"
  signature_algorithm: "ed25519"
```

### 4.2 `configs/policies/demo_policy.yaml`

```yaml
name: demo_policy
version: "1.0.0"
rules:
  - id: refund_limit
    priority: 10
    description: "Refunds over €500 require compliance officer approval"
    when:
      - field: "action"
        operator: "equals"
        value: "issue_refund"
      - field: "parameters.amount"
        operator: "greater_than"
        value: 500
    enforce:
      disposition: "require_approval"
      reason: "Refunds over €500 require compliance sign-off"
      require_role: "compliance_officer"
      severity: "high"
      ttl_seconds: 900

  - id: fraud_flagged_account
    priority: 5
    description: "Deny actions on fraud-flagged accounts"
    when:
      - field: "entity.fraud_flags"
        operator: "not_in"
        value: []
    enforce:
      disposition: "deny"
      reason: "Account is flagged for fraud investigation"

  - id: default_allow_refunds
    priority: 100
    description: "Allow refunds under €500 by default"
    when:
      - field: "action"
        operator: "equals"
        value: "issue_refund"
      - field: "parameters.amount"
        operator: "less_or_equal"
        value: 500
    enforce:
      disposition: "allow"
      reason: "Refund within authorized limit"
```

### 4.3 `configs/eval.yaml`

```yaml
benchmark_path: "data/eval/benchmark.jsonl"
metrics:
  enforcement:
    - policy_precision
    - policy_recall
    - false_positive_rate
    - false_negative_rate
    - policy_coverage
  evidence:
    - audit_completeness
    - chain_integrity
    - signature_validity
  oversight:
    - approval_latency_p50_ms
    - approval_latency_p95_ms
    - bypass_attempts_blocked_rate
bootstrap_samples: 1000
seed: 0
```

## 5. On-disk formats

| Artifact | Format | Path |
|---|---|---|
| Policies | YAML | `configs/policies/*.yaml` |
| Runtime config | YAML | `configs/runtime.yaml` |
| Eval config | YAML | `configs/eval.yaml` |
| Tool calls, evaluations, records | SQLite | `data/runtime.db` |
| Signing private key | PEM | `~/.compliance-runtime/keys/signing_key.pem` |
| Verification public key | PEM | `~/.compliance-runtime/keys/verification_key.pem` |
| Benchmark dataset | JSONL | `data/eval/benchmark.jsonl` |
| Eval results | JSON | `results/evals/{timestamp}.json` |
| Compliance dossiers | PDF | `results/dossiers/{timestamp}.pdf` |
| Application logs | JSONL | `logs/app.jsonl` |
| Mock agent scripts | JSON | `data/demo/agent_scripts/*.json` |

## 6. ID conventions

| Entity | Format | Derivation |
|---|---|---|
| `call_id` | ULID | generated on receipt |
| `correlation_id` | ULID | generated per agent session |
| `evaluation_id` | ULID | generated |
| `action_id` | ULID | generated |
| `request_id` | ULID | generated |
| `decision_id` | ULID | generated |
| `event_id` | ULID | generated |
| `previous_hash` | hex(64) | previous record's `current_hash`, or `"GENESIS"` for the first |
| `current_hash` | hex(64) | `sha256(canonical_json(record_without_hash_and_signature) + previous_hash)` |
| `signature` | base64 | `ed25519.sign(current_hash_bytes, private_key)` |

## 7. SQLite schema (DDL)

```sql
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
```

## 8. Canonical hashing

The `current_hash` is computed from a **canonical JSON representation**
of the record fields (excluding `current_hash` and `signature`), plus
the `previous_hash`. Canonicalization means:

- Keys sorted alphabetically
- No whitespace
- `datetime` serialized as ISO 8601 UTC
- `float` values serialized with full precision

```python
def canonical_hash(record_fields: dict, previous_hash: str) -> str:
    canonical = json.dumps(record_fields, sort_keys=True, separators=(",", ":"))
    payload = canonical + "|" + previous_hash
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

## 9. Policy condition fields

Supported fields for `PolicyCondition.field`:

| Field pattern | Type | Example |
|---|---|---|
| `action` | string | `"issue_refund"` |
| `parameters.<name>` | varies | `parameters.amount` |
| `agent_id` | string | `"support_agent_v3"` |
| `session_id` | string | `"sess_abc"` |
| `entity.<attr>` | varies | `entity.fraud_flags` |
| `timestamp.hour` | int | 0–23 |
| `rate.<action>_per_minute` | int | rolling window count |

**Anything not in this list is a validation error.** Extending the
field set requires an ADR amendment.

## 10. Migration policy

- SQLite schema changes are additive (add columns with defaults)
- Column removal requires two-phase migration (deprecate → drop in v2)
- `action_records`, `approval_decisions`, and `audit_events` never lose
  columns
- Migrations live in `src/compliance_runtime/storage/migrations/` as
  numbered SQL files, applied by `migrate.py`

## 11. What is NOT in this spec (yet)

- User authentication schema (v1 uses synthetic users)
- Multi-tenant isolation
- SCITT-compliant attestation receipts (v2)
- External GRC integration schemas (v2)