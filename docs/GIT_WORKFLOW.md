# Git Workflow for the FundTrail Team (8 people)

**Tasks #26 (branches), #27 (PRs), #28 (merge-conflict ownership).**

## The golden rules
1. **`main` is protected** — no direct pushes. Everything lands via Pull Request.
2. **One short-lived branch per task.** Branch from the latest `main`, do one thing,
   open a PR, merge, delete the branch. Branches that live a week cause merge hell.
3. **Never commit data or binaries** (`.db`, `uploads/`, datasets, `.exe`) — they
   can't be merged and conflict constantly. `.gitignore` already blocks them.

## Branch naming
```
feature/excel-import-coverage      fix/secret-key-regression
refactor/auth-blueprint            docs/architecture
ui/login-redesign                  test/upload-rowcounts
```

## Daily loop (every team member)
```bash
git checkout main && git pull --rebase origin main   # start from latest
git checkout -b feature/my-task                       # your branch
# ...work, commit small and often...
git push -u origin feature/my-task                    # publish
# open a Pull Request on GitHub → get 1 review → merge → delete branch
```

## Pull Requests
- Keep them **small** (one task, ideally < ~300 lines). Small PRs get reviewed fast
  and rarely conflict.
- Fill in the PR template (`.github/PULL_REQUEST_TEMPLATE.md`): what changed, how
  tested, which security `verify_*` scripts still pass.
- **At least 1 reviewer** approves before merge. Reviews are how the 2 experienced
  members teach the 6 beginners.

## Avoiding merge conflicts with 8 people — feature-based ownership
Assign **one module per person** so two people rarely touch the same file:

| Owner | Area / files |
|-------|--------------|
| A | Auth — `app/routes/auth.py`, login/session |
| B | Ingestion — `app/routes/ingestion.py` (Excel) |
| C | Analysis/graph — `app/routes/analysis.py`, `static/graph.js` |
| D | Letters — `app/routes/letters.py`, templates |
| E | Admin — `app/routes/admin.py` |
| F | UI/templates + CSS |
| G | Docs, tests, CI |
| H | DB models/migrations |

**The single biggest conflict source is the 3,577-line `app.py`.** Finishing the
split into `app/` (one file per area) is what makes 8 parallel branches possible —
so prioritise the refactor (#12).

## When a conflict still happens
```bash
git checkout main && git pull --rebase origin main
git checkout feature/my-task && git rebase main
# fix conflicts in the marked files, keep BOTH intents, test, then:
git add -A && git rebase --continue && git push --force-with-lease
```
If unsure, pair with the file's owner for 5 minutes rather than guessing.
