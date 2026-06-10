# Final Cleanup & Delivery Checklist

**Task #37** (and the bar for #40, "deliver clean/secure/documented code").
Tick every box before handing the project back.

## Code hygiene
- [ ] Monolith `app.py` merged into the `app/` package; duplicate removed (#12/#13)
- [ ] Dead/one-off scripts pruned from `main/scripts/` (keep only `verify_*`, admin, init)
- [ ] No commented-out code blocks left behind
- [ ] Every function has a docstring; comments explain *why* (#14)
- [ ] `black` + `ruff` clean across `main/`
- [ ] Duplicate letter routes consolidated (`/generate_letter[_pdf|_docx]`)

## Security (must be green — see SECURITY_FINDINGS.md)
- [ ] No hardcoded secrets; app refuses to start without `SECRET_KEY` (FT-006)
- [ ] No stray world-readable `.db` copies; one canonical store (FT-005/R-02)
- [ ] `.env` not committed; only `.env.example` is
- [ ] All `scripts/verify_*.py` pass → 14/14 findings hold (#38)
- [ ] Excel upload still sanitises cells on every sheet (FT-014)

## Data & repo
- [ ] No victim PII / `.db` / `uploads/` / datasets in Git history
- [ ] `.gitignore` + `.dockerignore` cover secrets/data/bloat
- [ ] `IFSC_CODES.pkl` documented as external (not committed)

## Functionality (#39)
- [ ] Login + roles (Admin/Officer/Viewer) work; lockout works
- [ ] Excel upload shows **complete** data incl. POS/AEPS (#10 fixed)
- [ ] Graph renders; put-on-hold + KYC save; letters generate (.docx/.pdf)

## Docs
- [ ] README, ARCHITECTURE, DATABASE, DEPLOYMENT, SECURITY_FINDINGS current
- [ ] TASK_CHECKLIST reflects final status
- [ ] Mentor questions answered/recorded

## Delivery
- [ ] Final build per OS verified on a clean machine (#34)
- [ ] Tagged release pushed to GitHub
- [ ] Handover walkthrough done with the team
