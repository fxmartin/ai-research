# Project Progress Tracker

*Last Updated: 2026-04-16*
*Overall Progress: 80% Complete (44/55 stories · 108/133 points)*

## 🎯 Project Overview
- **Total Epics:** 9 (8 functional + NFR)
- **Total Features:** 24
- **Total Stories:** 55 (50 functional + 5 NFR)
- **Completed:** 44 | **In Progress:** 0 | **Not Started:** 11

**MVP (Epics 01–04):** ✅ **100% complete** — 26/26 stories, 63/63 points.
**Phase 2 remaining:** Epic 05 (6 stories) + 5 NFR stories.

---

## 📊 Epic Progress Summary

### Epic 01: Foundation & Python Toolkit
**Progress:** 100% | **Status:** ✅ Done
- **Features:** 3/3 completed
- **Stories:** 9/9 completed
- **Blockers:** None
- **Next Milestone:** —

### Epic 02: Wiki Materialization & Indexing
**Progress:** 100% | **Status:** ✅ Done
- **Features:** 2/2 completed
- **Stories:** 6/6 completed
- **Blockers:** None
- **Next Milestone:** —

### Epic 03: Claude Code Slash Commands
**Progress:** 100% | **Status:** ✅ Done
- **Features:** 3/3 completed
- **Stories:** 6/6 completed
- **Blockers:** None
- **Next Milestone:** —

### Epic 04: Quality, Obsidian Compat & Docs
**Progress:** 100% | **Status:** ✅ Done
- **Features:** 3/3 completed
- **Stories:** 5/5 completed
- **Blockers:** None — `04.1-002` merged with nightly-CI DoD box still open (tracked as minor doc debt)
- **Next Milestone:** —

### Epic 05: Phase 2 — YouTube, Contradictions, Ops
**Progress:** 0% | **Status:** On Track (not started)
- **Features:** 0/3 completed
- **Stories:** 0/6 completed (17 pts)
- **Blockers:** None — all cross-epic deps satisfied
- **Next Milestone:** Start with `05.3-001` (`/status` — 2 pts) as kickoff

### Epic 06: MCP Server for Claude Desktop
**Progress:** 100% | **Status:** ✅ Done
- **Features:** 3/3 completed
- **Stories:** 8/8 completed (merged 2026-04-15)
- **Blockers:** None
- **Next Milestone:** — (epic footer and some DoD checkboxes are stale; git log is authoritative)

### Epic 07: Archive-After-Ingest
**Progress:** 100% | **Status:** ✅ Done
- **Features:** 3/3 completed
- **Stories:** 6/6 completed (merged 2026-04-15)
- **Blockers:** None
- **Next Milestone:** — (epic footer stale; needs cleanup)

### Epic 08: Dual Source Links
**Progress:** 100% | **Status:** ✅ Done
- **Features:** 3/3 completed
- **Stories:** 4/4 completed (merged 2026-04-15)
- **Blockers:** None
- **Next Milestone:** — (epic footer stale; needs cleanup)

### NFR: Non-Functional Requirements
**Progress:** 0% | **Status:** At Risk
- **Features:** n/a (flat list of 5 NFRs)
- **Stories:** 0/5 completed (8 pts)
- **Blockers:** None technical — MVP shipped without explicit NFR verification
- **Next Milestone:** Schedule NFR audit sprint after Epic 05

---

## 🚀 Feature Breakdown

### Epic 01: Foundation & Python Toolkit
#### ✅ Feature 01.1: Project Skeleton
- Status: **DONE** · Stories: 2/2 · Completion: 2026-04-14

#### ✅ Feature 01.2: Extract Adapters
- Status: **DONE** · Stories: 4/4 · Completion: 2026-04-14

#### ✅ Feature 01.3: Utility Verbs
- Status: **DONE** · Stories: 3/3 · Completion: 2026-04-14

### Epic 02: Wiki Materialization & Indexing
#### ✅ Feature 02.1: Atomic Page Writes
- Status: **DONE** · Stories: 3/3 · Completion: 2026-04-14

#### ✅ Feature 02.2: Retrieval Index
- Status: **DONE** · Stories: 3/3 · Completion: 2026-04-14

### Epic 03: Claude Code Slash Commands
#### ✅ Feature 03.1: `/ingest`
- Status: **DONE** · Stories: 2/2 · Completion: 2026-04-14

#### ✅ Feature 03.2: `/ingest-inbox`
- Status: **DONE** · Stories: 2/2 · Completion: 2026-04-14

#### ✅ Feature 03.3: `/ask`
- Status: **DONE** · Stories: 2/2 · Completion: 2026-04-14

### Epic 04: Quality, Obsidian Compat & Docs
#### ✅ Feature 04.1: Testing
- Status: **DONE** · Stories: 2/2 · Completion: 2026-04-14

#### ✅ Feature 04.2: Obsidian Compatibility
- Status: **DONE** · Stories: 1/1 · Completion: 2026-04-14

#### ✅ Feature 04.3: CI & Docs
- Status: **DONE** · Stories: 2/2 · Completion: 2026-04-15

### Epic 05: Phase 2 — YouTube, Contradictions, Ops
#### ⏳ Feature 05.1: YouTube Ingestion
- Status: **NOT STARTED** · Stories: 0/2 (6 pts)

#### ⏳ Feature 05.2: Contradiction Detection
- Status: **NOT STARTED** · Stories: 0/2 (8 pts)

#### ⏳ Feature 05.3: Ops (`/status` + launchd)
- Status: **NOT STARTED** · Stories: 0/2 (3 pts)

### Epic 06: MCP Server for Claude Desktop
#### ✅ Feature 06.1: Server Skeleton
- Status: **DONE** · Stories: 2/2 · Completion: 2026-04-15

#### ✅ Feature 06.2: Read-Only Tools (`ask`, `search`, `list_pages`, `get_page`)
- Status: **DONE** · Stories: 4/4 · Completion: 2026-04-15

#### ✅ Feature 06.3: Integration & Docs
- Status: **DONE** · Stories: 2/2 · Completion: 2026-04-15

### Epic 07: Archive-After-Ingest
#### ✅ Feature 07.1: Archive Move Wired Into Materialize
- Status: **DONE** · Stories: 3/3 · Completion: 2026-04-15

#### ✅ Feature 07.2: Slash-Command Contract Updates
- Status: **DONE** · Stories: 2/2 · Completion: 2026-04-15

#### ✅ Feature 07.3: Observability (`source lookup`)
- Status: **DONE** · Stories: 1/1 · Completion: 2026-04-15

### Epic 08: Dual Source Links
#### ✅ Feature 08.1: Dual-Bullet Source Rendering
- Status: **DONE** · Stories: 2/2 · Completion: 2026-04-15

#### ✅ Feature 08.2: Retroactive Rewrite (`sources rewrite`)
- Status: **DONE** · Stories: 1/1 · Completion: 2026-04-15

#### ✅ Feature 08.3: Obsidian Link Ergonomics
- Status: **DONE** · Stories: 1/1 · Completion: 2026-04-15

---

## 📋 Story Status Details

### Ready for Development (no in-scope blockers)
- [ ] 05.3-001 — `/status` slash command — vault health — Epic 05 / 05.3 — **2 pts** — Should Have
- [ ] 05.1-001 — `extract` adapter for YouTube URLs (captions) — Epic 05 / 05.1 — **3 pts** — Should Have
- [ ] 05.2-001 — `ai-research detect-contradictions --page <path>` — Epic 05 / 05.2 — **5 pts** — Should Have
- [ ] 05.3-002 — launchd agent template for background `/ingest-inbox` — Epic 05 / 05.3 — **1 pt** — Could Have
- [ ] NFR-PERF-001 — End-to-end ingest and `/ask` latency budgets — NFR — **2 pts** — Must Have
- [ ] NFR-REL-001 — Atomic, crash-safe state mutations — NFR — **2 pts** — Must Have
- [ ] NFR-PORT-001 — Vault works with zero tooling — NFR — **1 pt** — Must Have
- [ ] NFR-SEC-001 — All state local; no telemetry — NFR — **1 pt** — Must Have
- [ ] NFR-SCR-001 — Every slash command has a headless JSON contract — NFR — **2 pts** — Must Have

### Blocked on In-Scope Dependency
- [ ] 05.2-002 — `/ingest` appends contradiction callouts — Epic 05 / 05.2 — **3 pts** — blocked by `05.2-001`
- [ ] 05.1-002 — Whisper fallback for caption-less videos — Epic 05 / 05.1 — **3 pts** — blocked by `05.1-001`

### In Progress
_None._

### Done This Sprint (2026-04-14 → 2026-04-15)
- [x] Epic 01 — Foundation & Python Toolkit (9 stories) — 2026-04-14
- [x] Epic 02 — Wiki Materialization & Indexing (6 stories) — 2026-04-14
- [x] Epic 03 — Claude Code Slash Commands (6 stories) — 2026-04-14
- [x] Epic 04 — Quality, Obsidian Compat & Docs (5 stories) — 2026-04-14 → 04-15
- [x] Epic 06 — MCP Server for Claude Desktop (8 stories) — 2026-04-15
- [x] Epic 07 — Archive-After-Ingest (6 stories) — 2026-04-15
- [x] Epic 08 — Dual Source Links (4 stories) — 2026-04-15

---

## 🚨 Risks & Blockers

- **HIGH:** None.
- **MEDIUM:** **Story docs drift.** Epic-06 / Epic-07 / Epic-08 footers and multiple DoD checkboxes are stale — they claim work is incomplete while git history shows all stories merged 2026-04-15. Single-source-of-truth protocol (CLAUDE.md §Story Management) is being violated. Risk: next `/build-stories` run miscounts completion.
- **MEDIUM:** **NFR verification gap.** MVP shipped with zero NFR stories acceptance-tested. Performance, reliability, portability, security-locality, and scriptability envelopes are asserted by design but not evidenced by tests.
- **LOW:** `04.1-002` merged with one DoD box unchecked (nightly CI job for `/ask` JSON-contract harness). The test exists; only the nightly schedule is missing.
- **LOW:** `.build-progress.md` has no entries for Epics 06/07/08 — build run happened but progress file wasn't updated (git log is the only audit trail).

---

## 📅 Upcoming Milestones

- **Next build target:** Epic 05 (Phase 2) — 6 stories, 17 pts. Ready to kick off; no blockers.
- **Cleanup pass:** Reconcile DoD checkboxes and epic footers for Epics 06/07/08 against git log. ~15 min.
- **NFR audit:** Schedule after Epic 05 lands. 5 stories · 8 pts · all Must Have.
- **Shippable v1.1:** Epic 05 complete + NFR audit complete → second release after MVP (v1.0 already shipped via Epics 01–04 + 06/07/08).

---

*Update frequency: Weekly or after major status changes*
*For detailed story requirements, see [docs/STORIES.md](docs/STORIES.md)*
*Progress ledger (per-story merge audit): [docs/stories/.build-progress.md](docs/stories/.build-progress.md)*
