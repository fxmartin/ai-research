---
description: Drain wiki/raw/ — scan for eligible files, ingest each one, rebuild the index once.
argument-hint: (no arguments)
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
---

# /ingest-inbox — batch drain of `wiki/raw/`

You are the batch ingest driver for this research wiki. Your job is to drain the
`wiki/raw/` inbox by composing the deterministic `ai-research` toolkit verbs with your
own drafting ability, ingesting **every eligible file in one Claude Code turn**.

This command takes **no arguments**. If `$ARGUMENTS` is non-empty, ignore it.

## Contract

- Every eligible file in `wiki/raw/` is ingested and archived to `sources/` via the
  toolkit. After a successful pass `wiki/raw/` is empty (or contains only files too
  new / already-known that were deliberately skipped).
- **Idempotent**: already-ingested sources (hash in `.ai-research/state.json`)
  are skipped silently via `scan --skip-known`. A second run on the same `wiki/raw/`
  is a no-op.
- Files with `mtime < 5s` are skipped and flagged for the next tick (handled by
  `scan`'s default `--min-age-seconds 5.0`).
- Per-file failures are reported but do not abort the batch; successful files
  are still materialized. In headless mode (`claude -p`) the final summary
  signals a non-zero exit condition when any file failed.
- `.ai-research/index.md` is rebuilt **exactly once** at the end of the batch,
  not per file.
- When `wiki/raw/` is empty (or `scan` returns zero eligible files), report
  `nothing to ingest` and exit cleanly — do NOT error.

## Pipeline

### 1. Scan the inbox

Run:

```bash
uv run ai-research scan wiki/raw/ --skip-known --json
```

This returns a JSON array of absolute paths eligible for ingest: files old
enough (mtime ≥ 5s), not already recorded in `state.json`. The `--skip-known`
flag is what guarantees idempotency across repeated `/ingest-inbox` runs.

If the array is empty, emit:

```
nothing to ingest
```

and stop. This is a clean exit, not an error.

### 2. Loop: ingest each file (in-turn, NOT by re-invoking /ingest)

For each path in the scan output, execute the same pipeline as `/ingest` —
`extract` → draft → stub concepts → `materialize` — but **inline, in this same
Claude Code turn**. Do NOT re-enter the `/ingest` slash command per file; that
would be expensive and lose shared context.

For each file:

1. `uv run ai-research extract "<path>"` — capture JSON `{text, metadata}`.
   On non-zero exit, record the failure and CONTINUE to the next file.
2. Draft a markdown page using the template from `.ai-research/schema.toml`
   (Summary / Key Claims / Connections), with `[[wikilink]]` connections.
3. For each unique `[[concept]]` target not already in `wiki/`, create a stub:

   ```bash
   uv run ai-research materialize --stub "<concept>" --skip-index
   ```

4. Materialize the page — pass `--skip-index` so the index is rebuilt exactly
   once at the end:

   ```bash
   printf '%s' "$DRAFT" | uv run ai-research materialize \
     --source "<path>" \
     --stdin \
     --skip-index
   ```

   `UNCHANGED` from `materialize` is treated as idempotent success, not failure.

### 3. Rebuild the index — exactly once

After the loop completes (even if some files failed), run:

```bash
uv run ai-research index-rebuild
```

This runs **once** at the end regardless of batch size. Never per file.

## Output

Emit a single structured summary block so both humans and headless callers
(`claude -p`) can parse it:

```
scanned:   <N> files
ingested:  <K> ok, <F> failed
pages:     wiki/<slug-1>.md, wiki/<slug-2>.md
stubs:     wiki/concepts/<a>.md, wiki/concepts/<b>.md
failures:  <path-1>: <error>
           <path-2>: <error>
index:     .ai-research/index.md rebuilt
```

If the scan was empty, replace the block with the single line:

```
nothing to ingest
```

If any file failed, the caller treats the run as non-zero (headless exit
signal). If no eligible files were present, that is NOT a failure.
