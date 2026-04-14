---
description: Answer a question from the wiki with [[page-name]] citations. Supports interactive and headless JSON modes.
argument-hint: "<question>"
allowed-tools: Read, Grep, Bash
---

# /ask — Two-stage retrieval Q&A over the wiki

You are answering a question against the `ai-research` wiki (an Obsidian-compatible
markdown vault under `wiki/`) using a **deterministic two-stage retrieval protocol**.
There is NO vector DB. All retrieval is done by reading files directly.

## Input

The user's question is: **$ARGUMENTS**

If `$ARGUMENTS` is empty, respond with an error and stop.

## Output modes

You must detect which mode you are running in and format output accordingly:

- **Interactive mode** (default): Write a natural-language answer with inline
  `[[page-name]]` wikilinks as citations. End with a short "Sources:" bullet list
  of the cited pages.
- **Headless JSON mode**: If invoked under `claude -p --output-format json`, your
  **final message** must be a single JSON object on stdout matching EXACTLY this
  schema (no prose, no markdown fences, no extra keys):

  ```json
  {
    "answer": "string — the answer text with inline [[page-name]] wikilinks",
    "citations": ["page-name-1", "page-name-2"],
    "confidence": 0.0
  }
  ```

  - `answer` — string. Empty string `""` if the vault is empty or no pages match.
  - `citations` — array of strings. Each entry is a bare page name (no brackets,
    no `.md` extension, no path). Must be a subset of pages actually read.
  - `confidence` — float in `[0.0, 1.0]`. `0.0` if the vault is empty or the
    shortlist is empty; higher when multiple shortlisted pages corroborate.

  **When asked for JSON, return EXACTLY these keys.** Do not add commentary.

## Protocol

### Stage 0 — Preconditions

1. Verify `.ai-research/index.md` exists. If not, the vault is empty: emit an
   empty answer (JSON: `{"answer": "", "citations": [], "confidence": 0.0}`;
   interactive: "The wiki is empty — nothing to answer from.") and stop.
2. Verify `wiki/` exists and contains at least one `.md` file. If not, same
   empty-vault behavior.

### Stage 1 — Shortlist (3–8 pages)

1. **Read** `.ai-research/index.md` in full. Each line is:
   `page-name · tags · 1-line summary · H1 list · outbound-link count`.
2. Score lines against the question using keyword overlap, tag match, and
   summary relevance. Pick the **top 3–8 candidates**.
3. If fewer than 3 candidates look relevant, run the lexical fallback:
   ```bash
   ai-research search "<key terms from the question>"
   ```
   Merge results into the shortlist and re-rank. De-duplicate by page name.
4. If after fallback the shortlist is still empty, emit an empty answer with
   `confidence: 0.0` and stop.

### Stage 2 — Answer

1. **Read** the full markdown of every shortlisted page via the `Read` tool.
   Do not guess content — only cite what you have actually read.
2. Synthesize an answer grounded in the read pages. Every non-trivial claim
   must be followed by at least one `[[page-name]]` citation.
3. Do NOT invent page names. A citation is valid only if the page was in your
   shortlist AND you read it.
4. Compute `confidence`:
   - `0.0` — empty vault or empty shortlist.
   - `0.2–0.4` — only one page read, weak keyword match.
   - `0.5–0.7` — 2+ pages read, clear answer with some corroboration.
   - `0.8–0.95` — 3+ pages read, strongly corroborated, direct quotes available.
   - Never emit `1.0` — reserve for formal proofs.

### Stage 3 — Emit

- **Interactive**: print the answer with inline `[[wikilinks]]`, then a
  `Sources:` bullet list of cited page names.
- **JSON**: emit the JSON object described above as your final message, and
  nothing else.

## Constraints

- Never modify disk. `/ask` is read-only.
- Never cite a page you did not read.
- Never exceed 8 shortlisted pages — retrieval precision beats recall here.
- Prefer pages with higher outbound-link counts when ties occur (they are
  better-connected hubs).
