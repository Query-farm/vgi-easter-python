# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "vgi-python[http]>=0.8.0",
# ]
# ///
"""VGI worker that computes the date of Easter Sunday for a given year.

Provides a single scalar function, ``easter_date(year)``, that returns the
Gregorian (Western) date of Easter Sunday using the Anonymous Gregorian
algorithm (a.k.a. the Meeus/Jones/Butcher Computus). Pure standard library —
no external dependencies needed for the calculation.

Usage:
    uv run easter_worker.py

    SELECT easter_date(2025);
    SELECT year, easter_date(year) AS easter
    FROM range(2020, 2031) t(year);
"""

from __future__ import annotations

import dataclasses
import json
import os
from datetime import date
from importlib.metadata import PackageNotFoundError, version
from typing import Annotated, Any

import pyarrow as pa

from vgi import Worker
from vgi.arguments import Param, Returns
from vgi.catalog import Catalog, ReadOnlyCatalogInterface, Schema
from vgi.catalog.catalog_interface import CatalogAttachResult, CatalogInfo
from vgi.metadata import FunctionExample
from vgi.scalar_function import ScalarFunction

SOURCE_URL = "https://github.com/Query-farm/vgi-easter-python"

# The resolved data version the catalog reports (see ``EasterCatalog``); the
# computus algorithm's observable output is stable, so this is pinned at 1.0.0.
DATA_VERSION = "1.0.0"

# ``data_version_spec`` must be a semver *range* (VGI005), not a bare version.
DATA_VERSION_SPEC = ">=1.0.0,<2.0.0"


def _keywords(keywords: str) -> str:
    """Serialize a comma-separated keyword string as a JSON array string.

    ``vgi.keywords`` must be a JSON array of strings (VGI138), so this splits on
    commas, trims whitespace, drops empties, and JSON-encodes the result.
    """
    items = [k.strip() for k in keywords.split(",") if k.strip()]
    return json.dumps(items)


def _implementation_version() -> str:
    """Version reported as the catalog's ``implementation_version``.

    Prefer an explicit git SHA from ``VGI_EASTER_GIT_COMMIT`` (handy in CI/dev
    builds); otherwise fall back to the installed package version, so a normal
    ``pip install vgi-easter`` reports the release version (e.g. ``0.1.2``).
    ``"unknown"`` only if neither is available (e.g. an uninstalled checkout).
    """
    sha = os.environ.get("VGI_EASTER_GIT_COMMIT")
    if sha:
        return sha
    try:
        return version("vgi-easter")
    except PackageNotFoundError:
        return "unknown"


IMPLEMENTATION_VERSION = _implementation_version()


def _easter_sunday(year: int) -> date:
    """Return the Gregorian date of Easter Sunday for ``year``.

    Uses the Anonymous Gregorian algorithm (Meeus/Jones/Butcher Computus),
    valid for any year in the Gregorian calendar (1583 onward).
    """
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month = (h + ell - 7 * m + 114) // 31
    day = ((h + ell - 7 * m + 114) % 31) + 1
    return date(year, month, day)


class EasterDateFunction(ScalarFunction):
    """Return the date of Easter Sunday for a given year.

    This example demonstrates a minimal scalar function with:
    - a single column input (``pa.Int64Array`` -> inferred ``int64``)
    - an explicit ``date32`` output type via ``Returns(arrow_type=...)``
    - null propagation (a null year yields a null date)

    Example:
        SQL:    SELECT easter_date(year) FROM events
        Input:  year=[2024, 2025, 2026]
        Output: result=[2024-03-31, 2025-04-20, 2026-04-05]

    """

    class Meta:
        """Function metadata."""

        name = "easter_date"
        description = "Date of Western (Gregorian) Easter Sunday for a given year"
        categories = ["calendar", "date"]
        tags = {
            "vgi.title": "Easter Sunday Date",
            "vgi.doc_llm": (
                "Compute the date of **Western (Gregorian) Easter Sunday** for a year. "
                "`year` is a **BIGINT** (e.g. `2025`), not a DATE literal — pass the "
                "integer year, not a date. Returns a **DATE** that is always a Sunday "
                "falling between March 22 and April 25 inclusive (the only possible range "
                "for Easter). A NULL year yields NULL. This is the Western/Catholic-"
                "Protestant Easter computed with the Gregorian computus; it is **not** the "
                "Orthodox/Julian Easter, which can differ by up to five weeks. The result "
                "is reliable for years in the Gregorian calendar (1583 onward, after the "
                "1582 reform). For earlier years the function still returns a value, but it "
                "is the *proleptic* Gregorian date (the formula extended backward) and does "
                "not correspond to the Julian-calendar Easter actually observed at the time "
                "— it never errors or returns NULL for an in-range integer. Use it to "
                "compute, label, or filter on Easter (e.g. holiday calendars, derived dates "
                "like Good Friday = Easter - 2, or Pentecost = Easter + 49)."
            ),
            "vgi.doc_md": (
                "## easter_date(year)\n\n"
                "Returns the **DATE** of Western (Gregorian) Easter Sunday for the given "
                "`year`.\n\n"
                "- **`year`** — `BIGINT` (the integer year, e.g. `2025`), **not** a DATE "
                "literal.\n"
                "- **Returns** — `DATE`, always a **Sunday** between **March 22 and April "
                "25** inclusive. `NULL` year yields `NULL`.\n\n"
                "Computed with the Anonymous Gregorian algorithm (Meeus/Jones/Butcher "
                "computus). This is the **Western** Easter (Catholic/Protestant), **not** "
                "the Orthodox/Julian Easter.\n\n"
                "Reliable for **1583 onward** (after the 1582 Gregorian reform). For earlier "
                "years it returns the *proleptic* Gregorian date (the formula extended "
                "backward), which differs from the Julian-calendar Easter historically "
                "observed; it never errors or returns NULL for an in-range integer.\n\n"
                "```sql\n"
                "SELECT easter.main.easter_date(2025);            -- 2025-04-20\n"
                "SELECT easter.main.easter_date(2025) - 2;        -- Good Friday\n"
                "```"
            ),
            "vgi.keywords": _keywords(
                "easter, easter sunday, computus, gregorian easter, western easter, "
                "holiday, liturgical, movable feast, good friday, pentecost, calendar, date"
            ),
            "domain": "calendar",
            "category": "computus",
            "topic": "holidays",
            "vgi.executable_examples": json.dumps(
                [
                    {
                        "description": "Easter Sunday 2025 is 2025-04-20.",
                        "sql": "SELECT easter.main.easter_date(2025) AS easter",
                        "expected_result": [{"easter": "2025-04-20"}],
                    },
                    {
                        "description": "The result is always a Sunday.",
                        "sql": "SELECT dayname(easter.main.easter_date(2030)) AS dow",
                        "expected_result": [{"dow": "Sunday"}],
                    },
                ]
            ),
        }
        examples = [
            FunctionExample(
                sql="SELECT easter.main.easter_date(2025)",
                description="Easter Sunday in 2025 (2025-04-20)",
            ),
            FunctionExample(
                sql="SELECT year, easter.main.easter_date(year) AS easter FROM range(2020, 2031) t(year)",
                description="Easter dates for 2020 through 2030",
            ),
            FunctionExample(
                sql="SELECT easter.main.easter_date(2025) - 2 AS good_friday",
                description="Good Friday is two days before Easter (2025-04-18)",
            ),
            FunctionExample(
                sql="SELECT easter.main.easter_date(2025) + 49 AS pentecost",
                description="Pentecost is 49 days after Easter (2025-06-08)",
            ),
            FunctionExample(
                sql="SELECT dayname(easter.main.easter_date(2025)) AS dow",
                description="Easter is always a Sunday",
            ),
        ]

    @classmethod
    def compute(
        cls,
        year: Annotated[
            pa.Int64Array,
            Param(
                doc=(
                    "The year to compute Easter for, e.g. 2025 (pass the year itself, "
                    "not a date). Reliable for the Gregorian calendar (>= 1583); earlier "
                    "years return proleptic-Gregorian results. NULL yields NULL."
                )
            ),
        ],
    ) -> Annotated[pa.Array[Any], Returns(arrow_type=pa.date32())]:
        """Compute Easter Sunday for each input year."""
        return pa.array(
            [None if y is None else _easter_sunday(int(y)) for y in year.to_pylist()],
            type=pa.date32(),
        )


_CATALOG_DOC_LLM = (
    "Computes the date of **Western (Gregorian) Easter Sunday** for a given year. "
    "A single scalar function, `easter_date(year)`, takes a BIGINT year and returns "
    "the DATE of Easter Sunday (always a Sunday between March 22 and April 25). "
    "Use it to find, label, or filter on Easter and dates derived from it (Good "
    "Friday = Easter - 2, Ash Wednesday, Pentecost = Easter + 49, etc.). "
    "Scope: Western/Gregorian Easter only — this is **not** the Orthodox/Julian "
    "Easter (which can differ by up to five weeks). Reliable for years in the "
    "Gregorian calendar (1583 onward, after the 1582 reform); earlier years return "
    "proleptic-Gregorian results rather than the Julian Easter observed at the time. "
    "Contains a single `main` schema."
)

_CATALOG_DOC_MD = (
    "# easter\n\n"
    "Computes the date of **Western (Gregorian) Easter Sunday** using the computus "
    "(the algorithm for dating Easter) — specifically the Anonymous Gregorian / "
    "Meeus-Jones-Butcher algorithm. Pure arithmetic, no external data.\n\n"
    "Exposes one scalar function in the single `main` schema:\n\n"
    "- **`easter_date(year)`** — given a `BIGINT` year, returns the `DATE` of Easter "
    "Sunday (always a Sunday between March 22 and April 25).\n\n"
    "**Scope:** Western/Gregorian Easter only. This is **not** the Orthodox/Julian "
    "Easter, which uses the Julian calendar and can fall up to five weeks later.\n\n"
    "**Valid range:** reliable for **1583 onward** (after the 1582 Gregorian "
    "reform). For earlier years the function returns the *proleptic* Gregorian date "
    "(the formula extended backward), not the Julian-calendar Easter historically "
    "observed.\n\n"
    "```sql\n"
    "SELECT easter.main.easter_date(2025);   -- 2025-04-20\n"
    "```"
)

_SCHEMA_DOC_LLM = (
    "The single schema for the `easter` worker. It holds `easter_date(year)`, which "
    "computes the date of Easter Sunday — the Western (Gregorian) date, **not** the "
    "Orthodox/Julian one. `easter_date` is the entry point: pass a BIGINT year, get "
    "back the DATE of Easter Sunday (always a Sunday between March 22 and April 25; "
    "a NULL year yields NULL). Reliable for 1583 onward; earlier years return "
    "proleptic-Gregorian results, not the Julian Easter observed at the time. "
    "Example: `SELECT easter.main.easter_date(2025)` returns 2025-04-20."
)

_SCHEMA_DOC_MD = (
    "The single schema for the `easter` worker. It contains one scalar function, "
    "**`easter_date(year)`**, which computes the date of Easter Sunday for a given "
    "year. The result is the **Western (Gregorian)** Easter date (assumes the "
    "Gregorian calendar), **not** the Orthodox/Julian Easter. The returned DATE is "
    "always a Sunday between March 22 and April 25; a NULL year yields NULL. "
    "Reliable for 1583 onward (after the 1582 reform); earlier years return the "
    "*proleptic* Gregorian date.\n\n"
    "```sql\n"
    "SELECT easter.main.easter_date(2025);   -- 2025-04-20\n"
    "```"
)

_SCHEMA_EXAMPLE_QUERIES = (
    "SELECT easter.main.easter_date(2025);\n"
    "SELECT year, easter.main.easter_date(year) AS easter "
    "FROM range(2020, 2031) t(year);\n"
    "SELECT easter.main.easter_date(2025) - 2 AS good_friday;"
)

_EASTER_CATALOG = Catalog(
    name="easter",
    default_schema="main",
    comment="Western (Gregorian) Easter Sunday date for a given year (computus)",
    tags={
        "vgi.title": "Western (Gregorian) Easter Sunday",
        "vgi.keywords": _keywords(
            "easter, easter sunday, computus, gregorian easter, western easter, "
            "holiday, liturgical, movable feast, good friday, pentecost, calendar, date"
        ),
        "vgi.doc_llm": _CATALOG_DOC_LLM,
        "vgi.doc_md": _CATALOG_DOC_MD,
        "vgi.author": "Query.Farm",
        "vgi.copyright": "Copyright 2026 Query Farm LLC - https://query.farm",
        "vgi.license": "MIT",
        "vgi.support_contact": "https://github.com/Query-farm/vgi-easter-python/issues",
        "vgi.support_policy_url": "https://github.com/Query-farm/vgi-easter-python/blob/main/README.md",
    },
    source_url=SOURCE_URL,
    schemas=[
        Schema(
            name="main",
            comment="Computes the date of Western (Gregorian) Easter Sunday; holds easter_date",
            tags={
                "vgi.title": "Easter — main",
                "vgi.keywords": _keywords(
                    "easter, easter sunday, easter_date, computus, gregorian, "
                    "western easter, holiday, calendar, date"
                ),
                "domain": "calendar",
                "category": "computus",
                "topic": "holidays",
                "vgi.example_queries": _SCHEMA_EXAMPLE_QUERIES,
                "vgi.doc_llm": _SCHEMA_DOC_LLM,
                "vgi.doc_md": _SCHEMA_DOC_MD,
            },
            functions=[
                EasterDateFunction,
            ],
        ),
    ],
)


class EasterCatalog(ReadOnlyCatalogInterface):
    """Easter catalog advertising a data version and an implementation version.

    ``implementation_version`` is the git SHA (``VGI_EASTER_GIT_COMMIT``) when
    set, else the installed package version. See ``_implementation_version``.
    """

    catalog = _EASTER_CATALOG
    catalog_name = _EASTER_CATALOG.name

    def catalogs(self) -> list[CatalogInfo]:
        return [
            CatalogInfo(
                name=self._effective_catalog_name,
                implementation_version=IMPLEMENTATION_VERSION,
                data_version_spec=DATA_VERSION_SPEC,
                source_url=SOURCE_URL,
                attach_option_specs=[spec.serialize() for spec in self.attach_option_specs],
            )
        ]

    def catalog_attach(self, **kwargs: Any) -> CatalogAttachResult:
        result = super().catalog_attach(**kwargs)
        return dataclasses.replace(
            result,
            resolved_data_version=DATA_VERSION,
            resolved_implementation_version=IMPLEMENTATION_VERSION,
        )


class EasterWorker(Worker):
    """Worker process hosting the Easter date scalar function."""

    catalog = _EASTER_CATALOG
    catalog_interface = EasterCatalog


def main() -> None:
    """Run the Easter worker process."""
    EasterWorker.main()


if __name__ == "__main__":
    main()
