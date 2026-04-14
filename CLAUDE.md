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

## LLM Provider

v1 is **Anthropic-only** (Claude). Use prompt caching on system prompts and stable wiki context. Provider abstraction is deferred to P2 — do not introduce it until a second provider is actually being added.

## Storage Layout

```
sources/          # immutable raw inputs (PDF, URL-snapshot, .md, transcript)
wiki/             # Obsidian-compatible markdown pages (wikilinks + frontmatter)
  concepts/       # stub pages for cross-referenced concepts
  _contradictions.md  # Phase 2: index of flagged contradictions
.ai-research/
  schema.toml     # wiki structure & page templates
  state.json      # source hashes, page→source index
  cost.log        # per-command token + USD log
```

The vault under `wiki/` must remain openable as a pure Obsidian vault with zero tooling.

## Testing Strategy

- **Unit**: page CRUD, frontmatter parse, wikilink extraction, idempotency hashing.
- **Integration**: ingest → wiki page, against recorded Anthropic responses (vcrpy-style) to keep tests deterministic and free.
- **Golden-file**: fixture vault with a few sources; re-ingest must produce byte-identical output (except timestamps).
- **Smoke**: Obsidian-compat lint — all wikilinks resolve or point to stubs; frontmatter YAML parses.
- TDD for business logic (linker, contradiction detection). Authorization required to skip: "I AUTHORIZE YOU TO SKIP WRITING TESTS THIS TIME".

## CI/CD

- GitHub Actions: lint (`ruff`), type-check (`mypy` or `pyright`), tests (`pytest`) on push/PR.
- No deployment pipeline — local CLI, installed via `uv tool install .`.
- Release: tag-driven; `uv build` produces sdist + wheel.

## Key Docs

- `PROJECT-SEED.md` — bootstrap seed from `/project-init`.
- `REQUIREMENTS.md` — full PRD (problems, scope, P0/P1/P2, phases, risks).
- Source paper: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
