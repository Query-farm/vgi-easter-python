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
    (`DATA_VERSION = "1.0.0"`) and `implementation_version`
    (`_implementation_version()`: the `VGI_EASTER_GIT_COMMIT` SHA if set, else
    the installed package version, else `"unknown"`).
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

## Packaging, dependencies & Python version

Requires **Python 3.13+**, managed with `uv`. This repo is a published PyPI
distribution named **`vgi-easter`** (hatchling build; see `pyproject.toml`). The
sole dependency is **`vgi-python[http]`** (PyPI; imports as `vgi`) — the `http`
extra pulls in the HTTP-server transport. The distribution name on PyPI is
`vgi-python`, *not* `vgi` (which is unregistered); the inline path sources for
the sibling checkouts have been removed.

`pyproject.toml` packages the two flat modules (`easter_worker.py`, `serve.py`)
explicitly via `[tool.hatch.build.targets.wheel] include` and registers two
console scripts:

- `vgi-easter` → `easter_worker:main` (stdio transport)
- `vgi-easter-http` → `serve:main` (HTTP server)

The same modules also carry inline PEP 723 metadata
(`vgi-python[http]>=0.8.0`), so `uv run easter_worker.py` works from a checkout
without installing.

```bash
uv build      # build wheel + sdist into dist/
uv publish    # upload to PyPI
```

## Commands

```bash
# Run the worker in stdio mode (DuckDB spawns it as a subprocess)
uv run --python 3.13 easter_worker.py

# Run the HTTP server
VGI_SIGNING_KEY=dev uv run --python 3.13 serve.py --host 0.0.0.0 --port 8000

# Unit tests (pytest), installing exactly what uv.lock pins.
uv run --frozen --python 3.13 pytest tests/ -q
```

`uv.lock` is committed (dev/CI reproducibility + the Dependabot `uv` update
target); it does not affect end users, who install via the `pyproject.toml`
ranges. `.venv/` is gitignored. `uv sync --frozen --python 3.13` materialises
the locked environment (and the `vgi-easter` console script) under `.venv/`.

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
  (asserts `1.0.0`; `implementation_version` varies by build — git SHA or
  package version — and is *not* asserted), `ATTACH ... (TYPE vgi)`, and
  `information_schema.schemata`.
- `easter_function.test` — scalar calls (`easter.main.easter_date(2025)`),
  `typeof(...) = 'DATE'`, and `easter_date(NULL::BIGINT) IS NULL`.

Run them with the DuckDB `unittest` binary built with the VGI extension, with
`VGI_EASTER_WORKER` set to a worker LOCATION (stdio command or HTTP URL).

In CI this is automated without a C++ build: `ci/run-integration.sh` drives a
prebuilt standalone `haybarn-unittest` and installs the signed `vgi` extension
from the community channel, with `ci/preprocess-require.awk` rewriting each
`require <ext>` into `INSTALL/LOAD`. `.github/workflows/ci.yml` runs the unit +
integration suite on push/PR and is reused by `publish.yml` so nothing reaches
PyPI without a green extension run. See `ci/README.md`.

### CI / publishing

- `.github/workflows/ci.yml` — unit tests + extension integration suite on
  Linux, macOS, and Windows (reusable via `workflow_call`). A `resolve-haybarn`
  job picks the latest Haybarn release at run time (nothing pinned).
- `.github/workflows/publish.yml` — on GitHub Release (or manual dispatch),
  runs `ci.yml` then `uv build && uv publish`. Token-based, no trusted
  publishing: needs the `PYPI_API_TOKEN` repo secret (passed as
  `UV_PUBLISH_TOKEN`).
- `.github/dependabot.yml` — github-actions (weekly) + Python deps via `uv.lock`
  (daily). `.github/workflows/dependabot-auto-merge.yml` squash-merges green
  Dependabot PRs after CI passes (via `workflow_run`, so no branch protection is
  required and direct pushes to `main` still work).

## ATTACH syntax

The VGI extension auto-detects transport from LOCATION:

```sql
-- stdio: DuckDB spawns the worker (installed command, or `uvx vgi-easter`;
-- from a checkout, `uv run --python 3.13 easter_worker.py`)
ATTACH 'easter' AS easter (TYPE vgi, LOCATION 'uvx vgi-easter');

-- HTTP: worker running as a server (requires httpfs, which the extension auto-loads)
ATTACH 'easter' AS easter (TYPE vgi, LOCATION 'http://localhost:8000');
```

## Environment variables

- `VGI_SIGNING_KEY` — stable key for state-token signing (HTTP server).
- `VGI_EASTER_GIT_COMMIT` — when set, overrides the catalog
  `implementation_version` (otherwise it's the installed package version).
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
