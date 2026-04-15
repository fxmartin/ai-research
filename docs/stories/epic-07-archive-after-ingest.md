# Epic 7: Archive-After-Ingest

## Epic Overview
**Epic ID**: Epic-07
**Description**: Wire the existing `archive_source` helper into the ingest pipeline so that successfully materialized raw-inbox files move to the immutable `sources/<yyyy>/<mm>/<hash>-<slug>.<ext>` archive instead of persisting in `wiki/raw/` forever. Extend `state.json` to record the archive path alongside the page path, migrate existing records on load, and update `/ingest-inbox` and `/ingest` contracts so "inbox drained" means what it says.
**Business Value**: Today `wiki/raw/` grows unbounded — every ingested Obsidian Web Clipper drop stays in the inbox, relying on `scan --skip-known` for dedup. The intended storage layout (per `CLAUDE.md`) is an immutable `sources/` archive; without it the vault leaks user intent, the inbox loses its "to-do" semantics, and long-running watcher loops (launchd / `/loop`) produce noisier diffs than needed.
**Success Metrics**:
- After `/ingest-inbox` on a clean inbox, `wiki/raw/` contains only `.gitkeep` and files deliberately skipped (fresh < 5s).
- `sources/` contains one file per ingested source, keyed `<yyyy>/<mm>/<hash12>-<slug>.<ext>`.
- `state.json` records `{page, archive_path}` for each `source_hash`; `/ask` retrieval can resolve back to the original bytes.
- Zero new failures on the existing golden-vault test suite.

## Epic Scope
**Total Stories**: 6 | **Total Points**: 15 | **MVP Stories**: 5

---

## Features in This Epic

### Feature 07.1: Archive move wired into materialize

#### Stories

##### Story 07.1-001: Extend state.json schema to record archive_path
**User Story**: As FX, I want `state.sources[hash]` to hold both the page path and the archive path so that downstream tools (`/ask`, future `source lookup`) can resolve a wiki page back to the original bytes.
**Priority**: Must Have
**Story Points**: 3

**Acceptance Criteria**:
- **Given** a new ingest **When** `materialize` succeeds **Then** `state.sources[hash]` is `{"page": "wiki/foo.md", "archive_path": "sources/2026/04/abcdef123456-foo.md"}`.
- **Given** an old-format state (`state.sources[hash]` is a string) **When** `load_state` runs **Then** entries are migrated in-memory to the new dict shape with `archive_path: null` and a single `save_state` on next write persists the migration.
- **Given** the migrated state **When** `scan --skip-known` runs **Then** known-hash detection still works (no regression).

**Technical Notes**: Extend the `State` dataclass/model in `src/ai_research/state.py`. Keep the JSON schema backwards-readable for one release (warn on migration). Update `tests/test_state.py` with old-format → new-format migration fixtures.

**Definition of Done**:
- [ ] Old-format state files load without manual intervention.
- [ ] New ingests write the new shape.
- [ ] `scan --skip-known` regression tests green.

**Dependencies**: None.
**Risk Level**: Medium (format change — migration must be boringly correct)

---

##### Story 07.1-002: Call archive_source from materialize on successful write
**User Story**: As FX, I want `materialize` to move the source file into `sources/` right after the page write + state update so that `wiki/raw/` drains naturally and `sources/` becomes the single source of truth for raw bytes.
**Priority**: Must Have
**Story Points**: 5

**Acceptance Criteria**:
- **Given** a source at `wiki/raw/foo.md` **When** `materialize --source wiki/raw/foo.md ...` succeeds (CREATED or UPDATED) **Then** the file is moved to `sources/<yyyy>/<mm>/<hash12>-foo.md` and no longer present at the original path.
- **Given** `materialize` returns SKIPPED (unchanged source_hash) **When** the source is still in `wiki/raw/` **Then** it is still moved (idempotent archive — see archive_source's hash-keyed collision handling).
- **Given** `materialize` returns LOCKED or raises **When** the page write did not succeed **Then** the source stays in `wiki/raw/` for retry.
- **Given** a source already outside `wiki/raw/` (e.g. `/tmp/foo.md`) **When** `materialize` runs **Then** it is still archived to `sources/`.
- **Given** `archive_source` raises `ArchiveHashCollisionError` **When** materialize is mid-call **Then** the page write is preserved, the error bubbles up as a non-zero exit, and `state.json` is rolled back to not reference an absent archive.

**Technical Notes**: Call order: `atomic_write(page)` → `retire_stub_if_exists` → `archive_source` → `save_state` (with `archive_path` set). Rollback path on archive failure: re-load state before the save, so the partial page is still recorded but the hash→archive mapping is deferred; alternatively, wrap in a try/except that surfaces the collision to the operator. Add the `--no-archive` escape hatch for power users who pre-archived.

**Definition of Done**:
- [x] Unit tests: archive move happens on CREATED, UPDATED, and SKIPPED; not on LOCKED or error.
- [x] Golden-file test: `wiki/raw/` is empty after a materialize run; `sources/` contains exactly the archived file.
- [x] `materialize --no-archive` bypass works and documented.

**Dependencies**: 07.1-001.
**Risk Level**: Medium

---

##### Story 07.1-003: Propagate --no-archive through CLI and slash commands
**User Story**: As FX, I want an explicit opt-out so I can re-materialize a page from an already-archived source without triggering a failed second move.
**Priority**: Should Have
**Story Points**: 2

**Acceptance Criteria**:
- **Given** `ai-research materialize --source sources/2026/04/abcdef-foo.md --no-archive ...` **When** the call runs **Then** no archive move is attempted and materialize succeeds normally.
- **Given** a source already in `sources/` **When** `materialize` runs without `--no-archive` **Then** `archive_source` detects the already-archived shape (same target path, same hash) and no-ops silently.

**Technical Notes**: The `archive_source` helper already handles identical-hash idempotency; this story just surfaces the flag and documents when to use it.

**Definition of Done**:
- [ ] Flag documented in `--help` and in `.claude/commands/ingest.md`.
- [ ] Test: re-running `materialize` against an already-archived source is a no-op.

**Dependencies**: 07.1-002.
**Risk Level**: Low

---

### Feature 07.2: Slash-command contract updates

#### Stories

##### Story 07.2-001: Update /ingest-inbox contract wording + summary
**User Story**: As FX, I want `/ingest-inbox` to truthfully report "inbox drained" — the raw file must be gone from `wiki/raw/` on success, not just hash-recorded.
**Priority**: Must Have
**Story Points**: 2

**Acceptance Criteria**:
- **Given** one eligible source in `wiki/raw/` **When** `/ingest-inbox` runs to completion **Then** the summary block includes `archived: sources/<yyyy>/<mm>/<hash>-<slug>.<ext>` and `wiki/raw/` no longer contains the file.
- **Given** a file that failed extract or materialize **When** the batch ends **Then** the file is still in `wiki/raw/` and listed in `failures:` — it was never archived.
- **Given** the existing contract "After a successful pass `wiki/raw/` is empty" **When** the new behavior ships **Then** the contract is enforced (not aspirational).

**Technical Notes**: Update `.claude/commands/ingest-inbox.md` prose: drop the "raw file remains in place" caveat introduced earlier; add the `archived:` line to the summary.

**Definition of Done**:
- [ ] Contract prose updated.
- [ ] Headless JSON summary includes `archived` entries (once the summary gains structure).
- [ ] Manual end-to-end: drop a test file in `wiki/raw/`, run `/ingest-inbox`, verify it lands in `sources/`.

**Dependencies**: 07.1-002.
**Risk Level**: Low

---

##### Story 07.2-002: Update /ingest contract and .claude/commands/ingest.md
**User Story**: As FX, I want single-source `/ingest <path>` to behave the same as the batch driver re: archiving so the two paths don't diverge.
**Priority**: Must Have
**Story Points**: 1

**Acceptance Criteria**:
- **Given** `/ingest <raw-path>` **When** it completes successfully **Then** the source is archived to `sources/`.
- **Given** `/ingest <already-archived-path>` **When** it runs **Then** no duplicate archive is created.

**Technical Notes**: Prose-only change in `.claude/commands/ingest.md`.

**Definition of Done**:
- [ ] Contract updated.
- [ ] Examples refreshed.

**Dependencies**: 07.1-002.
**Risk Level**: Low

---

### Feature 07.3: Observability

#### Stories

##### Story 07.3-001: Add `ai-research source lookup <page-slug>` verb
**User Story**: As FX, when I'm reading a wiki page and want the original PDF/markdown bytes, I want `ai-research source lookup <slug>` to return the archive path.
**Priority**: Could Have
**Story Points**: 2

**Acceptance Criteria**:
- **Given** a slug with a materialized page **When** I run `ai-research source lookup <slug>` **Then** it prints the archive_path from `state.json`.
- **Given** a slug that exists only as a stub **When** I run the command **Then** it exits non-zero with a helpful message.
- **Given** a page whose source predates archiving (archive_path: null post-migration) **When** I run the command **Then** it reports "source not archived (pre-migration ingest)".

**Technical Notes**: Reverse lookup against `state.pages` / `state.sources`. Add `--json` output mode for programmatic callers.

**Definition of Done**:
- [x] Verb added, tested, documented.
- [x] `--json` mode validated.

**Dependencies**: 07.1-001.
**Risk Level**: Low

---

## Out of Scope

- **Re-archive CLI** (a one-off script to populate `archive_path` for historical entries by re-hashing files in `wiki/raw/`) — manual one-time migration acceptable for a single-user tool.
- **Archive pruning / retention policies** — `sources/` is intentionally append-only.
- **Remote archive backends** (S3, etc.) — local filesystem only in this epic.

## Completed: 0 / 6
