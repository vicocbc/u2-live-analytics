import datetime as dt

import pytest

from u2lib.catalog import (
    SingleInfo,
    album_rank,
    earliest_single_by_key,
    resolve_album_id,
    resolve_track_song_id,
    singles_history,
    synthetic_song_id,
)

D = dt.date

ALBUMS = [
    {"album_id": "rg-cdl", "title": "Carnaval de luz", "release_date": D(2026, 11, 13), "is_studio": True},
    {"album_id": "rg-doa", "title": "Days of Ash EP", "release_date": D(2026, 2, 18), "is_studio": False},
    {"album_id": "rg-el", "title": "Easter Lily EP", "release_date": D(2026, 4, 3), "is_studio": False},
    {"album_id": "rg-uf-single", "title": "The Unforgettable Fire", "release_date": D(1985, 4, 22), "is_studio": False},
    {"album_id": "rg-uf", "title": "The Unforgettable Fire", "release_date": D(1984, 10, 1), "is_studio": True},
    {"album_id": "rg-x2", "title": "Twin", "release_date": None, "is_studio": False},
    {"album_id": "rg-x1", "title": "Twin", "release_date": None, "is_studio": False},
]


def test_album_rank_prefers_studio_then_date_then_id():
    ranked = sorted(ALBUMS, key=album_rank)
    assert [a["album_id"] for a in ranked[:2]] == ["rg-uf", "rg-cdl"]
    assert [a["album_id"] for a in ranked[-2:]] == ["rg-x1", "rg-x2"]


@pytest.mark.parametrize(
    ("rg_id", "title", "expected"),
    [
        ("rg-doa", "Days of Ash", ("rg-doa", "id")),  # title alone would not match ("... EP")
        ("RG-EL ", "Easter Lily", ("rg-el", "id")),  # id compared trimmed and case-insensitive
        (None, "Carnaval de Luz", ("rg-cdl", "title")),  # casing differs from MusicBrainz
        ("", "The Unforgettable Fire", ("rg-uf", "title")),  # studio album beats the single
        ("rg-missing", "Carnaval de Luz", ("rg-cdl", "title")),  # unknown id falls back to the title
        (None, "Twin", ("rg-x1", "title")),  # no studio, no date: lowest id
        (None, "Days of Ash", (None, "unresolved")),
        ("rg-missing", None, (None, "unresolved")),
        (None, None, (None, "unresolved")),
    ],
)
def test_resolve_album_id(rg_id, title, expected):
    assert resolve_album_id(ALBUMS, rg_id, title) == expected


def test_synthetic_song_id():
    assert synthetic_song_id("get back to now") == "u2:get back to now"


RELEASE_WORKS = {"coexist i will bless the lord at all times": ["w-coexist-release"]}
WORKS = {
    "coexist i will bless the lord at all times": ["w-coexist-browse"],
    "song of the future": ["w-sotf"],
    "street of dreams": ["w-sod"],
}


@pytest.mark.parametrize(
    ("title", "override", "expected"),
    [
        ("COEXIST (I Will Bless the Lord at All Times?)", None, ("w-coexist-release", "release_work")),
        ("Song of the Future", None, ("w-sotf", "work")),
        ("Street of Dreams", "original", ("u2:street of dreams", "override")),
        ("Street of Dreams", " Original ", ("u2:street of dreams", "override")),
        ("Song of the Future", "w-other", ("w-other", "override")),
        ("Song of the Future", "ignore", ("w-sotf", "work")),
        ("Get Back to Now", None, ("u2:get back to now", "synthetic")),
        ("Go (Carnaval de Luz)", "", ("u2:go carnaval de luz", "synthetic")),
    ],
)
def test_resolve_track_song_id(title, override, expected):
    assert resolve_track_song_id(title, override, RELEASE_WORKS, WORKS) == expected


def test_resolve_track_song_id_without_indexes():
    assert resolve_track_song_id("La Reina") == ("u2:la reina", "synthetic")


def test_resolve_track_song_id_empty_title():
    with pytest.raises(ValueError):
        resolve_track_song_id("  ")


def test_earliest_single_by_key():
    singles = [
        ("Pride (In the Name of Love)", D(1984, 9, 3)),
        ("Pride (In the Name of Love)", D(2023, 1, 1)),
        ("Pride (In the Name of Love)", None),
        ("One", None),
        ("One", D(1992, 2, 24)),
        ("Desire", None),
        ("Fireflies", D(2026, 1, 1)),
        ("", D(2000, 1, 1)),
    ]
    assert earliest_single_by_key(singles, excluded_titles=["fireflies"]) == {
        "pride in the name of love": D(1984, 9, 3),
        "one": D(1992, 2, 24),
        "desire": None,
    }


def test_singles_history_orders_within_album():
    songs = [
        {"song_id": "w-pride", "title": "Pride (In the Name of Love)", "album_id": "uf"},
        {"song_id": "w-uf", "title": "The Unforgettable Fire", "album_id": "uf"},
        {"song_id": "w-bad", "title": "Bad", "album_id": "uf"},
        {"song_id": "w-one", "title": "One", "album_id": "ab"},
        {"song_id": "w-mys", "title": "Mysterious Ways", "album_id": "ab"},
        {"song_id": "w-undated", "title": "Undated", "album_id": "ab"},
        {"song_id": "w-nosong", "title": "Fireflies", "album_id": "ab"},
        {"song_id": "w-noalbum", "title": "Sweetest Thing", "album_id": None},
    ]
    singles = [
        ("The Unforgettable Fire", D(1985, 4, 22)),
        ("Pride", D(1990, 1, 1)),  # different key: not Pride (In the Name of Love)
        ("Pride (In the Name of Love)", D(1984, 9, 3)),
        ("Mysterious Ways", D(1991, 11, 24)),
        ("One", D(1992, 2, 24)),
        ("Undated", None),
        ("Sweetest Thing", D(1998, 10, 19)),
        ("Fireflies", D(2026, 5, 1)),
        ("Yeah, Yeah, Yeah, Yeah, Yeah", D(2026, 6, 1)),
    ]
    result = singles_history(songs, singles, excluded_titles=["Fireflies", "Yeah, Yeah, Yeah, Yeah, Yeah"])
    assert result == {
        "w-pride": SingleInfo(D(1984, 9, 3), 1),
        "w-uf": SingleInfo(D(1985, 4, 22), 2),
        "w-mys": SingleInfo(D(1991, 11, 24), 1),
        "w-one": SingleInfo(D(1992, 2, 24), 2),
        "w-undated": SingleInfo(None, 3),
    }


def test_singles_history_empty():
    assert singles_history([], []) == {}
