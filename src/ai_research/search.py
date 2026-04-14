"""Ripgrep wrapper emitting structured search hits over a wiki/ directory.

Zero LLM calls. Shells out to `rg --json` and re-emits a stable schema:
`{page, line, snippet}`. Used by `/ask` as a deterministic lexical pre-filter.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

__all__ = ["SearchHit", "run_search"]


@dataclass(frozen=True)
class SearchHit:
    """A single ripgrep match re-shaped to our stable public schema."""

    page: str
    line: int
    snippet: str

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


def _extract_text(obj: dict) -> str:
    """ripgrep JSON encodes text as either `{"text": "..."}` or `{"bytes": "..."}`.

    We only care about the text form; bytes (invalid UTF-8) are rare in a
    markdown vault so we fall back to an empty string.
    """
    if "text" in obj:
        return obj["text"]
    return ""


def run_search(
    query: str,
    *,
    wiki_dir: Path,
    limit: int | None = None,
) -> list[SearchHit]:
    """Run ripgrep against `wiki_dir` and return up to `limit` structured hits.

    Args:
        query: Literal or regex pattern handed straight to `rg`.
        wiki_dir: Root directory to search. Must exist.
        limit: If provided, truncate results to at most N hits.

    Raises:
        FileNotFoundError: If `wiki_dir` does not exist.
        RuntimeError: If the `rg` binary is not on PATH, or exits with a
            failure code (exit 1 is the "no matches" case and is handled).
    """
    if not wiki_dir.exists():
        raise FileNotFoundError(f"wiki directory not found: {wiki_dir}")

    if shutil.which("rg") is None:
        raise RuntimeError("ripgrep (`rg`) not found on PATH. Install via `brew install ripgrep`.")

    cmd = ["rg", "--json", "--", query, str(wiki_dir)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)

    # rg exit codes: 0 = matches, 1 = no matches, 2+ = error.
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"ripgrep failed (exit {proc.returncode}): {proc.stderr.strip()}")

    hits: list[SearchHit] = []
    for raw_line in proc.stdout.splitlines():
        if not raw_line.strip():
            continue
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "match":
            continue
        data = event.get("data", {})
        path_obj = data.get("path", {})
        lines_obj = data.get("lines", {})
        line_number = data.get("line_number")
        page = _extract_text(path_obj)
        snippet = _extract_text(lines_obj).rstrip("\n")
        if not page or line_number is None:
            continue
        hits.append(SearchHit(page=page, line=int(line_number), snippet=snippet))
        if limit is not None and len(hits) >= limit:
            break

    return hits
