# AI Compliance Runtime

> An open-source runtime that intercepts AI agent tool calls, enforces
> policy in real time, requires human approval for high-stakes actions,
> and produces cryptographically-verifiable evidence for regulators.
> **Works with any agent using OpenAI-compatible function calling.
> Costs $0 to run.**

[![CI](https://github.com/Vickkywhyte/compliance-runtime/actions/workflows/ci.yml/badge.svg)](https://github.com/Vickkywhyte/compliance-runtime/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green)]()

---

## TL;DR

AI agents are being deployed to take real actions inside enterprises —
issue refunds, approve claims, access customer records. Almost nobody
can prove what those agents were authorized to do, what they did, or
how the two were enforced.

**This runtime closes that gap.**

It sits between an agent and its tools. Every tool call passes through
it. It enforces policy at runtime (not after the fact), routes
high-stakes actions to human approval, and records every decision in a
tamper-evident, cryptographically-signed evidence chain.

Three differentiators:

1. **Runtime enforcement, not logging.** Actions are blocked *before*
   they execute. The runtime is a gatekeeper, not a log file.
2. **Tamper-evident evidence.** SHA-256 hash chain + Ed25519 signatures.
   Verification works offline. Even an attacker with database access
   cannot modify a record undetected.
3. **Multi-stage evaluation.** Enforcement precision, recall, false
   positive/negative rates, evidence completeness, chain integrity —
   all measured with bootstrap confidence intervals.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AI AGENT (external)                      │
│  OpenAI · Claude · Ollama · any OpenAI-compatible agent    │
└──────────────────────────┬──────────────────────────────────┘
                           │ tool call
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 AI COMPLIANCE RUNTIME                        │
│                                                             │
│   ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  │
│   │ Policy Engine│  │  Evidence    │  │  Approval      │  │
│   │              │  │  Recorder    │  │  Workflow      │  │
│   │ YAML rules   │  │ sha256 chain │  │  human-in-loop │  │
│   │ priority     │  │ ed25519 sig  │  │  optimistic    │  │
│   └──────┬───────┘  └──────┬───────┘  └────────┬───────┘  │
│          │                 │                   │          │
│          └─────────────────┼───────────────────┘          │
│                            ▼                              │
│   ┌──────────────────────────────────────────────────────┐│
│   │  Dispositions: allow / deny / require_approval / flag││
│   └──────────────────────────────────────────────────────┘│
└──────────────────────────┬──────────────────────────────────┘
                           │ response
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    AGENT (continued)                         │
│  Proceeds · Escalates · Waits for approval                  │
└─────────────────────────────────────────────────────────────┘
```

Full architecture in [`claude_chat/03_ARCHITECTURE.md`](claude_chat/03_ARCHITECTURE.md).

## How it works

**1. Intercept.** The agent's tool call arrives at the runtime in
OpenAI-compatible format.

**2. Evaluate.** The policy engine evaluates the call against rules in
priority order. First match wins.

**3. Dispose.** One of four outcomes:
- `allow` — action proceeds
- `deny` — action blocked with a reason
- `require_approval` — action paused for human decision
- `allow_with_flag` — action proceeds, marked for review

**4. Record.** Every decision produces a signed, hash-chained
`ActionRecord` in an append-only store.

**5. Respond.** The agent receives an OpenAI-compatible response.

## Example: the rogue refund

A customer emails about a duplicate charge. An AI agent wants to issue
a €1,200 refund.

**Without the runtime:** The refund executes. The account was actually
flagged for fraud investigation. €57,600 lost across a week before
anyone notices. No audit trail explains what happened.

**With the runtime:** The policy engine intercepts the call. The rule
`fraud_flagged_account` matches. The refund is **denied before
execution**. A signed record captures: what the agent tried, which
policy matched, why the account was flagged, and when. The agent
escalates to a human. Zero money lost. Full traceability.

## Evaluation — the differentiator

The runtime measures itself across three dimensions:

| Category | Metrics |
|---|---|
| **Enforcement** | policy_precision, policy_recall, false_positive_rate, false_negative_rate, policy_coverage |
| **Evidence** | audit_completeness, chain_integrity, signature_validity |
| **Oversight** | approval_latency_p50/p95, approval_rate, override_rate, auto_deny_rate |
| **Operational** | runtime_overhead_p50_ms, policy_eval_p50_ms, evidence_write_p50_ms |

Every metric has a target, a formula, and a hand-crafted test fixture.
Bootstrap 95% confidence intervals on all aggregates.

The benchmark dataset: **200+ hand-labeled tool calls** across four
disposition categories, quality-gated during curation.

Full spec in [`claude_chat/06_EVAL_SPEC.md`](claude_chat/06_EVAL_SPEC.md).

## Security

A full STRIDE threat model with **46 controls** (P0 and P1). Highlights:

- **Cryptographic attestation** — SHA-256 hash chain + Ed25519 signatures
  on every action record.
- **Append-only enforcement** — SQLite triggers reject UPDATE/DELETE on
  evidence tables, regardless of access path.
- **Approval integrity** — optimistic locking prevents double-approval;
  rejected and expired requests cannot be resurrected.
- **Policy bypass defense** — schema validation, strict typing, action
  name whitelisting, and prompt-injection filtering on tool-call
  parameters.
- **Key safety** — private keys never logged, never committed, mode
  0600, isolated to one module.

Full spec in [`claude_chat/07_SECURITY_MODEL.md`](claude_chat/07_SECURITY_MODEL.md).

## Results

*Populated after `make eval` runs against the benchmark dataset.
Placeholder format:*

| Metric | Value | Target |
|---|---|---|
| Policy precision | — | ≥ 0.90 |
| Policy recall | — | ≥ 0.95 |
| False positive rate | — | ≤ 0.05 |
| False negative rate | — | ≤ 0.03 |
| Policy coverage | — | ≥ 0.90 |
| Audit completeness | — | 1.00 |
| Chain integrity | — | 1.00 |
| Signature validity | — | 1.00 |
| Approval latency p50 | — | ≤ 60 s |
| Runtime overhead p50 | — | ≤ 100 ms |
| Cost per 1,000 actions | $0.00 | $0.00 |

## Quick start

```bash
git clone https://github.com/Vickkywhyte/compliance-runtime.git
cd compliance-runtime
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
make sync doctor
make demo
```

`make demo` starts a mock agent, runs it against demo policies, shows
live blocking, opens the dashboard, and generates a compliance dossier.
**Under 60 seconds.**

### Requirements

- Python 3.11
- Optional: Docker (for the compose-based flow)

### Or with Docker

```bash
docker compose up -d
# API:       http://localhost:8000/docs
# Dashboard: http://localhost:8501
```

## Repository structure

```
compliance-runtime/
├── claude_chat/                    # 13 planning docs (source of truth)
├── configs/                        # YAML configs + policies
├── data/
│   ├── eval/                       # benchmark dataset (committed)
│   └── demo/                       # mock agent scripts (committed)
├── src/compliance_runtime/
│   ├── policy/                     # YAML policy engine
│   ├── interception/               # HTTP API + Python SDK
│   ├── dispositions/               # allow / deny / approval / flag
│   ├── approvals/                  # human-in-the-loop
│   ├── evidence/                   # hash chain + Ed25519 signatures
│   ├── dossier/                    # compliance PDF generator
│   ├── evaluation/                 # metrics + runner
│   ├── dashboard/                  # Streamlit views
│   ├── storage/                    # SQLite repositories
│   └── mock_agent/                 # demo agent
├── scripts/                        # numbered entry points
├── tests/
│   └── security/                   # security tests
├── Dockerfile
├── docker-compose.yml
└── Makefile
```

## The 30-second pitch

> "I built an open-source runtime that makes AI agents defensible in
> regulated environments. It intercepts agent tool calls, enforces
> policy at runtime, requires human approval for high-stakes actions,
> and records every decision in a tamper-evident evidence chain. It
> works with any agent using OpenAI-compatible function calling, it's
> got a full evaluation framework with confidence intervals on
> precision, recall, and false positive rates, and it costs $0 to run.
> This is the layer that lets enterprises deploy AI agents without
> gambling on their judgment."

## Design decisions

- **Why no LLM in the critical path?** Determinism. Policy enforcement
  must be auditable and fast. LLM calls are neither.
- **Why SHA-256 + Ed25519?** Tamper-evident. Standard primitives.
  Verification works offline.
- **Why four dispositions, no more?** Closed set. Adding new
  dispositions would break the state machine and evaluation.
- **Why OpenAI-compatible function calling only?** One integration
  point. The emerging standard. Depth, not breadth.
- **Why human-in-the-loop?** Regulatory decisions cannot be delegated
  to autonomous systems. The runtime proposes; humans decide.

Full ADR list in [`claude_chat/04_TECH_DECISIONS.md`](claude_chat/04_TECH_DECISIONS.md).

## Screenshots

*Added after Phase 10. Planned views: Live actions, Pending approvals,
Evidence chain, Compliance summary.*

## Documentation

Full planning docs live in [`claude_chat/`](claude_chat/). Reading order:

1. [`00_START_HERE.md`](claude_chat/00_START_HERE.md)
2. [`00_DISCOVERY.md`](claude_chat/00_DISCOVERY.md)
3. [`01_LESSONS_APPLIED.md`](claude_chat/01_LESSONS_APPLIED.md)
4. [`02_PRD.md`](claude_chat/02_PRD.md)
5. [`03_ARCHITECTURE.md`](claude_chat/03_ARCHITECTURE.md)
6. [`04_TECH_DECISIONS.md`](claude_chat/04_TECH_DECISIONS.md)
7. [`05_DATA_SPEC.md`](claude_chat/05_DATA_SPEC.md)
8. [`06_EVAL_SPEC.md`](claude_chat/06_EVAL_SPEC.md) ← the differentiator
9. [`07_SECURITY_MODEL.md`](claude_chat/07_SECURITY_MODEL.md)
10. [`08_ROADMAP.md`](claude_chat/08_ROADMAP.md)
11. [`09_RUNTIME_DESIGN.md`](claude_chat/09_RUNTIME_DESIGN.md)

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

MIT — see [`LICENSE`](LICENSE).