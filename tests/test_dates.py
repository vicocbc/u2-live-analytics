from datetime import date

import pytest

from u2lib.dates import parse_setlistfm_date


def test_parses_dd_mm_yyyy():
    assert parse_setlistfm_date("25-09-1976") == date(1976, 9, 25)


def test_strips_whitespace():
    assert parse_setlistfm_date(" 01-01-2000 ") == date(2000, 1, 1)


@pytest.mark.parametrize("value", [None, "", "1976-09-25", "31-02-2001", "00-06-1980", "not a date"])
def test_invalid_returns_none(value):
    assert parse_setlistfm_date(value) is None
