# FundTrail — Coding Standards

**Task #29.** Keep the codebase readable and consistent for future maintainers.

## Python
- **Style:** PEP 8. Auto-format with **black**, lint with **ruff** or **flake8**.
  ```bash
  pip install black ruff
  black main/ && ruff check main/
  ```
- **Naming:** `snake_case` functions/variables, `PascalCase` classes,
  `UPPER_CASE` constants. Names say what they do (`find_sheet_name`, not `fsn`).
- **Functions:** one job each. If a function is > ~50 lines or needs section
  comments to follow, split it. (`upload_excel` is the prime example to break up.)
- **Docstrings on every function** (task #14): one line on what it does, plus args/
  returns if non-obvious. Comments explain **why**, not what the code already says.
- **No secrets in code.** Read from environment (`os.environ`). The hardcoded
  fallback secret was a real regression — never reintroduce one.
- **DB access** only through SQLAlchemy ORM (parameterised). No f-string SQL.
- **Untrusted input** (uploads, form fields) is validated and sanitised at the edge.

## Security invariants (must never regress — see SECURITY_FINDINGS.md)
- `@login_required` on every non-public route; `@admin_required` on admin routes.
- `check_case_access(ack_no)` on every case-scoped route (IDOR guard).
- Keep CSRF on; keep the cell sanitiser on every Excel sheet; keep SRI/CSP.

## Templates / JS / CSS
- Always use Jinja2 auto-escaping (`{{ value }}`) — never `| safe` on user data.
- Keep external scripts pinned with SRI hashes.
- CSS: use the shared design tokens/components (task #16/#17), no inline styles.

## Commits
- Small, focused, present-tense subject: `fix: restore SECRET_KEY guard (FT-006)`.
- Reference the task/finding ID where relevant.

## Definition of Done (per task)
Code formatted + linted · docstrings added · no secrets/data committed ·
relevant `verify_*` scripts pass · reviewed via PR · task marked complete.
