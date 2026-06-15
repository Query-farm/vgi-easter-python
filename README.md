# vgi-easter

A minimal [VGI (Vector Gateway Interface)](https://github.com/Query-farm) worker
that computes the date of **Western (Gregorian) Easter Sunday** for a given year
and exposes it to DuckDB as a SQL scalar function.

```sql
ATTACH 'easter' AS easter (TYPE vgi, LOCATION 'uvx vgi-easter');

SELECT easter_date(2025);
-- 2025-04-20

SELECT year, easter_date(year) AS easter
FROM range(2020, 2031) t(year);
-- 2020  2020-04-12
-- 2021  2021-04-04
-- ...
```

The function `easter_date(year)` takes a `BIGINT` year and returns a `DATE`,
computed with the Anonymous Gregorian algorithm (the Meeus/Jones/Butcher
*Computus*). It is pure standard-library arithmetic — no network calls, no
external data — which makes this repo a clean, self-contained example of a VGI
scalar-function worker.

## How it works

VGI lets a worker process publish catalogs, schemas, and functions that DuckDB
can `ATTACH` and query as if they were native. Data crosses the boundary as
Apache Arrow IPC, so values stay columnar end to end.

This worker publishes one catalog:

```
easter            (catalog,  data version 1.0.0)
└── main          (schema)
    └── easter_date(year BIGINT) -> DATE
```

`year` propagates nulls — a null year yields a null date.

The entire implementation lives in [`easter_worker.py`](easter_worker.py):

- `_easter_sunday(year)` — the Computus, returning a `datetime.date`.
- `EasterDateFunction` — a `ScalarFunction` mapping an `Int64Array` of years to
  a `date32` array, with metadata and SQL examples for catalog introspection.
- `EasterCatalog` / `EasterWorker` — wire the function into a VGI catalog that
  advertises a stable `data_version` (`1.0.0`) and a git-SHA
  `implementation_version` (from `VGI_EASTER_GIT_COMMIT`).

## Requirements

- Python **3.13+**
- [`uv`](https://docs.astral.sh/uv/) (recommended) or `pip`

The only dependency is [`vgi-python`](https://pypi.org/project/vgi-python/) (the
`http` extra adds the HTTP-server transport); it is published on PyPI, so no
sibling checkouts are needed.

## Installing

```bash
# Install from PyPI (provides the vgi-easter and vgi-easter-http commands)
pip install vgi-easter
# or run it ad hoc without installing
uvx vgi-easter
```

## Running

The worker supports both VGI transports. Two console scripts are installed:
`vgi-easter` (stdio) and `vgi-easter-http` (HTTP server).

### stdio (DuckDB spawns the worker)

DuckDB runs the worker as a subprocess and talks to it over stdin/stdout. No
server to manage — point the LOCATION at the installed command (or `uvx
vgi-easter` to fetch it on demand):

```sql
ATTACH 'easter' AS easter (TYPE vgi, LOCATION 'uvx vgi-easter');
SELECT easter_date(2025);
DETACH easter;
```

### HTTP

Start the worker as an HTTP server (`vgi-easter-http` calls
`EasterWorker.main_http()`):

```bash
VGI_SIGNING_KEY=dev vgi-easter-http --host 0.0.0.0 --port 8000
```

Then attach over HTTP (the VGI extension auto-loads `httpfs`):

```sql
ATTACH 'easter' AS easter (TYPE vgi, LOCATION 'http://localhost:8000');
SELECT easter_date(2025);
```

### From a source checkout

The two modules also carry inline [PEP 723](https://peps.python.org/pep-0723/)
metadata, so you can run them directly without installing:

```bash
uv run --python 3.13 easter_worker.py            # stdio
VGI_SIGNING_KEY=dev uv run --python 3.13 serve.py --host 0.0.0.0 --port 8000  # HTTP
```

## Testing

### Unit tests (pytest)

The `tests/` suite checks the Computus against known Easter dates (including the
March 22 / April 25 extremes) and the Arrow `compute()` path including null
propagation:

```bash
uv run --python 3.13 \
  --with pytest --with vgi-python \
  pytest tests/ --rootdir=. -o "addopts=" -q
```

The `--rootdir=. -o "addopts="` flags keep pytest from picking up an upstream
`pyproject.toml` that injects `--mypy --ruff`. `conftest.py` puts the repo root
on `sys.path` so the tests can `import easter_worker`.

### SQL integration tests (sqllogictest)

`test/sql/` contains [sqllogictest](https://duckdb.org/dev/sqllogictest/intro)
files that run against the worker through the real DuckDB VGI extension:

- `easter_catalog.test` — catalog discovery, `data_version_spec`, `ATTACH` and
  schema introspection.
- `easter_function.test` — scalar evaluation, the `DATE` result type, and null
  propagation.

Both are gated on `require-env VGI_EASTER_WORKER`, so point that at a worker
LOCATION (a stdio command or an HTTP URL) and run them with the DuckDB
`unittest` binary built with the VGI extension.

## Environment variables

| Variable                  | Purpose                                                              |
| ------------------------- | ------------------------------------------------------------------- |
| `VGI_SIGNING_KEY`         | Stable key for state-token signing (required for the HTTP server).  |
| `VGI_EASTER_GIT_COMMIT`   | Git SHA reported as the catalog's `implementation_version`.         |
| `VGI_HTTP_PORT` / `VGI_HTTP_HOST` | HTTP bind address (defaults: `8000` / all interfaces).      |
| `VGI_WORKER_DEBUG`        | Set to `1` for debug logging.                                       |

## Publishing

This repo is a packaged distribution (`vgi-easter`) built with hatchling:

```bash
uv build                       # writes dist/*.whl and dist/*.tar.gz
uv publish                     # upload to PyPI (needs a token)
```

## License

MIT — see [LICENSE](LICENSE). Copyright 2026 Query Farm LLC — https://query.farm
