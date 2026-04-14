"""Typer CLI entry point for ai-research.

Additional verbs (materialize, scan, ...) will be registered here by
subsequent stories. For now this provides the skeleton plus `version`,
the unified extract dispatcher (Story 01.2-004) covering PDF / markdown /
URL sources, and search over wiki/ (Story 01.3-002).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from ai_research import __version__
from ai_research.extract import (
    PdfExtractionError,
    PdftotextNotFoundError,
    UnsupportedSourceError,
    UrlExtractionError,
)
from ai_research.extract import (
    extract as extract_dispatch,
)
from ai_research.scan import DEFAULT_MIN_AGE_SECONDS, scan_raw
from ai_research.search import run_search
from ai_research.state import load_state

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
    source: str = typer.Argument(
        ..., help="Path or URL to a source (PDF, markdown, text, or http[s]://)."
    ),
) -> None:
    """Extract a source artifact into a ``{text, metadata}`` JSON record.

    Routing is delegated to :func:`ai_research.extract.extract`:

    * ``http://`` / ``https://`` URLs → URL adapter
    * ``.pdf`` → PDF adapter
    * ``.md`` / ``.markdown`` / ``.txt`` → markdown adapter
    * anything else → exit code 2 with a supported-types message.
    """
    try:
        result = extract_dispatch(source)
    except UnsupportedSourceError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except PdftotextNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except (PdfExtractionError, UrlExtractionError) as exc:
        typer.echo(f"extract: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

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


@app.command("scan")
def scan(
    raw_dir: Path = typer.Argument(  # noqa: B008
        ...,
        help="Path to the raw/ inbox directory to scan.",
    ),
    min_age_seconds: float = typer.Option(  # noqa: B008
        DEFAULT_MIN_AGE_SECONDS,
        "--min-age-seconds",
        help="Skip files whose mtime is newer than this many seconds.",
    ),
    skip_known: bool = typer.Option(  # noqa: B008
        False,
        "--skip-known",
        help="Exclude files whose SHA-256 already appears in state.json sources.",
    ),
    state_file: Path = typer.Option(  # noqa: B008
        Path(".ai-research/state.json"),
        "--state-file",
        help="Path to state.json used for --skip-known lookups.",
    ),
    as_json: bool = typer.Option(  # noqa: B008
        False,
        "--json",
        help="Emit results as a JSON array instead of one path per line.",
    ),
) -> None:
    """List files in ``raw_dir`` that are eligible for ingest."""
    state = load_state(state_file) if skip_known else None
    try:
        results = scan_raw(
            raw_dir,
            min_age_seconds=min_age_seconds,
            skip_known=skip_known,
            state=state,
        )
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    if as_json:
        typer.echo(json.dumps(results))
    else:
        for path in results:
            typer.echo(path)


if __name__ == "__main__":  # pragma: no cover
    app()
