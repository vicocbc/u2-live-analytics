"""Date parsing for setlist.fm values."""

from __future__ import annotations

from datetime import date, datetime


def parse_setlistfm_date(s: str | None) -> date | None:
    """Parse a setlist.fm `eventDate` (`dd-MM-yyyy`). Returns None for empty or invalid values."""
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), "%d-%m-%Y").date()
    except ValueError:
        return None
