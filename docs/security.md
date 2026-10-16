# Security Summary — AI Compliance Runtime

This is a public-facing summary for technical reviewers. The complete threat
model and control catalog live in
[`claude_chat/07_SECURITY_MODEL.md`](../claude_chat/07_SECURITY_MODEL.md).

## 1. Overview

The runtime intercepts an AI agent's tool calls, evaluates each against a
versioned policy set, requires human approval for high-stakes actions, and
records a tamper-evident, cryptographically-signed evidence chain. Its value
rests on two properties: **policy is enforced correctly** and **evidence is
recorded truthfully**. The security posture is therefore strict — the runtime
treats itself as the high-value target.

The runtime calls no LLM and makes no outbound network requests on its
critical path (ADR-013); evaluation and evidence are fully deterministic.

## 2. Threat model summary

- **T-01 Policy bypass via malformed tool call.** An agent crafts parameters
  to slip past a rule (type confusion, missing fields, nested shapes). Strict
  typing, missing-field-denies, and a 15-scenario bypass suite mitigate it.
- **T-03 Direct database tampering.** An attacker with filesystem access edits
  or deletes evidence rows. SQLite append-only triggers reject UPDATE/DELETE on
  `action_records`, `approval_decisions`, and `audit_events`; a SHA-256 hash
  chain and Ed25519 signatures detect any change that bypasses the triggers.
- **T-04 Signing-key compromise.** A leaked private key lets an attacker forge
  records. The key is generated on first run with mode 0600, never logged, and
  loaded only inside `evidence/signing.py`.
- **T-05 Approval bypass.** A pending request is approved without a human, or a
  decided request is mutated. All transitions go through one service, use
  optimistic locking, write an audit event in the same transaction, and reject
  terminal-state changes; concurrent decisions resolve to exactly one winner.
- **T-07 Denial of service.** An agent floods the runtime. A per-agent,
  per-action rate limiter caps request rate and exposes drop metrics.
- **T-10 Malicious dependency.** A compromised package runs code at import. All
  dependencies are pinned to exact versions via a `pip-compile` lockfile, and
  `pip-audit` runs in CI.

## 3. Controls by intent

- **Prompt injection:** string parameters are scanned for injection markers and
  denied; all displayed/logged strings are escaped (control chars in logs, HTML
  in the dashboard).
- **Evidence integrity:** every authorized action is hash-chained and signed;
  raw parameters are never stored (only a SHA-256 `parameters_hash`).
- **Key safety:** private key is 0600, never logged, isolated to one module;
  the public verification key is exported separately.
- **Approval integrity:** single-writer service, optimistic locking, terminal
  states, same-transaction audit, TTL expiry.
- **DoS resistance:** rate limiting, request-size limits, bounded SQLite writes.
- **Dependency hygiene:** exact pins, lockfile-only installs in CI, `pip-audit`.

## 4. Cryptographic guarantees

Each `ActionRecord` stores `current_hash = sha256(canonical_json(fields) | previous_hash)`
and an Ed25519 signature over that hash. Together these prove, offline and with
only the public key, that:

- **the record set has not been altered** (any field change breaks the hash),
- **no record was inserted, removed, or reordered** (the chain links break),
- **records were produced by the holder of the signing key** (signatures).

They do **not** prove that the policy itself is correct, that the host was
uncompromised at signing time, or anything about data the runtime never saw.

## 5. Known limitations / residual risks (v1)

- No multi-tenant isolation; single-tenant deployment only.
- No end-user authentication; v1 uses synthetic actor identities.
- Host compromise implies key compromise (no HSM/KMS in v1).
- The prompt-injection filter is a deterministic marker scan, not an
  LLM-based detector; it reduces, but does not eliminate, injection risk.
- Network perimeter is assumed (localhost or behind a reverse proxy).

## 6. Disclosure policy

Please report suspected vulnerabilities privately to the maintainer rather than
opening a public issue, and allow reasonable time for a fix before disclosure.

## Vulnerability exceptions

`pip-audit` is configured to skip the following advisory because it is
inapplicable to this project:

- **PYSEC-2026-3447** (`setuptools`): MANIFEST.in sdist packaging issue. This
  project does not publish packages to PyPI, does not build source
  distributions, and uses `setuptools` only for editable local installs. The
  vulnerability path is unreachable.

Any new advisory must be triaged and either fixed or documented here with a
justification. Blanket ignores are not permitted.

## 7. Full model

See [`claude_chat/07_SECURITY_MODEL.md`](../claude_chat/07_SECURITY_MODEL.md)
for the STRIDE threat model, the full P0/P1/P2 control catalog (C-01…C-46),
the verification plan, and accepted residual risks.
