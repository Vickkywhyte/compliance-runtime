# Runtime Design — AI Compliance Runtime

> **READ THIS FIRST (for Claude Code):**
> This document defines how the runtime reasons and enforces. It is the
> specification for the policy evaluation logic, the disposition
> handlers, and the evidence chain. Every decision is deterministic.
> There is no LLM in the critical path (ADR-013).
>
> **Dependencies:** `03_ARCHITECTURE.md` · `04_TECH_DECISIONS.md` ·
> `05_DATA_SPEC.md` · `06_EVAL_SPEC.md` · `07_SECURITY_MODEL.md`
> **Depended on by:** Phases 3, 4, 5, 6 code

---

## 1. What the runtime is

The runtime is a **deterministic gatekeeper**. It does not think, plan,
or reason. It:

1. Receives a tool call
2. Evaluates it against a set of rules
3. Returns a disposition
4. Records the decision

Every step is specified. Every step is testable. Every step produces
evidence.

**The runtime never calls an LLM.** No exceptions. ADR-013.

## 2. The evaluation pipeline

### 2.1 Input

A `ToolCall`:
```json
{
  "call_id": "01J...",
  "correlation_id": "01J...",
  "agent_id": "support_agent_v3",
  "session_id": "sess_abc",
  "action": "issue_refund",
  "parameters": {"customer_id": "cust_8842", "amount": 1200, "currency": "EUR"},
  "received_at": "2026-10-15T14:00:00Z",
  "metadata": {}
}
```

Optionally, an `entity_context`:
```json
{
  "customer_id": "cust_8842",
  "fraud_flags": ["credit_card_chargeback_risk"],
  "risk_tier": "high"
}
```

The context is provided by the caller (the agent framework) or looked up
via a configured resolver. It is used for policy conditions that
reference `entity.*`.

### 2.2 Step 1 — Schema validation

Before any policy evaluation:

1. The action name is validated against the whitelist.
2. If the action is not whitelisted → `deny` with
   `POLICY_VALIDATION_FAILED`.
3. The parameters are validated against the registered schema for that
   action. Missing required fields → `deny` (C-03).
4. Type mismatches → `deny` (C-02).
5. Prompt injection markers in any string parameter → `deny` with
   security warning (C-08).

If any check fails, the pipeline short-circuits to evidence recording.

### 2.3 Step 2 — Policy evaluation

Load the active policy set. Evaluate rules in **priority order**
(ascending). The first rule whose conditions are ALL true determines the
disposition.

**Condition evaluation:**

For each `PolicyCondition`:
- Resolve the `field` against the tool call + context:
  - `action` → `tool_call.action`
  - `parameters.<name>` → `tool_call.parameters[name]` (validated field path, no eval)
  - `agent_id` → `tool_call.agent_id`
  - `session_id` → `tool_call.session_id`
  - `entity.<attr>` → `entity_context[attr]`
  - `timestamp.hour` → hour of `received_at`
  - `rate.<action>_per_minute` → rolling window count (see §5)
- Apply the `operator` against the resolved value and the `value`.

If the field path does not exist → the condition is `False` (never raise
for missing fields).

**Rule matching:** A rule matches if ALL its conditions evaluate to
`True`. The first matching rule (lowest `priority` number) wins.

**No matching rule:** the default disposition from
`configs/runtime.yaml` is applied (default `allow_with_flag`). This is
recorded as `matched_rule_id: null`.

### 2.4 Step 3 — Disposition handling

Four dispositions. Each produces a specific response to the agent.

#### 2.4.1 `allow`

Response:
```json
{
  "call_id": "01J...",
  "success": true,
  "result": {"status": "allowed"},
  "disposition": "allow"
}
```

The caller is expected to execute the tool.

#### 2.4.2 `deny`

Response:
```json
{
  "call_id": "01J...",
  "success": false,
  "error": {
    "code": "POLICY_DENIED",
    "message": "Account is flagged for fraud investigation",
    "rule_id": "fraud_flagged_account",
    "evidence": {"entity.fraud_flags": ["credit_card_chargeback_risk"]}
  }
}
```

The caller MUST NOT execute the tool.

#### 2.4.3 `require_approval`

Response:
```json
{
  "call_id": "01J...",
  "success": null,
  "status": "pending",
  "request_id": "01J...",
  "expires_at": "2026-10-15T14:15:00Z"
}
```

The caller MUST NOT execute the tool yet. On approval, the runtime
provides a callback mechanism (a URL or an SDK event) to notify the
caller.

#### 2.4.4 `allow_with_flag`

Response:
```json
{
  "call_id": "01J...",
  "success": true,
  "result": {"status": "allowed"},
  "disposition": "allow_with_flag",
  "flagged": true
}
```

The caller executes the tool. The record is marked for post-hoc review.

### 2.5 Step 4 — Evidence recording

Every evaluation (regardless of disposition) produces an `ActionRecord`.

Order of operations:
1. Compute `parameters_hash = sha256(canonical_json(parameters))`
2. Load the last record's `current_hash` (or `"GENESIS"`)
3. Compute `current_hash` from canonical fields + `previous_hash`
4. Sign `current_hash` with Ed25519 → `signature`
5. Insert the record into `action_records` (append-only)
6. Write an `AuditEvent` in the same transaction

**All five writes happen in a single SQLite transaction.** Either all
succeed or none do.

## 3. Determinism guarantees

Given the same tool call, same context, same policy set, and same
previous evidence chain:

- The disposition is the same
- The `matched_rule_id` is the same
- The `current_hash` is the same
- The `signature` is the same (Ed25519 is deterministic)

**Test:** run the runtime twice on the same inputs (with the same
previous hash) and assert identical outputs.

## 4. Response to agents

Responses follow OpenAI-compatible tool response format:

```json
{
  "tool_call_id": "call_abc123",
  "role": "tool",
  "content": "<JSON string of the runtime response>"
}
```

The `content` field is a JSON string of the runtime's structured
response. This keeps the format compatible with any agent that speaks
OpenAI function calling.

**Design rationale:** agents that receive a denial can:
- Present the reason to the user
- Escalate to a human
- Try a different action

Agents that receive `require_approval` can:
- Inform the user that a review is pending
- Wait for the callback (if configured)
- Move on to other work and check back later

## 5. Rate limiting

Per-agent, per-action rolling window. Default: 100 calls per minute per
agent.

Implementation:
- An in-memory sliding window counter (per-process)
- Counts are also persisted periodically for the dashboard
- Exceeding the limit → `deny` with `POLICY_DENIED` and a rate-limit
  reason
- Metrics: `rate_limit_hits_per_minute`

**Note:** In-process counters are sufficient for v1 (single-process
deployment). Multi-process deployment (v2) requires an external
counter (Redis or SQLite-based).

## 6. The policy file format

Fully specified in `05_DATA_SPEC.md` §3.7 and §4.2.

**Required fields per rule:**
- `id` — stable, unique identifier
- `priority` — integer, ascending; first match wins
- `description` — human-readable
- `when` — list of conditions (ALL must match)
- `enforce` — disposition + reason + optional fields

**Validation on startup:**
- All rules have unique `id`s
- All `priority` values are unique
- All conditions use valid operators and field paths
- All `require_approval` rules specify `require_role`
- The policy set has a `name` and `version`

**If validation fails, the runtime refuses to start.** (C-31)

## 7. Evidence chain construction

### 7.1 Canonical hashing

```python
def canonicalize(fields: dict) -> str:
    """Deterministic JSON serialization."""
    return json.dumps(
        fields,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,  # handles datetime, etc.
    )
```

`_json_default` handles:
- `datetime` → ISO 8601 UTC string
- `UUID` → string
- `Decimal` → string (to preserve precision)
- `bytes` → base64 string

### 7.2 Hash computation

```python
def compute_current_hash(record_fields: dict, previous_hash: str) -> str:
    canonical = canonicalize(record_fields)
    payload = canonical + "|" + previous_hash
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

Fields included in `record_fields`:
- `action_id`, `call_id`, `evaluation_id`, `disposition`
- `agent_id`, `session_id`, `action`, `parameters_hash`
- `timestamp`, `runtime_version`
- NOT included: `previous_hash`, `current_hash`, `signature`

### 7.3 Signing

```python
def sign_hash(current_hash: str, private_key) -> str:
    signature = private_key.sign(current_hash.encode("utf-8"))
    return base64.b64encode(signature).decode("ascii")
```

Ed25519 is deterministic: same message + same key = same signature.

### 7.4 Chain verification

```python
def verify_chain(records: list[ActionRecord], public_key) -> VerificationReport:
    for i, record in enumerate(records):
        # recompute hash
        expected_prev = records[i-1].current_hash if i > 0 else "GENESIS"
        if record.previous_hash != expected_prev:
            return VerificationReport(chain_integrity=False, broken_at=i)
        expected_hash = compute_current_hash(
            record_fields(record), record.previous_hash
        )
        if record.current_hash != expected_hash:
            return VerificationReport(chain_integrity=False, broken_at=i)
        # verify signature
        try:
            public_key.verify(
                base64.b64decode(record.signature),
                record.current_hash.encode("utf-8"),
            )
        except InvalidSignature:
            return VerificationReport(signature_validity=False, broken_at=i)
    return VerificationReport(chain_integrity=True, signature_validity=True)
```

The verifier is a pure function — it does not depend on the runtime
being online. It can run offline against an exported record set.

## 8. The mock agent

For demo and testing, a mock agent simulates an LLM-driven agent
producing tool calls.

```python
class MockAgent:
    """Reads scripted tool calls from JSON and executes them via the runtime."""

    def __init__(self, script_path: Path, executor: ToolExecutor):
        self.script = json.loads(script_path.read_text())
        self.executor = executor

    def run(self) -> list[ToolCallResult]:
        results = []
        for step in self.script["steps"]:
            result = self.executor.execute(
                action=step["action"],
                parameters=step["parameters"],
                entity_context=step.get("entity_context"),
            )
            results.append(result)
        return results
```

Script format (`data/demo/agent_scripts/demo_001.json`):
```json
{
  "name": "demo_001",
  "description": "Refund workflow with a fraud-flagged account",
  "steps": [
    {
      "action": "issue_refund",
      "parameters": {"customer_id": "cust_1001", "amount": 250, "currency": "EUR"},
      "entity_context": {"customer_id": "cust_1001", "fraud_flags": []}
    },
    {
      "action": "issue_refund",
      "parameters": {"customer_id": "cust_1001", "amount": 850, "currency": "EUR"},
      "entity_context": {"customer_id": "cust_1001", "fraud_flags": []}
    },
    {
      "action": "issue_refund",
      "parameters": {"customer_id": "cust_8842", "amount": 1200, "currency": "EUR"},
      "entity_context": {"customer_id": "cust_8842", "fraud_flags": ["credit_card_chargeback_risk"]}
    }
  ]
}
```

The demo runs three scripts and shows:
- The allowed action (250, no flags)
- The paused action (850, exceeds limit)
- The denied action (1200, fraud-flagged)

No LLM required.

## 9. The Python SDK

```python
from compliance_runtime.sdk import ToolExecutor

executor = ToolExecutor.from_config("configs/runtime.yaml")

result = executor.execute(
    action="issue_refund",
    parameters={"customer_id": "cust_8842", "amount": 1200, "currency": "EUR"},
    entity_context={"customer_id": "cust_8842", "fraud_flags": ["credit_card_chargeback_risk"]},
)

if result.disposition == "deny":
    raise RuntimeError(f"Action denied: {result.reason}")
```

The SDK:
- Loads policies once at construction
- Holds the evidence recorder and signing key
- Executes the same pipeline as the HTTP server
- Returns a typed response object

## 10. The HTTP API

```
POST /v1/tools/execute
Content-Type: application/json

{
  "action": "issue_refund",
  "parameters": {...},
  "entity_context": {...},
  "agent_id": "...",
  "session_id": "...",
  "correlation_id": "..."
}
```

Response: JSON with the same structure as the SDK result.

Other endpoints:
- `GET /v1/approvals` — list pending approvals
- `GET /v1/approvals/{id}` — detail
- `POST /v1/approvals/{id}/decide` — approve / deny / modify
- `GET /v1/evidence/{action_id}` — retrieve record
- `POST /v1/evidence/verify` — verify chain
- `POST /v1/dossiers/generate` — generate dossier

## 11. What the runtime never does

- Never calls an LLM (ADR-013)
- Never executes the underlying tool (only authorizes or denies)
- Never modifies an existing evidence record (append-only)
- Never bypasses approval (all approval dispositions require human action)
- Never invents a rule (only rules from loaded policies apply)
- Never accepts a tool call with an unknown action
- Never logs a private key
- Never starts with an invalid policy set

## 12. Failure modes

| Failure | Behavior |
|---|---|
| Policy file malformed | Refuse to start (C-31) |
| Tool call malformed (bad schema) | `deny` with `POLICY_VALIDATION_FAILED` |
| Prompt injection marker in parameter | `deny` with security warning |
| Rate limit exceeded | `deny` with rate-limit reason |
| SQLite write failure | Transaction rolls back; error returned to agent |
| Signing key missing | Generate on first run; if generation fails, refuse to start |
| Last record's hash missing | Use `"GENESIS"` only if no records exist; else error |
| Concurrent write to evidence | Bounded queue; writes serialized via SQLite WAL |

## 13. Testing strategy

Every component has:

- **Happy path test:** well-formed input produces expected disposition
- **Edge case test:** missing fields, wrong types, unexpected shapes
- **Security test:** bypass attempt fails safely
- **Determinism test:** same input → same output
- **Evidence test:** record appears in the chain correctly

**No component ships without these five test categories.**

## 14. What "deterministic" means here

Given identical inputs and identical policy set, the runtime produces
identical outputs. There are no LLMs, no randomness, no time-based
divergence (timestamps come from the caller, not from `datetime.now()`).

**Test:** feed the same tool call twice with the same previous hash;
assert byte-identical action records (except the ULIDs, which are
generated but not included in the hash).

**Wait — ULIDs are generated per call.** How is this deterministic?
Answer: the ULID is generated but is NOT part of the hashed fields.
Only the hashed fields need to be deterministic. The signature is over
the hash, so it's deterministic too.