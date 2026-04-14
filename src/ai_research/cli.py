"""Typer CLI entry point for ai-research.

Additional verbs (extract, materialize, search, scan, ...) will be registered
here by subsequent stories. For now this provides the skeleton plus `version`.
"""

from __future__ import annotations

import typer

from ai_research import __version__

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


if __name__ == "__main__":  # pragma: no cover
    app()
