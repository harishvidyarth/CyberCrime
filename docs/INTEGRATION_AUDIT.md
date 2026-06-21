# Integration Audit

Audit date: 2026-06-21 (re-verified)

Scope: Sentry, Resend, GitGuardian, Dependabot, SOOS/Snyk, SonarCloud, CodeFactor, and Codecov.

## Local verification (2026-06-21)

Run from a clean checkout with the project venv:

- `ruff check main/ dev_seed.py` → **All checks passed**.
- `bandit --ini .bandit -r main/app.py main/models.py main/ifsc_utils.py main/email_utils.py main/scripts main/tests`
  (deterministic explicit target list — NOT a bare `-r main/`, which hangs) → **No issues identified**.
- `pip-audit -r main/requirements.txt --no-deps` → **No known vulnerabilities found**.
- `pytest --cov=main --cov-report=term-missing` (from repo root) → **passed**; plus the three
  standalone suites `smoke_test.py`, `test_access_control.py`, `test_mrm_workflow.py` all green.
- **No-`.env` boot:** started with only `SECRET_KEY` set (no `.env` file, all integrations unset) —
  `/healthz`, `/login`, `/forgot_password` all returned **200** with no startup errors. Every
  integration (Sentry, Resend, SOOS, Snyk, GitGuardian, Codecov, Sonar) is optional and inert until
  its secret is supplied, so the app ships cleanly as an EXE or web app with no `.env` present.

## Summary

| Integration | Status | Reason |
| --- | --- | --- |
| Sentry | WARNING | SDK and Flask integration are present, but only DSN is documented and there is no release/environment config. A guarded test endpoint was added. |
| Resend | WARNING | Package and password-reset usage are present. Sender is now environment-configurable, but production requires a verified sender/domain and secrets. |
| GitGuardian | WARNING | CI scan and config exist, but CI requires `GITGUARDIAN_API_KEY` and should fail only after the secret is configured. |
| Dependabot | PASS | Weekly pip updates are configured for `/main/`. |
| SOOS | WARNING | SOOS SCA workflow exists, but requires `SOOS_CLIENT_ID` and `SOOS_API_KEY`. |
| Snyk | WARNING | Snyk CI workflow exists, but requires the `SNYK_TOKEN` GitHub Actions secret. |
| SonarCloud | WARNING | Workflow and properties exist; projectKey/organization are now real-form (`harishvidyarth_CyberCrime` / `harishvidyarth`) — confirm they match your SonarCloud dashboard. Still needs `SONAR_TOKEN`; coverage path optional. |
| CodeFactor | WARNING | No repo config exists. README says to enable via GitHub Marketplace; operation depends on external app installation. |
| Codecov | WARNING | CI uploads `coverage.xml`, but requires `CODECOV_TOKEN` unless the repository is public and tokenless upload is enabled. |

## Sentry

Status: WARNING

Evidence found:
- `main/requirements.txt` includes `sentry-sdk[flask]==2.47.0`.
- `main/app.py` initializes `sentry_sdk` with `FlaskIntegration` when `SENTRY_DSN` is set.
- `.env.example` and `main/.env.example` document `SENTRY_DSN`.
- New guarded probe route: `POST /__integration_test/sentry`.

Files involved:
- `main/app.py`
- `main/requirements.txt`
- `.env.example`
- `main/.env.example`

Missing requirements:
- Production secret/environment value: `SENTRY_DSN`.
- Recommended Sentry metadata: environment, release/version, server name, and deployment release association.
- Alerting/project ownership is outside this repository and must be configured in Sentry.

How it works:
- On app startup, if `SENTRY_DSN` is present, the Flask integration registers with Sentry.
- Unhandled Flask exceptions are captured by Sentry.

Test method:
1. In a staging environment, set `SENTRY_DSN`, `ENABLE_INTEGRATION_TEST_ROUTES=true`, and a strong `INTEGRATION_TEST_TOKEN`.
2. Start the app.
3. Run:
   ```bash
   curl -X POST http://127.0.0.1:5050/__integration_test/sentry \
     -H "Authorization: Bearer $INTEGRATION_TEST_TOKEN"
   ```

Expected result:
- The endpoint returns a 500 response.
- Sentry receives `FundTrail Sentry integration test exception`.

Recommended fixes:
- Add `SENTRY_ENVIRONMENT`, `SENTRY_RELEASE`, and optionally `SENTRY_TRACES_SAMPLE_RATE` environment variables.
- Disable `ENABLE_INTEGRATION_TEST_ROUTES` after validation.

## Resend

Status: WARNING

Evidence found:
- `main/requirements.txt` includes `resend==2.21.0`.
- `main/email_utils.py` sends password reset emails through Resend when `RESEND_API_KEY` is present.
- Password reset flow in `main/app.py` calls `send_password_reset`.
- `.env.example` and `main/.env.example` document `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, and `RESEND_TEST_TO`.
- New guarded probe route: `POST /__integration_test/resend`.

Files involved:
- `main/email_utils.py`
- `main/app.py`
- `main/requirements.txt`
- `.env.example`
- `main/.env.example`

Missing requirements:
- Production secret: `RESEND_API_KEY`.
- Production sender: `RESEND_FROM_EMAIL` must use a Resend-verified domain/sender.
- `RESEND_TEST_TO` is needed only for manual validation.

How it works:
- During password reset, FundTrail generates a time-limited reset link and calls Resend.
- If the package or API key is missing, sending is skipped.

Test method:
1. In staging, set `RESEND_API_KEY`, verified `RESEND_FROM_EMAIL`, `RESEND_TEST_TO`, `ENABLE_INTEGRATION_TEST_ROUTES=true`, and `INTEGRATION_TEST_TOKEN`.
2. Start the app.
3. Run:
   ```bash
   curl -X POST http://127.0.0.1:5050/__integration_test/resend \
     -H "Authorization: Bearer $INTEGRATION_TEST_TOKEN"
   ```

Expected result:
- JSON response: `{"status":"sent","to":"..."}`.
- The test recipient receives one FundTrail integration test email.

Recommended fixes:
- Use a verified organizational sender in `RESEND_FROM_EMAIL`.
- Consider surfacing email-send health in operational logs/alerts.

## GitGuardian

Status: WARNING

Evidence found:
- `.gitguardian.yml` excludes large/static/migration paths.
- `.github/workflows/ci.yml` installs `ggshield` and runs `ggshield scan path .`.
- CI expects `GITGUARDIAN_API_KEY`.

Files involved:
- `.gitguardian.yml`
- `.github/workflows/ci.yml`
- `.gitignore`

Missing requirements:
- GitHub secret: `GITGUARDIAN_API_KEY`.
- Optional local developer setup: `ggshield auth login` or environment token.

How it works:
- CI scans repository contents for secrets using GitGuardian before merge.

Test method:
- Do not commit real secrets.
- Use GitGuardian's documented safe test/dummy secret pattern in a temporary branch, or run `ggshield secret scan pre-commit` locally against a disposable file containing only a documented test token.
- Delete the disposable file before merging.

Expected result:
- The scan fails on the dummy/test secret and reports the finding.

Recommended fixes:
- Add `GITGUARDIAN_API_KEY` to GitHub Actions secrets.
- Consider adding the GitGuardian app/pre-receive protection in GitHub for earlier feedback.

## Dependabot

Status: PASS

Evidence found:
- `.github/dependabot.yml` configures weekly pip updates for `/main/`.
- The project dependency manifest is `main/requirements.txt`.

Files involved:
- `.github/dependabot.yml`
- `main/requirements.txt`

Missing requirements:
- None in repository configuration.

How it works:
- GitHub Dependabot checks `main/requirements.txt` weekly and opens dependency PRs.

Test method:
- In GitHub, open Insights/Security/Dependabot or Dependency graph and trigger/re-run Dependabot checks.
- Alternatively, temporarily lower one package pin in a branch and wait for/schedule Dependabot to propose the latest secure version.

Expected result:
- Dependabot opens PRs labeled `dependencies` when updates are available.

Recommended fixes:
- Add `groups` if many PRs become noisy.
- Add GitHub reviewers/assignees if the team wants automatic routing.

## SOOS / Snyk

Status: SOOS WARNING, Snyk WARNING

Evidence found:
- `.github/workflows/ci.yml` runs `soos-io/soos-sca-github-action@v2`.
- `.github/workflows/snyk.yml` installs dependencies from `main/requirements.txt` and runs `snyk test --severity-threshold=high` from `main/`.

Files involved:
- `.github/workflows/ci.yml`
- `.github/workflows/snyk.yml`
- `main/requirements.txt`

Missing requirements:
- SOOS secrets: `SOOS_CLIENT_ID`, `SOOS_API_KEY`.
- Snyk secret: `SNYK_TOKEN`.
- Optional Snyk policy file: `.snyk`, only if the team needs documented ignores/patch policy.

How it works:
- SOOS SCA should upload/scan dependency inventory from CI.
- Snyk runs on push and pull requests, installs Python 3.11 dependencies, and fails the build on high/critical vulnerabilities.

Test method:
- For SOOS, push a branch after adding the SOOS secrets and verify the `SOOS SCA` CI step completes and a project appears in SOOS.
- For Snyk, add `SNYK_TOKEN` in GitHub Actions secrets, then push a branch or open a pull request.

Expected result:
- SOOS reports dependency inventory and vulnerability findings.
- Snyk reports dependency vulnerabilities and fails when high/critical findings are present.

Recommended fixes:
- Add SOOS secrets in GitHub Actions.
- Add `SNYK_TOKEN` in GitHub Actions secrets.
- Decide whether a checked-in `.snyk` policy file is needed for documented ignores.

## SonarCloud

Status: WARNING

Evidence found:
- `sonar-project.properties` exists.
- `.github/workflows/ci.yml` runs `SonarSource/sonarqube-scan-action@v6`.
- CI expects `SONAR_TOKEN`.

Files involved:
- `sonar-project.properties`
- `.github/workflows/ci.yml`
- `pyproject.toml`

Missing requirements:
- `sonar.projectKey=harishvidyarth_CyberCrime` and `sonar.organization=harishvidyarth` are now set to
  real-form values — confirm they exactly match the project created in your SonarCloud dashboard.
- GitHub secret: `SONAR_TOKEN`.
- Coverage path is not configured in `sonar-project.properties`, and the Sonar job does not consume the generated `coverage.xml` artifact.

How it works:
- After tests pass, GitHub Actions runs the SonarCloud scanner against `main/`.

Test method:
- Replace placeholders with the real SonarCloud project key and organization.
- Add `SONAR_TOKEN`.
- Push this branch; the new integration probe test should trigger analysis.

Expected result:
- SonarCloud analysis appears for the branch/PR.

Recommended fixes:
- Set real SonarCloud metadata.
- Add `sonar.python.coverage.reportPaths=coverage.xml` and pass/download `coverage.xml` into the Sonar job, or run scan in the test job after coverage generation.

## CodeFactor

Status: WARNING

Evidence found:
- `README.md` says to enable CodeFactor through GitHub Marketplace.
- No `.codefactor.yml` or CodeFactor workflow was found.

Files involved:
- `README.md`
- `pyproject.toml`
- `main/tests/test_integration_probes.py`

Missing requirements:
- External CodeFactor GitHub app installation.
- Optional repository-specific `.codefactor.yml`.

How it works:
- CodeFactor runs as a GitHub app against pushes/PRs once installed.
- It will inspect Python code and report quality issues externally.

Test method:
- Ensure the CodeFactor app is installed for this repository.
- Push this branch. The new test file and app route changes should trigger analysis.

Expected result:
- CodeFactor posts a commit/PR check.

Recommended fixes:
- Add `.codefactor.yml` only if default analysis is noisy or excludes are needed.
- Document the external app installation requirement in setup docs.

## Codecov

Status: WARNING

Evidence found:
- `.github/workflows/ci.yml` runs `pytest --cov=main --cov-report=xml`.
- The workflow uploads `./coverage.xml` with `codecov/codecov-action@v5`.
- `pyproject.toml` configures coverage source and omits tests/migrations.
- New `main/tests/test_integration_probes.py` adds coverage for the integration probes.

Files involved:
- `.github/workflows/ci.yml`
- `pyproject.toml`
- `main/tests/test_integration_probes.py`

Missing requirements:
- GitHub secret: `CODECOV_TOKEN`, unless tokenless upload is enabled for the repository.
- Optional `codecov.yml` for thresholds/status behavior.

How it works:
- Pytest writes `coverage.xml`.
- Codecov action uploads the report after tests complete.

Test method:
- Add `CODECOV_TOKEN` if required by the repository visibility/settings.
- Push this branch and inspect the Codecov check.

Expected result:
- Codecov receives `coverage.xml` and reports coverage for changed files.

Recommended fixes:
- Add `codecov.yml` with project/patch thresholds once a baseline is accepted.
- Consider making upload non-blocking only if Codecov availability should not block deployments.
