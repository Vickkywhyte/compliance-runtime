# Discovery — AI Compliance Runtime

> **READ THIS FIRST (for Claude Code):**
> This is the founding document. Every subsequent decision (ADR, schema,
> metric) derives from the problem statement, scope, and success metrics
> defined here. If a later document appears to contradict this one, stop
> and flag the contradiction — do not silently override.
>
> **Companion docs (locked, read in order):**
> `01_LESSONS_APPLIED.md` · `02_PRD.md` · `03_ARCHITECTURE.md` ·
> `04_TECH_DECISIONS.md` · `05_DATA_SPEC.md` · `06_EVAL_SPEC.md` ·
> `07_SECURITY_MODEL.md` · `08_ROADMAP.md` · `09_RUNTIME_DESIGN.md`

---

## 1. Problem statement

Enterprises are deploying AI agents — Claude, ChatGPT, Gemini, custom
LangChain/CrewAI systems — to take real actions inside their systems.
These agents now:

- Issue refunds and process payments
- Approve or deny insurance claims
- Access customer records and medical histories
- Screen candidates for jobs
- Place orders and execute trades
- Send legally-binding communications

The gap: **nobody can prove what these agents are actually authorized to
do, what they did, or how the two were enforced.**

Today, most enterprises rely on one of three approaches, all of which are
inadequate:

1. **Prompt engineering** — "please don't do X" in the system prompt.
   Unenforceable. A clever prompt or a confused model bypasses it.
2. **Static governance** — policy documents, risk assessments, and
   compliance checklists. No runtime enforcement. Nobody verifies that
   policies were actually applied when the agent acted.
3. **Framework-specific guardrails** — filtering bad LLM output before
   it reaches the user. Doesn't cover agent tool calls. Doesn't produce
   auditable evidence.

**The consequence is measurable.** The EU AI Act's high-risk obligations
become enforceable in December 2027 (Annex III) and August 2028 (Annex I).
Fines reach €20 million or 4% of global turnover. Regulators will ask:
*"Prove you had runtime controls on your AI agents."* Most enterprises
cannot.

The gap is not detection. It is **enforcement + evidence**. There is no
open-source, framework-agnostic system that (a) intercepts AI agent
actions in real time, (b) enforces policies before the action executes,
(c) requires human approval when policy demands it, and (d) produces
cryptographically-verifiable evidence for regulators.

This project builds that system.

## 2. Why this exists

**The three questions this project answers:**

1. **Enforcement** — Did the runtime correctly enforce policy when the
   agent took an action?
2. **Evidence** — Can we prove *what happened*, *when*, and *why* without
   gaps?
3. **Oversight** — Did humans stay in control of high-stakes decisions?

Every metric in `06_EVAL_SPEC.md` maps to one of these three. Every
architectural decision in `03_ARCHITECTURE.md` exists to make one of
these three measurable.

**Why this is hard (not a demo):**

- **Runtime interception requires framework-agnostic design.** We use
  OpenAI-compatible function calling (the emerging standard). One
  integration point, documented as `ADR-002`.
- **Policy enforcement needs a real engine.** Not just `if` statements.
  Conditions on action, parameters, entity attributes, time, and rate.
- **Attestation must be tamper-evident.** SHA-256 hash chains with
  Ed25519 signatures. Not "a log file." Not a spreadsheet.
- **Human-in-the-loop is a distributed coordination problem.** Approvals
  must be atomic, idempotent, and auditable. Optimistic locking required.
- **Evaluation is the differentiator.** Anyone can build a gatekeeper.
  Very few can prove the gatekeeper works.
- **The runtime itself is a high-value target.** A compromised runtime
  can approve anything. Its threat model is written before its code.

## 3. Target users

### Primary persona — **Priya, Head of AI Governance**

- Mid-to-large enterprise (bank, insurer, large fintech)
- Owns the internal AI policy, reports to CISO or CCO
- Needs: to prove to the board and regulators that AI is being deployed
  responsibly, not just documented responsibly
- Pain: her policies exist on paper. She has no way to prove they are
  enforced in production.
- Success for Priya: a dashboard showing real-time enforcement across
  every AI agent in the enterprise, with an audit trail she can hand to
  a regulator.

### Secondary persona — **Marcus, AI Platform Engineer**

- Builds and operates the enterprise's AI agents
- Owns the tool-calling layer (LangChain, custom framework, etc.)
- Needs: a way to add policy enforcement to his agents without
  rewriting them, and without coupling to a specific AI vendor
- Pain: he's been asked to "add guardrails" but there's no standard.
  Every solution he finds is either too narrow (Guardrails AI filters
  LLM output) or too heavy (enterprise GRC platforms that don't
  actually enforce).
- Success for Marcus: one integration point that works with his existing
  agents, deploys in a day, and gives his AI governance team the
  evidence they need.

### Tertiary persona — **Sarah, Compliance Officer**

- Reviews high-stakes AI decisions that were paused for human approval
- Needs: clear, contextual information about what the AI wants to do
  and why, in a form she can act on quickly
- Pain: approval workflows that lack context ("Agent wants to refund
  customer 8842"), or that route everything to her regardless of
  severity
- Success for Sarah: an approval queue with only the decisions that
  actually need her, with all context attached, and a one-click decision
  action.

### Non-users (explicit)

- **End customers.** They never interact with the runtime. It is
  internal infrastructure.
- **External auditors.** They receive exported evidence (dossiers), but
  do not access the runtime directly. Auditor-facing API is a v2
  concern.

## 4. The workflow

Every AI agent action passes through the runtime in five stages. Each
stage is a distinct component with its own evaluation surface.

**Stage 1 — Intercept**
The agent attempts a tool call (e.g., `issue_refund`). The runtime,
configured as the agent's tool executor, receives the call before any
downstream system sees it.

**Stage 2 — Evaluate**
The runtime loads the active policy set and evaluates the action against
every rule. Rules are ordered by priority; the first matching rule
determines the disposition.

**Stage 3 — Dispose**
One of four outcomes:
- `allow` — the action proceeds; a `success` response is returned to the agent
- `deny` — the action is blocked; an error with a reason is returned
- `require_approval` — a human approval request is created; the agent is
  told the action is pending
- `allow_with_flag` — the action proceeds, but is marked for post-hoc
  review

**Stage 4 — Record**
Every evaluation — regardless of disposition — produces an `ActionRecord`
with the full context: action, parameters, matched rules, evidence,
timestamp, and cryptographic hash chain link.

**Stage 5 — Respond**
The agent receives a structured response. Downstream systems only see
allowed actions.

**The runtime never executes actions itself.** It only authorizes or
denies. Execution happens in the downstream system that would have
received the call anyway.

## 5. Scope for v1

### In scope

**Agent integration:**
- OpenAI-compatible function calling (only)
- Works with OpenAI, Anthropic via OpenAI-compat, Ollama, OpenRouter,
  and any framework exposing the OpenAI tool-call API shape
- No support for LangChain, CrewAI, AutoGen, or custom frameworks in v1

**Policy engine:**
- YAML-based policy definitions
- 4 enforcement types: `allow`, `deny`, `require_approval`,
  `allow_with_flag`
- Conditions on: action name, parameter values, entity attributes, time
  windows, rate limits
- Priority-ordered rules; first match wins
- No custom expression language — YAML conditions with a fixed operator
  set

**Attestation:**
- SHA-256 hash chain on every record
- Ed25519 signatures on every record (using `cryptography` library)
- Chain verification function for auditors
- No blockchain in v1

**Human-in-the-loop:**
- Streamlit-based approval dashboard
- Approve / deny / modify-and-approve
- Time-bounded approval requests (auto-deny after configurable TTL)
- Optimistic locking on approval transitions

**Evidence store:**
- SQLite, append-only with triggers
- Queryable by action, agent, mandate, regulation
- Export to JSON
- Cryptographic verification on export

**Compliance dossier generator:**
- One command produces a PDF
- Covers EU AI Act Article 12 (logging) compliance summary
- Includes: total actions, disposition breakdown, policy coverage
  statistics, chain verification report

**Evaluation harness:**
- Benchmark dataset: 200+ hand-labeled actions
- Metrics: policy precision, recall, FPR, FNR, approval latency,
  evidence completeness, chain integrity
- Bootstrap confidence intervals on every aggregate

**Demo:**
- `make demo` starts a mock agent, runs it against policies, shows live
  blocking, opens the dashboard, generates a dossier
- Total time: under 60 seconds
- No external API calls required

### Out of scope (v1)

- Additional agent frameworks (LangChain, CrewAI, AutoGen)
- Blockchain-based attestation
- SCITT, AAI-1, or Policy Cards standards implementation
- Multi-tenant isolation
- Real authentication (v1 uses local users)
- Integration with external GRC tools (ServiceNow, Archer)
- Real-time streaming ingestion
- Non-English policy definitions
- Kubernetes deployment
- Hosted SaaS offering

All out-of-scope items are documented as v2 or later in `03_ARCHITECTURE.md`
§10, with rationale.

## 6. Success metrics

### Enforcement (Question 1)

| Metric | Target | How measured |
|---|---|---|
| Policy precision | ≥ 0.90 | % of denied actions that correctly violated a rule |
| Policy recall | ≥ 0.95 | % of known-violating actions that were denied |
| False positive rate | ≤ 0.05 | % of compliant actions incorrectly denied |
| False negative rate | ≤ 0.03 | % of non-compliant actions incorrectly allowed |
| Policy coverage | ≥ 0.90 | % of agent actions covered by at least one rule |
| Rule evaluation latency (p50) | ≤ 50 ms | Median time to evaluate all rules for one action |

### Evidence (Question 2)

| Metric | Target | How measured |
|---|---|---|
| Audit completeness | 1.00 | % of actions with full record |
| Chain integrity | 1.00 | % of records whose hash chain verifies |
| Signature validity | 1.00 | % of records whose Ed25519 signature verifies |
| Dossier completeness | 1.00 | % of required fields present in generated dossier |
| Evidence retrieval time | ≤ 200 ms | Time to retrieve full chain for one action |

### Oversight (Question 3)

| Metric | Target | How measured |
|---|---|---|
| Approval latency (p50) | ≤ 60 s | Median time from request to human decision |
| Approval rate | tracked | % of requests approved (no target; diagnostic only) |
| Override rate | tracked | % of approvals that modified the action |
| Auto-deny rate | tracked | % of requests that hit TTL and were denied |
| Bypass attempts blocked | 1.00 | % of attempts to execute without runtime |

### Operational

| Metric | Target | How measured |
|---|---|---|
| Runtime overhead (p50) | ≤ 100 ms | Added latency per agent action |
| Cost per 1,000 actions | $0.00 | Free-tier LLM + local |

## 7. The mock agent (for demo and testing)

To evaluate the runtime, we need an agent to enforce against. We build a
minimal **mock agent** whose tool calls can be scripted.

The mock agent:
- Exposes three tools: `issue_refund`, `access_customer_record`,
  `send_customer_email`
- Reads a scripted sequence of actions from a JSON file
- Attempts each action through the runtime
- Logs the response (allowed, denied, pending)

**No real LLM is required for the demo path.** The mock agent simulates
the tool-call format of OpenAI-compatible function calling. This means
the demo runs offline, is deterministic, and takes seconds.

Live runs with a real LLM are supported but not required. A separate
`make demo-live` target uses OpenRouter free tier or Ollama.

## 8. Non-goals

Explicit statements of what we are *not* building:

- We are not building an AI agent framework.
- We are not building an LLM.
- We are not replacing the AI governance platform (IBM OpenPages,
  ServiceNow, etc.). We complement it by providing the runtime
  enforcement layer they lack.
- We are not executing actions. We authorize or deny them.
- We are not a firewall. We operate at the tool-call layer, not the
  network layer.
- We are not audited or certified by any regulatory body.
- We are not offering multi-tenant isolation in v1.

## 9. Cost model

| Component | Approach | Monthly cost |
|---|---|---|
| LLM (optional, for live demo) | OpenRouter free tier + Ollama | $0 |
| Embeddings (optional) | sentence-transformers MiniLM (local) | $0 |
| Policy storage | SQLite | $0 |
| Evidence store | SQLite | $0 |
| Signing keys | Generated locally, stored in filesystem | $0 |
| Dashboard | Streamlit (local) | $0 |
| Deployment | Docker Compose on laptop | $0 |
| CI | GitHub Actions free tier | $0 |
| **Total** | | **$0** |

## 10. The three questions, restated

> **Enforcement:** Did the runtime correctly enforce policy when the
> agent took an action?
> **Evidence:** Can we prove *what happened*, *when*, and *why* without
> gaps?
> **Oversight:** Did humans stay in control of high-stakes decisions?

Every metric in `06_EVAL_SPEC.md` maps to exactly one of these three.
Every architectural decision in `03_ARCHITECTURE.md` exists to make one
of these three measurable.

## 11. What "done" means for v1

The project is done when:

- [ ] The runtime intercepts OpenAI-compatible function calls without
  requiring changes to the agent code
- [ ] Policies are defined in YAML and evaluated at runtime
- [ ] All four dispositions (`allow`, `deny`, `require_approval`,
  `allow_with_flag`) work correctly
- [ ] Every action produces a signed, hash-chained record
- [ ] The chain verification function proves integrity
- [ ] The Streamlit approval dashboard processes approvals end-to-end
- [ ] The dossier generator produces a PDF with EU AI Act Article 12
  compliance summary
- [ ] The benchmark dataset has 200+ hand-labeled actions
- [ ] All success metrics in §6 are measured and reported
- [ ] `make demo` runs end-to-end in under 60 seconds with no network
  calls
- [ ] The project runs with $0 in monthly costs

## 12. Founding commitments

Non-negotiable principles. Any future decision that violates one
requires explicit re-approval.

1. **The runtime is not a filter.** It blocks actions before they
   execute. Logging bad actions after the fact is not enforcement.
2. **Human-in-the-loop is the product.** The runtime proposes; humans
   decide on high-stakes actions. The approval workflow is not a
   limitation — it is the value.
3. **Evidence must be tamper-evident.** SHA-256 hash chains with Ed25519
   signatures. If a record can be edited without breaking verification,
   the system has failed.
4. **Zero cost to run.** Free-tier LLM plus local fallback. $0 monthly.
5. **Evaluation is first-class.** Enforcement, evidence, and oversight
   are measured continuously with confidence intervals.
6. **Security is structural.** The threat model is written before code
   and enforced from Phase 1. The runtime is a high-value target and
   is treated as such.
7. **Lessons applied.** Every failure from the prior two projects (see
   `01_LESSONS_APPLIED.md`) has an explicit prevention mechanism here.