"""End-to-end steps of the setlist prediction notebooks (SPEC-09 §9.4-9.6), kept here so the notebooks stay thin and a
local dry run executes exactly the same code.

`feature_table` builds `setlist_feature`; `backtest_and_predict` builds `setlist_prediction`, `setlist_backtest` and
`setlist_model_coef` from those rows plus the shows (for tour profiles).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from u2lib.features import (
    Show,
    SongInfo,
    Tour,
    TourProfile,
    assert_no_leakage,
    build_features,
    build_shows,
    build_song_infos,
    build_tours,
    tour_profile,
)
from u2lib.prediction import (
    RECENT_TOURS,
    TourPrediction,
    backtest_tour,
    expectation,
    in_tour_update,
    predict_tour,
)
from u2lib.songs import normalize_title

TRAINING_TOUR_TYPES = ("album",)  # anniversary tours and the residency only feed recency features (SPEC-09 §9.1)


@dataclass
class Inputs:
    """Everything the feature and prediction steps need, built from Silver rows."""

    shows: list[Show]
    tours: list[Tour]
    songs: dict[str, SongInfo]
    album_titles: dict[str, str]
    album_release: dict[str, dt.date | None]
    companions: dict[str, set[str]]


def prepare_inputs(
    show_rows: Iterable[Mapping],
    performance_rows: Iterable[Mapping],
    song_rows: Sequence[Mapping],
    album_rows: Sequence[Mapping],
    tour_rows: Iterable[Mapping],
    release_track_rows: Sequence[Mapping],
    planned_first_show: Mapping[str, dt.date],
    companion_titles: Mapping[str, Sequence[str]],
) -> Inputs:
    """Silver rows -> inputs. `show_rows`: shows with a setlist; `performance_rows`: `performance` joined to
    `song_map` (`song_id` null when unmapped or ignored).

    Companion releases: `companion_titles` names them per tour (studio albums or EPs, by `normalize_title`); a planned
    tour also gets every `release_track` release that is not its promoted album (the 2026 EPs).
    """
    fragment_ids = {s["song_id"] for s in song_rows if s.get("is_fragment")}
    shows = build_shows(show_rows, performance_rows, fragment_ids)
    tours = build_tours(tour_rows, shows, planned_first_show)
    songs = build_song_infos(song_rows, album_rows, release_track_rows)
    by_key: dict[str, list[Mapping]] = {}
    for a in album_rows:
        if a.get("album_type") in ("studio", "ep"):
            by_key.setdefault(normalize_title(a["title"]), []).append(a)
    companions: dict[str, set[str]] = {}
    for tour, titles in companion_titles.items():
        for title in titles:
            hits = by_key.get(normalize_title(title))
            if not hits:
                raise ValueError(f"Companion release {title!r} of {tour!r} is not a studio album or EP")
            companions.setdefault(tour, set()).add(min(hits, key=lambda a: a["album_id"])["album_id"])
    for t in tours:
        if t.is_planned:
            extra = {r["album_id"] for r in release_track_rows if r["album_id"] and r["album_id"] != t.album_id}
            companions.setdefault(t.name, set()).update(extra)
    return Inputs(
        shows=shows,
        tours=tours,
        songs=songs,
        album_titles={a["album_id"]: a["title"] for a in album_rows},
        album_release={a["album_id"]: a.get("release_date") for a in album_rows},
        companions=companions,
    )


def target_tours(tours: Sequence[Tour]) -> list[Tour]:
    """Album tours that have a previous album tour (training and backtest), plus planned album tours.

    A planned tour that has started (shows in Silver) is included once, with the album tours that have shows.
    """
    album = [t for t in tours if t.tour_type in TRAINING_TOUR_TYPES and t.first_show_date]
    played = sorted((t for t in album if t.n_shows), key=lambda t: t.first_show_date)
    planned = [t for t in album if t.is_planned and not t.n_shows]
    return played[1:] + sorted(planned, key=lambda t: t.first_show_date)


def feature_table(
    tours: Sequence[Tour],
    shows: Sequence[Show],
    songs: Mapping[str, SongInfo],
    album_titles: Mapping[str, str],
    album_release: Mapping[str, dt.date | None],
    companions: Mapping[str, Collection[str]],
) -> tuple[list[dict], dict[str, dict]]:
    """Feature rows of every target tour and, per target, the leakage evidence (latest history show, cutoff)."""
    rows, checks = [], {}
    for t in target_tours(tours):
        target_rows = build_features(t, tours, shows, songs, album_titles, album_release, companions.get(t.name, ()))
        latest = max((r["history_max_date"] for r in target_rows if r["history_max_date"]), default=None)
        assert_no_leakage([latest], t.first_show_date, t.name)
        checks[t.name] = {
            "cutoff": t.first_show_date,
            "history_max_date": latest,
            "rows": len(target_rows),
            "is_planned": t.is_planned,
            "tour_type": t.tour_type,
        }
        rows.extend(target_rows)
    return rows, checks


@dataclass
class RunResult:
    predictions: list[dict] = field(default_factory=list)  # setlist_prediction rows
    backtest: list[dict] = field(default_factory=list)  # setlist_backtest rows (tour, method, metric, value)
    coefs: list[dict] = field(default_factory=list)  # setlist_model_coef rows
    tour_predictions: dict[str, TourPrediction] = field(default_factory=dict)
    training_tours: dict[str, list[str]] = field(default_factory=dict)


def backtest_and_predict(
    feature_rows: Sequence[Mapping],
    tours: Sequence[Tour],
    shows: Sequence[Show],
    songs: Mapping[str, SongInfo],
    companions: Mapping[str, Collection[str]],
    backtest_from: str,
    companion_reference: str,
    model_version: str,
    l2: float = 1.0,
    prediction_tours: Collection[str] = (),
) -> RunResult:
    """Backtest every album tour from `backtest_from` on, then predict the planned tours (SPEC-09 §9.5-9.6).

    For each target: train on the feature rows of earlier album tours that ended before its first show, take the
    setlist shape from the last `RECENT_TOURS` album tours, predict, and score the model and B1-B3.
    Prediction tours (planned tours, plus `prediction_tours` once the planned flag is cleared after the first show)
    are never backtested or used for training; they get the pre-tour prediction and one in-tour update per show.
    """
    tour_by_name = {t.name: t for t in tours}
    rows_by_target: dict[str, list[Mapping]] = {}
    for r in feature_rows:
        rows_by_target.setdefault(r["target_tour_name"], []).append(r)
    targets = sorted((tour_by_name[n] for n in rows_by_target), key=lambda t: t.first_show_date)
    start = tour_by_name[backtest_from].first_show_date
    profiles: dict[str, TourProfile] = {
        t.name: tour_profile(t, shows, songs, {t.album_id}) for t in tours if t.tour_type == "album" and t.n_shows
    }
    ref = tour_by_name.get(companion_reference)
    ref_profile = tour_profile(ref, shows, songs, companions.get(ref.name, ())) if ref and ref.n_shows else None
    shows_by_tour: dict[str, list[Show]] = {}
    for s in shows:
        shows_by_tour.setdefault(s.tour_name, []).append(s)

    def is_prediction(t: Tour) -> bool:
        return t.is_planned or t.name in prediction_tours

    result = RunResult()
    for t in targets:
        if not is_prediction(t) and t.first_show_date < start:
            continue  # training-only tour
        cutoff = t.first_show_date
        train_tours = [
            u
            for u in targets
            if not is_prediction(u) and u.first_show_date < cutoff and u.tour_type in TRAINING_TOUR_TYPES
        ]
        assert_no_leakage([u.last_show_date for u in train_tours], cutoff, f"{t.name} training labels")
        training = [r for u in train_tours for r in rows_by_target[u.name]]
        past = sorted(
            (profiles[n] for n in profiles if tour_by_name[n].first_show_date < cutoff),
            key=lambda p: p.first_show_date,
        )
        recent = past[-RECENT_TOURS:]
        assert_no_leakage([p.last_show_date for p in recent], cutoff, f"{t.name} tour profiles")
        target_rows = rows_by_target[t.name]
        has_new_companion = any(r["is_new_material"] and r["release_role"] == "companion_release" for r in target_rows)
        use_ref = ref_profile if (ref_profile and ref_profile.last_show_date < cutoff) else None
        exp = expectation(recent, recent[-1], use_ref, has_new_companion)
        pred = predict_tour(target_rows, training, exp, l2)
        result.tour_predictions[t.name] = pred
        result.training_tours[t.name] = [u.name for u in train_tours]
        as_of = cutoff - dt.timedelta(days=1)
        for r in pred.rows:
            result.predictions.append(
                {
                    "target_tour_name": t.name,
                    "as_of_date": as_of,
                    "shows_observed": 0,
                    **{k: r[k] for k in ("song_id", "probability", "predicted_in_setlist")},
                    "predicted_position": r["predicted_position"],
                    "predicted_set": r["predicted_set"],
                    "model_part": r["model_part"],
                    "is_backtest": not is_prediction(t),
                    "model_version": model_version,
                }
            )
        for part, model in (("catalog", pred.catalog_model), ("new", pred.new_model)):
            if model is None:
                continue
            raw = model.raw_coefs()
            result.coefs.append(_coef_row(t.name, part, "intercept", None, raw["intercept"], model, model_version))
            for name, std in zip(model.names, model.coefs, strict=True):
                result.coefs.append(_coef_row(t.name, part, name, std, raw[name], model, model_version))

        if is_prediction(t):
            # In-tour update (SPEC-09 §9.5.4): one prediction per as_of_date = the day before each show played so far.
            played = [s for s in shows_by_tour.get(t.name, []) if s.event_date >= cutoff]
            dates = sorted({s.event_date for s in played})
            pre = [{"song_id": r["song_id"], "probability": r["probability"]} for r in pred.rows]
            parts = {r["song_id"]: r["model_part"] for r in pred.rows}
            for d in dates[1:]:
                so_far = [s.song_ids for s in played if s.event_date < d]
                for r in in_tour_update(pre, so_far, exp.songs_per_show):
                    result.predictions.append(
                        {
                            "target_tour_name": t.name,
                            "as_of_date": d - dt.timedelta(days=1),
                            "shows_observed": len(so_far),
                            "song_id": r["song_id"],
                            "probability": r["probability"],
                            "predicted_in_setlist": r["predicted_in_setlist"],
                            "predicted_position": None,
                            "predicted_set": None,
                            "model_part": parts[r["song_id"]],
                            "is_backtest": False,
                            "model_version": model_version,
                        }
                    )
            continue

        own = shows_by_tour[t.name]
        metrics = backtest_tour(target_rows, pred, own[0].song_ids, profiles[t.name].new_per_show)
        for method, values in metrics.items():
            for metric, value in values.items():
                result.backtest.append(
                    {
                        "target_tour_name": t.name,
                        "method": method,
                        "metric": metric,
                        "value": value,
                        "model_version": model_version,
                    }
                )
        for metric, value in (
            ("songs_per_show_predicted", float(exp.songs_per_show)),
            ("songs_per_show_actual", profiles[t.name].songs_per_show),
            ("core_size_actual", float(sum(1 for r in target_rows if r["is_core"]))),
            ("new_per_show_predicted", float(pred.details["n_new_predicted"])),
            ("new_per_show_actual", profiles[t.name].new_per_show),
        ):
            result.backtest.append(
                {
                    "target_tour_name": t.name,
                    "method": "context",
                    "metric": metric,
                    "value": value,
                    "model_version": model_version,
                }
            )
    return result


def _coef_row(tour: str, part: str, feature: str, std, raw, model, version) -> dict:
    return {
        "target_tour_name": tour,
        "model_part": part,
        "feature": feature,
        "coef_standardized": std,
        "coef_raw": raw,
        "n_train": model.n_train,
        "n_positive": model.n_positive,
        "model_version": version,
    }
