import datetime as dt

import pytest

from u2lib.features import NO_TOUR, LeakageError, SongInfo, Tour, build_shows
from u2lib.setlist import backtest_and_predict, feature_table, prepare_inputs, target_tours

D = dt.date


def world(planned_shows=0):
    """Three album tours (a1..a3, 10 shows each), an anniversary tour, a planned tour P (album a4, companion ep4)."""
    raw, perfs = [], []

    def add(tour, date, songs):
        sid = f"{tour}-{date.isoformat()}"
        raw.append({"setlist_id": sid, "event_date": date, "tour_name": tour})
        for i, s in enumerate(songs, start=1):
            perfs.append({"setlist_id": sid, "setlist_position": i, "song_id": s, "is_encore": s == "closer"})

    for k, year in ((1, 2000), (2, 2004), (3, 2008)):
        for i in range(10):
            extra = [f"a{k}_deep"] if i % 2 else []
            add(f"A{k}", D(year, 5, 1 + i), [f"a{k}_single", "hit", *extra, f"a{k - 1}_single", "closer"])
    for i in range(10):
        add("JT", D(2011, 5, 1 + i), ["a0_single", "hit"])
    add(None, D(2012, 1, 1), ["a4_single"])
    for i in range(planned_shows):
        add("P", D(2027, 2, 23 + i), ["a4_single", "hit", "ep4_song"])
    shows = build_shows(raw, perfs)
    tours = [
        Tour("A1", "album", D(2000, 5, 1), D(2000, 5, 10), "a1", False, 10),
        Tour("A2", "album", D(2004, 5, 1), D(2004, 5, 10), "a2", False, 10),
        Tour("A3", "album", D(2008, 5, 1), D(2008, 5, 10), "a3", False, 10),
        Tour("JT", "anniversary", D(2011, 5, 1), D(2011, 5, 10), "a0", False, 10),
        Tour(NO_TOUR, None, D(2012, 1, 1), D(2012, 1, 1), None, False, 1),
        Tour("P", "album", D(2027, 2, 23), None, "a4", True, planned_shows),
    ]
    songs = {}
    release = {
        "a0": D(1990, 1, 1),
        "a1": D(1999, 6, 1),
        "a2": D(2003, 6, 1),
        "a3": D(2007, 6, 1),
        "a4": D(2026, 11, 13),
        "ep4": D(2026, 2, 18),
    }
    for album, date in release.items():
        songs[f"{album}_single"] = SongInfo(
            f"{album}_single", f"{album} single", True, False, album, date, date - dt.timedelta(days=30)
        )
        songs[f"{album}_deep"] = SongInfo(f"{album}_deep", f"{album} deep", True, False, album, date, None)
    songs["ep4_song"] = SongInfo("ep4_song", "EP song", True, False, "ep4", release["ep4"], None)
    songs["hit"] = SongInfo("hit", "Hit", True, False, "a0", release["a0"], None)
    songs["closer"] = SongInfo("closer", "Closer", True, False, "a0", release["a0"], None)
    titles = {a: a.upper() for a in release}
    return tours, shows, songs, titles, release


def test_target_tours_skip_first_album_tour_and_other_types():
    tours, *_ = world()
    assert [t.name for t in target_tours(tours)] == ["A2", "A3", "P"]


def test_feature_table_records_leakage_evidence():
    tours, shows, songs, titles, release = world()
    rows, checks = feature_table(tours, shows, songs, titles, release, {"P": {"ep4"}})
    assert set(checks) == {"A2", "A3", "P"}
    for c in checks.values():
        assert c["history_max_date"] < c["cutoff"]
    assert checks["P"]["history_max_date"] == D(2012, 1, 1) and checks["P"]["is_planned"]
    assert {r["target_tour_name"] for r in rows} == {"A2", "A3", "P"}


def test_backtest_and_predict_end_to_end():
    tours, shows, songs, titles, release = world()
    companions = {"P": {"ep4"}, "A3": {"a2"}}
    rows, _ = feature_table(tours, shows, songs, titles, release, companions)
    res = backtest_and_predict(rows, tours, shows, songs, companions, "A3", "A3", "sl1.0-u2lib0.0.0")
    assert res.training_tours == {"A3": ["A2"], "P": ["A2", "A3"]}
    assert {b["target_tour_name"] for b in res.backtest} == {"A3"}
    methods = {(b["method"], b["metric"]) for b in res.backtest}
    assert ("model", "precision_at_n") in methods and ("B3", "brier_play_rate") in methods
    assert ("context", "songs_per_show_predicted") in methods
    planned = [p for p in res.predictions if p["target_tour_name"] == "P"]
    assert len(planned) == sum(1 for r in rows if r["target_tour_name"] == "P")
    assert {p["as_of_date"] for p in planned} == {D(2027, 2, 22)}
    n = res.tour_predictions["P"].expectation.songs_per_show
    assert sum(p["predicted_in_setlist"] for p in planned) == n
    positions = sorted(p["predicted_position"] for p in planned if p["predicted_in_setlist"])
    assert positions == list(range(1, n + 1))
    assert all(p["model_version"] == "sl1.0-u2lib0.0.0" for p in res.predictions)
    assert not any(p["is_backtest"] for p in planned)
    assert {c["model_part"] for c in res.coefs if c["target_tour_name"] == "P"} == {"catalog", "new"}


def test_backtest_and_predict_in_tour_update_after_shows():
    tours, shows, songs, titles, release = world(planned_shows=3)
    companions = {"P": {"ep4"}}
    rows, _ = feature_table(tours, shows, songs, titles, release, companions)
    res = backtest_and_predict(rows, tours, shows, songs, companions, "A3", "none", "v")
    planned = [p for p in res.predictions if p["target_tour_name"] == "P"]
    by_date = {}
    for p in planned:
        by_date.setdefault(p["as_of_date"], []).append(p)
    assert sorted(by_date) == [D(2027, 2, 22), D(2027, 2, 23), D(2027, 2, 24)]
    assert {p["shows_observed"] for p in by_date[D(2027, 2, 24)]} == {2}
    ep_pre = next(p for p in by_date[D(2027, 2, 22)] if p["song_id"] == "ep4_song")["probability"]
    ep_late = next(p for p in by_date[D(2027, 2, 24)] if p["song_id"] == "ep4_song")["probability"]
    assert ep_late > ep_pre


def test_backtest_and_predict_rejects_rows_with_late_history():
    tours, shows, songs, titles, release = world()
    rows, _ = feature_table(tours, shows, songs, titles, release, {})
    bad = [dict(r) for r in rows]
    tours_bad = [
        t if t.name != "A2" else Tour("A2", "album", D(2004, 5, 1), D(2030, 1, 1), "a2", False, 10) for t in tours
    ]
    with pytest.raises(LeakageError):
        backtest_and_predict(bad, tours_bad, shows, songs, {}, "A3", "none", "v")


def test_prepare_inputs_from_silver_rows():
    show_rows = [
        {"setlist_id": "s1", "event_date": D(2018, 5, 2), "tour_name": "E+I"},
        {"setlist_id": "s2", "event_date": D(2026, 9, 25), "tour_name": None},
    ]
    perf_rows = [
        {"setlist_id": "s1", "setlist_position": 1, "song_id": "soi1"},
        {"setlist_id": "s1", "setlist_position": 2, "song_id": "cry"},
        {"setlist_id": "s2", "setlist_position": 1, "song_id": "sil"},
    ]
    song_rows = [
        {"song_id": "soi1", "title": "Song for Someone", "first_album_id": "soi", "is_original": True},
        {"song_id": "cry", "title": "The Cry", "first_album_id": None, "is_original": True, "is_fragment": True},
        {
            "song_id": "sil",
            "title": "Silencio",
            "first_album_id": None,
            "is_original": True,
            "is_single": True,
            "single_date": D(2026, 9, 24),
        },
        {"song_id": "sotf", "title": "Song of the Future", "first_album_id": "doa", "is_original": True},
    ]
    album_rows = [
        {"album_id": "soi", "title": "Songs of Innocence", "release_date": D(2014, 9, 9), "album_type": "studio"},
        {"album_id": "soi-live", "title": "Songs of Innocence", "release_date": D(2015, 1, 1), "album_type": "live"},
        {"album_id": "doa", "title": "Days of Ash EP", "release_date": D(2026, 2, 18), "album_type": "ep"},
        {"album_id": "cdl", "title": "Carnaval de luz", "release_date": D(2026, 11, 13), "album_type": "studio"},
    ]
    tour_rows = [
        {"tour_name": "E+I", "tour_type": "album", "first_show_date": D(2018, 5, 2), "album_promoted_id": "soe"},
        {"tour_name": "P", "tour_type": "album", "is_planned": True, "album_promoted_id": "cdl"},
    ]
    rt_rows = [
        {"song_id": "sil", "album_id": "cdl", "release_date": D(2026, 11, 13)},
        {"song_id": "sotf", "album_id": "doa", "release_date": D(2026, 2, 18)},
    ]
    inp = prepare_inputs(
        show_rows,
        perf_rows,
        song_rows,
        album_rows,
        tour_rows,
        rt_rows,
        {"P": D(2027, 2, 23)},
        {"E+I": ["Songs of Innocence"]},
    )
    assert inp.companions == {"E+I": {"soi"}, "P": {"doa"}}
    assert [p.song_id for p in inp.shows[0].plays] == ["soi1"]  # fragment dropped
    assert inp.songs["sil"].album_id == "cdl" and inp.songs["sil"].release_date == D(2026, 11, 13)
    assert next(t for t in inp.tours if t.name == "P").first_show_date == D(2027, 2, 23)
    assert inp.album_titles["doa"] == "Days of Ash EP" and inp.album_release["soi"] == D(2014, 9, 9)
    with pytest.raises(ValueError, match="Companion"):
        prepare_inputs([], [], song_rows, album_rows, tour_rows, rt_rows, {}, {"E+I": ["Zooropa"]})
