# Project Bible — AI Compliance Runtime

A plain-English master document. If you read only this file, you should
understand what the project is, why it exists, how it is built, and what it
guarantees. For the full technical specs, follow the links into `claude_chat/`.

---

## 1. The problem, in one paragraph

Companies are handing AI agents the keys to real systems — agents that can
issue refunds, change customer records, move money. The trouble is nobody can
*prove* what an agent was allowed to do, what it actually did, or that the two
matched. When a regulator or an auditor asks "show me that every high-stakes
action was governed and recorded," most teams have nothing but scattered logs.
This project is the missing layer: a runtime that stands between the agent and
its tools, enforces the rules *before* an action happens, pauses the risky ones
for a human, and writes down everything in a way that cannot be quietly edited.

## 2. What it is

The AI Compliance Runtime is an open-source service. An AI agent asks it,
"may I run this tool with these arguments?" The runtime answers in one of four
ways:

- **Allow** — go ahead.
- **Deny** — do not do this, and here is the rule that stopped you.
- **Require approval** — a human must decide first.
- **Allow with flag** — go ahead, but this is marked for later review.

Every answer is recorded as a tamper-evident, digitally-signed entry in a
chain, so the full history can be verified later by anyone holding a public
key — even offline, even after the runtime is gone.

It works with any agent that uses OpenAI-style "function calling," needs no
changes to the agent's code, calls no large language model on its decision
path, and costs nothing to run.

## 3. Why it exists

The EU AI Act requires high-risk AI systems to keep automatic logs and to allow
human oversight (Articles 12 and 14). Those obligations land soon. But beyond
the regulation, there is a plain engineering gap: there is very little
open-source tooling that treats agent governance as *enforcement plus evidence*
rather than after-the-fact logging. Logging a bad action after it happened is
not control. Blocking it before it executes, and proving you did, is.

Three questions this runtime lets an organization answer:

1. **Coverage:** were all the high-stakes actions actually governed?
2. **Accuracy:** did we allow what we should and deny what we should?
3. **Action quality:** when a human was in the loop, what did they decide, and
   can we prove it?

## 4. The seven things that happen on every call

1. **Intercept** — the runtime receives the agent's tool call.
2. **Evaluate** — it checks the call against a list of YAML rules, in priority
   order; the first rule that fully matches wins.
3. **Dispose** — it picks one of the four outcomes.
4. **Record** — it writes a signed record linked to the previous one (a
   "hash chain"). It stores a *fingerprint* of the arguments, never the raw
   arguments, so sensitive data never lands in the evidence store.
5. **Respond** — it returns a normal tool response to the agent.
6. **Approve** (only when needed) — a reviewer approves, modifies, or rejects;
   that decision is itself recorded, can't be double-processed, and expires if
   left too long.
7. **Attest** — anytime, the whole chain can be verified, and exported as a PDF
   dossier that maps the evidence to the EU AI Act's requirements.

## 5. How it's built (the map)

Each part is a small, independently-tested module:

- **config** — one place to read configuration and one place that owns the
  signing key.
- **storage** — a single SQLite file with append-only guards baked into the
  database itself, so even someone with direct file access can't silently edit
  the evidence tables.
- **policy** — loads and validates the YAML rules and evaluates them
  deterministically (same input, same output, always).
- **evidence** — does the hashing and signing, and the offline verifier.
- **approvals** — the human-in-the-loop workflow, built so two reviewers racing
  on the same request produce exactly one winner.
- **interception** — the HTTP server and the in-process Python SDK, which share
  one pipeline so both behave identically.
- **evaluation** — measures 17 metrics with confidence intervals, so claims
  about the runtime are numbers, not adjectives.
- **dossier / mock_agent** — the PDF report and the scripted demo.
- **dashboard** — a Streamlit UI to watch actions, make approval decisions, and
  browse the evidence chain.

## 6. What it guarantees (and what it doesn't)

**It guarantees**, with only a public key and the record set, that: no record
was changed, none was inserted/removed/reordered, and all were produced by the
holder of the signing key. The database itself refuses to update or delete
evidence rows.

**It does not** guarantee that the *policy you wrote* is correct, that the host
machine wasn't compromised, or anything about data the runtime never saw. v1 is
single-tenant, has no end-user authentication, and uses a deterministic
injection-marker scan rather than an LLM-based detector. These limits are
written down, not hidden — see `docs/security.md`.

## 7. The seven founding commitments

1. The runtime **blocks before execution** — it is not a filter.
2. **Human-in-the-loop is the product**, not a limitation.
3. **Evidence is tamper-evident** — hash chain + signatures, or it failed.
4. **Zero cost to run.**
5. **Evaluation is first-class** — measured continuously, with intervals.
6. **Security is structural** — threat model before code, enforced from day one.
7. **Lessons applied** — every past failure has an explicit prevention
   mechanism.

## 8. How to see it work

```bash
make demo-noserve       # scripted agent → allow / deny / approval + a dossier
make serve-dashboard    # the operator view at http://localhost:8501
make eval-mini          # the metrics, written to results/evals/
```

## 9. Where to read more

- Problem & scope: `claude_chat/00_DISCOVERY.md`
- The 12 prevention mechanisms: `claude_chat/01_LESSONS_APPLIED.md`
- Requirements: `claude_chat/02_PRD.md`
- Architecture: `claude_chat/03_ARCHITECTURE.md`
- Locked decisions (ADRs): `claude_chat/04_TECH_DECISIONS.md`
- Every schema: `claude_chat/05_DATA_SPEC.md`
- Every metric: `claude_chat/06_EVAL_SPEC.md`
- Threat model & controls: `claude_chat/07_SECURITY_MODEL.md`
- The build plan, phase by phase: `claude_chat/08_ROADMAP.md`
- How the runtime reasons: `claude_chat/09_RUNTIME_DESIGN.md`
- The operating manual for contributors: `claude_chat/CLAUDE.md`
