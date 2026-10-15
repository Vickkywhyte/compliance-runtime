# Evaluation Specification — AI Compliance Runtime

> **READ THIS FIRST (for Claude Code):**
> This document defines every metric. A metric is not real until it is
> (a) defined here with a formula, (b) implemented as a `Metric`
> subclass, (c) tested against hand-crafted fixtures, and (d) referenced
> from the eval report. Do not add a metric without updating this doc
> first.
>
> **Dependencies:** `00_DISCOVERY.md` (§6) · `02_PRD.md` (FR-7) ·
> `05_DATA_SPEC.md`
> **Depended on by:** `08_ROADMAP.md` (Phase 7)

---

## 1. Evaluation philosophy

The runtime has three jobs: **enforce policy**, **record evidence**, and
**enable human oversight**. A failure in any one is a real-world
failure. Therefore, we measure all three independently.

**Every metric maps to one of the three questions** from
`00_DISCOVERY.md` §2:

| Question | Metrics |
|---|---|
| Enforcement | policy_precision, policy_recall, FPR, FNR, policy_coverage |
| Evidence | audit_completeness, chain_integrity, signature_validity |
| Oversight | approval_latency_p50/p95, bypass_attempts_blocked_rate |

## 2. Benchmark dataset

### 2.1 Schema (per line, `data/eval/benchmark.jsonl`)

```json
{
  "id": "b001",
  "description": "Refund of €1,200 on a fraud-flagged account",
  "tool_call": {
    "action": "issue_refund",
    "parameters": {"customer_id": "cust_8842", "amount": 1200, "currency": "EUR"},
    "agent_id": "support_agent_v3",
    "session_id": "sess_demo"
  },
  "entity_context": {
    "customer_id": "cust_8842",
    "fraud_flags": ["credit_card_chargeback_risk"],
    "risk_tier": "high"
  },
  "expected_disposition": "deny",
  "expected_rule_id": "fraud_flagged_account",
  "expected_assignee_role": null,
  "notes": "Account flagged for fraud investigation on 2026-10-12"
}
```

### 2.2 Composition rules

| Category | Minimum | Purpose |
|---|---|---|
| Should allow (compliant) | 80 | Test false positive rate |
| Should deny (non-compliant) | 60 | Test false negative rate |
| Should require approval | 40 | Test approval routing |
| Should allow with flag | 20 | Test flagging |
| **Total** | **≥ 200** | |

Each entry must include `entity_context` for any rules that reference
`entity.*` fields.

### 2.3 Curation

1. Authored by Claude Code under human review
2. Every entry has a single correct disposition
3. Every entry that maps to a rule references the rule's `id`
4. `annotator` field set to `"claude_code"` for honest provenance
5. Quality gate runs during curation (Lesson 4)

### 2.4 Quality gate

Fails on:
- Duplicate IDs
- Missing required fields
- `expected_disposition` not in the controlled vocabulary
- `expected_rule_id` references a nonexistent rule (when non-null)
- Any entry that references `entity.*` fields without `entity_context`
- Malformed JSON

## 3. Enforcement metrics (Question 1)

### 3.1 Policy precision

```
precision = (# actions denied AND expected to be denied)
          / (# actions denied)
```

Range: [0, 1]. Higher is better.

**Target:** ≥ 0.90

### 3.2 Policy recall

```
recall = (# actions denied AND expected to be denied)
       / (# actions expected to be denied)
```

Range: [0, 1]. Higher is better.

**Target:** ≥ 0.95

### 3.3 False positive rate

```
FPR = (# actions denied BUT expected to be allowed)
    / (# actions expected to be allowed)
```

Range: [0, 1]. Lower is better.

**Target:** ≤ 0.05

### 3.4 False negative rate

```
FNR = (# actions allowed BUT expected to be denied)
    / (# actions expected to be denied)
```

Range: [0, 1]. Lower is better.

**Target:** ≤ 0.03

### 3.5 Policy coverage

```
coverage = (# actions with a matched rule)
         / (# total actions)
```

Range: [0, 1]. Higher is better.

**Target:** ≥ 0.90

### 3.6 Test fixtures

| Fixture | Setup | Expected |
|---|---|---|
| `perfect_enforcement` | All actions correctly classified | precision=1.0, recall=1.0 |
| `one_false_positive` | 1 non-compliant allowed | FPR > 0 |
| `one_false_negative` | 1 compliant denied | FNR > 0 |
| `uncovered_action` | Action matches no rule | coverage < 1.0 |

## 4. Evidence metrics (Question 2)

### 4.1 Audit completeness

```
completeness = (# actions with a full ActionRecord)
             / (# total actions)
```

Range: [0, 1]. Target: **1.00**

A record is "full" if all required fields are present and non-null.

### 4.2 Chain integrity

```
integrity = (# records whose chain links verify)
          / (# total records)
```

Where "chain link verifies" means `record.previous_hash == prev_record.current_hash`
AND `record.current_hash == recompute(record)`.

Range: [0, 1]. Target: **1.00**

### 4.3 Signature validity

```
validity = (# records whose signature verifies)
         / (# total records)
```

Range: [0, 1]. Target: **1.00**

### 4.4 Test fixtures

| Fixture | Setup | Expected |
|---|---|---|
| `complete_chain` | 10 valid records | completeness=1.0, integrity=1.0 |
| `missing_record` | 1 record deleted from evidence store | completeness < 1.0 |
| `broken_chain` | 1 record's `previous_hash` tampered | integrity < 1.0 |
| `invalid_signature` | 1 record signed with wrong key | validity < 1.0 |

## 5. Oversight metrics (Question 3)

### 5.1 Approval latency

```
latency_ms = decided_at - created_at   (per request)
```

Report:
- `approval_latency_p50_ms` — median
- `approval_latency_p95_ms` — 95th percentile

**Targets:** p50 ≤ 60,000 ms; p95 ≤ 300,000 ms

### 5.2 Approval rate (diagnostic)

```
approval_rate = (# requests approved OR modified_approved)
              / (# requests)
```

No target. Diagnostic only. Very high or very low rates indicate
policy misconfiguration.

### 5.3 Override rate (diagnostic)

```
override_rate = (# requests modified_approved)
              / (# requests approved OR modified_approved)
```

No target. Diagnostic only.

### 5.4 Auto-deny rate

```
auto_deny_rate = (# requests that expired)
               / (# requests)
```

Target: ≤ 0.10. Higher rates indicate insufficient reviewer capacity
or misconfigured TTLs.

### 5.5 Bypass attempts blocked rate

```
bypass_rate = (# attempts to execute without runtime that were blocked)
            / (# attempts to execute without runtime)
```

Range: [0, 1]. Target: **1.00**

Measured via a test harness that attempts direct tool execution and
confirms the runtime intercepts it.

## 6. Operational metrics

| Metric | Definition | Target |
|---|---|---|
| `runtime_overhead_p50_ms` | Median added latency per tool call | ≤ 100 |
| `policy_eval_p50_ms` | Median policy evaluation time | ≤ 50 |
| `evidence_write_p50_ms` | Median evidence write time | ≤ 20 |
| `cost_per_1k_actions_usd` | Extrapolated cost (always $0 for v1) | 0.00 |

## 7. Aggregate reporting

Every evaluation run produces `results/evals/{timestamp}.json`:

```json
{
  "eval_id": "20261015T140000_eval",
  "run_at": "2026-10-15T14:00:00Z",
  "benchmark_hash": "abc123...",
  "n_entries": 200,
  "metrics": {
    "policy_precision": 0.92,
    "policy_recall": 0.96,
    "false_positive_rate": 0.04,
    "false_negative_rate": 0.02,
    "policy_coverage": 0.93,
    "audit_completeness": 1.00,
    "chain_integrity": 1.00,
    "signature_validity": 1.00,
    "approval_latency_p50_ms": 42000,
    "approval_latency_p95_ms": 180000,
    "approval_rate": 0.78,
    "override_rate": 0.14,
    "auto_deny_rate": 0.06,
    "bypass_attempts_blocked_rate": 1.00,
    "runtime_overhead_p50_ms": 62,
    "policy_eval_p50_ms": 31,
    "evidence_write_p50_ms": 14,
    "cost_per_1k_actions_usd": 0.0
  },
  "per_entry": [
    {
      "benchmark_id": "b001",
      "expected_disposition": "deny",
      "actual_disposition": "deny",
      "matched_rule_id": "fraud_flagged_account",
      "correct": true,
      "evidence_complete": true
    }
  ],
  "aggregate_ci": {
    "policy_precision": [0.88, 0.95],
    "policy_recall": [0.93, 0.98]
  }
}
```

## 8. Statistical hygiene

- **Confidence intervals:** bootstrap 1,000 samples, 95% interval.
  Reported on all aggregate metrics where n ≥ 20.
- **Determinism:** no LLM calls in the eval path. Same benchmark →
  same metrics.
- **No claims below CI width:** if two configs differ by less than the
  CI half-width, do not claim one is better.

## 9. Test fixtures

`tests/test_metrics.py` must contain these fixtures (from §3.6, §4.4)
and assert expected values within `1e-6` tolerance.

Any metric shipped without its fixtures is a **blocker**.

## 10. Evaluation run

```bash
make eval
```

Steps:
1. Verify benchmark integrity (quality gate)
2. Reset evaluation database (separate from production)
3. For each benchmark entry:
   - Feed the tool call through the runtime (with `entity_context`)
   - Capture the disposition and matched rule
   - Verify evidence record integrity
4. Compute all metrics
5. Bootstrap CIs
6. Write `results/evals/{timestamp}.json`
7. Print summary table

Wall clock estimate: 20–40 seconds for 200 entries (no LLM, no network).

## 11. Regression policy

- Every PR that touches `policy/`, `dispositions/`, or `evidence/` must
  run `make eval` and include the diff in the PR description.
- Metrics that drop more than the CI half-width are flagged.
- The benchmark dataset is versioned; changing it requires a new eval
  baseline.

## 12. What this spec does NOT do

- Does not evaluate tone, style, or readability of denial reasons
- Does not measure the quality of policy authoring (only its enforcement)
- Does not replace manual review of policy correctness
- Does not test the runtime under adversarial load (that's a security
  concern, see `07_SECURITY_MODEL.md`)

## 13. Sign-off checklist for Phase 7

- [ ] All metrics implemented as `Metric` subclasses
- [ ] All §9 fixtures pass at 1e-6 tolerance
- [ ] Benchmark passes the quality gate
- [ ] `make eval` produces a complete report
- [ ] Bootstrap CIs computed and stored
- [ ] Report rendered as a human-readable summary
- [ ] Any deviation from this spec captured as a new ADR