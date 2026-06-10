# Questions for the Mentor

**Task #36 (Notion-ready).** Tick each box when asked; record the answer inline.
These render as real checkboxes in Notion and GitHub.

## A. Scope & deployment
- [ ] Is FundTrail meant to run **offline (.exe per machine)** or **hosted on a central server**? → _answer:_
- [ ] Is **SQLite** acceptable for production, or do they specifically require **MySQL**? → _answer:_
- [ ] Roughly how many officers use it, and do multiple use one instance at once? → _answer:_

## B. Data & privacy (important)
- [ ] Are the sample Excel files / `.db` files **real case data (victim PII)**? (If yes, the data committed to the old repo is a handling incident to report.) → _answer:_
- [ ] Where should case data live, and what's the **backup / retention** expectation? → _answer:_
- [ ] Any **compliance rules** for handling victim/financial PII we must follow? → _answer:_

## C. Codebase & process
- [ ] Which is the **canonical codebase** — the monolith `app.py` or the modular `app/` package? OK to consolidate into one? → _answer:_
- [ ] Should we keep using **our new private repo**, or is there an official team repo? → _answer:_
- [ ] What is the **definition of "done"** for the security retest — zero High/Critical, or a signed-off report? → _answer:_

## D. Functional clarifications
- [ ] The importer currently ingests only 4 sheet types; **POS, AEPS and other withdrawal sheets are dropped**. Should those be added to the graph? Which sheets matter? → _answer:_
- [ ] **Password policy:** enforce strong passwords even for the default `admin`/`officer`, or keep simple ones for demos? → _answer:_
- [ ] Any required **letter format / letterhead** changes for the bank notices? → _answer:_
- [ ] Are there **report exports** expected beyond the current PDF/DOCX? → _answer:_

## E. Priorities & timeline
- [ ] Within the 60 days, what is the **single most important outcome** for them? → _answer:_
- [ ] Any **new features** expected beyond security + bug fixes (new analytics, dashboards)? → _answer:_
- [ ] Who **signs off**, and how do they want **progress demos** (weekly? milestone?)? → _answer:_

---
> Tip: ask A & B first — they decide the database, deployment, and whether the
> committed data is a privacy incident. Everything else depends on those answers.
