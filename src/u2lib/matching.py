"""Fuzzy matching of song keys against work titles."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from rapidfuzz import fuzz, process


def best_match(
    name: str,
    candidates: Iterable[str],
    threshold: float,
    scorer: Callable[..., float] = fuzz.ratio,
) -> tuple[str, float] | None:
    """Best candidate for `name` with a score in [0, 100], or None if nothing reaches `threshold`.

    Pass keys already normalised with `songs.normalize_title`. The default scorer is plain `ratio`
    (edit distance): partial scorers rate short titles such as "One" too high against longer ones.
    """
    if not name:
        return None
    result = process.extractOne(name, list(candidates), scorer=scorer, score_cutoff=threshold)
    if result is None:
        return None
    candidate, score, _ = result
    return candidate, float(score)
