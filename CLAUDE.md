# ai-research — An LLM-maintained research wiki

## Project Context

`ai-research` implements Karpathy's "LLM Wiki" pattern: an LLM incrementally builds and maintains an interconnected markdown knowledge base from raw sources, replacing ad-hoc RAG with a persistent, compounding wiki. Output is Obsidian-vault compatible (wikilinks + frontmatter) so a human curator can browse and refine alongside the LLM.

## Tech Stack

- **Language**: Python 3.12+
- **Package/Project manager**: uv
- **Framework**: FastAPI (for any future API surface)
- **CLI**: Typer/Click (TBD in `/brainstorm`)

## Architecture

CLI-first tool that ingests source documents, invokes an LLM to generate/update interconnected wiki pages on disk, and maintains a schema file describing wiki structure and workflows. Optional FastAPI surface for programmatic access.

## Repository Structure

```
ai-research/
├── src/ai_research/       # Library + CLI package
│   ├── cli.py
│   ├── wiki/              # Page generation, cross-referencing
│   ├── sources/           # Ingestion adapters
│   └── llm/               # LLM provider abstraction
├── tests/
├── wiki-data/             # Example/scratch wiki output (gitignored)
├── pyproject.toml
├── CLAUDE.md
├── PROJECT-SEED.md
└── .gitignore
```

## Preferred CLI Tools

| Instead of | Use | Why |
|------------|-----|-----|
| `find` | `fd` | Faster, respects `.gitignore` |
| `grep` | `rg` | ripgrep — faster, better defaults |
| `cat` | `bat` | Syntax highlighting |
| `cd` | `zoxide` (`z`) | Frecent dir jumps |
| LOC counting | `scc` | Fast, with complexity |
| PDF generation | `typst` | Modern typesetting |

## GitHub Operations — Use `gh` CLI (NOT MCP)

Always use `gh` CLI for issues, PRs, releases, API calls.

## LLM Runtime

v1 is **Claude Code-native**. No Anthropic SDK in the Python toolkit. All LLM work — page drafting, concept extraction, Q&A — happens inside Claude Code, either interactively or headless via `claude -p "<slash-command>"`. Claude Code owns prompt caching, retries, and usage accounting. Provider fallback (OpenAI/Ollama via an SDK layer) is P2 and only added if lock-in bites.

## Storage Layout

```
raw/              # INBOX — drop new files here; drained to sources/
sources/          # immutable archive (PDF, URL-snapshot, .md, transcript)
  <yyyy>/<mm>/<hash>-<slug>.<ext>
wiki/             # Obsidian-compatible markdown pages (wikilinks + frontmatter)
  concepts/       # stub pages for cross-referenced concepts
  _contradictions.md  # Phase 2: index of flagged contradictions
.ai-research/
  schema.toml     # wiki structure & page templates
  state.json      # source hashes, page→source index
  index.md        # one-line-per-page retrieval index (rebuilt on materialize)
.claude/
  commands/
    ingest.md        # /ingest <path-or-url>
    ingest-inbox.md  # /ingest-inbox — batch-drain raw/
    ask.md           # /ask "<question>" — JSON contract under claude -p
    status.md        # /status (P1)
```

The vault under `wiki/` must remain openable as a pure Obsidian vault with zero tooling.

## Orchestration

Three equivalent ways to invoke everything:

1. **Interactive**: open Claude Code in the repo, run `/ingest`, `/ingest-inbox`, `/ask`.
2. **Self-paced watcher**: `/loop` drives `/ingest-inbox` during a session.
3. **Headless / scheduled**: `claude -p "/ingest-inbox"` from launchd or cron; `claude -p "/ask 'q'" --output-format json | jq` in shell pipelines.

The Python package `ai-research` is a **deterministic file-ops toolkit** with zero LLM calls: `extract`, `materialize`, `index-rebuild`, `search`, `scan`. Slash commands compose these with Claude Code's native Read/Grep/Write tools.

## Retrieval (`/ask`)

Two-stage, no vector DB in v1:
1. **Shortlist**: read `.ai-research/index.md` (one line per page: title · tags · 1-line summary · H1 list · outbound-link count), plus optional `ai-research search "<q>"` (rg pre-filter for exact-term queries). Pick 3–8 candidates.
2. **Answer**: Read full markdown of shortlisted pages → emit answer with `[[page-name]]` citations. Under `claude -p --output-format json`, return `{answer, citations[], confidence}`.

Embeddings and graph-walk expansion (follow `[[wikilinks]]` 1–2 hops) are P2.

## Testing Strategy

- **Unit**: Python toolkit verbs — frontmatter parse, atomic write, idempotency hashing, `extract` adapters, `search` rg wrapper, `index-rebuild`.
- **Golden-file**: fixture vault; running the toolkit verbs against recorded inputs produces byte-identical output (except timestamps).
- **Smoke**: Obsidian-compat lint on `wiki/` — all wikilinks resolve or point to stubs; frontmatter YAML parses.
- **Slash commands** (prose, not code): weekly manual smoke test; `/ask` JSON output contract validated by a `claude -p --output-format json` harness test.
- TDD for all Python toolkit business logic. Authorization required to skip: "I AUTHORIZE YOU TO SKIP WRITING TESTS THIS TIME".

## CI/CD

- GitHub Actions: lint (`ruff`), type-check (`mypy` or `pyright`), tests (`pytest`) on push/PR.
- No deployment pipeline — local CLI, installed via `uv tool install .`.
- Release: tag-driven; `uv build` produces sdist + wheel.

## Key Docs

- `PROJECT-SEED.md` — bootstrap seed from `/project-init`.
- `REQUIREMENTS.md` — full PRD (problems, scope, P0/P1/P2, phases, risks).
- Source paper: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
