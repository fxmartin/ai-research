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

## Key Docs

<!-- Populated after /brainstorm and /generate-epics -->
- `PROJECT-SEED.md` — Project seed data for downstream skills
- Source paper: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
