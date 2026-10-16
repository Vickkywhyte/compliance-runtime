# AI Compliance Runtime

> An open-source runtime that enforces policy on AI agent tool calls in real
> time and produces cryptographically-verifiable evidence for regulators.

![CI](https://github.com/Vickkywhyte/compliance-runtime/actions/workflows/ci.yml/badge.svg)
![Python 3.11](https://img.shields.io/badge/python-3.11-blue)
![tests](https://img.shields.io/badge/tests-367%20passing-brightgreen)
![license](https://img.shields.io/badge/license-MIT-green)
![cost](https://img.shields.io/badge/cost%20to%20run-%240-brightgreen)

## TL;DR

AI agents are being deployed to take real actions inside enterprises — issuing
refunds, changing records, moving money. Almost nobody can prove what those
agents were **authorized** to do, what they **actually** did, or how the two
were enforced. This is the open-source runtime that closes that gap: it
intercepts an agent's tool calls, enforces a versioned policy in real time,
pauses high-stakes actions for human approval, and records every decision as a
signed, hash-chained evidence trail. It costs **$0** to run and calls **no
LLM** on its critical path.

## What it does

The runtime sits between an AI agent and the tools it wants to call. For every
tool call it: **intercepts** the call (OpenAI-compatible), **evaluates** it
against a priority-ordered policy set, **disposes** it as one of four outcomes,
**records** a signed hash-chained evidence record, and **responds** to the
agent. High-stakes actions are routed to a **human approval** workflow; the full
evidence chain can be exported as a regulator-ready **PDF dossier** mapped to EU
AI Act Article 12.

## Why this exists

The EU AI Act's logging and human-oversight obligations for high-risk AI
systems (Article 12, Article 14) take effect on a near horizon — Annex III
systems in 2026–2027, Annex I in 2027–2028. Enterprises deploying agentic AI
will have to answer three questions they mostly cannot today:

1. **Coverage** — were all high-stakes actions actually governed by policy?
2. **Accuracy** — did enforcement allow what it should and deny what it should?
3. **Action quality** — when a human was in the loop, what did they decide, and
   can you prove it?

There is very little open-source tooling that treats this as an *enforcement
and evidence* problem rather than an after-the-fact logging problem. This
project is a working, measured, security-first answer.

## Architecture

```
          AI AGENT  (any OpenAI-compatible function-calling agent)
                         │  tool call (JSON)
                         ▼
          INTERCEPTION LAYER   HTTP  POST /v1/tools/execute   |  Python SDK
                         ▼
          POLICY ENGINE   YAML rules, priority-ordered, first match wins
            ┌───────────┬───────────┬──────────────────┬───────────────┐
          ALLOW       DENY       REQUIRE_APPROVAL     ALLOW_WITH_FLAG
            └───────────┴───────────┴──────────────────┴───────────────┘
                         ▼
          EVIDENCE RECORDER   SHA-256 hash chain · Ed25519 signature · append-only
                         ▼
          RESPONSE TO AGENT   OpenAI-compatible tool response

   HUMAN-IN-THE-LOOP            DOSSIER GENERATOR          EVALUATION HARNESS
   Streamlit dashboard         PDF, EU AI Act Art. 12      17 metrics + CIs
   approve / deny / modify     field-whitelisted export    deterministic, no LLM
```

## How it works — the seven stages

- **Intercept.** The runtime receives an OpenAI-compatible tool call over HTTP
  (`POST /v1/tools/execute`) or in-process via the Python SDK (`ToolExecutor`).
  No change to the agent's code is required.
- **Evaluate.** A rule engine loads YAML policies and evaluates the call in
  ascending `priority` order; the first rule whose conditions all match wins.
  The operator set is closed; missing/invalid fields resolve to non-matching
  (never a crash). Evaluation is deterministic and consults no LLM.
- **Dispose.** Exactly one of four dispositions results: `allow`, `deny`,
  `require_approval`, or `allow_with_flag`.
- **Record.** Every disposition produces an `ActionRecord` that is SHA-256
  hash-chained to the previous record and Ed25519-signed. Raw parameters are
  never stored — only a `parameters_hash`.
- **Respond.** The runtime returns an OpenAI-compatible tool response the agent
  can act on (or must not, for `deny`/`require_approval`).
- **Approve (when required).** `require_approval` creates a pending request
  routed to a reviewer role. Decisions go through a single service with
  optimistic locking and a same-transaction audit event; terminal states and
  TTL expiry are enforced; concurrent decisions resolve to exactly one winner.
- **Attest.** The evidence chain verifies offline with only the public key, and
  exports as a PDF dossier mapping records to EU AI Act Article 12 obligations.

## The rogue refund scenario

A support agent, driven by an LLM, decides to issue a **€1,200 refund** to a
customer whose account is flagged for `credit_card_chargeback_risk`.

**Without the runtime:** the tool call executes. The refund goes out. If this
pattern repeats across a fleet of agents, the losses compound — a few dozen
such actions is tens of thousands of euros gone, with no record of who
authorized what.

**With the runtime:** the call is intercepted and evaluated. A priority-5
fraud rule matches first and returns `deny` — *before* the tool executes. The
agent receives a structured denial with the rule id and the matching evidence,
and escalates instead of paying out. A signed, hash-chained `ActionRecord` is
written capturing the attempt, the policy version, and the decision. Net loss:
**zero**. Traceability: **complete and cryptographically verifiable**.

## Evaluation — the differentiator

Enforcement, evidence, and oversight are measured continuously — not asserted.
The harness computes **17 metrics across four categories** and bootstraps 95%
confidence intervals on the seven metrics with well-defined per-entry means.
It is **deterministic** (same benchmark + seed → same metrics) and makes **zero
LLM or network calls**. A 200+ entry hand-labeled benchmark is the evaluation
target; a 20-entry mini benchmark ships in-repo and runs via `make eval-mini`.

### Benchmark targets

| Category | Metric | Target |
|---|---|---|
| Enforcement | policy_precision | ≥ 0.90 |
| Enforcement | policy_recall | ≥ 0.95 |
| Enforcement | false_positive_rate | ≤ 0.05 |
| Enforcement | false_negative_rate | ≤ 0.03 |
| Enforcement | policy_coverage | ≥ 0.90 |
| Evidence | audit_completeness | 1.00 |
| Evidence | chain_integrity | 1.00 |
| Evidence | signature_validity | 1.00 |
| Oversight | approval_latency_p50_ms | ≤ 60,000 |
| Oversight | approval_latency_p95_ms | ≤ 300,000 |
| Oversight | approval_rate | diagnostic |
| Oversight | override_rate | diagnostic |
| Oversight | auto_deny_rate | ≤ 0.10 |
| Operational | runtime_overhead_p50_ms | ≤ 100 |
| Operational | policy_eval_p50_ms | ≤ 50 |
| Operational | evidence_write_p50_ms | ≤ 20 |
| Operational | cost_per_1k_actions_usd | 0.00 |

Actual runs are written to `results/evals/{timestamp}.json`. See
[`claude_chat/06_EVAL_SPEC.md`](claude_chat/06_EVAL_SPEC.md) for every formula.

## Security

The runtime treats itself as a high-value target. A STRIDE threat model is
enforced from Phase 1, with P0 controls implemented, not deferred:

- **Policy bypass (T-01):** strict typing, missing-field-denies, and a
  15-scenario bypass suite.
- **Evidence tampering (T-03):** SQLite append-only triggers reject
  UPDATE/DELETE on `action_records`, `approval_decisions`, `audit_events`; a
  SHA-256 chain and Ed25519 signatures detect any change that bypasses them.
- **Key compromise (T-04):** signing key is mode 0600, never logged, loaded
  only inside `evidence/signing.py`.
- **Approval bypass (T-05):** single-writer service, optimistic locking,
  same-transaction audit, terminal states, single-winner concurrency.
- **DoS (T-07):** per-agent rate limiting with drop metrics.
- **Malicious dependency (T-10):** exact-pinned lockfile, `pip-audit` in CI.

See [`docs/security.md`](docs/security.md) for the public summary and
[`claude_chat/07_SECURITY_MODEL.md`](claude_chat/07_SECURITY_MODEL.md) for the
full model and the C-01…C-46 control catalog.

## Quick start

```bash
git clone https://github.com/Vickkywhyte/compliance-runtime.git
cd compliance-runtime
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

make doctor             # verify every module imports
make test               # run the test suite (367 passing)
make demo-noserve       # run the full demo end-to-end in < 1 second
make serve-dashboard    # dashboard at http://localhost:8501
make serve              # FastAPI runtime at http://localhost:8000
```

Run the evaluation harness on the in-repo mini benchmark:

```bash
make eval-mini          # writes results/evals/{timestamp}.json
```

Or run it in Docker:

```bash
make docker-build
make docker-up          # dashboard on 8501, API on 8000
```

## Project layout

```
src/compliance_runtime/
├── config/        typed config, the single config loader, Ed25519 key lifecycle
├── storage/       SQLite schema + migrations, repositories, append-only audit
├── policy/        YAML models, loader, validators, engine, rate limit, injection
├── evidence/      canonical hashing, signing, recorder, offline verifier
├── approvals/     state machine, TTL, the single-writer approval service
├── interception/  pipeline, FastAPI server, Python SDK, OpenAI adapter
├── dispositions/  allow / deny / approval / flagged handlers
├── evaluation/    17 metrics, benchmark gate, runner, bootstrap stats, report
├── dossier/       reportlab PDF generator, EU AI Act Article 12 mapping
├── mock_agent/    scripted demo agent + demo runner
└── dashboard/     Streamlit app: live actions, approvals, evidence, summary
```

## Status

All 11 build phases are complete: scaffolding, storage, policy engine, evidence
recorder/verifier, approval workflow, interception (HTTP + SDK), evaluation
harness, dashboard, dossier + demo, security hardening + Docker + CI, and this
documentation pass. See [`CHANGELOG.md`](CHANGELOG.md) for the per-phase record.

## The 30-second pitch

> *AI agents are being deployed to take real actions inside enterprises. Almost
> nobody can prove what those agents were authorized to do, what they actually
> did, or how the two were enforced. I built the open-source runtime that
> closes that gap.*

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Every change runs through the CI
(tests + `pip-audit` + Docker build) and the PR security checklist.

## License

MIT — see [`LICENSE`](LICENSE).
