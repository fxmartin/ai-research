# Contributing

## Golden-file test harness

`tests/golden/` holds byte-identical regression tests for the deterministic
toolkit verbs (`extract`, `materialize`, `index-rebuild`). Each test loads a
recorded fixture from `tests/golden/fixtures/<verb>/input/`, runs the verb,
normalizes volatile fields (ISO-8601 timestamps, machine-specific absolute
paths), and compares the result against the committed expected output under
`tests/golden/fixtures/<verb>/expected/`.

### Running

```sh
uv run pytest tests/golden/            # normal run: fails on any diff
uv run pytest tests/golden/ --update-golden   # deliberate refresh
```

`--update-golden` rewrites the expected files in place. Review the diff in
your PR — a golden churn is an API contract change.

### Adding a new golden

1. Drop input files under `tests/golden/fixtures/<verb>/input/`.
2. Write `tests/golden/test_<verb>_golden.py` using the `golden` fixture and
   the `normalize_timestamps` / `normalize_paths` helpers from
   `tests.golden.conftest`.
3. Run with `--update-golden` once to materialize expected output.
4. Run again without the flag to confirm byte-identity.
5. Commit both the test and the `expected/` file.

### Normalizing volatile fields

- Timestamps (`ingested_at`, any ISO-8601 string) → `<TIMESTAMP>` via
  `normalize_timestamps`.
- Absolute tmp paths → stable placeholders via
  `normalize_paths(text, (needle, replacement), ...)`.

Keep normalization minimal: the point of a golden is to detect real
regressions, so anything the verb genuinely controls should flow through
unmodified.
