"""Obsidian-compatibility vault lint (Story 04.2-001).

`vault-lint` walks the wiki/ vault and verifies it stays openable as a
pure Obsidian vault: every ``[[wikilink]]`` resolves (to a page or a
stub), all frontmatter parses as YAML, file names follow the slug
convention, and the report tallies pages / stubs / wikilinks / orphans
for downstream JSON consumers.

Pure file-ops — no LLM calls. Suitable for CI smoke tests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import frontmatter
import yaml

from ai_research.archive import slugify

__all__ = ["LintIssue", "LintReport", "lint_vault"]


_WIKILINK_RE = re.compile(r"\[\[([^\[\]\n]+?)\]\]")
# Obsidian-friendly slug: lowercase ASCII alnum + dashes, optional .md.
_VALID_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*$")


@dataclass(frozen=True)
class LintIssue:
    """A single lint violation.

    ``kind`` is one of: ``broken-wikilink``, ``frontmatter``, ``naming``.
    """

    kind: str
    path: Path
    line: int
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "path": str(self.path),
            "line": self.line,
            "message": self.message,
        }


@dataclass(frozen=True)
class LintReport:
    """Aggregate vault-lint result.

    Attributes:
        pages: Full markdown pages under ``wiki/`` (excluding ``concepts/``).
        stubs: Pages under ``wiki/concepts/``.
        wikilinks: Total non-empty wikilink targets discovered (with dupes).
        orphans: Pages with zero inbound wikilinks (stubs excluded).
        issues: All violations; ``ok`` is ``True`` iff this list is empty.
    """

    pages: int
    stubs: int
    wikilinks: int
    orphans: int
    issues: list[LintIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "pages": self.pages,
            "stubs": self.stubs,
            "wikilinks": self.wikilinks,
            "orphans": self.orphans,
            "issues": [i.to_dict() for i in self.issues],
        }


def _split_frontmatter(text: str) -> tuple[str | None, str, int]:
    """Return ``(yaml_block, body, body_start_line)``.

    ``body_start_line`` is 1-based and points at the first body line in the
    original file (so wikilink line numbers stay honest). If no frontmatter
    block is present, ``yaml_block`` is ``None`` and the body is the whole
    file starting at line 1.
    """
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        return None, text, 1
    lines = text.splitlines(keepends=True)
    # lines[0] is "---\n"; find closing fence.
    for idx in range(1, len(lines)):
        stripped = lines[idx].rstrip("\r\n")
        if stripped == "---" or stripped == "...":
            yaml_block = "".join(lines[1:idx])
            body = "".join(lines[idx + 1 :])
            return yaml_block, body, idx + 2
    # Unterminated frontmatter — treat as parse failure path.
    return "".join(lines[1:]), "", len(lines) + 1


def _slug_for(target: str) -> str:
    """Return the slug used to look up a wikilink target on disk."""
    cleaned = target.split("|", 1)[0].split("#", 1)[0].strip()
    if not cleaned:
        return ""
    return slugify(cleaned)


def _resolve(slug: str, page_slugs: set[str], stub_slugs: set[str]) -> bool:
    return slug in page_slugs or slug in stub_slugs


def lint_vault(wiki_dir: Path) -> LintReport:
    """Lint ``wiki_dir`` for Obsidian compatibility.

    Raises:
        FileNotFoundError: ``wiki_dir`` does not exist.
    """
    wiki_dir = Path(wiki_dir)
    if not wiki_dir.is_dir():
        raise FileNotFoundError(f"wiki_dir does not exist: {wiki_dir}")

    md_files = sorted(
        p
        for p in wiki_dir.rglob("*.md")
        # Skip the Obsidian Web Clipper inbox — wiki/raw/ holds ephemeral
        # clippings awaiting ingest, not curated wiki pages.
        if not (p.relative_to(wiki_dir).parts and p.relative_to(wiki_dir).parts[0] == "raw")
    )

    page_paths: list[Path] = []
    stub_paths: list[Path] = []
    page_slugs: set[str] = set()
    stub_slugs: set[str] = set()

    for path in md_files:
        rel = path.relative_to(wiki_dir)
        if rel.parts[0] == "concepts":
            stub_paths.append(path)
            stub_slugs.add(path.stem)
        else:
            page_paths.append(path)
            page_slugs.add(path.stem)

    issues: list[LintIssue] = []
    wikilink_total = 0
    inbound: dict[str, int] = {s: 0 for s in page_slugs}

    for path in md_files:
        text = path.read_text(encoding="utf-8")

        # Naming check — file stem must be a clean slug.
        if not _VALID_NAME_RE.match(path.stem):
            issues.append(
                LintIssue(
                    kind="naming",
                    path=path,
                    line=1,
                    message=f"file name not a clean slug: {path.name}",
                )
            )

        # Frontmatter parse — explicit YAML check beats python-frontmatter's
        # silent fallback so we surface broken YAML as a lint error.
        yaml_block, body, body_start = _split_frontmatter(text)
        if yaml_block is not None:
            try:
                yaml.safe_load(yaml_block)
                # Round-trip via python-frontmatter so callers can rely on it.
                frontmatter.loads(text)
            except (yaml.YAMLError, Exception) as exc:  # noqa: BLE001
                issues.append(
                    LintIssue(
                        kind="frontmatter",
                        path=path,
                        line=1,
                        message=f"frontmatter YAML parse failed: {exc}",
                    )
                )
                # Skip wikilink scan if frontmatter is broken — body offset
                # is unreliable.
                continue

        # Wikilink scan, line-by-line so we can report line numbers.
        body_lines = body.splitlines()
        for offset, line_text in enumerate(body_lines):
            for raw in _WIKILINK_RE.findall(line_text):
                slug = _slug_for(raw)
                if not slug:
                    continue
                wikilink_total += 1
                if _resolve(slug, page_slugs, stub_slugs):
                    if slug in inbound:
                        inbound[slug] += 1
                else:
                    issues.append(
                        LintIssue(
                            kind="broken-wikilink",
                            path=path,
                            line=body_start + offset,
                            message=f"unresolved wikilink: [[{raw}]]",
                        )
                    )

    orphans = sum(1 for slug, count in inbound.items() if count == 0)

    return LintReport(
        pages=len(page_paths),
        stubs=len(stub_paths),
        wikilinks=wikilink_total,
        orphans=orphans,
        issues=issues,
    )
