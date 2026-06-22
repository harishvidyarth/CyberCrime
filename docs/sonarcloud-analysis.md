# SonarCloud — Analysis, Hotspot Review & Remediation Plan

Companion to `docs/sonarcloud-report.md` (the raw before-fixes snapshot: 396 issues, 10 hotspots).

## 0. "Last analysis had warnings" (item 8)
The latest analysis status is **SUCCESS with `warningCount: 2`**. The warning *text* is not exposed by
the public `ce/analysis_warnings` API for this token; view it via the warning icon on the latest analysis
in SonarCloud -> Project -> *Background Tasks*. Most common causes for this setup:
1. **Shallow clone / SCM blame** — though `ci.yml` sets `fetch-depth: 0`, the scan job is a separate
   checkout; verify it also uses full depth so "new code" detection is accurate.
2. **Excluded/duplicate files or no coverage report imported** — the Sonar job does not consume
   `coverage.xml`, so coverage shows 0% and Sonar may warn.
Action: read the two warnings in the UI before trusting "new code" / coverage metrics.

## 1. Security Hotspots (10) — review & mark on the dashboard yourself
All ten assess as **SAFE** with the reasoning below. None auto-resolved (per instruction).

| # | Rule | Location | What it is | Why flagged | Recommendation |
|---|------|----------|------------|-------------|----------------|
| 1 | csrf | app.py:5797 | `@csrf.exempt` on `/__integration_test/sentry` | CSRF disabled | **Safe** — disabled-by-default JSON probe behind `ENABLE_INTEGRATION_TEST_ROUTES` + Bearer token; no browser form, no cookie-as-auth. |
| 2 | csrf | app.py:5807 | `@csrf.exempt` on `/__integration_test/resend` | CSRF disabled | **Safe** — same guarded probe pattern. |
| 3 | csrf | tests/test_access_control.py:37 | `WTF_CSRF_ENABLED=False` | CSRF off in tests | **Safe** — test-only config; CSRF itself is covered by `smoke_test.py`. |
| 4 | csrf | tests/test_mrm_workflow.py:27 | `WTF_CSRF_ENABLED=False` | CSRF off in tests | **Safe** — test-only. |
| 5 | dos | admin_dashboard.html:154 | JS `…toFixed(2).replace(/\.?0+$/, '')` | regex backtracking | **Safe** — anchored `0+$` on a short numeric string; linear, no nested quantifiers. |
| 6 | dos | admin_dashboard.html:155 | same number-format regex | regex backtracking | **Safe** — same. |
| 7 | dos | graph_tree1.html:1180 | `/^\s*Place\s*(?:\/Location)?\s*of\s*ATM\s*[:\-]\s*/i` | regex backtracking | **Safe** — `\s*` groups separated by literals; linear, input is a fixed sheet label. |
| 8 | dos | index.html:253 | number-format regex | regex backtracking | **Safe** — same as 5/6. |
| 9 | dos | index.html:254 | number-format regex | regex backtracking | **Safe** — same. |
| 10 | dos | app.py:4021 | email regex `^[^@\s]+@[^@\s]+\.[^@\s]+$` | polynomial backtracking | **Safe (optional hardening)** — `+` groups separated by literal `@`/`.`; input is a short admin-entered officer email. Optional: cap length for defense-in-depth. |

## 2. Security issues — false positives (no code change; mark "Safe"/"Won't fix")
- **`python:S2068` (7)** — the word "password" in **column-DDL strings** (`app.py:1068/1070`:
  `"must_change_password": "BOOLEAN…"`, `"password_changed_at": "DATETIME…"`) and **test fixtures**
  (`smoke_test.py:115/128/142/181`). Not credentials.
- **`secrets:S6697` (BLOCKER, setup.sql:33)** — `THE_PASSWORD` is a **documentation placeholder** in a
  comment, not a live secret. Optional: rename to `<YOUR_DB_PASSWORD>` to stop the matcher.
- **`text:S8565` (pyproject.toml)** — "missing lock file"; informational.

## 3. Security issues — FIXED
- **`python:S6437` (BLOCKER, app.py:1385)** — removed the hardcoded `"dummy_password"` literal in the
  login timing-attack mitigation; now hashes `secrets.token_urlsafe(16)` (random throwaway). Behavior
  unchanged (still a real constant-time hash op).

## 4. Security issues — real but deferred (need a small, careful batch — your go-ahead)
- **`pythonsecurity:S5145` (5, MINOR, app.py:506/518/3440/3583/3632)** — logging user-controlled values
  (e.g. ack_no) enables log-forging via CR/LF. Fix: a `safe_log(v)` helper that strips `\r\n` before
  interpolation, applied at the 5 sites. Low risk, ~1 small batch.
- **`githubactions:S7637` (3, MAJOR, ci.yml:32/46/69)** — third-party actions referenced by tag, not
  full commit SHA (supply-chain). Fix: pin `codecov/codecov-action`, `SonarSource/sonarqube-scan-action`,
  `soos-io/soos-sca-github-action` to commit SHAs. Mechanical but needs the exact SHAs.

## 5. Maintainability/Reliability (360 smells + 18 bugs) — prioritized plan
Too large to auto-fix safely in one pass; recommended order:
1. **`python:S1192` (51)** — duplicated string literals -> hoist to module constants. Mechanical, batchable.
2. **`python:S8572`/`S6965` (40/36)** — modern-Python migrations. Mechanical, but test after each batch.
3. **`javascript:S7761/S7764/S6582/S2004` (~80 in graph.js/templates)** — JS modernization (optional
   chaining, nesting depth). Pairs with the graph.js refactor in `PRD-graphjs.md`.
4. **`python:S3776` (18)** — cognitive complexity -> extract helpers. **Higher risk**, do last with tests.
5. **`css:S7924`, `Web:S6819`, `Web:InputWithoutLabelCheck` (~30)** — template a11y/markup; pairs with the
   accessibility gap noted in the graph.js PRD.

## 6. Before / after
- **Before (this snapshot):** 396 issues (2 BLOCKER, 95 CRITICAL, 212 MAJOR, 86 MINOR, 1 INFO), 10 hotspots.
- **After this pass:** 1 BLOCKER fixed in code (S6437); 1 BLOCKER + 7 MAJOR security flags identified as
  false positives to mark "Safe" on the dashboard. **Dashboard counts only refresh on the next CI
  SonarCloud analysis** — there is no API to recount locally without running the scanner. Re-pull
  `docs/sonarcloud-report.md` after the next CI run on `main`.
