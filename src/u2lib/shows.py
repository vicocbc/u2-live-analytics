"""Show-level rules on setlist.fm `info`."""

from __future__ import annotations

import re

_CANCELLED = re.compile(
    r"^\W*(cancel+ed|called off)\b"
    r"|\b(show|concert|gig|event)\s+(was\s+|has been\s+|got\s+)?(cancel+ed|called off)\b"
    r"|\bcancel+ation\b"
    r"|\b(did not|didn't|never) (take place|took place|happen)"
)
_POSTPONED = re.compile(
    r"^\W*(postponed|rescheduled)\b(?! from)"
    r"|\b(show|concert|gig|event)\s+(was\s+|has been\s+|got\s+)?(postponed|rescheduled)\b(?! from)"
    r"|\bpostponed (to|until)\b"
    r"|\brescheduled (to|for)\b"
)
# A show that did happen as the replacement of an earlier date.
_MAKEUP = re.compile(r"\b(postponed|rescheduled|moved) from\b|\boriginally (scheduled|planned)\b|\bmake-?up\b")


def exclusion_reason(info: str | None) -> str | None:
    """`"cancelled"`, `"postponed"` or None for a show's setlist.fm `info`."""
    if not info:
        return None
    text = info.casefold()
    if _CANCELLED.search(text):
        return "cancelled"
    if _MAKEUP.search(text):
        return None
    if _POSTPONED.search(text):
        return "postponed"
    return None


def is_cancelled(info: str | None) -> bool:
    """True when the show did not take place on this date (cancelled or postponed)."""
    return exclusion_reason(info) is not None
