"""Citation integrity check for ``/ask`` JSON answers (Story 03.3-002).

The ``/ask`` slash command emits a JSON payload of the shape::

    {"answer": str, "citations": list[str], "confidence": float}

Citations are ``[[page-name]]`` wikilinks or bare page names. A "valid"
citation is one whose slug resolves to a markdown file somewhere under the
wiki vault — either a full page at ``wiki/<slug>.md`` or a stub at
``wiki/concepts/<slug>.md``. This module provides a pure file-ops helper
plus a CLI verb (``ai-research ask-check``) to catch hallucinated
citations before they leak into downstream tooling.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai_research.archive import slugify

__all__ = [
    "AskPayloadError",
    "AskResponse",
    "CitationCheckResult",
    "check_citations",
    "normalize_citation",
]


_BARE_PAGE_RE = re.compile(r"^[^\[\]|#/\\.]+$")


class AskResponse(BaseModel):
    """Pydantic model of the ``/ask`` JSON contract (Story 04.1-002).

    The ``/ask`` slash command, when invoked under
    ``claude -p --output-format json``, emits exactly this shape on stdout::

        {"answer": "...", "citations": ["page-name", ...], "confidence": 0.0}

    - ``answer``: free-form string; empty string is legal (empty vault).
    - ``citations``: list of bare page names. No brackets, no ``.md``, no path
      components, no alias (``|``) or anchor (``#``) segments.
    - ``confidence``: float in the half-open interval ``[0.0, 1.0)``. ``1.0``
      is reserved for formal proofs per the slash-command spec.
    """

    model_config = ConfigDict(extra="forbid")

    answer: str
    citations: list[str]
    confidence: float = Field(ge=0.0, lt=1.0)

    @field_validator("citations")
    @classmethod
    def _validate_citation_shape(cls, value: list[str]) -> list[str]:
        for entry in value:
            if not isinstance(entry, str) or not entry.strip():
                raise ValueError(f"citation must be a non-empty string: {entry!r}")
            if not _BARE_PAGE_RE.match(entry):
                raise ValueError(
                    f"citation must be a bare page name (no brackets/anchor/alias/path): {entry!r}"
                )
        return value


_WIKILINK_RE = re.compile(r"^\[\[(?P<inner>.*)\]\]$")


class AskPayloadError(ValueError):
    """Raised when an ``/ask`` JSON payload is malformed."""


@dataclass(frozen=True)
class CitationCheckResult:
    """Outcome of a citation integrity sweep.

    Attributes:
        ok: ``True`` when every citation resolved to a vault page.
        resolved: Normalized citation names that resolved successfully.
        broken: Normalized citation names that did not resolve.
    """

    ok: bool
    resolved: list[str]
    broken: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "resolved": list(self.resolved), "broken": list(self.broken)}


def normalize_citation(citation: str) -> str:
    """Return the page-name portion of a citation string.

    Accepts bare names (``"Attention"``), wikilinks (``"[[Attention]]"``),
    and wikilinks with anchors or aliases
    (``"[[Attention#Heading|alias]]"``). Anchor (``#``) and alias (``|``)
    segments are stripped. Raises :class:`AskPayloadError` on empty input.
    """
    if not isinstance(citation, str):  # pragma: no cover — guarded by caller
        raise AskPayloadError(f"citation must be a string, got {type(citation).__name__}")
    text = citation.strip()
    match = _WIKILINK_RE.match(text)
    if match:
        text = match.group("inner")
    # Strip alias then anchor.
    text = text.split("|", 1)[0].split("#", 1)[0].strip()
    if not text:
        raise AskPayloadError(f"empty citation: {citation!r}")
    return text


def _page_exists(name: str, wiki_dir: Path) -> bool:
    slug = slugify(name)
    return (wiki_dir / f"{slug}.md").exists() or (wiki_dir / "concepts" / f"{slug}.md").exists()


def _validate_payload(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        raise AskPayloadError(f"payload must be a JSON object, got {type(payload).__name__}")
    if "citations" not in payload:
        raise AskPayloadError("payload missing required key: 'citations'")
    citations = payload["citations"]
    if not isinstance(citations, list):
        raise AskPayloadError("'citations' must be a list of strings")
    for entry in citations:
        if not isinstance(entry, str):
            raise AskPayloadError(f"citation entries must be strings, got {type(entry).__name__}")
    return citations


def check_citations(payload: Any, *, wiki_dir: Path) -> CitationCheckResult:
    """Verify every citation in ``payload`` resolves to a page in ``wiki_dir``.

    Args:
        payload: Parsed ``/ask`` JSON object with a ``citations: list[str]`` key.
        wiki_dir: Root of the Obsidian-compatible vault.

    Raises:
        AskPayloadError: Payload is not a dict or ``citations`` is malformed.
        FileNotFoundError: ``wiki_dir`` does not exist.
    """
    wiki_dir = Path(wiki_dir)
    if not wiki_dir.is_dir():
        raise FileNotFoundError(f"wiki_dir does not exist: {wiki_dir}")

    citations = _validate_payload(payload)
    resolved: list[str] = []
    broken: list[str] = []
    for raw in citations:
        name = normalize_citation(raw)
        if _page_exists(name, wiki_dir):
            resolved.append(name)
        else:
            broken.append(name)
    return CitationCheckResult(ok=not broken, resolved=resolved, broken=broken)
