"""Setlist prediction: model, baselines, backtest metrics and the in-tour update (SPEC-09 §9.5-9.6).

Works on the feature rows of `u2lib.features.build_features` (plain dicts), so the same code runs in Fabric and in
local tests. Pure Python on purpose: about ten comparable tours do not need more, and a rerun gives the same numbers
on any runtime. The logistic regression is the L2-penalised maximum-likelihood fit that scikit-learn's
`LogisticRegression(C=1/l2)` solves, on standardised features; the notebook cross-checks it against scikit-learn.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from u2lib.features import ROLE_COMPANION, ROLE_PROMOTED, TourProfile

MODEL_NAME = "sl1.0"  # bump when features, weights or rules change; model_version = f"{MODEL_NAME}-u2lib{version}"
PRIOR_STRENGTH = 5.0  # m of the Beta-binomial in-tour update (SPEC-09 §9.5.4)
RECENT_TOURS = 3  # expected songs per show and new-material share: median of the last three album tours

# Catalog part: logistic regression on is_core (SPEC-09 §9.5.1). Chosen before any backtest was run.
CATALOG_FEATURES: dict[str, Callable[[Mapping], float]] = {
    "prev_album_tour_rate": lambda r: r["prev_album_tour_rate"] or 0.0,
    "last_tour_rate": lambda r: r["last_tour_rate"] or 0.0,
    "career_rate": lambda r: r["career_rate"] or 0.0,
    "tours_played_share": lambda r: r["tours_played_share"] or 0.0,
    "recency": lambda r: 0.0 if r["tours_since_last_played"] is None else 1.0 / (1.0 + r["tours_since_last_played"]),
    "played_pre_tour": lambda r: 1.0 if (r["played_pre_tour"] or 0) > 0 else 0.0,
    "is_single": lambda r: 1.0 if r["is_single"] else 0.0,
}

# New-material part (SPEC-09 §9.5.2): a logistic regression on the new songs of past album tours (where singles and
# pre-tour plays are known) calibrates these weights; facts that never occur in the history get hand-set logit
# penalties instead.
NEW_FEATURES: dict[str, Callable[[Mapping], float]] = {
    "is_single": lambda r: 1.0 if r["is_single"] else 0.0,
    "single_order_inv": lambda r: 1.0 / r["single_order"] if r["single_order"] else 0.0,
    "played_pre_tour": lambda r: 1.0 if (r["played_pre_tour"] or 0) > 0 else 0.0,
    "is_title_track": lambda r: 1.0 if r["is_title_track"] else 0.0,
}
NEW_PENALTIES = {  # logit shift; not in the history (2026 seed facts), so set by hand
    "has_featured_artist": -1.0,
    "is_spoken_word": -2.0,
    "is_bonus_track": -2.0,
}


def model_version(u2lib_version: str) -> str:
    return f"{MODEL_NAME}-u2lib{u2lib_version}"


# --------------------------------------------------------------------------------------------------------------------
# Logistic regression


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Solve a·x = b by Gaussian elimination with partial pivoting (small dense systems)."""
    n = len(b)
    m = [[*row, b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-12:
            raise ValueError("Singular matrix")
        m[col], m[pivot] = m[pivot], m[col]
        for r in range(col + 1, n):
            f = m[r][col] / m[col][col]
            for c in range(col, n + 1):
                m[r][c] -= f * m[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (m[r][n] - sum(m[r][c] * x[c] for c in range(r + 1, n))) / m[r][r]
    return x


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


@dataclass(frozen=True)
class LogisticModel:
    names: tuple[str, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]  # 0 = constant column in training (coefficient forced to 0)
    intercept: float
    coefs: tuple[float, ...]  # on standardised features
    n_train: int
    n_positive: int

    def logit(self, x: Sequence[float]) -> float:
        z = self.intercept
        for v, mu, sd, w in zip(x, self.means, self.scales, self.coefs, strict=True):
            if sd:
                z += w * (v - mu) / sd
        return z

    def predict(self, x: Sequence[float]) -> float:
        return _sigmoid(self.logit(x))

    def raw_coefs(self) -> dict[str, float]:
        """Coefficients per unit of the original feature (plus `intercept`), for the report."""
        out = {"intercept": self.intercept}
        for n, mu, sd, w in zip(self.names, self.means, self.scales, self.coefs, strict=True):
            raw = w / sd if sd else 0.0
            out[n] = raw
            out["intercept"] -= raw * mu
        return out


def fit_logistic(
    x: Sequence[Sequence[float]],
    y: Sequence[int | bool],
    names: Sequence[str],
    l2: float = 1.0,
    max_iter: int = 100,
    tol: float = 1e-10,
) -> LogisticModel:
    """L2-penalised logistic regression by Newton-Raphson on standardised features (intercept not penalised).

    Minimises `0.5·l2·|w|² + Σ log-loss`, the objective of scikit-learn's `LogisticRegression(C=1/l2)`.
    Deterministic: no random state.
    """
    n = len(y)
    if n == 0:
        raise ValueError("No training rows")
    k = len(names)
    means = [sum(row[j] for row in x) / n for j in range(k)]
    scales = []
    for j in range(k):
        var = sum((row[j] - means[j]) ** 2 for row in x) / n
        scales.append(math.sqrt(var) if var > 1e-12 else 0.0)
    active = [j for j in range(k) if scales[j]]
    z = [[1.0] + [(row[j] - means[j]) / scales[j] for j in active] for row in x]
    p = len(active) + 1
    beta = [0.0] * p
    for _ in range(max_iter):
        grad = [0.0] * p
        hess = [[0.0] * p for _ in range(p)]
        for zi, yi in zip(z, y, strict=True):
            mu = _sigmoid(sum(b * v for b, v in zip(beta, zi, strict=True)))
            w = mu * (1 - mu)
            for a in range(p):
                grad[a] += (mu - float(yi)) * zi[a]
                for c in range(a, p):
                    hess[a][c] += w * zi[a] * zi[c]
        for a in range(1, p):
            grad[a] += l2 * beta[a]
            hess[a][a] += l2
        hess[0][0] += 1e-9  # keeps the intercept finite when y is constant
        for a in range(p):
            for c in range(a):
                hess[a][c] = hess[c][a]
        step = _solve(hess, grad)
        beta = [b - s for b, s in zip(beta, step, strict=True)]
        if max(abs(s) for s in step) < tol:
            break
    coefs = [0.0] * k
    for idx, j in enumerate(active, start=1):
        coefs[j] = beta[idx]
    return LogisticModel(
        names=tuple(names),
        means=tuple(means),
        scales=tuple(scales),
        intercept=beta[0],
        coefs=tuple(coefs),
        n_train=n,
        n_positive=sum(1 for v in y if v),
    )


def design(rows: Iterable[Mapping], features: Mapping[str, Callable[[Mapping], float]]) -> list[list[float]]:
    return [[f(r) for f in features.values()] for r in rows]


# --------------------------------------------------------------------------------------------------------------------
# Small helpers


def scale_to_total(probs: Sequence[float], total: float) -> list[float]:
    """Multiply probabilities by one factor so they sum to `total`, capping each at 1 (bisection on the factor)."""
    if total <= 0 or not probs:
        return [0.0 for _ in probs]
    if total >= sum(1 for p in probs if p > 0):
        return [1.0 if p > 0 else 0.0 for p in probs]
    lo, hi = 0.0, 1.0
    while sum(min(1.0, hi * p) for p in probs) < total:
        hi *= 2
    for _ in range(100):
        mid = (lo + hi) / 2
        if sum(min(1.0, mid * p) for p in probs) < total:
            lo = mid
        else:
            hi = mid
    return [min(1.0, hi * p) for p in probs]


def top_n(rows: Sequence[Mapping], key: Callable[[Mapping], float], n: int) -> list[Mapping]:
    """The `n` rows with the highest `key`; ties by `career_shows_played` (desc), then `song_id` (code-point order)."""
    ranked = sorted(rows, key=lambda r: (-key(r), -(r.get("career_shows_played") or 0), r["song_id"]))
    return ranked[: max(n, 0)]


def beta_binomial_update(prior: float, played: int, shows: int, strength: float = PRIOR_STRENGTH) -> float:
    """Posterior mean of a song's play probability after `shows` shows of the tour, `played` of which had it.

    Prior Beta(strength·prior, strength·(1-prior)); posterior mean (strength·prior + played) / (strength + shows).
    """
    if shows < 0 or played < 0 or played > shows:
        raise ValueError("Need 0 <= played <= shows")
    prior = min(max(prior, 0.0), 1.0)
    return (strength * prior + played) / (strength + shows)


# --------------------------------------------------------------------------------------------------------------------
# Metrics (SPEC-09 §9.6)


def precision_at_n(predicted: Iterable[str], core: Iterable[str]) -> float | None:
    predicted = list(predicted)
    if not predicted:
        return None
    core = set(core)
    return sum(1 for s in predicted if s in core) / len(predicted)


def jaccard(a: Iterable[str], b: Iterable[str]) -> float | None:
    a, b = set(a), set(b)
    union = a | b
    return len(a & b) / len(union) if union else None


def brier(probs: Sequence[float], actual: Sequence[float]) -> float | None:
    if not probs:
        return None
    return sum((p - a) ** 2 for p, a in zip(probs, actual, strict=True)) / len(probs)


def new_count_error(predicted_new: float, actual_new_per_show: float) -> float:
    return predicted_new - actual_new_per_show


# --------------------------------------------------------------------------------------------------------------------
# Tour-level expectations from past album tours


@dataclass(frozen=True)
class Expectation:
    songs_per_show: int  # N
    new_share: float  # median of the recent album tours' median new-material share per show
    n_new_album: int
    n_new_companion: int
    new_avg_position: float  # where new songs sit in the set (previous album tour)
    new_opener_share: float  # share of the recent album tours' shows opened by new material
    tours: tuple[str, ...]


def expectation(
    recent: Sequence[TourProfile],
    previous: TourProfile,
    companion_reference: TourProfile | None = None,
    has_new_companion: bool = False,
) -> Expectation:
    """Expected setlist shape for a target from the profiles of past album tours (all ended before its cutoff).

    `recent`: the last `RECENT_TOURS` album tours, profiled with "new" = their own promoted album.
    `companion_reference`: the e+i tour profiled with "new" = Songs of Innocence (the companion it kept).
    """
    if not recent:
        raise ValueError("Need at least one past album tour")
    n = round(statistics.median(p.songs_per_show for p in recent))
    share = float(statistics.median(p.new_share for p in recent))
    n_comp = round(companion_reference.new_share * n) if (has_new_companion and companion_reference) else 0
    return Expectation(
        songs_per_show=n,
        new_share=share,
        n_new_album=round(share * n),
        n_new_companion=n_comp,
        new_avg_position=previous.new_avg_position if previous.new_avg_position is not None else 0.5,
        new_opener_share=sum(p.new_opener_share for p in recent) / len(recent),
        tours=tuple(p.tour_name for p in recent),
    )


# --------------------------------------------------------------------------------------------------------------------
# Prediction of one tour


@dataclass
class TourPrediction:
    target_tour_name: str
    rows: list[dict]  # one per candidate: song_id, probability, predicted_in_setlist, position, set, model_part
    catalog_model: LogisticModel
    new_model: LogisticModel | None
    expectation: Expectation
    details: dict = field(default_factory=dict)


def _is_new(r: Mapping) -> bool:
    return bool(r["is_new_material"])


def predict_tour(
    target_rows: Sequence[Mapping],
    training_rows: Sequence[Mapping],
    exp: Expectation,
    l2: float = 1.0,
) -> TourPrediction:
    """Pre-tour prediction for one target (SPEC-09 §9.5.1-3).

    `training_rows`: feature rows of earlier album tours (with `is_core`); never the target's own rows.
    """
    target_name = target_rows[0]["target_tour_name"]
    if any(r["target_tour_name"] == target_name for r in training_rows):
        raise ValueError("Training rows include the target tour")
    cat_train = [r for r in training_rows if not _is_new(r)]
    cat_model = fit_logistic(
        design(cat_train, CATALOG_FEATURES), [bool(r["is_core"]) for r in cat_train], list(CATALOG_FEATURES), l2
    )
    new_train = [r for r in training_rows if _is_new(r)]
    new_model = (
        fit_logistic(design(new_train, NEW_FEATURES), [bool(r["is_core"]) for r in new_train], list(NEW_FEATURES), l2)
        if new_train
        else None
    )

    out = []
    for r in target_rows:
        if _is_new(r):
            z = new_model.logit([f(r) for f in NEW_FEATURES.values()]) if new_model else 0.0
            z += sum(w for k, w in NEW_PENALTIES.items() if r.get(k))
            out.append({"row": r, "score": z, "probability": _sigmoid(z), "model_part": "new"})
        else:
            p = cat_model.predict([f(r) for f in CATALOG_FEATURES.values()])
            out.append({"row": r, "score": p, "probability": p, "model_part": "catalog"})

    # How many: new songs per release group; the group's probabilities are rescaled to sum to its expected count.
    groups = {
        ROLE_PROMOTED: exp.n_new_album,
        ROLE_COMPANION: exp.n_new_companion,
    }
    picked: set[str] = set()
    for role, count in groups.items():
        members = [o for o in out if o["model_part"] == "new" and o["row"]["release_role"] == role]
        for o, p in zip(members, scale_to_total([o["probability"] for o in members], count), strict=True):
            o["probability"] = p
        ranked = sorted(members, key=lambda o: (-o["score"], o["row"]["song_id"]))
        picked.update(o["row"]["song_id"] for o in ranked[:count])
    n_new = len(picked)
    catalog = sorted(
        (o for o in out if o["model_part"] == "catalog"), key=lambda o: (-o["probability"], o["row"]["song_id"])
    )
    picked.update(o["row"]["song_id"] for o in catalog[: max(exp.songs_per_show - n_new, 0)])

    _order(out, picked, exp)
    rows = [
        {
            "song_id": o["row"]["song_id"],
            "probability": o["probability"],
            "predicted_in_setlist": o["row"]["song_id"] in picked,
            "predicted_position": o.get("position"),
            "predicted_set": o.get("set"),
            "model_part": o["model_part"],
            "score": o["score"],
        }
        for o in out
    ]
    return TourPrediction(target_name, rows, cat_model, new_model, exp, {"n_new_predicted": n_new})


def _order(out: list[dict], picked: set[str], exp: Expectation) -> None:
    """Order the predicted setlist (SPEC-09 §9.5.3): catalog songs at their previous (else career) average relative
    position, encore if they were in the encore at least half the time on the previous album tour; new songs at the
    previous album tour's average position for new songs, in score order. The opener is the best new single when
    new material opened at least half the shows of the recent album tours, else the catalog song that opened most
    often on the previous album tour."""
    chosen = [o for o in out if o["row"]["song_id"] in picked]
    new = [o for o in chosen if o["model_part"] == "new"]
    opener = None
    if new and exp.new_opener_share >= 0.5:
        opener = min(new, key=lambda o: (not o["row"]["is_single"], -o["score"], o["row"]["song_id"]))
    else:
        cat = [o for o in chosen if o["model_part"] == "catalog" and (o["row"]["prev_opener_rate"] or 0) > 0]
        if cat:
            opener = max(cat, key=lambda o: (o["row"]["prev_opener_rate"] * o["probability"], o["row"]["song_id"]))

    def sort_key(o: dict) -> tuple:
        r = o["row"]
        if o is opener:
            return (0, -1.0, 0.0, r["song_id"])
        encore = o["model_part"] == "catalog" and (r["prev_encore_rate"] or 0) >= 0.5
        o["set"] = "encore" if encore else "main"
        if o["model_part"] == "new":
            pos = exp.new_avg_position
        else:
            pos = r["prev_avg_position"]
            if pos is None:
                pos = r["career_avg_position"] if r["career_avg_position"] is not None else 0.5
        return (1 if encore else 0, pos, -o["score"], r["song_id"])

    for i, o in enumerate(sorted(chosen, key=sort_key), start=1):
        o["position"] = i
        o.setdefault("set", "main")


# --------------------------------------------------------------------------------------------------------------------
# Baselines and backtest metrics


BASELINES: dict[str, Callable[[Mapping], float]] = {
    "B1": lambda r: r["prev_album_tour_rate"] or 0.0,  # previous album tour's core set
    "B2": lambda r: r["career_rate"] or 0.0,  # probability for the Brier score; the set is the most-played songs
    "B3": lambda r: r["last_tour_rate"] or 0.0,  # latest tour of any type
}


def baseline_set(rows: Sequence[Mapping], method: str, n: int) -> list[Mapping]:
    """Predicted set of a baseline: top `n` by previous album tour rate (B1), career shows played (B2) or latest
    tour rate (B3)."""
    if method == "B2":
        return top_n(rows, lambda r: float(r["career_shows_played"] or 0), n)
    return top_n(rows, BASELINES[method], n)


def evaluate(
    target_rows: Sequence[Mapping],
    predicted_ids: Iterable[str],
    probabilities: Mapping[str, float],
    predicted_new: float,
    first_show_ids: Iterable[str],
    actual_new_per_show: float,
) -> dict[str, float | None]:
    """The four SPEC-09 §9.6 metrics for one method on one backtest tour."""
    core = [r["song_id"] for r in target_rows if r["is_core"]]
    return {
        "precision_at_n": precision_at_n(predicted_ids, core),
        "jaccard_first_show": jaccard(predicted_ids, first_show_ids),
        "brier_play_rate": brier(
            [probabilities[r["song_id"]] for r in target_rows], [r["play_rate"] or 0.0 for r in target_rows]
        ),
        "new_count_error": new_count_error(predicted_new, actual_new_per_show),
    }


def backtest_tour(
    target_rows: Sequence[Mapping],
    prediction: TourPrediction,
    first_show_ids: Iterable[str],
    actual_new_per_show: float,
) -> dict[str, dict[str, float | None]]:
    """Metrics of the model and of B1-B3 on one backtest tour, all with the same N."""
    first_show_ids = list(first_show_ids)
    n = prediction.expectation.songs_per_show
    pred = {r["song_id"]: r for r in prediction.rows}
    results = {
        "model": evaluate(
            target_rows,
            [s for s, r in pred.items() if r["predicted_in_setlist"]],
            {s: r["probability"] for s, r in pred.items()},
            prediction.details["n_new_predicted"],
            first_show_ids,
            actual_new_per_show,
        )
    }
    for method, prob in BASELINES.items():
        chosen = baseline_set(target_rows, method, n)
        results[method] = evaluate(
            target_rows,
            [r["song_id"] for r in chosen],
            {r["song_id"]: prob(r) for r in target_rows},
            sum(1 for r in chosen if r["is_new_material"]),
            first_show_ids,
            actual_new_per_show,
        )
    return results


def in_tour_update(
    pre_tour: Sequence[Mapping],
    shows_so_far: Sequence[frozenset[str]],
    songs_per_show: int,
    strength: float = PRIOR_STRENGTH,
) -> list[dict]:
    """Posterior probabilities after the tour's first `len(shows_so_far)` shows (SPEC-09 §9.5.4).

    `pre_tour`: rows with `song_id` and `probability`. Returns rows with the posterior `probability` and
    `predicted_in_setlist` = top `songs_per_show` by posterior (ties by pre-tour probability, then song id).
    """
    n = len(shows_so_far)
    counts = {r["song_id"]: sum(1 for s in shows_so_far if r["song_id"] in s) for r in pre_tour}
    post = [
        {**r, "probability": beta_binomial_update(r["probability"], counts[r["song_id"]], n, strength)}
        for r in pre_tour
    ]
    prior = {r["song_id"]: r["probability"] for r in pre_tour}
    ranked = sorted(post, key=lambda r: (-r["probability"], -prior[r["song_id"]], r["song_id"]))
    chosen = {r["song_id"] for r in ranked[:songs_per_show]}
    for r in post:
        r["predicted_in_setlist"] = r["song_id"] in chosen
    return post
