# Epic 2: Wiki Materialization & Indexing

## Epic Overview
**Epic ID**: Epic-02
**Description**: Atomic wiki-page writes with YAML frontmatter, idempotency by `source_hash`, concept-stub creation, and the `index.md` retrieval surface that `/ask` depends on. All LLM-drafted content arrives via stdin/file — this epic is pure file I/O.
**Business Value**: Turns Claude Code's drafts into a durable, Obsidian-compatible vault. Without idempotency and atomic writes the vault corrupts on re-ingest.
**Success Metrics**:
- Re-running `materialize` with an unchanged `source_hash` is a no-op.
- `.ai-research/index.md` regenerates deterministically from `wiki/`.
- All writes are crash-safe (temp + rename).

## Epic Scope
**Total Stories**: 6 | **Total Points**: 16 | **MVP Stories**: 6

---

## Features in This Epic

### Feature 02.1: Atomic Page Writes

#### Stories

##### Story 02.1-001: `materialize` writes a wiki page with frontmatter
**User Story**: As FX, I want `ai-research materialize --source <path> --from <draft.md>` to write `wiki/<slug>.md` with standard frontmatter and atomic rename, so Claude Code drafts land durably.
**Priority**: Must Have
**Story Points**: 3

**Acceptance Criteria**:
- **Given** a draft file and source path **When** materialize runs **Then** `wiki/<slug>.md` exists with frontmatter (`title`, `source`, `ingested_at`, `source_hash`, `locked: false`) and the draft body.
- **Given** a crash mid-write **When** I inspect `wiki/` **Then** there is no half-written file (temp + rename).
- **Given** `--stdin` **When** materialize reads draft from stdin **Then** behavior is identical to `--from`.
- **Given** materialize succeeds **When** I inspect `state.json` **Then** `source_hash → page_path` mapping is present.

**Technical Notes**: Slug from frontmatter `title` or filename. Frontmatter via `python-frontmatter` or hand-rolled YAML emitter.

**Definition of Done**:
- [x] Unit tests cover frontmatter shape, atomic write, state update.
- [x] Crash-mid-write test (kill between temp write and rename).

**Dependencies**: 01.1-002, 01.3-003
**Risk Level**: Medium — crash-safety is easy to get wrong.

---

##### Story 02.1-002: Idempotent re-ingest via `source_hash`
**User Story**: As FX, I want `materialize` to skip writes when `source_hash` is unchanged and update (preserving `locked: true`) when it differs, so re-ingesting is safe and manual edits are protected.
**Priority**: Must Have
**Story Points**: 3

**Acceptance Criteria**:
- **Given** an existing page with a matching `source_hash` **When** I materialize the same source **Then** the file's mtime is unchanged and exit code is 0.
- **Given** an existing page with `locked: true` **When** I materialize **Then** the file is not overwritten and a warning is printed (exit 0).
- **Given** a different `source_hash` for the same source **When** I materialize **Then** the page body is updated, `ingested_at` refreshed, frontmatter `source_hash` updated.
- **Given** `--force` **When** materialize runs **Then** `locked: true` is bypassed.

**Technical Notes**: Lookup via `state.get_page_for_hash(hash)` first, then frontmatter check.

**Definition of Done**:
- [ ] Unit tests for skip / lock-respect / update / force paths.

**Dependencies**: 02.1-001
**Risk Level**: Low

---

##### Story 02.1-003: Concept-stub creation
**User Story**: As FX, I want `materialize --stub <concept-name>` to create `wiki/concepts/<slug>.md` for unseen concepts (idempotent — no-op if exists), so cross-linking never leaves broken wikilinks.
**Priority**: Must Have
**Story Points**: 2

**Acceptance Criteria**:
- **Given** a concept name with no existing stub **When** stub runs **Then** `wiki/concepts/<slug>.md` is created with frontmatter `stub: true` and a one-line placeholder body.
- **Given** a stub or full page already exists with that slug **When** stub runs **Then** it is a no-op (exit 0).
- **Given** stub creation **When** I inspect the file **Then** Obsidian wikilinks pointing to `[[<concept-name>]]` resolve.

**Technical Notes**: `--stub` accepts repeated flags for batch creation.

**Definition of Done**:
- [ ] Unit tests for new/existing/batch.

**Dependencies**: 02.1-001
**Risk Level**: Low

---

### Feature 02.2: Retrieval Index

#### Stories

##### Story 02.2-001: `index-rebuild` regenerates `.ai-research/index.md`
**User Story**: As FX, I want `ai-research index-rebuild` to scan `wiki/` and produce `.ai-research/index.md` (one line per page), so `/ask` has a deterministic retrieval surface.
**Priority**: Must Have
**Story Points**: 3

**Acceptance Criteria**:
- **Given** a populated `wiki/` **When** I run `index-rebuild` **Then** `.ai-research/index.md` exists with one line per page.
- **Given** a line **When** I inspect it **Then** it contains: page title (from frontmatter or H1), tags (frontmatter), H1 section names verbatim, outbound-link count, 1-line summary (frontmatter `summary` if present, else blank).
- **Given** two consecutive rebuilds with no vault changes **When** I diff the output **Then** they are byte-identical.
- **Given** a broken page (bad frontmatter) **When** index-rebuild runs **Then** the page is listed with an `[INVALID]` marker and exit code is 0 (non-fatal).

**Technical Notes**: One line ≈ 200 chars target. Include H1s verbatim (not LLM summary) — risk mitigation from REQUIREMENTS §8.

**Definition of Done**:
- [x] Unit tests with fixture vault.
- [x] Determinism test (run twice, diff).

**Dependencies**: 02.1-001
**Risk Level**: Low

---

##### Story 02.2-002: `materialize` auto-triggers `index-rebuild`
**User Story**: As FX, I want every successful `materialize` to rebuild `index.md` automatically so the retrieval surface is always fresh.
**Priority**: Must Have
**Story Points**: 2

**Acceptance Criteria**:
- **Given** a successful `materialize` **When** it returns **Then** `.ai-research/index.md` reflects the new/updated page.
- **Given** `--skip-index` **When** materialize runs **Then** the index is not rebuilt (for batch performance).
- **Given** a batch `--skip-index` run **When** it finishes **Then** the caller is responsible for a single trailing `index-rebuild`.

**Technical Notes**: For batches > 10 pages, invoke `index-rebuild` once at the end. Slash commands handle this.

**Definition of Done**:
- [ ] Unit test verifies the trigger; test verifies `--skip-index`.

**Dependencies**: 02.1-001, 02.2-001
**Risk Level**: Low

---

##### Story 02.2-003: Page `## Sources` back-reference
**User Story**: As FX, I want every wiki page to end with a `## Sources` section linking to the archived source file, so I can always trace a claim back to its origin.
**Priority**: Must Have
**Story Points**: 3

**Acceptance Criteria**:
- **Given** `materialize` runs with a source **When** the page is written **Then** the body ends with `## Sources\n- [<title>](<sources/relative/path>)`.
- **Given** an update (new hash) **When** the page is re-materialized **Then** the new source is appended (not replaced) to `## Sources` if the path differs.
- **Given** a URL source **When** the page is written **Then** the `## Sources` entry includes both the archived HTML/markdown snapshot path AND the original URL.

**Technical Notes**: Detect an existing `## Sources` section in the draft; merge rather than duplicate.

**Definition of Done**:
- [x] Unit tests for fresh, update-same-source, update-different-source.

**Dependencies**: 02.1-001
**Risk Level**: Medium — merge logic is the easiest place to introduce bugs.

---

## Epic Progress

- [x] Story 02.1-001 (3 pts)
- [ ] Story 02.1-002 (3 pts)
- [x] Story 02.1-003 (2 pts)
- [x] Story 02.2-001 (3 pts)
- [ ] Story 02.2-002 (2 pts)
- [x] Story 02.2-003 (3 pts)

**Completed**: 4 / 6 stories · 11 / 16 pts.
