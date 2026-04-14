# Non-Functional Requirements

## Overview
**Total Stories**: 5 | **Total Points**: 8

Covers performance, reliability, portability, privacy, and scriptability — the envelopes every functional epic must respect.

---

## Performance Requirements

### Story NFR-PERF-001: End-to-end ingest and `/ask` latency budgets
**User Story**: As FX, I want ingest < 60s for a 20-page PDF and `/ask` round-trip < 10s on a 200-page vault so the tool stays snappy at realistic scale.
**Priority**: Must Have
**Story Points**: 2

**Acceptance Criteria**:
- **Given** a 20-page PDF **When** `/ingest` runs **Then** total wall time < 60s.
- **Given** a 200-page fixture vault **When** `/ask` runs headless **Then** total wall time < 10s.
- **Given** a regression test **When** it runs in CI (nightly) **Then** it fails if these thresholds are exceeded.

**Technical Notes**: Budgets are LLM-cache-warm. Cold runs permitted to exceed by 2x.

**Definition of Done**:
- [ ] Timed smoke tests wired into the nightly CI job.

**Dependencies**: Epic-03, Epic-04
**Risk Level**: Medium

---

## Reliability Requirements

### Story NFR-REL-001: Atomic, crash-safe state mutations
**User Story**: As FX, I want every write to `wiki/`, `sources/`, `state.json`, and `index.md` to be atomic (temp + rename on the same filesystem) so a crash never corrupts the vault.
**Priority**: Must Have
**Story Points**: 2

**Acceptance Criteria**:
- **Given** a crash simulated between temp-write and rename **When** I restart **Then** the target file is either the previous version or the new one — never half-written.
- **Given** `state.json` writes **When** concurrent writers run **Then** last-writer-wins but neither produces invalid JSON.

**Technical Notes**: Shared `atomic_write` helper in `state.py`. Document that cross-filesystem moves (e.g., iCloud synced drives) may not be atomic — warn in README.

**Definition of Done**:
- [ ] Crash-simulation test in place.
- [ ] README warns about non-local filesystems.

**Dependencies**: 01.1-002
**Risk Level**: Medium

---

## Portability Requirements

### Story NFR-PORT-001: Vault works with zero tooling
**User Story**: As FX, I want `wiki/` to remain a pure Obsidian vault so my knowledge survives the death of this project or Claude Code.
**Priority**: Must Have
**Story Points**: 1

**Acceptance Criteria**:
- **Given** `wiki/` copied to a machine with nothing but Obsidian **When** I open the vault **Then** all wikilinks resolve (or point to stubs), frontmatter parses, graph renders.
- **Given** the `.ai-research/` directory is deleted **When** I re-run `ai-research index-rebuild` **Then** the index is faithfully regenerated from `wiki/` alone.

**Technical Notes**: `wiki/` must never contain paths that assume `.ai-research/` exists.

**Definition of Done**:
- [ ] Manual test: copy `wiki/` to a scratch dir, open in Obsidian.

**Dependencies**: Epic-02
**Risk Level**: Low

---

## Privacy / Security Requirements

### Story NFR-SEC-001: All state local; no telemetry
**User Story**: As FX, I want all state to live locally and the Python toolkit to make **zero** outbound network calls (except optional URL fetching for ingest) so my research stays private.
**Priority**: Must Have
**Story Points**: 1

**Acceptance Criteria**:
- **Given** the Python toolkit **When** I run any verb **Then** no DNS / TCP traffic leaves the host except (a) explicitly requested URL fetches in `extract`, (b) Claude Code's own LLM calls (out of scope for this story).
- **Given** a network-egress test **When** I run the toolkit with a mock resolver **Then** no unexpected hosts are hit.

**Technical Notes**: No analytics libraries. Document Claude Code's network behavior as a distinct concern in the README privacy section.

**Definition of Done**:
- [ ] Privacy section in README.
- [ ] No `requests`/`httpx` imports outside `extract/web.py`.

**Dependencies**: Epic-01
**Risk Level**: Low

---

## Scriptability / Integration Requirements

### Story NFR-SCR-001: Every slash command has a headless JSON contract
**User Story**: As FX, I want every user-facing slash command to produce useful structured output under `claude -p --output-format json` so I can drive shell pipelines and scheduled jobs.
**Priority**: Must Have
**Story Points**: 2

**Acceptance Criteria**:
- **Given** `/ingest`, `/ingest-inbox`, `/ask`, `/status` **When** invoked with `claude -p ... --output-format json` **Then** each emits a documented, Pydantic-validated JSON object.
- **Given** any slash command **When** its JSON contract is defined **Then** the contract schema lives in `src/ai_research/contracts.py` as a Pydantic model and is referenced from the slash-command prose.

**Technical Notes**: Contracts in one place so drift is easy to spot. Harness tests validate each.

**Definition of Done**:
- [ ] `contracts.py` with `IngestResponse`, `IngestInboxResponse`, `AskResponse`, `VaultStatus`.
- [ ] At least one harness test per contract.

**Dependencies**: Epic-03, 04.1-002
**Risk Level**: Medium — slash-command prose is the weakest link.

---

## NFR Progress

- [ ] Story NFR-PERF-001 (2 pts)
- [ ] Story NFR-REL-001 (2 pts)
- [ ] Story NFR-PORT-001 (1 pt)
- [ ] Story NFR-SEC-001 (1 pt)
- [ ] Story NFR-SCR-001 (2 pts)

**Completed**: 0 / 5 stories · 0 / 8 pts.
