import pytest

from u2lib.songs import is_snippet, normalize_title


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("Pride (In the Name of Love)", "pride in the name of love"),
        ("Stuck in a Moment You Can't Get Out Of", "stuck in a moment you cant get out of"),
        ("Stuck in a Moment You Can’t Get Out Of", "stuck in a moment you cant get out of"),
        ("Hold Me, Thrill Me, Kiss Me, Kill Me", "hold me thrill me kiss me kill me"),
        ('"40"', "40"),
        ("The Fly", "fly"),
        ("The Unforgettable Fire", "unforgettable fire"),
        ("Theme from Mission: Impossible", "theme from mission impossible"),
        ("Rock & Roll", "rock and roll"),
        ("Rock and Roll", "rock and roll"),
        ("  Bad   [extended] ", "bad extended"),
        ("Café", "cafe"),
        ("ONE", "one"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_title(raw, key):
    assert normalize_title(raw) == key


def test_normalize_is_idempotent():
    key = normalize_title("The Sweetest Thing")
    assert normalize_title(key) == key


@pytest.mark.parametrize(
    "info",
    [
        "snippet",
        "Snippet",
        "(snippet)",
        "partial",
        "short version",
        "Shortened",
        "acoustic; snippet",
        "Edge on vocals, partial",
        "tease",
    ],
)
def test_self_snippet(info):
    assert is_snippet(info)


@pytest.mark.parametrize(
    "info",
    [
        None,
        "",
        "acoustic",
        "with 'Ruby Tuesday' snippet",
        'with "Sympathy for the Devil" and "Ruby Tuesday" snippets',
        "snippet of 'Ruby Tuesday'",
        "snippets from 'Bad'",
        "contains snippets of 'Norwegian Wood'",
        "Shortcut version intro",
    ],
)
def test_not_self_snippet(info):
    assert not is_snippet(info)


# T-18: real setlist.fm info texts reviewed on lk_silver.dbo.performance (run 20261021T150024Z).
@pytest.mark.parametrize(
    "info",
    [
        "Bono and The Edge only; shortened",
        "partial version with minimal backing by The Edge",
        "Bono and Edge only; partial version",
        "snippet / first verse",
        'Bono and The Edge only; shortened; with "Hallelujah" snippet',
        'acoustic; shortened; car bomb outro, with "When Johnny Comes Marching Home" snippet',
        "shortened due to vocal issues by Bono",
        "Snippet; first time extended",
    ],
)
def test_self_snippet_real_cases(info):
    assert is_snippet(info)


@pytest.mark.parametrize(
    "info",
    [
        "with Stephen Sondheim's 'Send in the Clowns' snippet",
        'with "Send in the Clowns"snippet',
        '"Send In the Clowns" snippet - only appeared during set 1',
        "with 'Get Off of My Cloud' / 'Give Peace a Chance' snippets",
        "Rebel Rebel snippet",
        "Love to Love You Baby, Barbara Ann, Discotheque Howie B Hairy B Mix and Whole Lotta Love snippets",
        'with "Wise Blood" excerpt and "Eeny Meeny Miny Moe" snippet',
        "With “Drowning Man” snippet",
        'with "Twilight" tease intro',
        "with false start; partially stripped down to just drums and vocals",
        "with first verse in French instead of Spanish",
        "Two takes; First take aborted around a minute into the song due to technical issues",
        "residency debut; a cappella; first time played since 2017",
    ],
)
def test_not_self_snippet_real_cases(info):
    assert not is_snippet(info)


# T-18 change requests for u2lib.songs.is_snippet (SPEC-03 §3.1), implemented in u2lib 0.3.0.
# CR-1: a bare "snippet" after a "with ..." segment or an intro note refers to the other song.
@pytest.mark.parametrize(
    "info",
    [
        'with "Teenage Kicks", snippet',
        'with "Amazing Grace", snippet',
        'with"You\'ll Never Walk Alone", snippet',
        'Live debut; with US Mix intro / snippet; with "Maybe the time is right" verse',
    ],
)
def test_cr1_snippet_of_other_song(info):
    assert not is_snippet(info)


# CR-2: more phrasings of a partly played song.
@pytest.mark.parametrize(
    "info",
    [
        "acoustic; shorted",
        "Spontaneous performance, cut short before Edge's solo. First time since 10/12/1993",
        "aborted due to police",
        "not on the printed setlist; first verse & chorus",
    ],
)
def test_cr2_more_self_snippet_phrasings(info):
    assert is_snippet(info)
