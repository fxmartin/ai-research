"""PDF extraction via the `pdftotext` CLI (Poppler).

Shells out to `pdftotext -layout <pdf> -` and returns a structured
`{text, metadata}` payload. We prefer the Poppler binary over a Python
library because it's the same engine FX already runs locally, it's fast,
and it keeps our runtime dep surface minimal (no native wheels).

Hash semantics: `metadata.sha256` is computed over the raw PDF bytes —
**not** the extracted text — so it remains stable even if `pdftotext`
layout heuristics change between versions.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path
from typing import Any

_POPPLER_INSTALL_HINT = (
    "pdftotext not found on PATH. Install Poppler: `brew install poppler` "
    "(macOS) or your distro's `poppler-utils` package."
)


class PdfExtractionError(RuntimeError):
    """Raised when `pdftotext` cannot extract text from the given PDF."""


class PdftotextNotFoundError(PdfExtractionError):
    """Raised when the `pdftotext` binary is not on PATH."""


def _sha256_of_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _count_pages(text: str) -> int:
    """Count pages via the form-feed delimiters `pdftotext` emits.

    `pdftotext` separates pages with `\\f` (0x0C). For a non-empty output,
    page count = (number of form feeds) + 1 when the stream does not end
    in a form feed, else = number of form feeds. Empty output => 0.
    """
    if not text:
        return 0
    ff_count = text.count("\f")
    if ff_count == 0:
        return 1
    # pdftotext terminates each page with \f, so N form-feeds => N pages.
    return ff_count


def extract_pdf(path: Path | str) -> dict[str, Any]:
    """Extract text + metadata from a PDF file.

    Args:
        path: Filesystem path to a PDF.

    Returns:
        ``{"text": str, "metadata": {"pages": int, "source_type": "pdf",
        "sha256": str, "path": str}}``.

    Raises:
        PdftotextNotFoundError: `pdftotext` is not on PATH.
        PdfExtractionError: The file is missing or `pdftotext` failed.
    """
    pdf_path = Path(path)
    if not pdf_path.is_file():
        raise PdfExtractionError(f"PDF not found: {pdf_path}")

    binary = shutil.which("pdftotext")
    if binary is None:
        raise PdftotextNotFoundError(_POPPLER_INSTALL_HINT)

    try:
        completed = subprocess.run(
            [binary, "-layout", str(pdf_path), "-"],
            capture_output=True,
            check=False,
        )
    except OSError as exc:  # pragma: no cover — defensive
        raise PdfExtractionError(f"Failed to invoke pdftotext: {exc}") from exc

    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise PdfExtractionError(
            f"pdftotext failed (exit {completed.returncode}) on {pdf_path}: {stderr}"
        )

    text = completed.stdout.decode("utf-8", errors="replace")

    return {
        "text": text,
        "metadata": {
            "source_type": "pdf",
            "pages": _count_pages(text),
            "sha256": _sha256_of_file(pdf_path),
            "path": str(pdf_path.resolve()),
        },
    }
