# Epic 3: Claude Code Slash Commands

## Epic Overview
**Epic ID**: Epic-03
**Description**: The product surface — four project-scoped slash commands in `.claude/commands/` that compose the Python toolkit into user-visible capabilities: `/ingest`, `/ingest-inbox`, `/ask`, and `/status` (P1 in Epic-05). Every command must work in three modes: interactive, under `/loop`, and headless via `claude -p --output-format json`.
**Business Value**: This is what FX actually uses. The toolkit is invisible; the slash commands are the UX.
**Success Metrics**:
- `claude -p "/ingest ./paper.pdf"` produces a wiki page non-interactively.
- `claude -p "/ask 'q'" --output-format json` emits a parseable `{answer, citations[], confidence}` object.
- `/ingest-inbox` drains `raw/` identically interactive vs headless.

## Epic Scope
**Total Stories**: 6 | **Total Points**: 17 | **MVP Stories**: 6

---

## Features in This Epic

### Feature 03.1: `/ingest` — single-source pipeline

#### Stories

##### Story 03.1-001: Author `.claude/commands/ingest.md`
**User Story**: As FX, I want a `/ingest <path-or-url>` slash command that extracts, drafts a page (summary + key claims + `[[wikilinks]]`), creates needed concept stubs, and materializes the result, so ingest is one user action.
**Priority**: Must Have
**Story Points**: 5

**Acceptance Criteria**:
- **Given** I run `/ingest ./paper.pdf` in Claude Code **When** the command completes **Then** `wiki/<slug>.md` exists and opens in Obsidian.
- **Given** the draft references 3 new concepts **When** materialize runs **Then** 3 stubs exist in `wiki/concepts/`.
- **Given** an unsupported file type **When** `/ingest` runs **Then** it reports the error and does not modify disk.
- **Given** the source already ingested (same hash) **When** `/ingest` runs **Then** it reports "already ingested" and is a no-op.

**Technical Notes**: The slash command is a prose spec telling Claude: (1) call `ai-research extract`, (2) draft the page per template, (3) collect concept names, (4) call `ai-research materialize --stub` per concept, (5) call `ai-research materialize --source ... --from -`. Keep it brief and deterministic — less room for model drift.

**Definition of Done**:
- [ ] `.claude/commands/ingest.md` committed.
- [ ] Interactive smoke test on a real PDF.
- [ ] Headless smoke test: `claude -p "/ingest ./fixtures/paper.pdf"` succeeds.

**Dependencies**: Epic-01, Epic-02
**Risk Level**: Medium — prose drift across Claude versions.

---

##### Story 03.1-002: Page-draft prompt template in `schema.toml`
**User Story**: As FX, I want the page-draft structure (sections, tone, bullet-density rules) encoded in `.ai-research/schema.toml` so I can tune it without editing the slash command.
**Priority**: Must Have
**Story Points**: 2

**Acceptance Criteria**:
- **Given** `schema.toml` defines `[page_template]` with `sections = ["Summary", "Key Claims", "Connections"]` **When** `/ingest` runs **Then** the drafted page uses those headings.
- **Given** an invalid template **When** schema loads **Then** the error is surfaced before any LLM work.

**Technical Notes**: The slash command reads the template and includes it in Claude's drafting context. No LLM call in Python; just data plumbing.

**Definition of Done**:
- [x] Default `schema.toml` committed with sensible sections.
- [x] Template override honored by `/ingest` interactively and headless.

**Dependencies**: 01.1-002
**Risk Level**: Low

---

### Feature 03.2: `/ingest-inbox` — batch drain

#### Stories

##### Story 03.2-001: Author `.claude/commands/ingest-inbox.md`
**User Story**: As FX, I want `/ingest-inbox` to scan `raw/`, call `/ingest` per eligible file, and summarize results, so I can drop sources and walk away.
**Priority**: Must Have
**Story Points**: 3

**Acceptance Criteria**:
- **Given** `raw/` contains 3 PDFs and 1 markdown **When** I run `/ingest-inbox` **Then** all 4 are ingested and `raw/` is empty.
- **Given** one file fails **When** the batch completes **Then** the failure is reported, successful files are still moved, and exit code is non-zero (headless mode).
- **Given** a file with mtime < 5s **When** `/ingest-inbox` runs **Then** it is skipped and flagged for the next tick.
- **Given** batch > 1 file **When** it finishes **Then** `index-rebuild` runs once (not per file).

**Technical Notes**: Command shells out to `ai-research scan raw/ --json` then loops calling the Python verbs directly — NOT re-invoking `/ingest` per file (that would re-enter a slash command, which is expensive). The drafting step for each file still happens in the same Claude Code turn.

**Definition of Done**:
- [ ] `.claude/commands/ingest-inbox.md` committed.
- [ ] Headless smoke: `claude -p "/ingest-inbox"` against a fixture `raw/`.

**Dependencies**: 03.1-001, 01.3-001
**Risk Level**: Medium

---

##### Story 03.2-002: `/loop` compatibility smoke test
**User Story**: As FX, I want to validate that `/loop` driving `/ingest-inbox` at 20-minute intervals drains `raw/` over time, so I can trust the solo workflow.
**Priority**: Must Have
**Story Points**: 1

**Acceptance Criteria**:
- **Given** an open Claude Code session with `/loop 20m /ingest-inbox` **When** I drop files into `raw/` **Then** they appear in `sources/` and `wiki/` within 20 minutes.
- **Given** `raw/` is empty on a tick **When** `/loop` fires **Then** the command reports "nothing to ingest" and does not error.

**Technical Notes**: Mostly documentation and a manual smoke-test checklist in the README.

**Definition of Done**:
- [ ] Checklist added to README.
- [ ] One-pass manual smoke test recorded.

**Dependencies**: 03.2-001
**Risk Level**: Low

---

### Feature 03.3: `/ask` — Q&A

#### Stories

##### Story 03.3-001: Author `.claude/commands/ask.md` (interactive + JSON)
**User Story**: As FX, I want `/ask "<question>"` to read `.ai-research/index.md`, shortlist pages, read them, and answer with `[[page-name]]` citations — with a JSON contract under `claude -p --output-format json` — so Q&A works in any shell.
**Priority**: Must Have
**Story Points**: 5

**Acceptance Criteria**:
- **Given** a populated vault **When** I run `/ask "what does paper X say about Y?"` interactively **Then** Claude reads `index.md`, shortlists 3–8 pages, reads them, and answers with inline `[[page]]` citations.
- **Given** `claude -p "/ask 'q'" --output-format json` **When** it completes **Then** stdout contains valid JSON: `{"answer": string, "citations": string[], "confidence": number}`.
- **Given** low-confidence shortlist **When** `/ask` runs **Then** it invokes `ai-research search "<key-terms>"` as a lexical fallback and re-shortlists.
- **Given** the vault is empty **When** `/ask` runs **Then** the answer field is empty string and confidence is 0.0.

**Technical Notes**: The slash command prose should explicitly pin the JSON schema ("When asked for JSON, return EXACTLY these keys"). This is the most drift-sensitive command — add a harness test.

**Definition of Done**:
- [ ] `.claude/commands/ask.md` committed.
- [ ] JSON contract validated by a test that runs `claude -p` and validates with a Pydantic model.
- [ ] Interactive smoke on fixture vault passes.

**Dependencies**: Epic-02, 01.3-002
**Risk Level**: High — pinning JSON across model updates; confidence calibration is subjective.

---

##### Story 03.3-002: `/ask` citation integrity check
**User Story**: As FX, I want every `[[page-name]]` in an `/ask` answer to resolve to an actual page in `wiki/` so I never chase a hallucinated citation.
**Priority**: Must Have
**Story Points**: 1

**Acceptance Criteria**:
- **Given** an `/ask` answer **When** the harness validates it **Then** every citation resolves via `state.json` or disk.
- **Given** a hallucinated citation **When** the harness checks **Then** the test fails with the offending link.

**Technical Notes**: A small post-processor (in the Python toolkit: `ai-research validate-citations --json <answer.json>`) the slash command or a wrapper can call.

**Definition of Done**:
- [ ] `validate-citations` verb in toolkit.
- [ ] Harness test uses it.

**Dependencies**: 03.3-001
**Risk Level**: Medium

---

## Epic Progress

- [ ] Story 03.1-001 (5 pts)
- [x] Story 03.1-002 (2 pts)
- [ ] Story 03.2-001 (3 pts)
- [ ] Story 03.2-002 (1 pt)
- [ ] Story 03.3-001 (5 pts)
- [ ] Story 03.3-002 (1 pt)

**Completed**: 1 / 6 stories · 2 / 17 pts.
