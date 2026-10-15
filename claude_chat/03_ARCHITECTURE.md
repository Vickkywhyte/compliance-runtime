# Architecture — AI Compliance Runtime

> **READ THIS FIRST (for Claude Code):**
> This document defines *how* the system is structured. Every module
> boundary, every data flow, and every concurrency decision lives here.
> Implementation details live in `04_TECH_DECISIONS.md` (ADRs) and
> `05_DATA_SPEC.md` (schemas).
>
> **Dependencies:** `00_DISCOVERY.md` · `01_LESSONS_APPLIED.md` ·
> `02_PRD.md`
> **Depended on by:** `04_TECH_DECISIONS.md` · `05_DATA_SPEC.md` ·
> `07_SECURITY_MODEL.md` · `08_ROADMAP.md` · `09_RUNTIME_DESIGN.md`

---

## 1. System overview

```
┌───────────────────────────────────────────────────────────────────────┐
│                         AI AGENT (external)                          │
│  Any agent using OpenAI-compatible function calling                   │
└─────────────────────────────┬─────────────────────────────────────────┘
                              │ tool call (JSON)
                              ▼
┌───────────────────────────────────────────────────────────────────────┐
│                   RUNTIME — INTERCEPTION LAYER                        │
│   HTTP API (POST /v1/tools/execute)                                   │
│   or Python SDK (for in-process integration)                          │
└─────────────────────────────┬─────────────────────────────────────────┘
                              ▼
┌───────────────────────────────────────────────────────────────────────┐
│                   POLICY ENGINE                                        │
│   Load policies from YAML → evaluate in priority order                │
│   Four dispositions: allow / deny / require_approval / allow_with_flag│
└────┬────────────────┬────────────────┬────────────────┬──────────────┘
     │                │                │                │
     ▼                ▼                ▼                ▼
  ┌──────┐        ┌──────┐         ┌─────────┐      ┌────────┐
  │ALLOW │        │DENY  │         │APPROVAL │      │FLAGGED │
  └───┬──┘        └───┬──┘         └────┬────┘      └───┬────┘
      │               │                 │               │
      ▼               ▼                 ▼               ▼
┌───────────────────────────────────────────────────────────────────────┐
│                   EVIDENCE RECORDER                                    │
│   SHA-256 hash chain · Ed25519 signature · append-only store          │
└─────────────────────────────┬─────────────────────────────────────────┘
                              ▼
┌───────────────────────────────────────────────────────────────────────┐
│                   RESPONSE TO AGENT                                    │
│   OpenAI-compatible tool response                                     │
└───────────────────────────────────────────────────────────────────────┘

     ┌──────────────────────────┐       ┌──────────────────────────┐
     │  HUMAN-IN-THE-LOOP       │       │  DOSSIER GENERATOR       │
     │  Streamlit dashboard     │       │  PDF compliance report   │
     │  Approve / deny / modify │       │  EU AI Act Art. 12       │
     └──────────────────────────┘       └──────────────────────────┘

     ┌──────────────────────────────────────────────────────────┐
     │  EVALUATION HARNESS (parallel)                           │
     │  Policy precision/recall · FPR/FNR · approval latency    │
     │  Evidence completeness · chain integrity                 │
     └──────────────────────────────────────────────────────────┘
```

## 2. Component responsibilities

| Component | Responsibility | Interface |
|---|---|---|
| **Interceptor** | Receive tool calls from agents | `intercept(call: ToolCall) -> ToolResponse` |
| **PolicyLoader** | Load and validate YAML policies | `load_policies(path) -> list[Policy]` |
| **PolicyEngine** | Evaluate tool calls against policies | `evaluate(call) -> PolicyEvaluation` |
| **DispositionHandler** | Route to allow/deny/approval/flag | `handle(evaluation) -> ToolResponse` |
| **ApprovalService** | Manage human approval workflow | `request() / decide() / expire()` |
| **EvidenceRecorder** | Sign and append action records | `record(action) -> ActionRecord` |
| **EvidenceVerifier** | Verify hash chain and signatures | `verify() -> VerificationReport` |
| **DossierGenerator** | Produce PDF compliance report | `generate(range) -> Path` |
| **Evaluator** | Compute runtime metrics | `evaluate(benchmark) -> EvalReport` |
| **Dashboard** | Streamlit UI | Server-rendered views |
| **SDK** | Python client for in-process integration | `ToolExecutor.execute(call) -> Response` |

## 3. Data flows

### 3.1 Tool call interception

```
Agent code
    │
    ▼
Tool definition registered with runtime
    │
    ▼
Agent calls tool with args
    │
    ▼
Interceptor receives {action, params, agent_id, session_id}
    │
    ▼
PolicyEngine evaluates in priority order
    │
    ├── match found → disposition
    └── no match → default disposition (configurable; default = allow_with_flag)
    │
    ▼
EvidenceRecorder writes ActionRecord (signed, hash-chained)
    │
    ▼
DispositionHandler produces response:
    ├── allow           → {success: true, ...}
    ├── deny            → {success: false, rule_id, reason, evidence}
    ├── require_approval→ {success: null, status: pending, request_id}
    └── allow_with_flag → {success: true, flagged: true, ...}
    │
    ▼
Response returned to agent
```

### 3.2 Approval workflow

```
ApprovalRequest created (state=pending, ttl=900s)
    │
    ▼
Dashboard shows request to the correct role
    │
    ▼
Reviewer examines: action, params, agent, matched rule, evidence
    │
    ▼
Reviewer takes action:
    ├── approve → state=approved
    ├── deny    → state=denied
    └── modify  → state=modified_approved, with edits
    │
    ▼
ApprovalService uses optimistic locking (version check)
    │
    ▼
On success:
    ├── ActionRecord updated (state transition recorded)
    ├── AuditEvent written
    └── Callback fired (optional; allows the agent to continue)
    │
    ▼
On TTL expiry:
    ├── state=expired
    ├── treated as denial
    └── AuditEvent written
```

### 3.3 Evidence recording

```
Action decision produced
    │
    ▼
Build ActionRecord:
    ├── action_id (ULID)
    ├── timestamp
    ├── action (name, params)
    ├── agent_id, session_id
    ├── matched_rule_id, policy_version
    ├── disposition
    ├── previous_hash (from last record)
    ├── current_hash = sha256(record_content + previous_hash)
    └── signature = ed25519_sign(current_hash, private_key)
    │
    ▼
Append to SQLite (append-only enforced by triggers)
    │
    ▼
Verification:
    ├── Recompute hash of each record
    ├── Verify chain (record.previous_hash == prev_record.current_hash)
    └── Verify signature with public key
```

### 3.4 Dossier generation

```
Input: time range, agent filter
    │
    ▼
Query ActionRecords in range
    │
    ▼
Compute:
    ├── Total actions
    ├── Disposition breakdown (allow/deny/approval/flagged)
    ├── Policy coverage (% actions with a matched rule)
    ├── Approval statistics (rate, latency, override rate)
    └── Chain verification report
    │
    ▼
Map to EU AI Act Article 12 obligations:
    ├── Logging (Art. 12.1)
    ├── Traceability (Art. 12.2)
    ├── Record retention (Art. 12.3)
    └── Human oversight (Art. 14, referenced)
    │
    ▼
Render PDF via reportlab
    │
    ▼
Write to results/dossiers/{timestamp}.pdf
```

## 4. Concurrency model

| Stage | Concurrency | Rationale |
|---|---|---|
| Interception | Fully async; ≥ 100 calls/s | Agent calls arrive concurrently |
| Policy evaluation | Per-call; CPU-bound | Rule evaluation is fast (< 50 ms) |
| Evidence recording | Serialized per DB | SQLite WAL mode; single writer |
| Approval service | Optimistic locking | Prevent double-approval |
| Dashboard | Async per request | Streamlit handles |
| Dossier generation | Sequential | CPU-bound; runs on-demand |

**Global concurrency limits:**
- No LLM calls in the critical path (v1 uses rules only)
- Evidence writes serialized via SQLite connection pool
- Approval state transitions use optimistic locking (version field)

## 5. Persistence

| Concern | Store | Rationale |
|---|---|---|
| Policies | Filesystem (YAML) | Human-editable, git-versioned |
| Tool calls + evaluations | SQLite | Structured, transactional |
| Action records | SQLite (append-only, triggers) | Tamper-evident |
| Approval requests | SQLite | Structured, queryable |
| Approval decisions | SQLite | Append-only |
| Audit events | SQLite (append-only) | Full traceability |
| Signing keys | Filesystem (`~/.compliance-runtime/keys/`) | Generated on first run |
| Application logs | Filesystem (`logs/app.jsonl`) | Structured JSON |

**Why SQLite:** $0, single file, ACID, adequate for 100k+ records.

## 6. Module structure

```
src/compliance_runtime/
├── __init__.py
├── config/                    # Pydantic config loaders
│   ├── loader.py
│   ├── models.py
│   └── keys.py                # Ed25519 key generation and loading
├── policy/
│   ├── __init__.py
│   ├── models.py              # Policy Pydantic models
│   ├── loader.py              # YAML loading
│   ├── validators.py          # Schema validation
│   └── engine.py              # Evaluation engine
├── interception/
│   ├── __init__.py
│   ├── models.py              # ToolCall, ToolResponse
│   ├── server.py              # FastAPI app
│   ├── sdk.py                 # Python SDK for in-process integration
│   └── openai_compat.py       # OpenAI-compatible schema
├── dispositions/
│   ├── __init__.py
│   ├── allow.py
│   ├── deny.py
│   ├── approval.py
│   └── flagged.py
├── approvals/
│   ├── __init__.py
│   ├── service.py             # Approve / deny / modify
│   ├── state.py               # State machine + optimistic locking
│   └── ttl.py                 # TTL expiry handling
├── evidence/
│   ├── __init__.py
│   ├── recorder.py            # Record + sign
│   ├── verifier.py            # Verify chain + signatures
│   ├── signing.py             # Ed25519 utilities
│   └── hashing.py             # SHA-256 chain utilities
├── dossier/
│   ├── __init__.py
│   ├── generator.py
│   ├── ai_act_mapping.py      # EU AI Act Article 12 mapping
│   └── templates/
├── evaluation/
│   ├── __init__.py
│   ├── metrics/
│   ├── runner.py
│   └── report.py
├── dashboard/
│   ├── __init__.py
│   ├── app.py
│   ├── views/
│   └── components/
├── storage/
│   ├── __init__.py
│   ├── db.py
│   ├── models.py              # Pydantic models
│   ├── actions.py             # Action repository
│   ├── approvals.py
│   └── audit.py               # Append-only audit
├── mock_agent/
│   ├── __init__.py
│   ├── agent.py               # The demo agent
│   └── scripts/               # Scripted tool call sequences
├── utils/
│   ├── __init__.py
│   ├── logging.py
│   ├── ids.py
│   └── time.py
└── exceptions.py
```

Every module has:
- Module docstring
- Public classes/functions typed and documented
- `if __name__ == "__main__"` self-test entry point

## 7. Extension points

| Add a... | Do this |
|---|---|
| New policy operator | Add to `policy/validators.py` and `policy/engine.py` |
| New disposition type | Subclass `DispositionHandler`, register |
| New dossier section | Add to `dossier/generator.py` |
| New metric | Subclass `Metric` in `evaluation/metrics/`, add to `06_EVAL_SPEC.md` |
| New agent framework | Extend `interception/openai_compat.py` (v2) |
| New storage backend | Implement the repository ABCs in `storage/` |

## 8. Cross-cutting concerns

### 8.1 Logging
- `structlog` JSON to stdout + `logs/app.jsonl`
- Every log line: `ts, level, event, correlation_id, component`
- Verified by read-back

### 8.2 Correlation IDs
- Every tool call has a correlation ID (ULID)
- All log lines and audit events reference it

### 8.3 Error handling
- Typed exceptions in `exceptions.py`
- Fail loud on policy file errors (refuse to start)
- Fail soft per-action; continue processing other calls

### 8.4 Configuration
- Pydantic models for every config file
- Loaded once at startup; immutable at runtime
- `os.getenv` only in `config/loader.py`

### 8.5 Security (see `07_SECURITY_MODEL.md`)
- The runtime is a high-value target
- Threat model written before code
- Signing keys never logged or committed
- Policies treated as trusted; tool call content treated as untrusted

## 9. Non-choices (explicit)

- No message queue (Kafka, RabbitMQ)
- No microservices
- No Kubernetes
- No blockchain
- No external GRC integration
- No multi-tenancy
- No real authentication (v1)
- No LLM in the critical path

## 10. Extension path (v2 and beyond)

- **v2.1** — Additional agent frameworks (LangChain, CrewAI, AutoGen)
- **v2.2** — SCITT-compliant attestation
- **v2.3** — Multi-tenant support
- **v2.4** — GRC integrations (ServiceNow, Archer)
- **v2.5** — Real-time streaming
- **v2.6** — LLM-based policy suggestions

## 11. Deployment topology

```
┌────────────────────────────────────────────────┐
│  Docker Compose (single host)                  │
│                                                │
│  ┌──────────────┐        ┌──────────────────┐ │
│  │  runtime     │        │  dashboard       │ │
│  │  (FastAPI)   │◄───────│  (Streamlit)     │ │
│  │  :8000       │        │  :8501           │ │
│  └──────┬───────┘        └──────────────────┘ │
│         │                                     │
│         ▼                                     │
│  ┌──────────────────────────────────────────┐ │
│  │  Volumes:                                │ │
│  │  ./data  (SQLite, keys)                  │ │
│  │  ./configs/policies  (YAML)              │ │
│  │  ./logs                                  │ │
│  │  ./results/dossiers                      │ │
│  └──────────────────────────────────────────┘ │
└────────────────────────────────────────────────┘
```

## 12. Architecture decision summary

Every architectural choice here is defended in `04_TECH_DECISIONS.md`
as an ADR. This document describes *what*; the ADRs describe *why*.