# Product Requirements Document — AI Compliance Runtime

> **READ THIS FIRST (for Claude Code):**
> This PRD defines *what* to build and *why*. It does not define *how* —
> that is `03_ARCHITECTURE.md` and `04_TECH_DECISIONS.md`. Every
> functional requirement has a stable ID (FR-*) referenced from the
> roadmap and tests.
>
> **Dependencies:** `00_DISCOVERY.md` · `01_LESSONS_APPLIED.md`
> **Depended on by:** `03_ARCHITECTURE.md` · `04_TECH_DECISIONS.md` ·
> `08_ROADMAP.md`

---

## 1. Product summary

An open-source runtime that intercepts AI agent tool calls, enforces
policy in real time, requires human approval for high-stakes actions,
and produces cryptographically-verifiable evidence for regulators.
Works with any agent that uses OpenAI-compatible function calling.
Costs $0 to run.

## 2. Goals

- **G1** — Intercept every agent tool call before it reaches a
  downstream system
- **G2** — Enforce policy with ≥ 0.90 precision and ≥ 0.95 recall
- **G3** — Produce tamper-evident records (hash chain + signature) for
  every action
- **G4** — Route high-stakes actions to human approval with ≤ 60 s p50
  latency
- **G5** — Generate a regulator-ready compliance dossier from evidence
- **G6** — Run at $0 monthly cost
- **G7** — Onboard a new developer in under 30 minutes

## 3. Non-goals (v1)

See `00_DISCOVERY.md` §8 for the full list. Summary:

- No support for LangChain, CrewAI, AutoGen
- No blockchain
- No SCITT, AAI-1, or Policy Cards standards implementation
- No multi-tenant isolation
- No real authentication
- No external GRC integrations
- No SaaS offering

## 4. Personas (summary)

Full personas in `00_DISCOVERY.md` §3.

| Persona | Primary need | Success signal |
|---|---|---|
| Priya — Head of AI Governance | Proof that policies are enforced in production | Dashboard + audit trail she can defend to the board |
| Marcus — AI Platform Engineer | One integration point that works with his agents | Deploys in a day; no vendor lock-in |
| Sarah — Compliance Officer | A queue of decisions that actually need her | High-signal approvals; full context |

## 5. User stories

### US-1 — Runtime interception

*As an AI platform engineer, I want the runtime to intercept every tool
call from my agent without changing the agent's code.*

**Acceptance:**
- The runtime is configured as the agent's tool executor (a single
  integration point)
- The agent's tool calls arrive at the runtime in OpenAI-compatible
  format
- The runtime returns a response in OpenAI-compatible format
- No changes to the agent's system prompt or tool definitions are
  required beyond pointing at the runtime

### US-2 — Policy evaluation

*As an AI governance lead, I want to define policies in YAML that the
runtime enforces at every action.*

**Acceptance:**
- Policies are defined in `configs/policies/*.yaml`
- Conditions can reference action name, parameter values, entity
  attributes, time windows, and rate limits
- Rules are priority-ordered; first match determines the disposition
- Four dispositions: `allow`, `deny`, `require_approval`,
  `allow_with_flag`

### US-3 — Denial with reason

*As an AI agent, I receive a structured denial when my action is
blocked, so I can inform the user or escalate.*

**Acceptance:**
- Denial includes: the rule that was matched, the reason, and evidence
- The agent can programmatically distinguish denial from success
- The agent can escalate to a human if it chooses

### US-4 — Approval workflow

*As a compliance officer, I see a queue of high-stakes actions awaiting
my decision, with full context.*

**Acceptance:**
- Dashboard shows pending approvals filtered by my role
- Each approval request includes: action, parameters, agent, matched
  rule, evidence, and time remaining
- I can approve, deny, or modify-and-approve
- My decision is recorded with my user ID, timestamp, and rationale

### US-5 — Tamper-evident evidence

*As a regulator, I can verify that the evidence chain has not been
modified since it was recorded.*

**Acceptance:**
- Every action record includes `previous_hash` and `current_hash`
- Every action record is signed with Ed25519
- A verification command proves the chain is intact
- The verification command can run offline (no server required)

### US-6 — Compliance dossier

*As an AI governance lead, I can generate a regulator-ready compliance
dossier covering EU AI Act Article 12 obligations.*

**Acceptance:**
- One command produces a PDF
- The dossier includes: total actions, disposition breakdown, policy
  coverage statistics, chain verification report
- Every figure is traceable to source records

### US-7 — Audit trail export

*As a compliance officer, I can export the audit trail in JSON for
independent review.*

**Acceptance:**
- Export includes all records for a time range, agent, or action type
- Export includes the verification key or its fingerprint
- Export is self-contained (can be verified offline)

### US-8 — Demo mode

*As a new developer, I can see the runtime work end-to-end in under 60
seconds with `make demo`.*

**Acceptance:**
- `make demo` starts a mock agent, runs it against policies, shows live
  blocking, opens the dashboard, generates a dossier
- No network calls required
- Every stage visible

### US-9 — Evaluation

*As an AI governance lead, I can measure the runtime's own accuracy and
produce a report.*

**Acceptance:**
- A benchmark dataset of 200+ hand-labeled actions exists
- Metrics: policy precision, recall, FPR, FNR, approval latency,
  evidence completeness, chain integrity
- All aggregate metrics include bootstrap confidence intervals
- `make eval` produces `results/evals/{timestamp}.json`

## 6. Functional requirements

### FR-1 Runtime interception

- **FR-1.1** — Accept OpenAI-compatible function call format
- **FR-1.2** — Return OpenAI-compatible function response format
- **FR-1.3** — Integrate as the agent's tool executor with a single
  configuration change
- **FR-1.4** — No modifications to the agent's system prompt required
- **FR-1.5** — Support both synchronous and asynchronous tool calls

### FR-2 Policy engine

- **FR-2.1** — Load policies from YAML files in `configs/policies/`
- **FR-2.2** — Evaluate policies in priority order
- **FR-2.3** — Support conditions on: action name, parameter values,
  entity attributes, time windows, rate limits
- **FR-2.4** — Support four dispositions: `allow`, `deny`,
  `require_approval`, `allow_with_flag`
- **FR-2.5** — Provide a validation command for policy syntax
- **FR-2.6** — Support policy versioning (each policy has a version ID
  recorded in every decision)

### FR-3 Dispositions

- **FR-3.1** — `allow`: response returned to agent with `success: true`
- **FR-3.2** — `deny`: response returned with `success: false` and
  structured reason
- **FR-3.3** — `require_approval`: response returned with
  `status: pending`; an approval request is created
- **FR-3.4** — `allow_with_flag`: response returned with
  `success: true`; the record is flagged for review

### FR-4 Evidence recording

- **FR-4.1** — Every action (regardless of disposition) produces an
  `ActionRecord`
- **FR-4.2** — Every record includes `previous_hash` and `current_hash`
- **FR-4.3** — Every record is signed with Ed25519
- **FR-4.4** — Records are append-only at the storage layer
- **FR-4.5** — Verification command proves chain integrity
- **FR-4.6** — Records include the matched rule's ID and version

### FR-5 Approval workflow

- **FR-5.1** — Approval requests are created with a TTL (default 900 s)
- **FR-5.2** — Dashboard shows pending requests filtered by role
- **FR-5.3** — Each request displays: action, parameters, agent,
  matched rule, evidence, TTL
- **FR-5.4** — Actions: approve, deny, modify-and-approve
- **FR-5.5** — Approval transitions use optimistic locking
- **FR-5.6** — Expired requests are auto-denied and recorded
- **FR-5.7** — Every approval decision records actor, timestamp,
  decision, edits (if any), and rationale

### FR-6 Compliance dossier

- **FR-6.1** — One command generates a PDF
- **FR-6.2** — Dossier includes: reporting period, total actions,
  disposition breakdown, policy coverage, chain verification report
- **FR-6.3** — Dossier maps evidence to EU AI Act Article 12
  obligations
- **FR-6.4** — Dossier is self-contained (includes verification key)

### FR-7 Evaluation harness

- **FR-7.1** — Benchmark dataset of 200+ actions exists at
  `data/eval/benchmark.jsonl`
- **FR-7.2** — Every action in the benchmark is labeled with the correct
  disposition
- **FR-7.3** — Metrics computed per `06_EVAL_SPEC.md`
- **FR-7.4** — `make eval` produces a JSON report and a human-readable
  summary
- **FR-7.5** — Bootstrap confidence intervals on all aggregates

### FR-8 Demo mode

- **FR-8.1** — `make demo` seeds a mock agent and runs it against
  policies
- **FR-8.2** — Demo shows: allowed actions, denied actions, pending
  approvals
- **FR-8.3** — Demo opens the dashboard automatically
- **FR-8.4** — Demo generates a dossier at the end
- **FR-8.5** — Runs in under 60 seconds

### FR-9 Dashboard

- **FR-9.1** — Views: Live actions, Pending approvals, Evidence chain,
  Compliance summary
- **FR-9.2** — All views render in ≤ 2 s
- **FR-9.3** — Approval actions are performed through the dashboard
- **FR-9.4** — Dashboard reads from the same evidence store as the
  runtime

### FR-10 API

- **FR-10.1** — HTTP endpoint for tool call interception
  (`POST /v1/tools/execute`)
- **FR-10.2** — HTTP endpoint for approval actions
  (`POST /v1/approvals/{id}/decide`)
- **FR-10.3** — HTTP endpoint for evidence verification
  (`POST /v1/evidence/verify`)
- **FR-10.4** — HTTP endpoint for dossier generation
  (`POST /v1/dossiers/generate`)

## 7. Non-functional requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-1 | Rule evaluation latency (p50) | ≤ 50 ms |
| NFR-2 | Runtime overhead (p50) | ≤ 100 ms |
| NFR-3 | Dashboard render | ≤ 2 s |
| NFR-4 | Concurrent tool calls | ≥ 100/s |
| NFR-5 | Evidence store growth | ≤ 500 MB for 6 months |
| NFR-6 | Cost to run | $0 |
| NFR-7 | Recovery from policy file errors | Fail loud; refuse to start |
| NFR-8 | Audit completeness | 100% |
| NFR-9 | Chain integrity | 100% |
| NFR-10 | Test coverage (core modules) | ≥ 85% |
| NFR-11 | Security controls | All P0 controls implemented per `07_SECURITY_MODEL.md` |
| NFR-12 | Onboarding time | `make demo` in ≤ 5 min from clone |

## 8. Interfaces

### CLI commands (via Makefile)

| Command | Purpose |
|---|---|
| `make sync` | Install/update dependencies |
| `make doctor` | Verify all imports resolve |
| `make policy-validate` | Validate policy YAML |
| `make serve` | Start runtime API + dashboard |
| `make demo` | Mock agent + policies + dashboard + dossier |
| `make eval` | Run evaluation harness |
| `make verify` | Verify evidence chain integrity |
| `make dossier` | Generate compliance dossier |
| `make test` | Run test suite |

### HTTP API

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Liveness + version |
| `/v1/tools/execute` | POST | Intercept tool call |
| `/v1/approvals` | GET | List pending approvals |
| `/v1/approvals/{id}` | GET | Approval detail |
| `/v1/approvals/{id}/decide` | POST | Approve / deny / modify |
| `/v1/evidence/{action_id}` | GET | Retrieve action record |
| `/v1/evidence/verify` | POST | Verify chain integrity |
| `/v1/dossiers/generate` | POST | Generate compliance dossier |

### Dashboard (Streamlit)

| View | Purpose |
|---|---|
| Live actions | Chronological feed of tool calls and dispositions |
| Pending approvals | Approvals awaiting human decision |
| Evidence chain | Browse and verify individual records |
| Compliance summary | Disposition breakdown + policy coverage |

## 9. Data model summary

Full schema in `05_DATA_SPEC.md`. Top-level entities:

- **ToolCall** — an intercepted agent tool call
- **PolicyEvaluation** — the result of evaluating a tool call against
  policies
- **ActionRecord** — the immutable, signed record of a decision
- **ApprovalRequest** — a pending human decision
- **ApprovalDecision** — a human's action on a request
- **Policy** — a YAML-defined rule set
- **AuditEvent** — an append-only log of system events

## 10. Success criteria (DoD)

See `00_DISCOVERY.md` §11. Restated:

- [ ] All FR-* and NFR-* requirements implemented
- [ ] All success metrics in `00_DISCOVERY.md` §6 measured and within
  target
- [ ] `make demo` works from a fresh clone in ≤ 60 seconds
- [ ] All `01_LESSONS_APPLIED.md` prevention mechanisms verified
- [ ] `07_SECURITY_MODEL.md` P0 controls implemented
- [ ] Full audit trail demonstrated end-to-end

## 11. Open questions

Tracked here until resolved.

- **OQ-1** — Which Ed25519 library? (`cryptography` is the default; no
  decision needed unless a specific issue arises.)
- **OQ-2** — How many policies for the demo? (Resolve in Phase 6.)
- **OQ-3** — Dashboard layout details. (Resolve in Phase 8.)
- **OQ-4** — Dossier PDF template. (Resolve in Phase 9.)