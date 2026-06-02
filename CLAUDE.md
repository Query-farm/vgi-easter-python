# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A minimal **VGI (Vector Gateway Interface)** worker that exposes one SQL scalar
function, `easter_date(year)`, returning the Western (Gregorian) Easter Sunday
date for a year. It is intentionally small — a clean reference example of a VGI
scalar function. The computation is pure standard-library arithmetic (the
Anonymous Gregorian Computus); there are no network calls or external data.

VGI lets a worker publish catalogs/schemas/functions that DuckDB can `ATTACH`
and query natively, exchanging values as Apache Arrow IPC.

## Architecture

Effectively everything lives in two files:

- **`easter_worker.py`** (~160 lines) — the whole worker:
  - `_easter_sunday(year)` — the Computus, returns `datetime.date`.
  - `EasterDateFunction(ScalarFunction)` — maps `pa.Int64Array` years to a
    `pa.date32()` array. Output type is set explicitly via
    `Returns(arrow_type=pa.date32())`; nulls propagate. `Meta` carries the
    function name (`easter_date`), description, and `FunctionExample`s used for
    catalog introspection.
  - `_EASTER_CATALOG` — `Catalog(name="easter")` with a single `main` schema
    holding `EasterDateFunction`.
  - `EasterCatalog(ReadOnlyCatalogInterface)` — advertises `data_version`
    (`DATA_VERSION = "1.0.0"`) and `implementation_version` (`GIT_COMMIT`, from
    `VGI_EASTER_GIT_COMMIT`, else `"unknown"`).
  - `EasterWorker(Worker)` — binds the catalog + interface. `main()` runs stdio
    mode; `main_http()` runs the HTTP server.
- **`serve.py`** — three lines: imports `EasterWorker` and calls `main_http()`.
  This is the HTTP entrypoint.
- **`conftest.py`** — puts the repo root on `sys.path` so tests can
  `import easter_worker` / `import serve`.

### The scalar-function pattern

A VGI scalar function subclasses `ScalarFunction` and implements a `compute`
classmethod whose params/return are annotated:

- inputs: `Annotated[pa.Int64Array, Param(doc=...)]` — Arrow array per argument.
- output: `Annotated[pa.Array[Any], Returns(arrow_type=pa.date32())]` — when the
  result type isn't the natural inference of the input, set it explicitly with
  `Returns(arrow_type=...)`.
- null handling is manual: `compute` iterates `year.to_pylist()` and maps
  `None -> None`.

## Dependencies & Python version

Requires **Python 3.13+**, managed with `uv`. Deps are declared inline as
PEP 723 script metadata in `easter_worker.py` and `serve.py`:

```python
# dependencies = ["vgi[http,oauth]", "vgi-rpc[sentry]"]
# [tool.uv.sources]
# vgi = { path = "../vgi-python" }
# vgi-rpc = { path = "../vgi-rpc" }
```

In development, `vgi` and `vgi-rpc` resolve against the sibling checkouts
`~/Development/vgi-python` and `~/Development/vgi-rpc`.

## Commands

```bash
# Run the worker in stdio mode (DuckDB spawns it as a subprocess)
uv run --python 3.13 easter_worker.py

# Run the HTTP server
VGI_SIGNING_KEY=dev uv run --python 3.13 serve.py --host 0.0.0.0 --port 8000

# Unit tests (pytest). The --rootdir/-o flags stop pytest from picking up an
# upstream pyproject that injects --mypy --ruff.
uv run --python 3.13 \
  --with pytest --with pyarrow --with ../vgi-python --with ../vgi-rpc \
  pytest tests/ --rootdir=. -o "addopts=" -q
```

There is no `.venv` checked in (it's gitignored); the `uv run --with ...`
invocation above resolves a throwaway environment. If you create a project venv,
prefer `.venv/bin/pytest` over bare `pytest`.

## Testing

### Unit tests — `tests/test_easter.py`

- `_easter_sunday` against a table of known Easter dates, including the extremes
  (1818 → Mar 22, the earliest possible; 1943 → Apr 25, the latest).
- `EasterDateFunction.compute` over an `Int64Array` batch, asserting the result
  type is `date32` and values match.
- Null propagation through `compute`.

### SQL integration tests — `test/sql/`

sqllogictest files exercised through the real DuckDB VGI extension, gated on
`require-env VGI_EASTER_WORKER`:

- `easter_catalog.test` — `vgi_catalogs()` discovery, `data_version_spec`
  (asserts `1.0.0`; `implementation_version` is the varying git SHA and is *not*
  asserted), `ATTACH ... (TYPE vgi)`, and `information_schema.schemata`.
- `easter_function.test` — scalar calls (`easter.main.easter_date(2025)`),
  `typeof(...) = 'DATE'`, and `easter_date(NULL::BIGINT) IS NULL`.

Run them with the DuckDB `unittest` binary built with the VGI extension, with
`VGI_EASTER_WORKER` set to a worker LOCATION (stdio command or HTTP URL).

## ATTACH syntax

The VGI extension auto-detects transport from LOCATION:

```sql
-- stdio: DuckDB spawns the worker
ATTACH 'easter' AS easter (TYPE vgi, LOCATION 'uv run --python 3.13 easter_worker.py');

-- HTTP: worker running as a server (requires httpfs, which the extension auto-loads)
ATTACH 'easter' AS easter (TYPE vgi, LOCATION 'http://localhost:8000');
```

## Environment variables

- `VGI_SIGNING_KEY` — stable key for state-token signing (HTTP server).
- `VGI_EASTER_GIT_COMMIT` — reported as the catalog `implementation_version`.
- `VGI_HTTP_PORT` (default 8000), `VGI_HTTP_HOST` — HTTP bind address.
- `VGI_WORKER_DEBUG=1` — debug logging.

## Conventions

- Keep the worker self-contained and dependency-light — the value of this repo is
  being a *minimal* example. Don't add network calls or external data sources.
- The catalog name (`easter`), schema (`main`), and function name (`easter_date`)
  are part of the public surface the SQL tests assert against; changing any of
  them means updating both `easter_worker.py` and `test/sql/`.
- Bump `DATA_VERSION` when the function's observable output semantics change;
  `easter_catalog.test` asserts the current value.
