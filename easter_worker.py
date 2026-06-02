# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "vgi[http,oauth]",
#     "vgi-rpc[sentry]",
# ]
#
# [tool.uv.sources]
# vgi = { path = "../vgi-python" }
# vgi-rpc = { path = "../vgi-rpc" }
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
import os
from datetime import date
from typing import Annotated, Any

import pyarrow as pa

from vgi import Worker
from vgi.arguments import Param, Returns
from vgi.catalog import Catalog, ReadOnlyCatalogInterface, Schema
from vgi.catalog.catalog_interface import CatalogAttachResult, CatalogInfo
from vgi.metadata import FunctionExample
from vgi.scalar_function import ScalarFunction

DATA_VERSION = "1.0.0"
GIT_COMMIT = os.environ.get("VGI_EASTER_GIT_COMMIT") or "unknown"


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
        examples = [
            FunctionExample(
                sql="SELECT easter_date(2025)",
                description="Easter Sunday in 2025 (2025-04-20)",
            ),
            FunctionExample(
                sql="SELECT year, easter_date(year) AS easter FROM range(2020, 2031) t(year)",
                description="Easter dates for 2020 through 2030",
            ),
        ]

    @classmethod
    def compute(
        cls,
        year: Annotated[pa.Int64Array, Param(doc="Year, e.g. 2025 (Gregorian, >= 1583)")],
    ) -> Annotated[pa.Array[Any], Returns(arrow_type=pa.date32())]:
        """Compute Easter Sunday for each input year."""
        return pa.array(
            [None if y is None else _easter_sunday(int(y)) for y in year.to_pylist()],
            type=pa.date32(),
        )


_EASTER_CATALOG = Catalog(
    name="easter",
    default_schema="main",
    schemas=[
        Schema(
            name="main",
            comment="Computus: the date of Western (Gregorian) Easter Sunday",
            functions=[
                EasterDateFunction,
            ],
        ),
    ],
)


class EasterCatalog(ReadOnlyCatalogInterface):
    """Easter catalog that advertises a data version and git-SHA implementation version."""

    catalog = _EASTER_CATALOG
    catalog_name = _EASTER_CATALOG.name

    def catalogs(self) -> list[CatalogInfo]:
        return [
            CatalogInfo(
                name=self._effective_catalog_name,
                implementation_version=GIT_COMMIT,
                data_version_spec=DATA_VERSION,
                attach_option_specs=[spec.serialize() for spec in self.attach_option_specs],
            )
        ]

    def catalog_attach(self, **kwargs: Any) -> CatalogAttachResult:
        result = super().catalog_attach(**kwargs)
        return dataclasses.replace(
            result,
            resolved_data_version=DATA_VERSION,
            resolved_implementation_version=GIT_COMMIT,
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
