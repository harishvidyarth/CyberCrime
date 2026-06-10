# Tooling & Infrastructure Decisions

Honest evaluations for **tasks #19 (caching), #20 (message queue), #31 (MetaGPT),
#32 (Graphify), #33 (Docker)**. Principle: this is one internal tool for a handful
of officers — match the tooling to that reality, don't cargo-cult big-company stacks.

## #31 — MetaGPT → ❌ SKIP
MetaGPT auto-generates whole codebases from a prompt. This project's value is a set
of **pentest-verified security fixes**; regenerating code over it is the fastest way
to silently regress them (we already caught one human regression — FT-006). Use it,
at most, to *draft* documentation you then review — never to generate app code.

## #32 — Graphify (knowledge graph) → ❌ SKIP
FundTrail **is already a graph application** (D3.js fund-flow graphs). A separate
"knowledge graph for reference" adds a dependency and maintenance burden for no
investigative value. If the goal is understanding the codebase, the diagram in
`ARCHITECTURE.md` does the job. Revisit only if you later need cross-case link
analysis across many complaints — and even then, evaluate Neo4j directly.

## #19 — Caching → ✅ already done; minor additions only
The one hot path is the **51 MB IFSC lookup**, already cached (`IFSC_CODES.pkl` +
`ifsc_state_cache.json`) in memory. That's the right call. Possible small wins:
`functools.lru_cache` on `ifsc_info` lookups and on the statewise-summary aggregation
per `ack_no`. **No Redis** — it adds a server to an offline app for no real benefit.

## #20 — Message queue → ❌ SKIP (no qualifying workload)
There are no long-running background jobs. The only slowish operations are large
Excel imports and batch letter generation, both request-scoped. If a future import
gets huge, use a simple **threaded background task** or RQ — not Kafka/RabbitMQ,
which are operational overhead an offline single-machine tool can't justify.

## #33 — Docker → ✅ modest, optional yes
Not needed to *ship* the offline `.exe`, but genuinely useful to (a) give all 8
teammates one identical dev environment and (b) produce reproducible **Linux**
builds. A single `docker-compose.yml` (app + optional MySQL) is provided. Keep it
opt-in: contributors who prefer a local venv shouldn't be forced into Docker.

## Backend topics from the brief — pragmatic verdicts
| Topic | For this app |
|-------|--------------|
| SOLID / design patterns | ✅ apply during the monolith→blueprint refactor (#12) |
| Caching | ✅ already present (IFSC); add small `lru_cache` only |
| Message queueing | ❌ no qualifying jobs |
| Deployment | ✅ offline `.exe` per machine (see DEPLOYMENT.md) |
| Database design | ✅ incremental migrations (see DATABASE.md) |
| System design | ✅ documented (ARCHITECTURE.md) — keep it a modular monolith |
| Docker | ✅ dev env + Linux builds, optional |

**Bottom line:** finish the refactor, fix the Excel coverage, harden the few open
security items, and polish the UI. Skip MetaGPT, Graphify, Redis, and message queues
— they'd cost you weeks of the 60 and add risk for zero user benefit.
