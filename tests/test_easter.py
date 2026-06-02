"""Tests for the Easter date worker."""

from __future__ import annotations

from datetime import date

import pyarrow as pa
import pytest

from easter_worker import EasterDateFunction, _easter_sunday

# Known Western (Gregorian) Easter Sunday dates.
KNOWN_EASTERS = [
    (2020, date(2020, 4, 12)),
    (2021, date(2021, 4, 4)),
    (2022, date(2022, 4, 17)),
    (2023, date(2023, 4, 9)),
    (2024, date(2024, 3, 31)),
    (2025, date(2025, 4, 20)),
    (2026, date(2026, 4, 5)),
    (2027, date(2027, 3, 28)),
    (2030, date(2030, 4, 21)),
    (1818, date(1818, 3, 22)),  # earliest possible Easter (March 22)
    (1943, date(1943, 4, 25)),  # latest possible Easter (April 25)
]


@pytest.mark.parametrize(("year", "expected"), KNOWN_EASTERS)
def test_easter_sunday(year: int, expected: date) -> None:
    assert _easter_sunday(year) == expected


def test_compute_batch() -> None:
    years = pa.array([2024, 2025, 2026], type=pa.int64())
    result = EasterDateFunction.compute(years)
    assert result.type == pa.date32()
    assert result.to_pylist() == [date(2024, 3, 31), date(2025, 4, 20), date(2026, 4, 5)]


def test_compute_null_propagation() -> None:
    years = pa.array([2025, None, 2026], type=pa.int64())
    result = EasterDateFunction.compute(years)
    assert result.to_pylist() == [date(2025, 4, 20), None, date(2026, 4, 5)]
