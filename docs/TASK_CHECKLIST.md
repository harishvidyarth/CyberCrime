# FundTrail — Master Task Checklist (60-day internship)

The canonical 40-item plan. This mirrors the live task board and is Notion-ready
(matches task #30). **Status:** ✅ done · 🔵 in progress · ⏳ to do.

| # | Task | Status | Where it stands |
|---|------|--------|-----------------|
| 1 | Create GitHub private repo + upload via SSH | ✅ | Pushed to `github.com/harishvidyarth/CyberCrime` (SSH alias `github-harishvidyarth`) |
| 2 | Create `old_files/` (original) + `new_files/` (improved) | ✅ | Done; root cleaned (780 MB originals vs 1.3 MB clean source) |
| 3 | Understand complete application flow & architecture | ✅ | `docs/PROJECT_BRIEFING.md` §1 |
| 4 | Review SAST, Pentest & Retest reports | ✅ | Retest (authoritative, 14 findings) read & cross-checked; originals in `old_files/reports/` |
| 5 | Document all findings & vulnerabilities | ✅ | `docs/SECURITY_FINDINGS.md` (14 official + 4 of our own) |
| 6 | Audit authentication, authorization & DB security | ✅ | All 14 controls verified against live code |
| 7 | Identify hardcoded credentials, secrets & sensitive data | ✅ | Found FT-006 regression, `.env` placeholder, weak reset-script creds |
| 8 | Review all Flask routes, APIs & business logic | 🔵 | Structure & upload path mapped; deep per-route pass ongoing |
| 9 | Review DB schema, tables, indexes & relationships | ⏳ | `models.py` reviewed; full schema doc pending (app on SQLite) |
| 10 | Investigate Excel import/export issues | ⏳ | **NEXT** — reproduce & root-cause the "partial data" bug |
| 11 | Fix security vulnerabilities without breaking functionality | 🔵 | FT-006 + FT-010 fixed & compiled; FT-005 strays, R-03, R-04 remain |
| 12 | Refactor code using SOLID principles | ⏳ | Merge monolith → modular `app/` package |
| 13 | Remove redundant & unused code/files | ⏳ | Kill duplicate app + dead one-off scripts |
| 14 | Add meaningful comments & documentation | ⏳ | Docstring every function in the clean tree |
| 15 | Improve folder structure & project organization | 🔵 | `old_files`/`new_files` done; code-tree cleanup with refactor (#12/#13) |
| 16 | Improve UI/UX across the application | ⏳ | Tailwind base, heavily customized, built to static CSS (offline-safe) |
| 17 | Standardize forms, tables, dashboards & navigation | ⏳ | Component library as part of #16 |
| 18 | Add proper logging & error handling | ⏳ | Some exists (RotatingFileHandler, error pages); standardize |
| 19 | Add caching where required | ⏳ | IFSC lookup already cached; evaluate others |
| 20 | Add message queue if background jobs exist | ⏳ | Evaluate — likely unnecessary for this app |
| 21 | Improve database design if needed | ⏳ | Normalize, indexes, constraints |
| 22 | Create system architecture documentation | ⏳ | Expand briefing into a dedicated doc + diagram |
| 23 | Create deployment documentation | ⏳ | Offline `.exe` per machine (Mac/Win/Linux build steps) |
| 24 | Create README & setup guide | ✅ | `README.md` (Mac run steps, DB options, gotchas) |
| 25 | Add automated testing where possible | ⏳ | pytest for auth, upload, access control |
| 26 | Use branches for each feature/fix | ⏳ | Workflow documented (briefing §6); adopt |
| 27 | Use Pull Requests for code reviews | ⏳ | Define PR process |
| 28 | Resolve merge conflicts via feature-based ownership | ⏳ | One module per person (briefing §6) |
| 29 | Create coding standards for the team | ⏳ | Style + commit + review conventions |
| 30 | Use Notion for requirements/tasks/docs/tracking | ⏳ | I generate Markdown; you paste (can't connect directly) |
| 31 | Evaluate MetaGPT for documentation/planning | ⏳ | Preliminary: **skip** (regression risk) — formalize |
| 32 | Evaluate Graphify for knowledge graph | ⏳ | Preliminary: **skip** (app already a graph tool) — formalize |
| 33 | Decide Docker strategy & containerization | ⏳ | Modest `docker-compose` (dev env + Linux builds) |
| 34 | Verify Mac & Linux build/deployment requirements | ⏳ | PyInstaller can't cross-compile; build per-OS |
| 35 | Identify files that must NOT be uploaded to GitHub | ✅ | `docs/FILES_TO_UPLOAD.md` + `.gitignore` (.env, creds, DBs, logs, generated) |
| 36 | Create mentor questions & clarify unknowns | ✅ | `docs/PROJECT_BRIEFING.md` §8 |
| 37 | Create final cleanup checklist | ⏳ | Pre-delivery checklist |
| 38 | Perform final security review | ⏳ | Re-run all `verify_*.py`; confirm 14/14 |
| 39 | Perform final functional testing | ⏳ | End-to-end: login, upload, graph, letters |
| 40 | Deliver clean, secure, documented, maintainable code | ⏳ | Final tagged release |

**Progress: 10 done · 3 in progress · 27 to do.** Next up: **#10 (Excel bug)**, then continue **#11** security fixes.
