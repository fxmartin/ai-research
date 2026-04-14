# Epic 4: Quality, Obsidian Compat & Docs

## Epic Overview
**Epic ID**: Epic-04
**Description**: Tests that keep the deterministic half honest, an Obsidian-compatibility lint that catches vault corruption before it compounds, a README that lets FX (and future readers) install and run, and a minimal CI.
**Business Value**: MVP is only shippable if the vault opens in Obsidian cleanly and the toolkit's idempotency holds under repeated ingest.
**Success Metrics**:
- Golden-file tests cover materialize + index-rebuild.
- Obsidian smoke passes on a populated fixture vault.
- `README.md` is copy-pasteable for a clean-machine install.

## Epic Scope
**Total Stories**: 5 | **Total Points**: 11 | **MVP Stories**: 5

---

## Features in This Epic

### Feature 04.1: Testing

#### Stories

##### Story 04.1-001: pytest baseline + golden-file harness
**User Story**: As FX, I want a pytest setup with a golden-file harness that verifies byte-identical output for deterministic verbs so regressions are caught on every commit.
**Priority**: Must Have
**Story Points**: 3

**Acceptance Criteria**:
- **Given** a fixture input and a committed golden output **When** pytest runs **Then** the test diffs them and fails on mismatch.
- **Given** `--update-golden` pytest option **When** running **Then** goldens regenerate for deliberate refreshes.
- **Given** a timestamp field in the output **When** the test runs **Then** it is normalized before comparison.

**Technical Notes**: Use `syrupy` or a tiny custom helper. Fixtures under `tests/fixtures/`.

**Definition of Done**:
- [x] `pytest` passes locally.
- [x] Golden harness documented in `CONTRIBUTING.md` or README.

**Dependencies**: 01.1-001
**Risk Level**: Low

---

##### Story 04.1-002: `/ask` JSON-contract harness test
**User Story**: As FX, I want a test that runs `claude -p "/ask 'fixture-question'" --output-format json` against a fixture vault and validates the JSON with a Pydantic model so slash-command drift fails CI.
**Priority**: Must Have
**Story Points**: 3

**Acceptance Criteria**:
- **Given** a fixture vault under `tests/fixtures/vault/` **When** the test runs **Then** it shells out to `claude -p`, captures stdout, and validates against `AskResponse` (`{answer, citations[], confidence}`).
- **Given** citations in the response **When** the test runs **Then** every citation is validated via `ai-research validate-citations`.
- **Given** `CLAUDE_CODE_AVAILABLE=false` env (CI without `claude` CLI) **When** the test runs **Then** it is `pytest.skip`'d cleanly.

**Technical Notes**: Marked `@pytest.mark.slow` — only runs in pre-commit smoke or nightly. Pins a Claude model via slash-command frontmatter when possible.

**Definition of Done**:
- [ ] Harness test file committed.
- [ ] CI workflow invokes it under a `nightly` job.

**Dependencies**: 03.3-001, 03.3-002, 04.1-001
**Risk Level**: High — subject to model drift; will need periodic re-baselining.

---

### Feature 04.2: Obsidian Compatibility

#### Stories

##### Story 04.2-001: `ai-research vault-lint` — Obsidian smoke test
**User Story**: As FX, I want `ai-research vault-lint` to verify that every wikilink in `wiki/` resolves (or points to a stub), all frontmatter parses, and Obsidian's graph view will render cleanly, so I catch vault corruption before it accumulates.
**Priority**: Must Have
**Story Points**: 3

**Acceptance Criteria**:
- **Given** a vault with a broken `[[foo]]` **When** lint runs **Then** exit code is non-zero and the broken link is reported with line number.
- **Given** a page with invalid frontmatter YAML **When** lint runs **Then** it is reported.
- **Given** a stub page **When** lint runs **Then** it is counted separately (not treated as broken).
- **Given** a clean vault **When** lint runs **Then** exit 0 and stdout prints `{pages, stubs, wikilinks, orphans}` JSON.

**Technical Notes**: Parse frontmatter + regex for `[[...]]` wikilinks. Resolve against `state.json` and `wiki/**/*.md`. Aliases (`[[target|display]]`) supported.

**Definition of Done**:
- [x] Unit tests for each failure mode.
- [x] Invoked in CI.

**Dependencies**: 02.1-001, 02.1-003, 02.2-001
**Risk Level**: Medium — wikilink syntax has edge cases (aliases, section anchors).

---

### Feature 04.3: CI & Docs

#### Stories

##### Story 04.3-001: GitHub Actions CI (lint + types + tests)
**User Story**: As FX, I want a GitHub Actions workflow that runs `ruff`, `pyright`, and `pytest` on push and PR so broken commits never merge.
**Priority**: Must Have
**Story Points**: 1

**Acceptance Criteria**:
- **Given** a PR **When** CI runs **Then** `ruff check`, `pyright`, and `pytest -m "not slow"` all pass.
- **Given** `main` pushed **When** CI runs **Then** it also runs `ai-research vault-lint tests/fixtures/vault/`.
- **Given** a nightly schedule **When** CI runs **Then** it executes the slow tests (including 04.1-002).

**Technical Notes**: `uv` in CI via `astral-sh/setup-uv`. Matrix: Python 3.12 only in v1.

**Definition of Done**:
- [ ] `.github/workflows/ci.yml` committed.
- [ ] Status badge in README.

**Dependencies**: 04.1-001, 04.2-001
**Risk Level**: Low

---

##### Story 04.3-002: README documents install + all slash commands and verbs
**User Story**: As FX (and future-me), I want a README that covers install, three invocation modes (interactive, `/loop`, headless), and every slash command + toolkit verb with one concrete example each, so I never have to re-derive usage.
**Priority**: Must Have
**Story Points**: 1

**Acceptance Criteria**:
- **Given** a clean machine with `uv`, `poppler`, and `claude` CLI installed **When** I follow the README **Then** I can ingest a PDF and `/ask` about it in < 10 minutes.
- **Given** the README **When** I search for `/ingest-inbox` **Then** I find: interactive example, `/loop` example, headless `claude -p` example.
- **Given** every toolkit verb **When** I look it up in the README **Then** there is a one-line description and at least one example.
- **Given** a troubleshooting section **When** I hit "pdftotext not found" **Then** the fix is documented.

**Definition of Done**:
- [ ] `README.md` committed.
- [ ] Links to REQUIREMENTS.md, STORIES.md, and the Karpathy gist.

**Dependencies**: All MVP stories
**Risk Level**: Low

---

## Epic Progress

- [x] Story 04.1-001 (3 pts)
- [ ] Story 04.1-002 (3 pts)
- [x] Story 04.2-001 (3 pts)
- [ ] Story 04.3-001 (1 pt)
- [ ] Story 04.3-002 (1 pt)

**Completed**: 2 / 5 stories · 6 / 11 pts.
