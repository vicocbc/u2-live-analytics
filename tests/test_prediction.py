import math

import pytest

from u2lib.features import ROLE_CATALOG, ROLE_COMPANION, ROLE_PROMOTED, TourProfile
from u2lib.prediction import (
    CATALOG_FEATURES,
    NEW_FEATURES,
    _sigmoid,
    _solve,
    backtest_tour,
    baseline_set,
    beta_binomial_update,
    brier,
    expectation,
    fit_logistic,
    in_tour_update,
    jaccard,
    model_version,
    new_count_error,
    precision_at_n,
    predict_tour,
    scale_to_total,
    top_n,
)

# ---------------------------------------------------------------------------------------------------------------------
# Logistic regression


def test_solve_with_pivoting_and_singular():
    assert _solve([[0.0, 1.0], [2.0, 0.0]], [3.0, 4.0]) == pytest.approx([2.0, 3.0])
    with pytest.raises(ValueError):
        _solve([[1.0, 2.0], [2.0, 4.0]], [1.0, 2.0])


def test_sigmoid_is_stable():
    assert _sigmoid(0) == 0.5
    assert _sigmoid(-1000) == 0.0 and _sigmoid(1000) == 1.0


X = [[0.0, 1.0], [1.0, 1.0], [2.0, 1.0], [3.0, 1.0], [1.5, 1.0], [0.5, 1.0], [2.5, 1.0], [1.0, 1.0]]
Y = [0, 0, 1, 1, 1, 0, 0, 1]


def test_fit_logistic_satisfies_the_penalised_optimality_conditions():
    m = fit_logistic(X, Y, ["x", "const"], l2=1.0)
    assert m.scales[1] == 0.0 and m.coefs[1] == 0.0  # constant column ignored
    z = [(row[0] - m.means[0]) / m.scales[0] for row in X]
    mu = [_sigmoid(m.intercept + m.coefs[0] * v) for v in z]
    assert sum(p - y for p, y in zip(mu, Y, strict=True)) == pytest.approx(0, abs=1e-8)
    grad = sum((p - y) * v for p, y, v in zip(mu, Y, z, strict=True)) + 1.0 * m.coefs[0]
    assert grad == pytest.approx(0, abs=1e-8)
    assert m.coefs[0] > 0 and (m.n_train, m.n_positive) == (8, 4)
    assert m.predict([3.0, 1.0]) > m.predict([0.0, 1.0])


def test_fit_logistic_raw_coefs_reproduce_the_logit():
    m = fit_logistic(X, Y, ["x", "const"])
    raw = m.raw_coefs()
    for row in X:
        assert raw["intercept"] + raw["x"] * row[0] + raw["const"] * row[1] == pytest.approx(m.logit(row))


def test_fit_logistic_stronger_penalty_shrinks():
    weak, strong = fit_logistic(X, Y, ["x", "c"], l2=0.1), fit_logistic(X, Y, ["x", "c"], l2=100.0)
    assert abs(strong.coefs[0]) < abs(weak.coefs[0])


def test_fit_logistic_constant_target_and_empty():
    m = fit_logistic([[0.0], [1.0]], [1, 1], ["x"])
    assert m.predict([0.5]) > 0.9
    with pytest.raises(ValueError):
        fit_logistic([], [], ["x"])


# ---------------------------------------------------------------------------------------------------------------------
# Helpers and metrics


def test_scale_to_total_caps_at_one():
    assert sum(scale_to_total([0.2, 0.2, 0.1], 1.0)) == pytest.approx(1.0)
    out = scale_to_total([0.9, 0.1, 0.1], 2.0)
    assert out[0] == 1.0 and sum(out) == pytest.approx(2.0)
    assert scale_to_total([0.5, 0.0], 3) == [1.0, 0.0]
    assert scale_to_total([0.5, 0.2], 0) == [0.0, 0.0]
    assert scale_to_total([], 2) == []


def test_top_n_ties_by_career_then_id():
    rows = [
        {"song_id": "b", "v": 1.0, "career_shows_played": 5},
        {"song_id": "a", "v": 1.0, "career_shows_played": 5},
        {"song_id": "c", "v": 1.0, "career_shows_played": 9},
        {"song_id": "d", "v": 0.5, "career_shows_played": 99},
    ]
    assert [r["song_id"] for r in top_n(rows, lambda r: r["v"], 3)] == ["c", "a", "b"]
    assert top_n(rows, lambda r: r["v"], -1) == []


@pytest.mark.parametrize(
    ("prior", "played", "shows", "expected"),
    [(0.5, 0, 0, 0.5), (0.2, 5, 5, (1 + 5) / 10), (0.9, 0, 10, 4.5 / 15), (1.5, 0, 0, 1.0)],
)
def test_beta_binomial_update(prior, played, shows, expected):
    assert beta_binomial_update(prior, played, shows) == pytest.approx(expected)


def test_beta_binomial_update_rejects_bad_counts():
    with pytest.raises(ValueError):
        beta_binomial_update(0.5, 3, 2)


def test_metrics():
    assert precision_at_n(["a", "b", "c", "d"], ["a", "c", "x"]) == 0.5
    assert precision_at_n([], ["a"]) is None
    assert jaccard(["a", "b"], ["b", "c"]) == pytest.approx(1 / 3)
    assert jaccard([], []) is None
    assert brier([1.0, 0.0], [0.5, 0.5]) == 0.25
    assert brier([], []) is None
    assert new_count_error(6, 7.5) == -1.5


def test_model_version_fits_gold_column():
    assert model_version("0.5.0") == "sl1.0-u2lib0.5.0"
    assert len(model_version("10.10.10")) <= 20


# ---------------------------------------------------------------------------------------------------------------------
# Expectation and one-tour prediction


def profile(name, songs, share, per_show, opener, pos, first=1, last=2):
    import datetime as dt

    return TourProfile(
        name, dt.date(2000 + first, 1, 1), dt.date(2000 + last, 1, 1), 10, songs, share, per_show, opener, pos
    )


def test_expectation_uses_recent_tours_and_companion_reference():
    recent = [
        profile("A", 20, 0.3, 6, 1.0, 0.4),
        profile("B", 22, 0.2, 4, 0.0, 0.5),
        profile("C", 24, 0.25, 6, 1.0, None),
    ]
    ref = profile("C", 24, 0.1, 2, 0.0, 0.5)
    e = expectation(recent, recent[-1], ref, has_new_companion=True)
    assert (e.songs_per_show, e.n_new_album, e.n_new_companion) == (22, 6, 2)
    assert e.new_avg_position == 0.5 and e.new_opener_share == pytest.approx(2 / 3)
    assert e.tours == ("A", "B", "C")
    assert expectation(recent, recent[0], ref, has_new_companion=False).n_new_companion == 0
    with pytest.raises(ValueError):
        expectation([], recent[0])


def row(song_id, tour="T", core=None, new=False, role=ROLE_CATALOG, **kw):
    base = {
        "target_tour_name": tour,
        "song_id": song_id,
        "is_new_material": new,
        "release_role": role,
        "is_core": core,
        "play_rate": None if core is None else (0.9 if core else 0.1),
        "prev_album_tour_rate": 0.0,
        "last_tour_rate": 0.0,
        "career_rate": 0.0,
        "career_shows_played": 0,
        "tours_played_share": None,
        "tours_since_last_played": None,
        "played_pre_tour": 0,
        "is_single": False,
        "single_order": None,
        "is_title_track": False,
        "has_featured_artist": False,
        "is_spoken_word": False,
        "is_bonus_track": False,
        "prev_avg_position": None,
        "prev_encore_rate": None,
        "prev_opener_rate": None,
        "career_avg_position": None,
    }
    base.update(kw)
    return base


def training_rows():
    rows = []
    for t in ("T1", "T2"):
        for i in range(6):
            hit = i < 3
            rows.append(
                row(
                    f"{t}c{i}",
                    t,
                    core=hit,
                    prev_album_tour_rate=0.9 if hit else 0.1,
                    career_rate=0.8 if hit else 0.05,
                    career_shows_played=100 if hit else 3,
                    tours_since_last_played=0 if hit else 3,
                )
            )
        for i in range(4):
            rows.append(
                row(
                    f"{t}n{i}",
                    t,
                    core=i < 2,
                    new=True,
                    role=ROLE_PROMOTED,
                    is_single=i < 2,
                    single_order=i + 1 if i < 2 else None,
                )
            )
    return rows


def target_rows(tour="T3", with_targets=True):
    def core(v):
        return v if with_targets else None

    return [
        row(
            "hit1",
            tour,
            core(True),
            prev_album_tour_rate=1.0,
            career_rate=0.9,
            career_shows_played=200,
            tours_since_last_played=0,
            prev_avg_position=0.9,
            prev_encore_rate=1.0,
            prev_opener_rate=0.0,
        ),
        row(
            "hit2",
            tour,
            core(True),
            prev_album_tour_rate=0.8,
            career_rate=0.7,
            career_shows_played=150,
            tours_since_last_played=0,
            prev_avg_position=0.2,
            prev_encore_rate=0.0,
            prev_opener_rate=0.6,
        ),
        row(
            "old",
            tour,
            core(False),
            prev_album_tour_rate=0.1,
            career_rate=0.05,
            career_shows_played=5,
            tours_since_last_played=2,
            last_tour_rate=1.0,
        ),
        row("s1", tour, core(True), new=True, role=ROLE_PROMOTED, is_single=True, single_order=1),
        row("s2", tour, core(True), new=True, role=ROLE_PROMOTED, is_single=True, single_order=2, played_pre_tour=1),
        row("deep", tour, core(False), new=True, role=ROLE_PROMOTED),
        row("bonus", tour, core(False), new=True, role=ROLE_PROMOTED, is_bonus_track=True),
        row("ep", tour, core(False), new=True, role=ROLE_COMPANION, is_spoken_word=True),
        row("ep2", tour, core(False), new=True, role=ROLE_COMPANION),
    ]


def exp(n=4, n_new=2, n_comp=1, opener_share=1.0):
    recent = [profile("T2", n, n_new / n, n_new, opener_share, 0.4)]
    ref = profile("R", n, n_comp / n, n_comp, 0.0, 0.5)
    return expectation(recent, recent[-1], ref, has_new_companion=n_comp > 0)


def test_predict_tour_shape_order_and_parts():
    pred = predict_tour(target_rows(), training_rows(), exp())
    by_id = {r["song_id"]: r for r in pred.rows}
    chosen = sorted((r for r in pred.rows if r["predicted_in_setlist"]), key=lambda r: r["predicted_position"])
    # N = 4: two album songs, one companion song, one catalog song; best new single opens, encore last
    assert [r["song_id"] for r in chosen] == ["s1", "s2", "ep2", "hit1"]
    assert [r["predicted_position"] for r in chosen] == [1, 2, 3, 4]
    assert by_id["hit1"]["predicted_set"] == "encore" and by_id["s1"]["predicted_set"] == "main"
    assert by_id["s1"]["model_part"] == "new" and by_id["hit1"]["model_part"] == "catalog"
    album = [r for r in pred.rows if r["model_part"] == "new" and r["song_id"] not in ("ep", "ep2")]
    assert sum(r["probability"] for r in album) == pytest.approx(2.0)  # rescaled to the expected album count
    assert by_id["ep"]["probability"] + by_id["ep2"]["probability"] == pytest.approx(1.0)
    assert by_id["ep2"]["probability"] > by_id["ep"]["probability"]  # spoken-word penalty
    assert by_id["deep"]["probability"] > by_id["bonus"]["probability"]  # bonus-track penalty
    assert pred.details["n_new_predicted"] == 3
    assert pred.new_model is not None and pred.catalog_model.n_train == 12


def test_predict_tour_rejects_target_in_training():
    with pytest.raises(ValueError, match="Training rows"):
        predict_tour(target_rows("T1"), training_rows(), exp())


def test_predict_tour_catalog_opener_when_new_material_rarely_opens():
    pred = predict_tour(target_rows(), training_rows(), exp(n=3, n_new=1, n_comp=0, opener_share=0.0))
    first = min((r for r in pred.rows if r["predicted_in_setlist"]), key=lambda r: r["predicted_position"])
    assert first["song_id"] == "hit2"


def test_predict_tour_without_new_training_rows():
    cat_only = [r for r in training_rows() if not r["is_new_material"]]
    pred = predict_tour(target_rows(), cat_only, exp())
    assert pred.new_model is None
    assert sum(r["predicted_in_setlist"] for r in pred.rows) == 4


def test_backtest_tour_scores_model_and_baselines():
    rows = target_rows()
    pred = predict_tour(rows, training_rows(), exp())
    res = backtest_tour(rows, pred, ["hit1", "s1", "x"], actual_new_per_show=2.0)
    assert set(res) == {"model", "B1", "B2", "B3"}
    assert set(res["model"]) == {"precision_at_n", "jaccard_first_show", "brier_play_rate", "new_count_error"}
    assert res["B1"]["new_count_error"] == -1.0  # 3 songs with a rate, the 4th slot filled by song id ("bonus")
    assert res["model"]["new_count_error"] == 1.0
    assert [r["song_id"] for r in baseline_set(rows, "B2", 2)] == ["hit1", "hit2"]
    assert [r["song_id"] for r in baseline_set(rows, "B3", 1)] == ["old"]
    assert res["model"]["precision_at_n"] >= res["B3"]["precision_at_n"]


def test_in_tour_update_moves_probabilities_and_reselects():
    pre = [
        {"song_id": "a", "probability": 0.9},
        {"song_id": "b", "probability": 0.2},
        {"song_id": "c", "probability": 0.2},
    ]
    shows = [frozenset({"b", "c"}), frozenset({"b"})]
    post = {r["song_id"]: r for r in in_tour_update(pre, shows, songs_per_show=2)}
    assert post["a"]["probability"] == pytest.approx(4.5 / 7)
    assert post["b"]["probability"] == pytest.approx(3 / 7)
    assert post["c"]["probability"] == pytest.approx(2 / 7)
    assert {s for s, r in post.items() if r["predicted_in_setlist"]} == {"a", "b"}
    assert {r["song_id"] for r in in_tour_update(pre, [], 1) if r["predicted_in_setlist"]} == {"a"}


def test_feature_maps_cover_null_values():
    r = row("x")
    assert all(not math.isnan(f(r)) for f in CATALOG_FEATURES.values())
    assert all(f(r) == 0.0 for f in NEW_FEATURES.values())
    assert CATALOG_FEATURES["recency"](row("x", tours_since_last_played=1)) == 0.5
