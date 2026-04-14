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
from ai_research.wiki.ask import AskPayloadError, check_citations
from ai_research.wiki.index_rebuild import rebuild_index as rebuild_index_impl
from ai_research.wiki.materialize import MaterializeStatus
from ai_research.wiki.materialize import materialize as materialize_page
from ai_research.wiki.stubs import create_stub

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


@app.command("materialize")
def materialize(
    source: Path | None = typer.Option(  # noqa: B008
        None,
        "--source",
        help="Path to the archived source file (used for source_hash + frontmatter).",
    ),
    draft: Path | None = typer.Option(  # noqa: B008
        None,
        "--from",
        help="Path to the markdown draft to materialize. Mutually exclusive with --stdin.",
    ),
    read_stdin: bool = typer.Option(  # noqa: B008
        False,
        "--stdin",
        help="Read the markdown draft from stdin instead of a file.",
    ),
    wiki_dir: Path = typer.Option(  # noqa: B008
        Path("wiki"),
        "--wiki-dir",
        help="Root of the wiki vault to write into.",
    ),
    state_file: Path = typer.Option(  # noqa: B008
        Path(".ai-research/state.json"),
        "--state-file",
        help="Path to state.json to update with the source_hash → page mapping.",
    ),
    source_url: str | None = typer.Option(  # noqa: B008
        None,
        "--source-url",
        help="Original URL for web sources; recorded in the ## Sources section.",
    ),
    force: bool = typer.Option(  # noqa: B008
        False,
        "--force",
        help="Rewrite even when the page is locked or the source_hash is unchanged.",
    ),
    index_file: Path = typer.Option(  # noqa: B008
        Path(".ai-research/index.md"),
        "--index-file",
        help="Path to the retrieval index; rebuilt after CREATED/UPDATED writes.",
    ),
    skip_index: bool = typer.Option(  # noqa: B008
        False,
        "--skip-index",
        help="Do not auto-rebuild the index (use for bulk runs; rebuild once at the end).",
    ),
    stubs: list[str] = typer.Option(  # noqa: B008
        [],
        "--stub",
        help=(
            "Create a concept stub at wiki/concepts/<slug>.md for the given "
            "name. Repeatable. Mutually exclusive with --source/--from/--stdin."
        ),
    ),
) -> None:
    """Write ``wiki/<slug>.md`` from a draft, atomically, with frontmatter.

    With one or more ``--stub NAME`` flags, create concept stubs instead of
    materializing a full page (Story 02.1-003).
    """
    if stubs:
        for name in stubs:
            stub_path = create_stub(name, wiki_dir=wiki_dir)
            typer.echo(str(stub_path))
        return

    if source is None:
        typer.echo("materialize: --source is required unless --stub is used.", err=True)
        raise typer.Exit(code=2)
    if draft is None and not read_stdin:
        typer.echo(
            "materialize: provide --from <draft.md> or --stdin to supply the draft body.",
            err=True,
        )
        raise typer.Exit(code=2)

    try:
        result = materialize_page(
            source=source,
            draft_path=draft,
            wiki_dir=wiki_dir,
            state_path=state_file,
            stdin=sys.stdin if read_stdin else None,
            source_url=source_url,
            force=force,
            index_path=index_file,
            skip_index=skip_index,
        )
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    if result.status is MaterializeStatus.SKIPPED:
        typer.echo(f"skipped (source_hash unchanged): {result.page_path}")
    elif result.status is MaterializeStatus.LOCKED:
        typer.echo(
            f"warning: page is locked, skipping rewrite: {result.page_path}",
            err=True,
        )
        typer.echo(str(result.page_path))
    elif result.status is MaterializeStatus.UPDATED:
        typer.echo(f"updated: {result.page_path}")
    else:
        typer.echo(str(result.page_path))


@app.command("index-rebuild")
def index_rebuild(
    wiki_dir: Path = typer.Option(  # noqa: B008
        Path("wiki"),
        "--wiki-dir",
        help="Root of the wiki vault to index.",
    ),
    index_file: Path = typer.Option(  # noqa: B008
        Path(".ai-research/index.md"),
        "--index-file",
        help="Path to write the regenerated one-line-per-page index.",
    ),
) -> None:
    """Regenerate ``.ai-research/index.md`` from the wiki vault."""
    try:
        entries = rebuild_index_impl(wiki_dir=wiki_dir, index_path=index_file)
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(f"indexed {len(entries)} page(s) -> {index_file}")


@app.command("ask-check")
def ask_check(
    json_path: Path | None = typer.Option(  # noqa: B008
        None,
        "--json",
        help="Path to an /ask JSON payload file. Mutually exclusive with --stdin.",
    ),
    read_stdin: bool = typer.Option(  # noqa: B008
        False,
        "--stdin",
        help="Read the /ask JSON payload from stdin instead of a file.",
    ),
    wiki_dir: Path = typer.Option(  # noqa: B008
        Path("wiki"),
        "--wiki-dir",
        help="Root of the wiki vault to resolve citations against.",
    ),
) -> None:
    """Verify every citation in an ``/ask`` JSON payload resolves to a vault page.

    Exit code ``0`` means every citation resolved. Exit code ``1`` means one
    or more citations are broken (the JSON result is still emitted on stdout
    for tooling). Exit code ``2`` covers usage errors: missing input, invalid
    JSON, malformed payload schema, or missing wiki directory.
    """
    if json_path is None and not read_stdin:
        typer.echo("ask-check: provide --json <payload.json> or --stdin.", err=True)
        raise typer.Exit(code=2)
    if json_path is not None and read_stdin:
        typer.echo("ask-check: --json and --stdin are mutually exclusive.", err=True)
        raise typer.Exit(code=2)

    raw = sys.stdin.read() if read_stdin else json_path.read_text(encoding="utf-8")  # type: ignore[union-attr]
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        typer.echo(f"ask-check: invalid JSON: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    try:
        result = check_citations(payload, wiki_dir=wiki_dir)
    except AskPayloadError as exc:
        typer.echo(f"ask-check: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(json.dumps(result.to_dict()))
    if not result.ok:
        raise typer.Exit(code=1)


if __name__ == "__main__":  # pragma: no cover
    app()
