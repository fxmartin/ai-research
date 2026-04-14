"""Typer CLI entry point for ai-research.

Additional verbs (materialize, scan, ...) will be registered here by
subsequent stories. For now this provides the skeleton plus `version`,
extract adapters for markdown and PDF (Stories 01.2-001 and 01.2-003),
and search over wiki/ (Story 01.3-002).
The unified dispatcher (Story 01.2-004) will add URL routing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from ai_research import __version__
from ai_research.extract.markdown import SUPPORTED_SUFFIXES, extract_markdown
from ai_research.extract.pdf import (
    PdfExtractionError,
    PdftotextNotFoundError,
    extract_pdf,
)
from ai_research.search import run_search

app = typer.Typer(
    name="ai-research",
    help="Claude Code-native CLI + Python toolkit for AI research workflows.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def _main() -> None:
    """ai-research root command group.

    A no-op callback is required so Typer treats subcommands as subcommands
    rather than collapsing a single-command app into a flat CLI.
    """


@app.command("version")
def version() -> None:
    """Print the installed ai-research version."""
    typer.echo(__version__)


@app.command("extract")
def extract(
    source: str = typer.Argument(..., help="Path to a source file (PDF, markdown, or text)."),
) -> None:
    """Extract a source artifact into a ``{text, metadata}`` JSON record.

    Supports PDF (.pdf), markdown (.md, .markdown), and plain text (.txt).
    The unified dispatcher (Story 01.2-004) will add URL support.
    """
    src_path = Path(source)
    suffix = src_path.suffix.lower()

    # Dispatch by extension
    if suffix == ".pdf":
        # PDF extractor (Story 01.2-001)
        try:
            result = extract_pdf(src_path)
        except PdftotextNotFoundError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc
        except PdfExtractionError as exc:
            typer.echo(f"extract: {exc}", err=True)
            raise typer.Exit(code=1) from exc
    elif suffix in SUPPORTED_SUFFIXES:
        # Markdown/text extractor (Story 01.2-003)
        try:
            result = extract_markdown(src_path)
        except FileNotFoundError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
    else:
        typer.echo(
            f"Unsupported source type {suffix!r}. "
            f"Supported: .pdf, {', '.join(sorted(SUPPORTED_SUFFIXES))}.",
            err=True,
        )
        raise typer.Exit(code=2)

    json.dump(result, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


@app.command("search")
def search(
    query: str = typer.Argument(..., help="Pattern passed to ripgrep."),  # noqa: B008
    wiki_dir: Path = typer.Option(  # noqa: B008
        Path("wiki"),
        "--wiki-dir",
        help="Root of the wiki vault to search.",
    ),
    limit: int | None = typer.Option(  # noqa: B008
        None,
        "--limit",
        "-n",
        min=1,
        help="Maximum number of hits to emit.",
    ),
) -> None:
    """Run ripgrep over the wiki and emit JSON hits as `[{page, line, snippet}]`."""
    try:
        hits = run_search(query, wiki_dir=wiki_dir, limit=limit)
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps([h.to_dict() for h in hits]))


if __name__ == "__main__":  # pragma: no cover
    app()
