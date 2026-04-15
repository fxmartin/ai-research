---
description: Ingest a single source (PDF / markdown / URL) into the wiki — extract, draft, materialize, index.
argument-hint: <path-or-url>
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
---

# /ingest — single-source pipeline

You are the ingest pipeline for this research wiki. Compose the deterministic `ai-research`
toolkit verbs with your own drafting ability to turn **one** source into a materialized
Obsidian-compatible wiki page plus any concept stubs it references.

The argument is `$ARGUMENTS` — treat it as `<path-or-url>`. If empty, STOP and tell the
user: `usage: /ingest <path-or-url>`.

## Contract

- Exactly one page gets written under `wiki/<slug>.md`.
- Every `[[wikilink]]` in the draft must resolve — either to an existing page or to a
  stub you create under `wiki/concepts/<slug>.md` before materializing the main page.
- **Archive-on-ingest**: on a successful materialize (CREATED, UPDATED, or SKIPPED),
  the source file is moved into the immutable archive at
  `sources/<yyyy>/<mm>/<hash>-<slug>.<ext>`. After `/ingest` returns, the original
  path under `wiki/raw/` (or wherever the user pointed at) is **gone** — the bytes
  live only in `sources/` and the mapping is recorded in
  `.ai-research/state.json` as `state.sources[hash] = {page, archive_path}`.
- **Already-archived input**: if `$ARGUMENTS` already points inside `sources/`
  (e.g. re-materializing from the archive), no duplicate move is attempted —
  `archive_source` detects the identical target and no-ops. Pass
  `--no-archive` to `materialize` to skip the move explicitly when needed.
- Idempotent: if the source hash is already recorded in `.ai-research/state.json`,
  report `already ingested: <page>` and make **no disk writes** (and no archive
  move — the source is assumed already archived).
- Unsupported file type → report the CLI's error verbatim and make **no disk writes**.
- The `.ai-research/index.md` is rebuilt exactly once, at the end.

To recover the archive path from a wiki page later, use the observability verb
(story 07.3-001):

```bash
uv run ai-research source lookup <page-slug>
# → sources/2026/04/abcdef123456-foo.md
```

## Pipeline

Execute these steps in order. Stop on the first failure and surface the error.

### 1. Extract

Run:

```bash
uv run ai-research extract "$ARGUMENTS"
```

This emits a JSON record `{text, metadata}` to stdout. Capture it. If exit code is
non-zero (unsupported type, unreachable URL, missing file), report the stderr message
and stop — do not continue to step 2.

Note the `metadata.source_hash`. Before drafting, grep `.ai-research/state.json` for
that hash: if present, report `already ingested: <page>` and exit (no writes).

### 2. Draft

Using the extracted `text` and the page template from `.ai-research/schema.toml`
(sections, tone, bullet-density) when present, draft a markdown page in memory with:

- An H1 title derived from `metadata.title` or a slugified filename.
- A short **Summary** (2–4 sentences).
- **Key Claims** — bullets, each a standalone statement grounded in the source.
- **Connections** — bullets that use `[[wikilink]]` syntax for every cross-referenced
  concept or neighbouring page. Prefer reusing existing page slugs; grep the wiki
  before coining a new one:

  ```bash
  uv run ai-research search "<candidate term>"
  ```

- A `## Sources` section referencing the archived source.

Do NOT emit frontmatter by hand — `materialize` owns that.

### 3. Stub referenced concepts

Collect every unique `[[concept]]` target from the draft. For each concept that does
NOT already resolve to an existing `wiki/**/*.md` file, create a stub:

```bash
uv run ai-research materialize --stub "<concept name>" --skip-index
```

Pass `--skip-index` so we rebuild once at the end, not per stub.

### 4. Materialize the page

Pipe the draft into `materialize`:

```bash
printf '%s' "$DRAFT" | uv run ai-research materialize \
  --source "$ARGUMENTS" \
  --stdin \
  --skip-index
```

For URL sources also pass `--source-url "$ARGUMENTS"` so the `## Sources` section
records the original URL.

On success, `materialize` also moves the source file into `sources/` and records
the `archive_path` in `state.json`. If `$ARGUMENTS` already lives under
`sources/` (re-materialize flow), the archive step is a silent no-op; you may
additionally pass `--no-archive` to assert that intent:

```bash
printf '%s' "$DRAFT" | uv run ai-research materialize \
  --source "$ARGUMENTS" \
  --no-archive \
  --stdin \
  --skip-index
```

If materialize reports `UNCHANGED` the source hash matched; treat as idempotent success
(the archive move is still attempted and is a no-op for already-archived inputs).

#### `--no-archive` opt-out

Pass `--no-archive` to `ai-research materialize` when the source is **already
under `sources/`** (e.g. you're re-materializing an Obsidian-side edit of a
wiki page against its recorded archive path). This skips the archive-move step
entirely so the source stays in place.

```bash
printf '%s' "$DRAFT" | uv run ai-research materialize \
  --source "sources/2026/04/abcdef123456-foo.md" \
  --stdin \
  --skip-index \
  --no-archive
```

Without `--no-archive`, `archive_source` detects the already-archived shape
(canonical target path + matching SHA-256) and no-ops silently — running
materialize a second time against a source that is literally at its archive
path is safe. Use `--no-archive` only when you've pre-archived out-of-band
and want to make the intent explicit (and keep `archive_path` untouched in
`state.json`).

### 5. Rebuild the index

Exactly once, at the end:

```bash
uv run ai-research index-rebuild
```

## Output

Report a short, structured summary the user (and `claude -p`) can scan:

```
ingested: <path-or-url>
page:     wiki/<slug>.md                          (CREATED | UPDATED | UNCHANGED)
archived: sources/<yyyy>/<mm>/<hash>-<slug>.<ext> (or: already archived)
stubs:    wiki/concepts/<a>.md, wiki/concepts/<b>.md
index:    .ai-research/index.md rebuilt
```

Concrete example — `/ingest wiki/raw/attention-is-all-you-need.pdf` on 2026-04-15:

```
ingested: wiki/raw/attention-is-all-you-need.pdf
page:     wiki/attention-is-all-you-need.md                           (CREATED)
archived: sources/2026/04/9f2c1a8b4d7e-attention-is-all-you-need.pdf
stubs:    wiki/concepts/self-attention.md, wiki/concepts/transformer.md
index:    .ai-research/index.md rebuilt
```

After this call, `wiki/raw/attention-is-all-you-need.pdf` no longer exists — the
bytes live at the `archived:` path. Use `ai-research source lookup
attention-is-all-you-need` to recover it.

If any step failed, replace the block with a single `error: <message>` line and ensure
no partial writes remain (the toolkit verbs are atomic per-file, so nothing to clean
up beyond not proceeding).
