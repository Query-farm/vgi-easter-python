<p align="center">
  <img src="https://raw.githubusercontent.com/Query-farm/vgi-easter/main/assets/vgi-logo.png" alt="Vector Gateway Interface" width="420">
</p>

# vgi-easter

[![CI](https://github.com/Query-farm/vgi-easter/actions/workflows/ci.yml/badge.svg)](https://github.com/Query-farm/vgi-easter/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/vgi-easter.svg)](https://pypi.org/project/vgi-easter/)
[![Python](https://img.shields.io/pypi/pyversions/vgi-easter.svg)](https://pypi.org/project/vgi-easter/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A tiny [VGI (Vector Gateway Interface)](https://github.com/Query-farm) worker
that gives DuckDB one SQL function — `easter_date(year)` — returning the date of
Western (Gregorian) Easter Sunday. It has no external data and almost no code,
which makes it a clean, copyable example of a VGI scalar-function worker.

## Quick start

In DuckDB:

```sql
ATTACH 'easter' (TYPE 'vgi', LOCATION 'uvx vgi-easter');

SELECT easter.easter_date(2025);   -- 2025-04-20

SELECT year, easter.easter_date(year) AS easter
FROM range(2020, 2025) t(year);
```

DuckDB launches the worker for you, and `easter_date` then behaves like a native
function (a null year yields a null date). The `uvx vgi-easter` location fetches
the worker on demand; to keep it around, `pip install vgi-easter`.

## How it works

A VGI worker publishes catalogs, schemas, and functions that DuckDB can `ATTACH`
and query as if they were built in. Values cross the boundary as Apache Arrow,
so they stay columnar end to end.

This worker publishes a single function:

```
easter                                  (catalog)
└── main                                (schema)
    └── easter_date(year BIGINT) → DATE
```

The whole implementation is ~160 lines in
[`easter_worker.py`](easter_worker.py): the date calculation
(`_easter_sunday`, the Anonymous Gregorian *Computus* — pure standard library),
a `ScalarFunction` that maps an Arrow array of years to dates, and a few lines
wiring it into a catalog.

## Running it

Once installed, the package gives you one command per VGI transport:

| Command           | Transport | Use it when                                              |
| ----------------- | --------- | -------------------------------------------------------- |
| `vgi-easter`      | stdio     | DuckDB spawns the worker as a subprocess (the quickstart)|
| `vgi-easter-http` | HTTP      | you want a long-running server to attach to              |

To run over HTTP, start the server and attach to its URL:

```bash
VGI_SIGNING_KEY=dev vgi-easter-http --host 0.0.0.0 --port 8000
```

```sql
ATTACH 'easter' (TYPE 'vgi', LOCATION 'http://localhost:8000');
```

Working from a checkout instead? Both modules carry
[PEP 723](https://peps.python.org/pep-0723/) metadata, so `uv run
easter_worker.py` (stdio) and `uv run serve.py` (HTTP) run without installing
anything.

## Configuration

| Variable                          | Purpose                                                       |
| --------------------------------- | ------------------------------------------------------------- |
| `VGI_SIGNING_KEY`                 | Signing key for HTTP state tokens (required by the HTTP server).|
| `VGI_HTTP_HOST` / `VGI_HTTP_PORT` | HTTP bind address (default: all interfaces / `8000`).         |
| `VGI_EASTER_GIT_COMMIT`           | Reported as the catalog's `implementation_version`.           |
| `VGI_WORKER_DEBUG`                | Set to `1` for debug logging.                                 |

## Development

Requires Python 3.13+ and [`uv`](https://docs.astral.sh/uv/); the only
dependency is [`vgi-python`](https://pypi.org/project/vgi-python/).

```bash
uv run --frozen pytest tests/ -q
```

The `tests/` suite covers the Easter calculation (including the March 22 /
April 25 extremes) and the Arrow compute path. A separate
[sqllogictest](https://duckdb.org/dev/sqllogictest/intro) suite in `test/sql/`
drives the worker through the **real** DuckDB `vgi` extension. CI runs both on
Linux, macOS, and Windows — see [`ci/README.md`](ci/README.md).

## Releasing

`vgi-easter` is built with hatchling and published to PyPI by CI when a GitHub
Release is created (it runs the test suites, then `uv build && uv publish`). To
cut a release, bump `version` in `pyproject.toml` and publish a GitHub Release.

## License

MIT — see [LICENSE](LICENSE). Copyright 2026 Query Farm LLC — https://query.farm
