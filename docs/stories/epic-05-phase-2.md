# Epic 5: Phase 2 — YouTube, Contradictions, Ops

## Epic Overview
**Epic ID**: Epic-05
**Description**: Post-MVP depth: YouTube transcript ingestion, contradiction detection across the vault, `/status` slash command with vault stats, and a launchd agent template for background `/ingest-inbox` so `wiki/raw/` drains without an open Claude Code session.
**Business Value**: MVP validates the premise. This epic makes ai-research a durable daily tool — more source types, proactive quality signals, and hands-off operation.
**Success Metrics**:
- YouTube videos ingest as cleanly as PDFs.
- Contradictions surface automatically; `_contradictions.md` has non-zero useful entries after 10+ sources.
- `/status` renders usable vault health in < 2s.
- Launchd agent drains `wiki/raw/` overnight.

## Epic Scope
**Total Stories**: 6 | **Total Points**: 17 | **MVP Stories**: 0

---

## Features in This Epic

### Feature 05.1: YouTube Ingestion

#### Stories

##### Story 05.1-001: `extract` adapter for YouTube URLs (captions)
**User Story**: As FX, I want `ai-research extract <youtube-url>` to prefer auto-captions (via `yt-dlp --write-auto-subs --skip-download`) so most videos ingest with no audio processing.
**Priority**: Should Have
**Story Points**: 3

**Acceptance Criteria**:
- **Given** a YouTube URL with captions **When** extract runs **Then** stdout is `{text, metadata}` where metadata includes `video_id`, `title`, `channel`, `duration`, `source_type: "youtube"`, `sha256` (of transcript).
- **Given** a YouTube URL without captions **When** extract runs with `--whisper-fallback=false` **Then** it exits non-zero with a clear message.
- **Given** `--whisper-fallback=true` **When** captions are missing **Then** the adapter delegates to Story 05.1-002.

**Technical Notes**: Reuse URL-sniffing from 01.2-004; detect `youtube.com` / `youtu.be` and dispatch here.

**Definition of Done**:
- [ ] Unit tests with recorded `yt-dlp --dump-json` output.
- [ ] Integration test behind `--slow` marker.

**Dependencies**: 01.2-004
**Risk Level**: Medium — YouTube ToS / rate limits.

---

##### Story 05.1-002: Whisper fallback for caption-less videos
**User Story**: As FX, I want a Whisper fallback that transcribes audio when captions are missing so I can ingest any video.
**Priority**: Could Have
**Story Points**: 3

**Acceptance Criteria**:
- **Given** a caption-less video with `--whisper-fallback=true` **When** extract runs **Then** audio is downloaded, transcribed with `whisper.cpp` or `faster-whisper`, and emitted as text.
- **Given** transcription > 10 minutes of audio **When** extract runs **Then** progress is logged to stderr.
- **Given** a failure mid-transcription **When** extract runs **Then** no partial output is emitted.

**Technical Notes**: Prefer `faster-whisper` CPU mode for portability; accept a slower path over a GPU requirement.

**Definition of Done**:
- [ ] Optional dep — install via `uv add --optional whisper faster-whisper`.
- [ ] Docs call out the extra install step.

**Dependencies**: 05.1-001
**Risk Level**: High — accuracy + performance vary wildly.

---

### Feature 05.2: Contradiction Detection

#### Stories

##### Story 05.2-001: `ai-research detect-contradictions --page <path>`
**User Story**: As FX, I want a toolkit verb that takes a drafted page + the existing wiki and produces a list of claim conflicts so the slash command can append warnings.
**Priority**: Should Have
**Story Points**: 5

**Acceptance Criteria**:
- **Given** a new page and a populated wiki **When** the verb runs **Then** stdout is JSON `[{claim, conflicts_with_page, conflicts_with_quote, confidence}]`.
- **Given** no conflicts **When** the verb runs **Then** the list is empty and exit 0.
- **Given** the verb **When** I inspect it **Then** it performs *no* LLM calls — it takes a pre-drafted conflict list from stdin (produced by Claude in the slash command) and validates it against the wiki.

**Technical Notes**: Conflict *detection* lives in the slash command (Claude does it). This verb is the deterministic validator + persister.

**Definition of Done**:
- [ ] Unit tests with fixture claims and wiki.

**Dependencies**: Epic-02
**Risk Level**: Medium

---

##### Story 05.2-002: `/ingest` appends contradiction callouts + updates `_contradictions.md`
**User Story**: As FX, I want `/ingest` to detect contradictions against existing pages and emit Obsidian `> [!warning] Contradicts [[X]]` callouts inline + append to `wiki/_contradictions.md` so I see conflicts without searching.
**Priority**: Should Have
**Story Points**: 3

**Acceptance Criteria**:
- **Given** a new page's claim conflicts with an existing page **When** `/ingest` runs **Then** the drafted page includes a `> [!warning] Contradicts [[X]]: …` callout.
- **Given** conflicts **When** `/ingest` runs **Then** `wiki/_contradictions.md` is appended with a dated row: `| date | new-page | conflicts-with | status |`.
- **Given** no conflicts **When** `/ingest` runs **Then** `_contradictions.md` is untouched.

**Technical Notes**: Update `ingest.md` slash command spec. The table format makes it easy to mark `resolved` manually later.

**Definition of Done**:
- [ ] Updated `.claude/commands/ingest.md`.
- [ ] Manual smoke on two sources that disagree.

**Dependencies**: 05.2-001, 03.1-001
**Risk Level**: Medium

---

### Feature 05.3: Ops

#### Stories

##### Story 05.3-001: `/status` slash command — vault health
**User Story**: As FX, I want `/status` to print vault stats (page count, stub count, orphan rate, avg wikilinks/page, open contradictions) in < 2s so I know the wiki is healthy at a glance.
**Priority**: Should Have
**Story Points**: 2

**Acceptance Criteria**:
- **Given** `/status` in Claude Code **When** it runs **Then** it prints a human-readable summary.
- **Given** `claude -p "/status" --output-format json` **When** it runs **Then** stdout is a JSON object matching the `VaultStatus` Pydantic model.
- **Given** the vault is empty **When** `/status` runs **Then** it clearly says so (no null errors).

**Technical Notes**: Backed by a toolkit verb `ai-research vault-stats --json` that reads `state.json` + `index.md`.

**Definition of Done**:
- [ ] `.claude/commands/status.md` + toolkit verb committed.
- [ ] Interactive + headless smoke.

**Dependencies**: Epic-02, Epic-03
**Risk Level**: Low

---

##### Story 05.3-002: launchd agent template for background `/ingest-inbox`
**User Story**: As FX, I want a documented launchd agent that runs `claude -p "/ingest-inbox"` on a schedule (e.g. every 20 min) so `wiki/raw/` drains without me opening Claude Code.
**Priority**: Could Have
**Story Points**: 1

**Acceptance Criteria**:
- **Given** `scripts/com.fxmartin.ai-research.ingest.plist` **When** I install it via `launchctl bootstrap gui/<uid> <plist>` **Then** the agent runs on schedule and logs to `.ai-research/launchd.log`.
- **Given** `claude` CLI missing from the agent's PATH **When** it fires **Then** the log clearly reports the problem.
- **Given** the README **When** I read the install steps **Then** both `load` and `unload` are documented.

**Technical Notes**: Keep the plist parameterized (interval, log path). Ship as a template the user copies, not as an auto-installed artifact.

**Definition of Done**:
- [ ] plist template committed under `scripts/`.
- [ ] README section "Background ingestion" documents install/uninstall.

**Dependencies**: 03.2-001
**Risk Level**: Low

---

## Epic Progress

- [ ] Story 05.1-001 (3 pts)
- [ ] Story 05.1-002 (3 pts)
- [ ] Story 05.2-001 (5 pts)
- [ ] Story 05.2-002 (3 pts)
- [ ] Story 05.3-001 (2 pts)
- [ ] Story 05.3-002 (1 pt)

**Completed**: 0 / 6 stories · 0 / 17 pts.
