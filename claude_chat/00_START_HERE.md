# AI Compliance Runtime — Start Here

> **TL;DR:** An open-source runtime that intercepts AI agent tool calls,
> enforces policy at runtime, requires human approval for high-stakes
> actions, and produces cryptographically-verifiable evidence.
> Works with any agent using OpenAI-compatible function calling.
> Costs $0 to run.

---

## What this is

An **open-source compliance runtime** for AI agents. It sits between an
agent and its tools. Every tool call passes through it. It:

- **Intercepts** OpenAI-compatible tool calls
- **Enforces** policies defined in YAML
- **Routes** high-stakes actions to human approval
- **Records** every decision in a tamper-evident evidence chain
- **Generates** regulator-ready compliance dossiers

The agent proposes. The runtime enforces. Humans decide. The evidence
chain proves it.

## Why it exists

Enterprises are deploying AI agents to take real actions — issue refunds,
approve claims, access customer records, place orders. The EU AI Act's
high-risk obligations become enforceable in December 2027 (Annex III)
and August 2028 (Annex I). Fines reach €20M or 4% of global turnover.

Regulators will ask: *"Prove you had runtime controls on your AI
agents."*

Most enterprises cannot. They rely on prompt engineering ("please don't
do X"), static governance (policies nobody enforces), or framework
guardrails (which filter LLM output, not agent actions).

**The gap is enforcement + evidence.** This project closes it.

## The three questions this project answers

1. **Enforcement** — Did the runtime correctly enforce policy when the
   agent took an action?
2. **Evidence** — Can we prove *what happened*, *when*, and *why*
   without gaps?
3. **Oversight** — Did humans stay in control of high-stakes decisions?

## Who it's for

| Persona | Need |
|---|---|
| Head of AI Governance | Proof that policies are enforced in production |
| AI Platform Engineer | One integration point that works with existing agents |
| Compliance Officer | A queue of decisions that actually need them |

## The differentiator

Most AI governance tools are black boxes or static checklists. This one
is a **runtime with a full evaluation framework**:

- **Enforcement metrics** — policy precision, recall, FPR, FNR, coverage
- **Evidence metrics** — audit completeness, chain integrity, signature
  validity
- **Oversight metrics** — approval latency, override rate, auto-deny rate
- **Operational metrics** — runtime overhead, per-action latency

All with bootstrap confidence intervals. All measured against a
200+ entry benchmark dataset.

## Reading order

### Tier 1 — Foundations
1. `PROJECT_INSTRUCTIONS.md` — how to work in this repo
2. `CLAUDE.md` — operating rules for AI-assisted work
3. `00_DISCOVERY.md` — problem, scope, success metrics
4. `01_LESSONS_APPLIED.md` — 12 prevention mechanisms
5. `02_PRD.md` — product requirements
6. `03_ARCHITECTURE.md` — component design

### Tier 2 — Specifications
7. `04_TECH_DECISIONS.md` — 18 locked ADRs
8. `05_DATA_SPEC.md` — every schema
9. `06_EVAL_SPEC.md` — every metric
10. `07_SECURITY_MODEL.md` — threat model + 46 controls
11. `09_RUNTIME_DESIGN.md` — how the runtime reasons and enforces

### Tier 3 — Execution
12. `08_ROADMAP.md` — 11 phases
13. `CHANGELOG.md` — running log

---

## Current status

| Phase | Status | Notes |
|---|---|---|
| Planning (`claude_chat/`) | 🟢 Complete | 13 docs locked |
| Phase 1 — Scaffolding + safety rails | 🟢 Complete | Phase 2 next |
| Phase 2 — Storage + evidence foundations | 🟢 Complete | Phase 3 next |
| Phase 3 — Policy engine | 🟢 Complete | Phase 4 next |
| Phase 4 — Evidence recorder + verifier | 🟢 Complete | Phase 5 next |
| Phase 5 — Approval workflow | 🟢 Complete | Phase 6 next |
| Phase 6 — Interception layer (HTTP + SDK) | 🟢 Complete | Phase 7 next |
| Phase 7 — Evaluation harness | 🟢 Complete | Phase 8 next |
| Phase 8 — Dashboard | 🟢 Complete | Phase 9 next |
| Phase 9 — Dossier generator + mock agent + demo | 🟢 Complete | Phase 10 next |
| Phases 10–11 | ⚪ Not started | See `08_ROADMAP.md` |

**Legend:** 🟢 done · 🟡 in progress · ⚪ not started · 🔴 blocked

---

## Project Definition of Done

### Functional
- [ ] Intercepts OpenAI-compatible tool calls
- [ ] Enforces policies defined in YAML (priority-ordered)
- [ ] Four dispositions: allow, deny, require_approval, allow_with_flag
- [ ] Routes high-stakes actions to human approval
- [ ] Records every action as a signed, hash-chained record
- [ ] Verifies chain and signatures offline
- [ ] Generates regulator-ready compliance dossier
- [ ] Ships mock agent for demo
- [ ] Runs end-to-end in < 60 seconds with `make demo`

### Evaluation
- [ ] All metrics in `06_EVAL_SPEC.md` §3–§6 implemented
- [ ] All §9 fixtures pass
- [ ] Benchmark dataset of 200+ entries, quality-gate-validated
- [ ] `make eval` produces a complete report
- [ ] Bootstrap CIs computed

### Security
- [ ] All P0 controls implemented
- [ ] All P1 controls implemented
- [ ] All security tests pass on every PR
- [ ] `pip-audit` clean

### Quality
- [ ] Test coverage ≥ 85% on core modules
- [ ] All 11 phases closed with evidence
- [ ] `make demo` runs in ≤ 60 seconds from a fresh clone
- [ ] README with real numbers and screenshots
- [ ] CI green

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

## Quick start (once built)

```bash
git clone <repo> && cd compliance-runtime
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make sync doctor          # install deps, verify imports
make demo                 # mock agent + policies + dashboard + dossier
make serve                # HTTP API + dashboard
```

Then open `http://localhost:8501`.

## Repository structure

```
compliance-runtime/
├── claude_chat/                    # 13 planning docs
├── configs/                        # YAML configs + policies
├── data/
│   ├── runtime.db                  # SQLite (gitignored)
│   ├── eval/                       # benchmark dataset
│   └── demo/                       # mock agent scripts
├── src/compliance_runtime/         # library code
│   ├── config/                     # config loaders
│   ├── policy/                     # YAML policy engine
│   ├── interception/               # HTTP + SDK
│   ├── dispositions/               # allow/deny/approval/flag
│   ├── approvals/                  # human-in-the-loop
│   ├── evidence/                   # hash chain + signatures
│   ├── dossier/                    # compliance PDF generator
│   ├── evaluation/                 # metrics + runner
│   ├── dashboard/                  # Streamlit
│   ├── storage/                    # SQLite repositories
│   └── mock_agent/                 # demo agent
├── scripts/                        # numbered entry points
├── tests/
│   └── security/                   # security tests
├── Dockerfile
├── docker-compose.yml
└── Makefile
```

## Cost model

| Component | Cost |
|---|---|
| Policy evaluation | $0 (rules-based, no LLM) |
| Evidence storage | $0 (SQLite) |
| Signing | $0 (local Ed25519 key) |
| Dashboard | $0 (Streamlit local) |
| Hosting | $0 (Docker Compose on laptop) |
| **Total** | **$0** |

## Non-goals (v1)

Documented in `00_DISCOVERY.md` §8. Highlights:

- No support for LangChain, CrewAI, AutoGen
- No blockchain
- No SCITT, AAI-1, or Policy Cards implementation
- No multi-tenant isolation
- No real authentication

## License

MIT