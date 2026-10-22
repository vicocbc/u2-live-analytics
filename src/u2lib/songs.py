"""Song-name normalisation and performance flags."""

from __future__ import annotations

import re
import unicodedata

_APOSTROPHES = re.compile(r"['‘’ʼ`]")
_NON_WORD = re.compile(r"[^\w\s]|_")
_SPACES = re.compile(r"\s+")
_LEADING_THE = re.compile(r"^the\s+")

# A segment of `info` that describes the performance itself as incomplete.
_SELF_SNIPPET = re.compile(
    r"^(partial|snippet|short|shortened|shorted|cut short|abbreviated|fragment|excerpt|tease|teaser|aborted"
    r"|first verse)\b"
    r"(?!s? (of|from)\b)"
)
# A bare "snippet" segment describes the other song when the previous segment names one ("with ...") or an intro.
_BARE_SNIPPET = re.compile(r"^snippets?$")
_REFERS_TO_OTHER = re.compile(r"^with\b|\bintro\b")
_INFO_SEPARATORS = re.compile(r"[;,/]")


def normalize_title(s: str | None) -> str:
    """Matching key for a song title.

    Casefold, drop accents and quotes, turn brackets and other punctuation into spaces, unify `&` and `and`,
    collapse spaces and remove a leading "the ". Only for matching: never display the result.
    """
    if not s:
        return ""
    text = unicodedata.normalize("NFKD", s)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("&", " and ")
    text = _APOSTROPHES.sub("", text)
    text = _NON_WORD.sub(" ", text)
    text = _SPACES.sub(" ", text).strip()
    return _LEADING_THE.sub("", text)


def is_snippet(info: str | None) -> bool:
    """True when setlist.fm `info` says the song itself was only partly played.

    Notes about snippets of other songs inside a full performance ("with 'Ruby Tuesday' snippet",
    "snippets of ...", 'with "Teenage Kicks", snippet', "with US Mix intro / snippet") are not snippets of this song.
    """
    if not info:
        return False
    previous = ""
    for segment in _INFO_SEPARATORS.split(info.casefold()):
        segment = segment.strip(" \t()[]\"'")
        refers_to_other = _BARE_SNIPPET.match(segment) and _REFERS_TO_OTHER.search(previous)
        if _SELF_SNIPPET.match(segment) and not refers_to_other:
            return True
        previous = segment
    return False
