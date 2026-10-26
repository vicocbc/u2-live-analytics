import datetime as dt

import pytest

from u2lib.features import (
    NO_TOUR,
    ROLE_CATALOG,
    ROLE_COMPANION,
    ROLE_PROMOTED,
    LeakageError,
    SongInfo,
    Tour,
    assert_no_leakage,
    build_features,
    build_shows,
    build_song_infos,
    build_tours,
    is_low_precision_date,
    is_played,
    is_title_track,
    previous_album_tour,
    qualifying_tours,
    single_known_before,
    singles_as_of,
    tour_profile,
)

D = dt.date


# ---------------------------------------------------------------------------------------------------------------------
# Leakage


def test_assert_no_leakage_passes_and_counts():
    assert assert_no_leakage([D(2020, 1, 1), None, D(2020, 12, 31)], D(2021, 1, 1)) == 2


def test_assert_no_leakage_fails_on_cutoff_day():
    with pytest.raises(LeakageError, match="1 show"):
        assert_no_leakage([D(2020, 1, 1), D(2021, 1, 1)], D(2021, 1, 1), "T")


# ---------------------------------------------------------------------------------------------------------------------
# Shows


def perf(setlist_id, pos, song_id, **kw):
    return {"setlist_id": setlist_id, "setlist_position": pos, "song_id": song_id, **kw}


def test_is_played_excludes_tapes_snippets_fragments_and_unmapped():
    assert is_played(perf("a", 1, "s1"))
    assert not is_played(perf("a", 1, "s1", is_tape=True))
    assert not is_played(perf("a", 1, "s1", is_snippet=True))
    assert not is_played(perf("a", 1, None))
    assert not is_played(perf("a", 1, "cry"), fragment_ids={"cry"})


def test_build_shows_positions_opener_dedup_and_order():
    shows = [
        {"setlist_id": "b", "event_date": D(2020, 1, 2), "tour_name": "T"},
        {"setlist_id": "a", "event_date": D(2020, 1, 1), "tour_name": None},
        {"setlist_id": "c", "event_date": D(2020, 1, 3), "tour_name": "T"},
    ]
    perfs = [
        perf("a", 1, "intro", is_tape=True),
        perf("a", 3, "s2", is_encore=True),
        perf("a", 2, "s1"),
        perf("a", 4, "s3"),
        perf("a", 5, "s1"),  # reprise counts once
        perf("b", 1, "s9"),
    ]
    a, b, c = build_shows(shows, perfs)
    assert (a.setlist_id, a.tour_name) == ("a", NO_TOUR)
    assert [p.song_id for p in a.plays] == ["s1", "s2", "s3"]
    assert [p.position for p in a.plays] == [0.0, 0.5, 1.0]
    assert [p.is_opener for p in a.plays] == [True, False, False]
    assert a.plays[1].is_encore
    assert a.song_ids == frozenset({"s1", "s2", "s3"})
    assert b.plays[0].position == 0.0 and b.plays[0].is_opener
    assert c.plays == ()


# ---------------------------------------------------------------------------------------------------------------------
# Tours


def make_tour(name, tour_type="album", first=None, last=None, album=None, planned=False, n=0):
    return Tour(name, tour_type, first, last, album, planned, n)


def test_build_tours_counts_shows_and_fills_planned_first_show():
    shows = build_shows(
        [
            {"setlist_id": "1", "event_date": D(2020, 1, 1), "tour_name": "A"},
            {"setlist_id": "2", "event_date": D(2020, 1, 2), "tour_name": "A"},
        ],
        [],
    )
    tours = build_tours(
        [
            {"tour_name": "P", "tour_type": "album", "is_planned": True, "first_show_date": None},
            {"tour_name": "A", "tour_type": "album", "first_show_date": D(2020, 1, 1), "last_show_date": D(2020, 1, 2)},
        ],
        shows,
        {"P": D(2027, 2, 23)},
    )
    assert [(t.name, t.n_shows, t.first_show_date, t.is_planned) for t in tours] == [
        ("A", 2, D(2020, 1, 1), False),
        ("P", 0, D(2027, 2, 23), True),
    ]


def test_previous_album_tour_skips_other_types_and_empty_tours():
    tours = [
        make_tour("A1", first=D(2000, 1, 1), n=5),
        make_tour("JT", "anniversary", first=D(2010, 1, 1), n=5),
        make_tour("A2", first=D(2005, 1, 1), n=5),
        make_tour("Ghost", first=D(2008, 1, 1), n=0),
    ]
    assert previous_album_tour(tours, D(2011, 1, 1)).name == "A2"
    assert previous_album_tour(tours, D(2000, 1, 1)) is None


def test_qualifying_tours_need_min_shows_and_skip_no_tour():
    raw = [{"setlist_id": f"a{i}", "event_date": D(2000, 1, i + 1), "tour_name": "A"} for i in range(3)]
    raw += [{"setlist_id": f"n{i}", "event_date": D(2001, 1, i + 1), "tour_name": None} for i in range(3)]
    raw += [{"setlist_id": "b0", "event_date": D(2002, 1, 1), "tour_name": "B"}]
    shows = build_shows(raw, [])
    tours = [make_tour("A"), make_tour("B"), make_tour(NO_TOUR, None)]
    assert [t.name for t in qualifying_tours(tours, shows, min_shows=1)] == ["A", "B"]
    assert [t.name for t in qualifying_tours(tours, shows, min_shows=2)] == ["A"]


# ---------------------------------------------------------------------------------------------------------------------
# Songs and singles


def test_build_song_infos_release_from_release_track_album_or_year():
    songs = [
        {"song_id": "new", "title": "Get Back to Now", "first_album_id": None, "is_original": True},
        {
            "song_id": "old",
            "title": "One",
            "first_album_id": "ab",
            "is_original": True,
            "is_single": True,
            "single_date": D(1992, 2, 24),
        },
        {"song_id": "yr", "title": "B-side", "first_album_id": None, "first_release_year": 1987, "is_original": True},
        {"song_id": "cov", "title": "Cover", "is_original": False, "is_single": False, "single_date": D(2000, 1, 1)},
    ]
    albums = [{"album_id": "ab", "release_date": D(1991, 11, 18)}]
    tracks = [
        {
            "song_id": "new",
            "album_id": "cdl",
            "release_date": D(2026, 11, 13),
            "featured_artist": None,
            "is_spoken_word": False,
            "is_bonus_track": True,
        }
    ]
    infos = build_song_infos(songs, albums, tracks)
    assert (infos["new"].album_id, infos["new"].release_date, infos["new"].is_bonus_track) == (
        "cdl",
        D(2026, 11, 13),
        True,
    )
    assert (infos["old"].album_id, infos["old"].release_date, infos["old"].single_date) == (
        "ab",
        D(1991, 11, 18),
        D(1992, 2, 24),
    )
    assert infos["yr"].release_date == D(1987, 1, 1)
    assert infos["cov"].release_date is None and infos["cov"].single_date is None


def test_is_low_precision_date():
    assert is_low_precision_date(D(1984, 1, 1))
    assert not is_low_precision_date(D(1984, 1, 2))
    assert not is_low_precision_date(None)


@pytest.mark.parametrize(
    ("single", "album", "cutoff", "expected"),
    [
        (None, D(1987, 3, 9), D(1990, 1, 1), False),
        (D(1987, 3, 1), D(1987, 3, 9), D(1987, 4, 2), True),  # With or Without You before the JT tour
        (D(1992, 6, 7), D(1991, 11, 18), D(1992, 2, 29), False),  # EBTTRT after Zoo TV's first show
        (D(2017, 4, 21), D(1987, 3, 9), D(2018, 5, 2), False),  # Red Hill Mining Town: reissue, never a single
        (D(2009, 2, 16), D(1987, 3, 9), D(2018, 5, 2), False),  # Running to Stand Still: reissue
        (D(1988, 3, 7), D(1987, 3, 9), D(1989, 9, 21), True),  # One Tree Hill: within 12 months
        (D(1984, 1, 1), D(1984, 10, 1), D(1984, 8, 29), False),  # TUF single (year only), album not out yet
        (D(1997, 1, 1), D(1997, 2, 26), D(1997, 4, 25), True),  # Discothèque (year only), album out before PopMart
        (D(1993, 1, 1), D(1993, 7, 5), D(1997, 4, 25), True),  # Numb (year only), earlier year
        (D(2027, 1, 1), None, D(2026, 4, 1), False),  # year only, later year
    ],
)
def test_single_known_before(single, album, cutoff, expected):
    assert single_known_before(single, album, cutoff) is expected


def song(song_id, title="x", album=None, release=None, single=None, original=True, fragment=False, **kw):
    return SongInfo(song_id, title, original, fragment, album, release, single, **kw)


def test_singles_as_of_ranks_per_album_by_known_singles():
    songs = {
        "tuf": song("tuf", "The Unforgettable Fire", "uf", single=D(1984, 1, 1)),
        "pride": song("pride", "Pride", "uf", single=D(1984, 8, 27)),
        "sotf": song("sotf", "Song of the Future", "doa", single=D(2026, 2, 18)),
        "sod": song("sod", "Street of Dreams", "cdl", single=D(2026, 7, 7)),
        "sil": song("sil", "Silencio", "cdl", single=D(2026, 9, 24)),
        "none": song("none", "Deep cut", "cdl"),
    }
    release = {"uf": D(1984, 10, 1), "doa": D(2026, 2, 18), "cdl": D(2026, 11, 13)}
    assert singles_as_of(songs, release, D(1984, 8, 29)) == {"pride": 1}
    assert singles_as_of(songs, release, D(1987, 4, 2)) == {"tuf": 1, "pride": 2}  # stored order kept (T-46 note)
    assert singles_as_of(songs, release, D(2027, 2, 23)) == {"pride": 2, "tuf": 1, "sotf": 1, "sod": 1, "sil": 2}


@pytest.mark.parametrize(
    ("song_title", "album", "tour", "expected"),
    [
        (
            "The Greatest Show on Earth",
            "Carnaval de luz",
            "Carnaval De Luz Presents: The Greatest Show On Earth World Tour",
            True,
        ),
        ("Go (Carnaval de Luz)", "Carnaval de luz", "Some tour", True),
        ("The Unforgettable Fire", "The Unforgettable Fire", "The Unforgettable Fire", True),
        ("Elevation", "All That You Can't Leave Behind", "Elevation", True),
        ("Glorify", "Carnaval de luz", "Carnaval De Luz Presents: The Greatest Show On Earth World Tour", False),
        ("Show", None, "Greatest Showman Tour", False),  # word-bounded
        ("", "x", "y", False),
    ],
)
def test_is_title_track(song_title, album, tour, expected):
    assert is_title_track(song_title, album, tour) is expected


# ---------------------------------------------------------------------------------------------------------------------
# Feature rows on a small synthetic history


def history():
    """Album tour A1 (album a1, 10 shows, 2000), anniversary tour JT (10 shows, 2003), promo show (2004),
    album tour A2 (album a2, 4 shows, 2005), planned tour P (album a3, companion ep3)."""
    raw, perfs = [], []

    def add(tour, date, songs, encore=()):
        sid = f"{tour}-{date.isoformat()}"
        raw.append({"setlist_id": sid, "event_date": date, "tour_name": tour})
        for i, s in enumerate(songs, start=1):
            perfs.append(perf(sid, i, s, is_encore=s in encore))

    for i in range(10):
        add(
            "A1",
            D(2000, 3, 1 + i),
            ["a1_single", "old_hit", "a1_deep" if i < 3 else "old_rare", "cover_x"],
            encore=("cover_x",),
        )
    for i in range(10):
        add("JT", D(2003, 6, 1 + i), ["old_hit", "jt_song"])
    add(None, D(2004, 9, 1), ["a2_single", "old_hit"])
    for i in range(4):
        add("A2", D(2005, 3, 1 + i), ["a2_single", "old_hit", "a1_single" if i < 2 else "a2_deep"])
    shows = build_shows(raw, perfs)
    tours = [
        make_tour("A1", first=D(2000, 3, 1), last=D(2000, 3, 10), album="a1", n=10),
        make_tour("JT", "anniversary", D(2003, 6, 1), D(2003, 6, 10), album="a0", n=10),
        make_tour(NO_TOUR, None, D(2004, 9, 1), D(2004, 9, 1), n=1),
        make_tour("A2", first=D(2005, 3, 1), last=D(2005, 3, 4), album="a2", n=4),
        make_tour("P", first=D(2027, 2, 23), album="a3", planned=True),
    ]
    songs = {
        "old_hit": song("old_hit", "Old Hit", "a0", D(1990, 1, 5), single=D(1990, 1, 5)),
        "old_rare": song("old_rare", "Old Rare", "a0", D(1990, 1, 5)),
        "jt_song": song("jt_song", "JT Song", "a0", D(1990, 1, 5)),
        "never": song("never", "Never Played", "a0", D(1990, 1, 5)),
        "unreleased": song("unreleased", "Unreleased", None, None),
        "fragment": song("fragment", "The Cry", "a0", D(1990, 1, 5), fragment=True),
        "a1_single": song("a1_single", "A1 Single", "a1", D(1999, 10, 1), single=D(1999, 9, 1)),
        "a1_deep": song("a1_deep", "A1 Deep", "a1", D(1999, 10, 1)),
        "a2_single": song("a2_single", "A2 Single", "a2", D(2004, 11, 1), single=D(2004, 10, 1)),
        "a2_deep": song("a2_deep", "A2 Deep", "a2", D(2004, 11, 1)),
        "a3_title": song("a3_title", "Album Three", "a3", D(2026, 11, 13), single=D(2026, 10, 15)),
        "a3_feat": song("a3_feat", "Duet", "a3", D(2026, 11, 13), has_featured_artist=True),
        "ep3_song": song("ep3_song", "EP Song", "ep3", D(2026, 2, 18)),
        "cover_x": song("cover_x", "Cover X", None, None, original=False),
        "cover_y": song("cover_y", "Cover Y", None, None, original=False),
    }
    titles = {"a0": "Zero", "a1": "One Album", "a2": "Two Album", "a3": "Album Three", "ep3": "EP Three"}
    release = {
        "a0": D(1990, 1, 5),
        "a1": D(1999, 10, 1),
        "a2": D(2004, 11, 1),
        "a3": D(2026, 11, 13),
        "ep3": D(2026, 2, 18),
    }
    return tours, shows, songs, titles, release


def test_build_features_backtest_tour():
    tours, shows, songs, titles, release = history()
    rows = {r["song_id"]: r for r in build_features(tours[3], tours, shows, songs, titles, release)}
    assert "fragment" not in rows and "unreleased" not in rows and "cover_y" not in rows
    assert "cover_x" in rows  # cover played on the previous album tour
    assert "never" in rows  # released, never played
    hit = rows["old_hit"]
    assert hit["prev_album_tour_name"] == "A1" and hit["prev_album_tour_rate"] == 1.0
    assert hit["last_tour_name"] == "JT" and hit["last_tour_type"] == "anniversary" and hit["last_tour_rate"] == 1.0
    assert hit["career_rate"] == 1.0 and hit["career_shows_played"] == 21
    assert hit["tours_played_share"] == 1.0 and hit["tours_since_last_played"] == 0
    assert hit["played_pre_tour"] == 1 and hit["is_single"] and hit["single_order"] == 1
    assert hit["history_max_date"] == D(2004, 9, 1) and hit["history_shows"] == 21
    assert hit["play_rate"] == 1.0 and hit["is_core"] and hit["in_first_show"]
    deep = rows["a1_deep"]
    assert deep["prev_album_tour_rate"] == pytest.approx(0.3) and deep["last_tour_rate"] == 0.0
    assert deep["tours_since_last_played"] == 1 and deep["prev_avg_position"] == pytest.approx(2 / 3)
    assert rows["never"]["career_rate"] is None or rows["never"]["career_rate"] == 0.0
    assert rows["never"]["tours_since_last_played"] is None
    single = rows["a2_single"]
    assert single["release_role"] == ROLE_PROMOTED and single["is_new_material"]
    assert single["played_pre_tour"] == 1 and single["is_single"] and single["days_release_to_tour"] == 120
    assert rows["a2_deep"]["play_rate"] == 0.5 and rows["a2_deep"]["is_core"] and not rows["a2_deep"]["in_first_show"]
    assert rows["a1_single"]["release_role"] == ROLE_CATALOG and rows["a1_single"]["play_rate"] == 0.5
    assert rows["cover_x"]["prev_encore_rate"] == 1.0 and rows["a1_single"]["prev_opener_rate"] == 1.0


def test_build_features_planned_tour_has_no_targets_and_companion_is_new():
    tours, shows, songs, titles, release = history()
    rows = {r["song_id"]: r for r in build_features(tours[4], tours, shows, songs, titles, release, {"ep3"})}
    assert rows["a3_title"]["is_title_track"] and rows["a3_title"]["is_single"]
    assert rows["a3_title"]["play_rate"] is None and rows["a3_title"]["is_core"] is None
    assert rows["ep3_song"]["release_role"] == ROLE_COMPANION and rows["ep3_song"]["is_new_material"]
    assert rows["a3_feat"]["has_featured_artist"]
    assert rows["old_hit"]["prev_album_tour_name"] == "A2" and rows["old_hit"]["prev_album_tour_rate"] == 1.0
    assert rows["old_hit"]["history_max_date"] == D(2005, 3, 4)


def test_build_features_companion_already_promoted_is_not_new():
    tours, shows, songs, titles, release = history()
    rows = {r["song_id"]: r for r in build_features(tours[3], tours, shows, songs, titles, release, {"a1"})}
    assert rows["a1_deep"]["release_role"] == ROLE_COMPANION and not rows["a1_deep"]["is_new_material"]


def test_build_features_needs_a_first_show():
    tours, shows, songs, titles, release = history()
    with pytest.raises(ValueError, match="first show"):
        build_features(make_tour("X"), tours, shows, songs, titles, release)


def test_build_features_never_reads_target_shows():
    """Adding plays on or after the cutoff must not change any feature (only the targets)."""
    tours, shows, songs, titles, release = history()
    base = build_features(tours[3], tours, shows, songs, titles, release)
    later = build_shows(
        [{"setlist_id": "late", "event_date": D(2030, 1, 1), "tour_name": None}], [perf("late", 1, "never")]
    )
    again = build_features(tours[3], tours, shows + later, songs, titles, release)
    assert base == again


def test_tour_profile():
    tours, shows, songs, _, _ = history()
    prof = tour_profile(tours[3], shows, songs, {"a2"})
    assert (prof.n_shows, prof.songs_per_show, prof.new_per_show) == (4, 3.0, 1.5)
    assert prof.new_share == pytest.approx(0.5) and prof.new_opener_share == 1.0
    assert prof.new_avg_position == pytest.approx((0 * 4 + 1 * 2) / 6)
    assert prof.first_show_date == D(2005, 3, 1) and prof.last_show_date == D(2005, 3, 4)
    with pytest.raises(ValueError):
        tour_profile(tours[4], shows, songs, {"a3"})
