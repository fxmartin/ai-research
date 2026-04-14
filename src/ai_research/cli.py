"""Typer CLI entry point for ai-research.

Additional verbs (materialize, search, scan, ...) will be registered here by
subsequent stories. For now this provides the skeleton plus `version` and a
markdown-only `extract` (Story 01.2-003); the unified dispatcher arrives in
Story 01.2-004.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from ai_research import __version__
from ai_research.extract.markdown import SUPPORTED_SUFFIXES, extract_markdown

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
    source: str = typer.Argument(..., help="Path to a .md / .markdown / .txt file."),
) -> None:
    """Extract a source artifact into a ``{text, metadata}`` JSON record.

    v1 handles local markdown/text only; the PDF, URL, and unified dispatcher
    adapters are delivered by sibling stories under Feature 01.2.
    """
    src_path = Path(source)
    suffix = src_path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        typer.echo(
            f"Unsupported source type {suffix!r}. "
            f"Supported in this build: {sorted(SUPPORTED_SUFFIXES)}.",
            err=True,
        )
        raise typer.Exit(code=2)

    try:
        result = extract_markdown(src_path)
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    json.dump(result, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":  # pragma: no cover
    app()
