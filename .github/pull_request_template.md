<!-- Pull request template for the AI Compliance Runtime. -->

## Summary
<!-- What does this PR do? -->

## Changes
<!-- List the files changed -->

## Security checklist (from 07_SECURITY_MODEL.md §7)
- [ ] No new hardcoded secrets
- [ ] No new os.getenv outside config/loader.py
- [ ] No new raw SQL outside storage/
- [ ] No new eval/exec/shell=True
- [ ] No new file paths derived from user input without validation
- [ ] All new policies validated on startup
- [ ] All new state transitions write to audit_events in same transaction
- [ ] All new string fields escaped in logs and dashboards
- [ ] pip-audit shows no high-severity vulnerabilities
- [ ] Private key material never appears in any test output or fixture

## Test coverage
- [ ] All new code has tests
- [ ] pytest tests/ passes locally
- [ ] No FAILED/ERROR in test output

## Documentation
- [ ] CHANGELOG.md updated
- [ ] Relevant spec (05_DATA_SPEC / 06_EVAL_SPEC / 07_SECURITY_MODEL)
      updated if behavior changed
