from rapidfuzz import fuzz

from u2lib.matching import best_match

TITLES = ["one", "one tree hill", "with or without you", "where the streets have no name", "bad"]


def test_exact_match_scores_100():
    assert best_match("bad", TITLES, 92) == ("bad", 100.0)


def test_close_spelling_matches():
    match = best_match("where the streets have no names", TITLES, 92)
    assert match is not None
    assert match[0] == "where the streets have no name"
    assert match[1] >= 92


def test_short_title_does_not_match_longer_one():
    assert best_match("one tree", ["one tree hill"], 92) is None


def test_below_threshold_returns_none():
    assert best_match("vertigo", TITLES, 92) is None


def test_empty_inputs():
    assert best_match("", TITLES, 92) is None
    assert best_match("bad", [], 92) is None


def test_custom_scorer_and_generator_candidates():
    match = best_match("you without with or", (t for t in TITLES), 90, scorer=fuzz.token_sort_ratio)
    assert match == ("with or without you", 100.0)
