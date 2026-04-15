# Epic 1: Foundation & Python Toolkit

## Epic Overview
**Epic ID**: Epic-01
**Description**: The deterministic Python package `ai-research` — Typer CLI, state + schema, extract adapters (PDF/URL/markdown), and utility verbs (`search`, `scan`). **Zero LLM calls.** Everything downstream composes these verbs.
**Business Value**: Without the toolkit, slash commands have nothing deterministic to call. This epic is the load-bearing foundation.
**Success Metrics**:
- `uv run ai-research --help` lists all verbs.
- Each `extract` adapter returns `{text, metadata}` for its format.
- `scan wiki/raw/` and `search "<q>"` work against fixture data.

## Epic Scope
**Total Stories**: 9 | **Total Points**: 19 | **MVP Stories**: 9

---

## Features in This Epic

### Feature 01.1: Project Skeleton

#### Stories

##### Story 01.1-001: Initialize uv project and Typer CLI skeleton
**User Story**: As FX, I want a `uv`-managed Python project with a Typer CLI entry point so that I can add verbs incrementally without re-plumbing.
**Priority**: Must Have
**Story Points**: 2

**Acceptance Criteria**:
- **Given** an empty repo **When** I run `uv init && uv add typer` **Then** `pyproject.toml` declares `ai-research` as a package.
- **Given** the package installed via `uv tool install -e .` **When** I run `ai-research --help` **Then** it prints the Typer help.
- **Given** `src/ai_research/cli.py` **When** I run `ai-research version` **Then** it prints a version string from `__version__`.

**Technical Notes**: Src layout. Entry point via `[project.scripts]`. Python 3.12+.

**Definition of Done**:
- [x] `pyproject.toml` committed.
- [x] `ai-research --help` works after `uv tool install -e .`.
- [x] `ruff` + `pyright` configured and clean.

**Dependencies**: None.
**Risk Level**: Low

---

##### Story 01.1-002: Schema.toml loader and state.json read/write
**User Story**: As FX, I want typed access to `.ai-research/schema.toml` and atomic read/write of `state.json` so that all verbs share a single source of truth for config and idempotency state.
**Priority**: Must Have
**Story Points**: 3

**Acceptance Criteria**:
- **Given** a `.ai-research/schema.toml` with page templates **When** `load_schema()` is called **Then** it returns a validated Pydantic model.
- **Given** `state.json` missing **When** a writer runs **Then** it creates a valid empty state atomically (temp + rename).
- **Given** concurrent writers **When** both finish **Then** the file is never half-written (rename is atomic on the same volume).
- **Given** a `source_hash` lookup **When** the hash exists **Then** it returns the page path; else `None`.

**Technical Notes**: `tomllib` (stdlib) + `tomli-w` for write. `state.py` module exports `load_state`, `save_state`, `atomic_write`.

**Definition of Done**:
- [x] Unit tests cover missing file, valid file, corrupt file, concurrent write.
- [x] `atomic_write` tested with a deliberate crash between temp write and rename.

**Dependencies**: 01.1-001
**Risk Level**: Low

---

### Feature 01.2: Extract Adapters

#### Stories

##### Story 01.2-001: PDF extractor via `pdftotext`
**User Story**: As FX, I want `ai-research extract <path.pdf>` to shell out to `pdftotext` and emit `{text, metadata}` JSON so that slash commands can draft wiki pages from PDFs.
**Priority**: Must Have
**Story Points**: 2

**Acceptance Criteria**:
- **Given** a local PDF **When** I run `ai-research extract paper.pdf` **Then** stdout contains `{"text": "...", "metadata": {"pages": N, "source_type": "pdf", "sha256": "..."}}`.
- **Given** a malformed PDF **When** extraction fails **Then** exit code is non-zero and stderr explains.
- **Given** `pdftotext` not on PATH **When** I run extract **Then** the error message tells me to `brew install poppler`.

**Technical Notes**: Run `pdftotext -layout <pdf> -`. Hash is of the raw PDF bytes, not the extracted text.

**Definition of Done**:
- [x] Unit test with a fixture PDF under `tests/fixtures/`.
- [x] Error messaging tested.

**Dependencies**: 01.1-001
**Risk Level**: Low

---

##### Story 01.2-002: URL extractor via `trafilatura`
**User Story**: As FX, I want `ai-research extract <url>` to fetch and extract main-content text so that I can ingest blog posts and arxiv abstract pages.
**Priority**: Must Have
**Story Points**: 3

**Acceptance Criteria**:
- **Given** an HTTP(S) URL **When** I run extract **Then** stdout contains `{text, metadata}` where metadata includes `url`, `title`, `fetched_at`, `source_type: "url"`, `sha256` (of extracted markdown).
- **Given** a URL that fails to fetch **When** extract runs **Then** exit code is non-zero.
- **Given** a URL pointing to a PDF **When** extract runs **Then** it downloads and delegates to the PDF extractor (MIME sniff).

**Technical Notes**: `trafilatura` with `output_format="markdown"`. Archive the fetched HTML to `sources/` alongside the extracted markdown snapshot.

**Definition of Done**:
- [x] Unit test with a recorded HTML fixture (no live HTTP in tests).
- [x] Integration smoke test hits one real URL behind a `--slow` pytest marker.

**Dependencies**: 01.1-001, 01.2-001 (for PDF fallback)
**Risk Level**: Medium — trafilatura edge cases.

---

##### Story 01.2-003: Markdown passthrough extractor
**User Story**: As FX, I want `ai-research extract <file.md>` to pass the file through with computed metadata so that local notes can be ingested without transformation.
**Priority**: Must Have
**Story Points**: 1

**Acceptance Criteria**:
- **Given** a `.md` or `.txt` file **When** I run extract **Then** stdout is `{text: <file contents>, metadata: {source_type: "markdown", sha256, path}}`.
- **Given** existing YAML frontmatter **When** extract runs **Then** it is preserved in `text` and parsed into `metadata.frontmatter`.

**Technical Notes**: `python-frontmatter` or hand-rolled splitter.

**Definition of Done**:
- [x] Unit tests for with/without frontmatter.

**Dependencies**: 01.1-001
**Risk Level**: Low

---

##### Story 01.2-004: Unified `extract` dispatcher
**User Story**: As FX, I want a single `ai-research extract <path-or-url>` command that picks the right adapter by file extension or URL scheme so that slash commands don't need to branch.
**Priority**: Must Have
**Story Points**: 2

**Acceptance Criteria**:
- **Given** `.pdf` extension **When** extract runs **Then** it dispatches to the PDF adapter.
- **Given** `http://` or `https://` **When** extract runs **Then** it dispatches to the URL adapter.
- **Given** `.md`/`.txt` **When** extract runs **Then** it dispatches to markdown.
- **Given** an unknown extension **When** extract runs **Then** exit code 2 with a helpful message listing supported types.

**Technical Notes**: Registry pattern in `extract/__init__.py`.

**Definition of Done**:
- [x] Dispatch table unit-tested.

**Dependencies**: 01.2-001, 01.2-002, 01.2-003
**Risk Level**: Low

---

### Feature 01.3: Utility Verbs

#### Stories

##### Story 01.3-001: `scan wiki/raw/` lists files eligible for ingest
**User Story**: As FX, I want `ai-research scan wiki/raw/` to list files that need ingestion (skipping too-fresh partial writes) so that `/ingest-inbox` can iterate safely.
**Priority**: Must Have
**Story Points**: 2

**Acceptance Criteria**:
- **Given** files in `wiki/raw/` older than 5 seconds **When** I run `scan` **Then** their paths print one per line (or JSON with `--json`).
- **Given** a file with mtime < 5s **When** I run `scan` **Then** it is excluded.
- **Given** a file whose `sha256` already exists in `state.json` **When** I run `scan --skip-known` **Then** it is excluded.

**Technical Notes**: Configurable `--min-age-seconds` (default 5).

**Definition of Done**:
- [x] Unit tests with mocked mtimes.

**Dependencies**: 01.1-002
**Risk Level**: Low

---

##### Story 01.3-002: `search "<query>"` — ripgrep wrapper over `wiki/`
**User Story**: As FX, I want `ai-research search "<query>"` to run `rg` against `wiki/` and emit structured hits so that `/ask` has a deterministic lexical pre-filter.
**Priority**: Must Have
**Story Points**: 2

**Acceptance Criteria**:
- **Given** a query **When** I run `search "foo"` **Then** stdout is JSON list of `{page, line, snippet}`.
- **Given** `rg` not on PATH **When** search runs **Then** clear error message.
- **Given** `--limit N` **When** search runs **Then** at most N hits are returned.

**Technical Notes**: Shell out to `rg --json`; parse and re-emit a stable schema.

**Definition of Done**:
- [x] Unit test with a fixture `wiki/`.

**Dependencies**: 01.1-001
**Risk Level**: Low

---

##### Story 01.3-003: Source archival helper
**User Story**: As FX, I want a `ai-research archive-source <path>` helper that computes the archive path (`sources/<yyyy>/<mm>/<hash>-<slug>.<ext>`), creates parent dirs, and moves the file atomically, so that `materialize` and other verbs share one archival implementation.
**Priority**: Must Have
**Story Points**: 2

**Acceptance Criteria**:
- **Given** a source file **When** archive runs **Then** the file is moved (not copied) to the computed path.
- **Given** the target path already exists with identical hash **When** archive runs **Then** it deletes the source and returns the existing path (idempotent).
- **Given** the target exists with a different hash **When** archive runs **Then** exit code non-zero — hash collision requires manual review.

**Technical Notes**: `shutil.move` within the same filesystem; slug generation from metadata.title (fall back to filename).

**Definition of Done**:
- [x] Unit tests for fresh, duplicate, collision cases.

**Dependencies**: 01.1-002
**Risk Level**: Low

---

## Epic Progress

- [x] Story 01.1-001 (2 pts)
- [x] Story 01.1-002 (3 pts)
- [x] Story 01.2-001 (2 pts)
- [x] Story 01.2-002 (3 pts)
- [x] Story 01.2-003 (1 pt)
- [x] Story 01.2-004 (2 pts)
- [x] Story 01.3-001 (2 pts)
- [x] Story 01.3-002 (2 pts)
- [x] Story 01.3-003 (2 pts)

**Completed**: 9 / 9 stories · 19 / 19 pts.
