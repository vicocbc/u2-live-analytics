import pytest

from u2lib.geo import CONTINENT_BY_CODE, UNKNOWN, continent


@pytest.mark.parametrize(
    ("code", "name"),
    [
        ("IE", "Europe"),
        ("gb", "Europe"),
        ("UK", "Europe"),
        ("TR", "Europe"),
        ("US", "North America"),
        ("MX", "North America"),
        ("BR", "South America"),
        ("ZA", "Africa"),
        ("JP", "Asia"),
        ("AE", "Asia"),
        ("AU", "Oceania"),
        ("NZ", "Oceania"),
        (" de ", "Europe"),
    ],
)
def test_continent(code, name):
    assert continent(code) == name


@pytest.mark.parametrize("code", [None, "", "ZZ", "USA"])
def test_unknown(code):
    assert continent(code) == UNKNOWN


def test_mapping_has_no_duplicates_and_covers_iso_list():
    # 249 ISO 3166-1 alpha-2 codes plus XK (Kosovo, user-assigned but used by setlist.fm).
    assert len(CONTINENT_BY_CODE) == 250
    assert all(len(code) == 2 and code.isupper() for code in CONTINENT_BY_CODE)
