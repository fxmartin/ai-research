# Epic 8: Dual Source Links (URL + Local Archive)

## Epic Overview
**Epic ID**: Epic-08
**Description**: Every wiki page's `## Sources` section should render both the origin URL and the local archive path on disk, so readers can reach the authoritative public copy *and* the bytes the page was drafted against. Applies to all source types — PDF, markdown, URL snapshot — and extends to a one-shot retroactive rewrite pass that backfills existing pages once Epic-07's `archive_path` ledger is populated.
**Business Value**: Today `## Sources` carries only a URL (web sources) or a filename (PDFs). That makes verification unreliable: URLs rot, and the filename alone doesn't resolve to bytes anyone can inspect. Linking to the immutable `sources/<yyyy>/<mm>/<hash>-<slug>.ext` gives FX — and any future Obsidian reader — a clickable path to the exact file used, while keeping the URL for public reference. It also closes the loop on the "read page → inspect original" workflow that `ai-research source lookup` (Epic-07.3) partially addresses.
**Success Metrics**:
- 100% of newly materialized pages emit both `- URL:` and `- Archive:` bullets where both exist; Archive-only when no URL.
- The retroactive rewrite pass updates all pages whose `source_hash` has an `archive_path` in `state.json`, leaving pre-archive pages untouched.
- Obsidian renders the archive bullet as a working relative link (clicking opens the PDF / md file in-vault).

## Epic Scope
**Total Stories**: 4 | **Total Points**: 11 | **MVP Stories**: 3

---

## Features in This Epic

### Feature 08.1: Dual-bullet source rendering on write

#### Stories

##### Story 08.1-001: Extend SourceEntry / merge_sources_section to emit URL + Archive bullets
**User Story**: As FX, I want new pages to render two lines per source — one for the origin URL, one for the local archive path — so I can verify claims against the immutable bytes on disk.
**Priority**: Must Have
**Story Points**: 5

**Acceptance Criteria**:
- **Given** a source with both URL and archive path **When** `materialize` writes the page **Then** `## Sources` contains:
  ```
  - URL: https://example.com/foo
  - Archive: [sources/2026/04/abcdef-foo.pdf](sources/2026/04/abcdef-foo.pdf)
  ```
- **Given** a PDF source with no URL **When** `materialize` writes **Then** only the `- Archive:` bullet is emitted (no empty `URL:` line).
- **Given** a page re-materialized from a second source **When** `merge_sources_section` runs **Then** both sources are preserved, each with its own URL/Archive pair.
- **Given** a source whose `archive_path` is null (pre-Epic-07 ledger entry) **When** rendering **Then** only the `- URL:` bullet is emitted, with a comment or fallback — existing behavior preserved.
- **Given** the archive path is a relative POSIX path **When** rendered inside `wiki/<slug>.md` **Then** the link resolves from the vault root (Obsidian convention).

**Technical Notes**: Update `src/ai_research/wiki/sources.py` — `SourceEntry` already has `title`, `path`, `url`; add `archive_path: str | None`. Update `_format_entry` and `_parse_entry` symmetrically. Merge logic must treat a tuple of (URL, Archive) as one entry identified by the source_hash, not two. Obsidian prefers Markdown-flavor links `[text](path)` for non-wikilink file references — keep wikilinks reserved for concepts.

**Definition of Done**:
- [x] `SourceEntry` extended; `merge_sources_section` emits both bullets.
- [x] Unit tests: URL+archive, archive-only, URL-only (legacy), re-materialize with additional source.
- [x] Golden-file test: fixture page with two sources renders both pairs.

**Dependencies**: Epic-07.1-001 (`archive_path` in state.json), Epic-07.1-002 (materialize populates it).
**Risk Level**: Medium (source-section parsing is load-bearing; existing idempotency tests must stay green)

---

##### Story 08.1-002: Plumb archive_path from materialize through to SourceEntry
**User Story**: As FX, I want `materialize` to pass the archive path it just produced into the sources rendering so the two stay in sync in a single write.
**Priority**: Must Have
**Story Points**: 2

**Acceptance Criteria**:
- **Given** `archive_source` returns `sources/2026/04/abc-foo.pdf` **When** `materialize` builds `SourceEntry` **Then** `archive_path` is set on the entry before `merge_sources_section` runs.
- **Given** `materialize --no-archive` is used **When** the entry is built **Then** `archive_path` is `None` (only the URL bullet is rendered).

**Technical Notes**: Small wiring change in `src/ai_research/wiki/materialize.py` between `archive_source(...)` and `merge_sources_section(...)`. Order must be: archive → build entry → merge → atomic_write.

**Definition of Done**:
- [x] Wiring in place; integration test covers end-to-end.
- [x] `--no-archive` path still renders URL bullet only.

**Dependencies**: 08.1-001, Epic-07.1-002.
**Risk Level**: Low

---

### Feature 08.2: Retroactive rewrite of existing pages

#### Stories

##### Story 08.2-001: Add `ai-research sources rewrite` verb
**User Story**: As FX, I want a one-shot command that walks every page in `wiki/` and backfills `Archive:` bullets for sources whose `archive_path` is known in `state.json`, so my existing vault catches up to the new format without me hand-editing pages.
**Priority**: Must Have
**Story Points**: 3

**Acceptance Criteria**:
- **Given** a page whose sources all already have URL+Archive bullets **When** the verb runs **Then** it is a no-op (byte-identical).
- **Given** a page with URL-only bullets and a matching `archive_path` in state **When** the verb runs **Then** the page is rewritten to include the `Archive:` bullet and reports `UPDATED`.
- **Given** a page with a source whose hash has no `archive_path` in state **When** the verb runs **Then** that bullet is left as URL-only (nothing to backfill).
- **Given** `--dry-run` **When** the verb runs **Then** it prints the set of files that *would* change without writing.
- **Given** a page is locked (`locked: true` in frontmatter) **When** the verb runs **Then** the page is skipped and listed separately; `--force` bypasses the lock.

**Technical Notes**: Reuse `merge_sources_section` logic for the rewrite, keyed on `source_hash`. The rewrite touches only the `## Sources` section — no other bytes should change. Atomic write per page (temp + rename). Rebuild the index once at the end if any pages were updated.

**Definition of Done**:
- [x] Verb added, `--dry-run` + `--force` supported.
- [x] Golden-file test: vault with mixed legacy/new pages rewrites only the legacy-with-archive ones.
- [x] README + `.claude/commands/` prose updated.

**Dependencies**: 08.1-001, Epic-07.1-001 (state schema).
**Risk Level**: Medium (touches every page — byte-diff discipline is the entire job)

---

### Feature 08.3: Obsidian link ergonomics

#### Stories

##### Story 08.3-001: Render Archive link with human-readable label
**User Story**: As FX, when I click the Archive bullet in Obsidian I want it labeled by filename (not the full path) so the page stays readable.
**Priority**: Should Have
**Story Points**: 1

**Acceptance Criteria**:
- **Given** an archive path `sources/2026/04/abcdef123456-machines-of-loving-grace.md` **When** rendered **Then** the bullet reads `- Archive: [machines-of-loving-grace.md](sources/2026/04/abcdef123456-machines-of-loving-grace.md)`.
- **Given** a PDF at `sources/2026/02/deadbeef-opus-card.pdf` **When** rendered **Then** the label is the file basename including extension.

**Technical Notes**: Tiny formatting helper in `sources.py`. The hash prefix stays in the path but not in the visible label.

**Definition of Done**:
- [x] Helper + test.
- [ ] Obsidian manual smoke: click opens the correct file.

**Dependencies**: 08.1-001.
**Risk Level**: Low

---

## Out of Scope

- **Backlinks from source to page** — a `sources/<file>` page doesn't appear in the vault; it's raw bytes only. No reverse index.
- **External-URL archival** (wayback-style snapshots) — outside the scope of this epic.
- **Re-hashing / re-archiving existing URLs already materialized before Epic-07** — the rewrite verb only backfills what's already in the ledger; a separate migration epic can handle historical re-archive.

## Epic Progress

- [x] Story 08.1-001 (5 pts)
- [x] Story 08.1-002 (2 pts)
- [x] Story 08.2-001 (3 pts)
- [x] Story 08.3-001 (1 pt)

**Completed**: 4 / 4 stories · 11 / 11 pts.
