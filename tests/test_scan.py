"""Tests for the `scan` raw/ inbox verb (Story 01.3-001)."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_research.cli import app
from ai_research.scan import scan_raw
from ai_research.state import State, save_state

runner = CliRunner()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _age_file(path: Path, seconds: float) -> None:
    """Backdate mtime/atime of ``path`` by ``seconds``."""
    target = time.time() - seconds
    os.utime(path, (target, target))


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    d = tmp_path / "raw"
    d.mkdir()
    return d


def test_scan_lists_old_enough_files(raw_dir: Path) -> None:
    a = raw_dir / "a.pdf"
    a.write_bytes(b"hello a")
    _age_file(a, 60)

    b = raw_dir / "b.md"
    b.write_bytes(b"hello b")
    _age_file(b, 60)

    results = scan_raw(raw_dir)
    paths = {Path(p).name for p in results}
    assert paths == {"a.pdf", "b.md"}


def test_scan_excludes_fresh_files(raw_dir: Path) -> None:
    fresh = raw_dir / "fresh.txt"
    fresh.write_bytes(b"brand new")
    # Do not backdate — mtime ~= now.

    old = raw_dir / "old.txt"
    old.write_bytes(b"seasoned")
    _age_file(old, 60)

    results = scan_raw(raw_dir, min_age_seconds=5)
    names = {Path(p).name for p in results}
    assert names == {"old.txt"}


def test_scan_configurable_min_age(raw_dir: Path) -> None:
    f = raw_dir / "x.txt"
    f.write_bytes(b"x")
    _age_file(f, 2)

    # Default (5s) → excluded
    assert scan_raw(raw_dir) == []

    # Lower threshold → included
    results = scan_raw(raw_dir, min_age_seconds=1)
    assert len(results) == 1 and Path(results[0]).name == "x.txt"


def test_scan_skip_known_excludes_hashed_sources(raw_dir: Path, tmp_path: Path) -> None:
    known = raw_dir / "known.pdf"
    known_bytes = b"already ingested"
    known.write_bytes(known_bytes)
    _age_file(known, 60)

    new = raw_dir / "new.pdf"
    new.write_bytes(b"fresh content")
    _age_file(new, 60)

    state = State(sources={_sha256_bytes(known_bytes): "wiki/known.md"})

    results = scan_raw(raw_dir, skip_known=True, state=state)
    names = {Path(p).name for p in results}
    assert names == {"new.pdf"}


def test_scan_without_skip_known_keeps_hashed(raw_dir: Path) -> None:
    f = raw_dir / "dupe.pdf"
    data = b"dup"
    f.write_bytes(data)
    _age_file(f, 60)

    state = State(sources={_sha256_bytes(data): "wiki/dupe.md"})

    results = scan_raw(raw_dir, skip_known=False, state=state)
    assert len(results) == 1


def test_scan_ignores_dotfiles(raw_dir: Path) -> None:
    # Regression: #30 — .gitkeep and other dotfiles are never real sources
    # and must be filtered out before the mtime / skip-known checks.
    (raw_dir / ".gitkeep").write_bytes(b"")
    (raw_dir / ".DS_Store").write_bytes(b"junk")
    real = raw_dir / "real.md"
    real.write_bytes(b"content")
    for p in raw_dir.iterdir():
        _age_file(p, 60)

    results = scan_raw(raw_dir)
    names = {Path(p).name for p in results}
    assert names == {"real.md"}


def test_scan_ignores_directories(raw_dir: Path) -> None:
    (raw_dir / "subdir").mkdir()
    f = raw_dir / "file.md"
    f.write_bytes(b"hi")
    _age_file(f, 60)

    results = scan_raw(raw_dir)
    names = {Path(p).name for p in results}
    assert names == {"file.md"}


def test_scan_missing_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        scan_raw(tmp_path / "nope")


def test_scan_results_sorted(raw_dir: Path) -> None:
    for name in ["c.md", "a.md", "b.md"]:
        p = raw_dir / name
        p.write_bytes(name.encode())
        _age_file(p, 60)
    results = [Path(p).name for p in scan_raw(raw_dir)]
    assert results == sorted(results)


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------


def test_cli_scan_prints_paths_one_per_line(raw_dir: Path) -> None:
    a = raw_dir / "a.md"
    a.write_bytes(b"a")
    _age_file(a, 60)
    b = raw_dir / "b.md"
    b.write_bytes(b"b")
    _age_file(b, 60)

    result = runner.invoke(app, ["scan", str(raw_dir)])
    assert result.exit_code == 0, result.stdout
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lines) == 2
    assert all(ln.endswith(".md") for ln in lines)


def test_cli_scan_json_flag(raw_dir: Path) -> None:
    a = raw_dir / "a.md"
    a.write_bytes(b"a")
    _age_file(a, 60)

    result = runner.invoke(app, ["scan", str(raw_dir), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    assert len(payload) == 1
    assert payload[0].endswith("a.md")


def test_cli_scan_min_age_option(raw_dir: Path) -> None:
    f = raw_dir / "fresh.md"
    f.write_bytes(b"fresh")
    _age_file(f, 2)

    # Default: excluded
    r1 = runner.invoke(app, ["scan", str(raw_dir)])
    assert r1.exit_code == 0
    assert r1.stdout.strip() == ""

    # Lowered: included
    r2 = runner.invoke(app, ["scan", str(raw_dir), "--min-age-seconds", "1"])
    assert r2.exit_code == 0
    assert "fresh.md" in r2.stdout


def test_cli_scan_skip_known_with_state(raw_dir: Path, tmp_path: Path) -> None:
    known = raw_dir / "known.md"
    known_bytes = b"ingested"
    known.write_bytes(known_bytes)
    _age_file(known, 60)

    new = raw_dir / "new.md"
    new.write_bytes(b"unseen")
    _age_file(new, 60)

    state_path = tmp_path / "state.json"
    save_state(state_path, State(sources={_sha256_bytes(known_bytes): "wiki/known.md"}))

    result = runner.invoke(
        app,
        [
            "scan",
            str(raw_dir),
            "--skip-known",
            "--state-file",
            str(state_path),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "new.md" in result.stdout
    assert "known.md" not in result.stdout


def test_cli_scan_missing_dir_exit_2(tmp_path: Path) -> None:
    result = runner.invoke(app, ["scan", str(tmp_path / "missing")])
    assert result.exit_code == 2
