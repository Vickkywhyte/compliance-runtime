# Architecture Decision Records — AI Compliance Runtime

> **READ THIS FIRST (for Claude Code):**
> These 18 ADRs are **locked**. Every code decision must trace to one of
> them. If a proposed change contradicts an ADR, stop and propose a new
> ADR that supersedes it — do not silently deviate. ADRs are immutable
> once locked; they can only be superseded.
>
> **Dependencies:** `00_DISCOVERY.md` · `01_LESSONS_APPLIED.md` ·
> `02_PRD.md` · `03_ARCHITECTURE.md`
> **Depended on by:** `05_DATA_SPEC.md` · `06_EVAL_SPEC.md` ·
> `07_SECURITY_MODEL.md` · `08_ROADMAP.md` · `09_RUNTIME_DESIGN.md`

---

## ADR-001 — Python 3.11 as the implementation language

**Status:** Locked

**Context:** Two prior projects used Python 3.11 successfully. The
compliance runtime needs mature libraries for cryptography, HTTP,
SQLite, Streamlit, and Pydantic — all Python-first.

**Decision:** Python 3.11.

**Consequences:**
- ✅ Best ecosystem for the required libraries
- ✅ Pydantic v2, structlog, SQLite, Chroma all stable on 3.11
- ✅ Precedent: same interpreter as prior projects reduces onboarding
- ⚠️ GIL limits true parallelism; mitigated by async I/O

**Alternatives:**
- TypeScript: weaker crypto ecosystem
- Go: faster, but no mature Streamlit equivalent
- Rust: overkill for portfolio scope

---

## ADR-002 — OpenAI-compatible function calling as the only integration point

**Status:** Locked

**Context:** AI agents use many frameworks (LangChain, CrewAI, AutoGen,
OpenAI Assistants, Anthropic tool use, Ollama, custom). Supporting all
of them creates unbounded surface area. The industry is converging on
OpenAI-compatible function calling as the de facto standard.

**Decision:** Integrate with OpenAI-compatible function calling only.

**Consequences:**
- ✅ One integration point — depth, not breadth
- ✅ Works with OpenAI, Anthropic via compatibility mode, Ollama,
  OpenRouter, vLLM, and any framework exposing the OpenAI shape
- ✅ Easier to test, audit, and document
- ⚠️ Some frameworks with custom tool-call formats need an adapter
  (documented as v2 work)

**Alternatives:**
- Multiple frameworks in v1: unacceptable scope expansion
- Custom protocol: reinventing an existing standard

---

## ADR-003 — SQLite as the primary datastore

**Status:** Locked

**Context:** Need structured storage for action records, approval
requests, decisions, and audit events. Estimated volume: 10k–1M records
over 6 months. Must be $0, ACID-compliant, and reproducible.

**Decision:** SQLite, single file at `data/runtime.db`, WAL mode.

**Consequences:**
- ✅ $0, no server, single file
- ✅ ACID transactions (critical for approval state + evidence chain)
- ✅ Adequate for 1M+ records
- ✅ WAL mode enables concurrent reads while one writer holds the lock
- ⚠️ Not appropriate for multi-node deployment
- ⚠️ Migration path to Postgres documented for v2

**Alternatives:**
- Postgres: overkill for v1, adds container
- DuckDB: strong for analytics, weaker on OLTP transactions
- Filesystem + JSON: no transactions, no queries

---

## ADR-004 — SHA-256 hash chain + Ed25519 signatures for evidence

**Status:** Locked

**Context:** Evidence must be tamper-evident. A simple log is not
sufficient — a regulator needs cryptographic proof that records have not
been modified. Multiple emerging standards (SCITT, TRACE, AAI-1) all
require cryptographic attestation.

**Decision:**
- Every action record includes `previous_hash` and `current_hash`,
  forming a SHA-256 hash chain
- Every record is signed with Ed25519 using a key generated on first run
- Signing keys are stored at `~/.compliance-runtime/keys/` and never
  logged or committed
- Verification recomputes the chain and checks every signature

**Consequences:**
- ✅ Tamper-evident: modifying any record breaks the chain
- ✅ Signable and verifiable offline
- ✅ Standard primitives (`cryptography` library)
- ✅ Aligns with emerging attestation standards
- ⚠️ Key management is a real concern (documented in `07_SECURITY_MODEL.md`)
- ⚠️ Chain verification is O(n) — acceptable for realistic data volumes

**Alternatives:**
- Merkle tree: overkill; adds complexity without v1 benefit
- Blockchain: unacceptable complexity and cost
- HMAC: not asymmetric; verifier needs the signing key
- No cryptographic proof: fails the tamper-evident requirement

---

## ADR-005 — YAML-based policy definitions with priority-ordered rules

**Status:** Locked

**Context:** Policies must be human-readable, versioned in git, and
testable. Complex expression languages (Rego, CEL) add learning curve
without v1 benefit.

**Decision:** Policies are YAML files in `configs/policies/`. Rules are
ordered by explicit `priority` field (ascending; first match wins).
Conditions use a fixed operator set (equals, not_equals, greater_than,
less_than, in, not_in, matches_regex).

**Consequences:**
- ✅ Human-editable; diffable in git
- ✅ No custom parser needed
- ✅ Well-defined semantics; no ambiguity
- ⚠️ Limited expressiveness compared to Rego/CEL
- ⚠️ Complex policies may need workarounds

**Alternatives:**
- Rego (OPA): powerful but steep learning curve
- CEL: similar issue
- Python callbacks: unsafe (arbitrary code execution)
- JSON: less human-readable than YAML

---

## ADR-006 — Four dispositions, closed set

**Status:** Locked

**Context:** Enforcement outcomes must be a closed set. Adding new
dispositions ad-hoc would break the state machine and evaluation.

**Decision:** Four dispositions only:
- `allow` — action proceeds
- `deny` — action blocked with reason
- `require_approval` — action paused; human decision required
- `allow_with_flag` — action proceeds but marked for review

**Consequences:**
- ✅ Simple state machine
- ✅ Well-defined responses to agents
- ✅ Measurable across all four
- ⚠️ Some policies may want "allow with condition" — handled by
  re-evaluating after the condition is met (v2)

**Alternatives:**
- More dispositions (defer, escalate, etc.): scope creep
- Custom dispositions per policy: breaks evaluation consistency

---

## ADR-007 — Human-in-the-loop approval with optimistic locking and TTL

**Status:** Locked

**Context:** Approval workflows must be atomic and idempotent. Multiple
reviewers may open the same request concurrently. Requests must not
hang indefinitely if the approver is unavailable.

**Decision:**
- Approval requests have a TTL (default 900 s)
- Approve/deny/modify transitions use optimistic locking (version check)
- Expired requests are treated as denials
- Every transition writes an audit event in the same transaction

**Consequences:**
- ✅ Single-winner semantics under concurrent access
- ✅ No hung requests
- ✅ Full audit trail per decision
- ⚠️ TTL must be tuned per deployment
- ⚠️ Approval callbacks require idempotency at the agent side (documented)

**Alternatives:**
- Pessimistic locking: blocks readers unnecessarily
- No TTL: requests can hang indefinitely
- Auto-approval on timeout: violates human-in-the-loop

---

## ADR-008 — Pydantic v2 for all cross-module data

**Status:** Locked

**Context:** The runtime has strict schemas (an ActionRecord must have
certain fields; an ApprovalRequest must have a TTL). Data crosses module
boundaries constantly.

**Decision:** Pydantic v2 for every model crossing a module boundary.
`extra="forbid"` on configs; `extra="ignore"` on I/O models.

**Consequences:**
- ✅ Schema violations raise at boundaries
- ✅ Serialization for free (JSON, SQLite row mapping)
- ✅ Type-safe; catches errors early
- ⚠️ Learning curve for contributors new to Pydantic v2

**Alternatives:**
- dataclasses: no validation
- attrs: no JSON serialization for free
- Marshmallow: older, more verbose

---

## ADR-009 — structlog for structured logging with secret scrubbing

**Status:** Locked

**Context:** Compliance requires auditable, queryable logs. The prior
projects had logging misconfiguration issues. Signing keys and any
sensitive content must never be logged.

**Decision:** `structlog` with stdlib integration. JSON output to stdout
and `logs/app.jsonl` (rotating 10 MB × 5). A processor scrubs strings
matching known secret patterns (private key PEM markers, `sk-*` keys,
etc.) before logging.

**Consequences:**
- ✅ Every log line is a JSON object
- ✅ Read-back verified in Phase 1
- ✅ Logs are queryable
- ✅ Secrets cannot leak through logs
- ⚠️ Scrubber must be comprehensive; tested against known patterns

**Alternatives:**
- stdlib logging only: no structured events
- Loguru: no first-class structlog integration
- No scrubber: unacceptable for a security-critical component

---

## ADR-010 — FastAPI for the HTTP interception endpoint

**Status:** Locked

**Context:** The runtime must be integrable from any language or
framework. HTTP is the universal interface. The agent calls a URL
instead of executing the tool directly.

**Decision:** FastAPI for the HTTP layer.

**Consequences:**
- ✅ Async-native; handles concurrent calls well
- ✅ Auto-generated OpenAPI docs
- ✅ Pydantic integration for request/response validation
- ✅ Well-known ecosystem
- ⚠️ Adds a required HTTP server to the deployment (mitigated by also
  providing a Python SDK for in-process use)

**Alternatives:**
- Flask: synchronous; slower for concurrent calls
- gRPC: overkill; HTTP is simpler
- In-process only (no HTTP): limits integration options

---

## ADR-011 — Python SDK alongside the HTTP API

**Status:** Locked

**Context:** HTTP adds latency (~5-50 ms per call). For high-throughput
or latency-sensitive use cases, an in-process integration is preferable.

**Decision:** Provide a Python SDK (`compliance_runtime.sdk.ToolExecutor`)
that runs the same policy engine and evidence recorder in-process.

**Consequences:**
- ✅ Two integration options: HTTP (universal) and Python (fast)
- ✅ Same code path, same evidence format
- ✅ Enables embedded deployment
- ⚠️ Two surfaces to test
- ⚠️ SDK changes are breaking changes when shipped

**Alternatives:**
- HTTP only: acceptable but not optimal
- SDK only: limits language integration

---

## ADR-012 — Streamlit for the approval dashboard

**Status:** Locked

**Context:** Need an approval interface fast. The audience is compliance
officers, not developers. Prior projects used Streamlit successfully.

**Decision:** Streamlit for the dashboard.

**Consequences:**
- ✅ Ship in days, not weeks
- ✅ Renders tables, charts, forms — all needed here
- ✅ Single language (Python) across stack
- ⚠️ Not designed for high-traffic production UIs
- ⚠️ If customer-facing, would pick React — documented as v2

**Alternatives:**
- React + FastAPI: 3-5× build time
- Gradio: weaker layouts
- Plain HTML: more work

---

## ADR-013 — No LLM in the critical path

**Status:** Locked

**Context:** LLM calls add latency (100s of ms to seconds), cost, and
nondeterminism. The runtime's core job — enforce policy — does not
require an LLM.

**Decision:** Policy evaluation is rule-based only. No LLM calls in the
interception path.

**Consequences:**
- ✅ Deterministic decisions
- ✅ Fast (< 50 ms per action)
- ✅ $0 marginal cost
- ✅ Auditable (no "the model decided")
- ⚠️ Some policies that would benefit from semantic understanding are
  out of scope for v1 (documented as v2)

**Alternatives:**
- LLM-based policy evaluation: unacceptable latency and cost
- Hybrid (rules first, LLM for edge cases): complexity not justified

---

## ADR-014 — Closed operator set for policy conditions

**Status:** Locked

**Context:** Policy conditions need to be expressive enough to cover
real cases but simple enough to validate and evaluate deterministically.

**Decision:** Closed operator set:
- `equals`, `not_equals`
- `greater_than`, `less_than`, `greater_or_equal`, `less_or_equal`
- `in`, `not_in`
- `matches_regex`

**Consequences:**
- ✅ Deterministic evaluation
- ✅ Simple validator
- ✅ Predictable performance
- ⚠️ Complex conditions require multiple rules
- ⚠️ No user-defined operators in v1

**Alternatives:**
- Full expression language: too complex
- Python callbacks: security risk (arbitrary code)
- No operators: too limited

---

## ADR-015 — Append-only evidence store with SQLite triggers

**Status:** Locked

**Context:** Evidence records must be tamper-evident. The repository
layer enforces append-only, but a direct database access could bypass
the repository.

**Decision:** SQLite triggers reject UPDATE and DELETE on
`action_records`, `approval_decisions`, and `audit_events`. Defense in
depth: repository enforces append-only AND database enforces
append-only.

**Consequences:**
- ✅ Tampering impossible even with direct DB access
- ✅ Complements the hash chain (chain proves integrity; triggers
  prevent tampering)
- ✅ Tested via direct SQL attempt in test suite
- ⚠️ Schema migrations must handle triggers carefully

**Alternatives:**
- Repository-only enforcement: bypassable
- File-level immutability: not portable; OS-specific

**Note:** This pattern was used in the prior compliance monitoring
agent and worked well.

---

## ADR-016 — Mock agent for demo and testing

**Status:** Locked

**Context:** The runtime needs an agent to enforce against. Requiring
a real LLM for the demo adds cost, network dependency, and
nondeterminism.

**Decision:** Ship a mock agent (`mock_agent/agent.py`) that reads
scripted tool-call sequences from JSON and attempts each action through
the runtime. No LLM required for the demo path.

**Consequences:**
- ✅ Demo runs offline, deterministic, in seconds
- ✅ Tests use the mock agent (no network)
- ✅ Live demo with real LLM is a separate target (`make demo-live`)
- ⚠️ Demo doesn't showcase LLM integration directly (mitigated by
  providing the live variant)

**Alternatives:**
- Real LLM only: slower demo, network dependency
- Both required: unnecessary friction for new users

---

## ADR-017 — Single key pair per runtime instance

**Status:** Locked

**Context:** Every signed record requires a private key. Multiple keys
add rotation complexity and verification ambiguity.

**Decision:** One Ed25519 key pair per runtime instance. Generated on
first run at `~/.compliance-runtime/keys/signing_key.pem`. Public key
exported to `~/.compliance-runtime/keys/verification_key.pem`.

**Consequences:**
- ✅ Simple model
- ✅ All records verifiable with one public key
- ✅ No rotation in v1 (acceptable for portfolio scope)
- ⚠️ Key rotation is a v2 concern (multi-key verification)
- ⚠️ Key loss means losing the ability to sign new records; existing
  records remain verifiable with the public key

**Alternatives:**
- Multiple keys with key IDs: complexity not justified for v1
- External KMS: adds cost and complexity
- No signing (hash chain only): weaker guarantee

---

## ADR-018 — No custom agent framework

**Status:** Locked

**Context:** The runtime is not an agent framework. It sits between an
agent and its tools. The temptation to "add agent capabilities" would
bloat scope.

**Decision:** The runtime does not orchestrate agents, does not manage
agent state, does not provide agent memory. It only intercepts tool
calls.

**Consequences:**
- ✅ Clear scope
- ✅ Works with any agent framework
- ✅ Smaller attack surface
- ✅ Easier to reason about
- ⚠️ Users must bring their own agent (the mock agent is for demo only)

**Alternatives:**
- Full agent framework: different project entirely
- Runtime + limited agent features: scope creep

---

## ADR index

| ID | Title | Status |
|---|---|---|
| ADR-001 | Python 3.11 | Locked |
| ADR-002 | OpenAI-compatible function calling only | Locked |
| ADR-003 | SQLite as primary datastore | Locked |
| ADR-004 | SHA-256 chain + Ed25519 signatures | Locked |
| ADR-005 | YAML policies with priority ordering | Locked |
| ADR-006 | Four dispositions, closed set | Locked |
| ADR-007 | Approval with optimistic locking and TTL | Locked |
| ADR-008 | Pydantic v2 for cross-module data | Locked |
| ADR-009 | structlog with secret scrubbing | Locked |
| ADR-010 | FastAPI for HTTP interception | Locked |
| ADR-011 | Python SDK alongside HTTP API | Locked |
| ADR-012 | Streamlit for approval dashboard | Locked |
| ADR-013 | No LLM in the critical path | Locked |
| ADR-014 | Closed operator set for conditions | Locked |
| ADR-015 | Append-only store with SQLite triggers | Locked |
| ADR-016 | Mock agent for demo and testing | Locked |
| ADR-017 | Single key pair per instance | Locked |
| ADR-018 | No custom agent framework | Locked |

**How to amend:** Add a new ADR (e.g., ADR-019) titled
"Supersedes ADR-XXX — ..." and update this index. Never edit a locked
ADR in place. The project pauses until the new ADR is approved.