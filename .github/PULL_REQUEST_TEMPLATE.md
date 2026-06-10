<!-- FundTrail PR template — fill this in before requesting review (task #27) -->

## What & why
<!-- One or two sentences: what this PR changes and the task/finding it addresses -->
Closes task #

## Changes
-

## How I tested
<!-- Commands run, files uploaded, screens checked -->
-

## Security checklist (don't regress verified fixes — see docs/SECURITY_FINDINGS.md)
- [ ] No secrets/credentials/data committed (`.env`, `*.db`, `uploads/`)
- [ ] `@login_required` / `@admin_required` intact on affected routes
- [ ] `check_case_access()` still guards any `<ack_no>` route I touched
- [ ] CSRF, cell-sanitiser, SRI/CSP untouched or preserved
- [ ] Relevant `scripts/verify_*.py` still pass

## Reviewer
- [ ] Code reviewed by at least one teammate
- [ ] Formatted (`black`) + linted (`ruff`)
