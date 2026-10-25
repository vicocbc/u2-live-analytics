"""Catalog helpers for Silver: release and track resolution, singles history (SPEC-03 §3.2, SPEC-09 §9.2-9.3).

Albums are plain mappings with the keys of `lk_silver.dbo.album` that matter here:
`album_id`, `title`, `release_date` (`date` or None), `is_studio`.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass

from u2lib.songs import normalize_title

_FAR_FUTURE = dt.date(9999, 12, 31)

OVERRIDE_ORIGINAL = "original"
OVERRIDE_IGNORE = "ignore"


def album_rank(album: Mapping) -> tuple:
    """Preference among albums sharing a title: studio first, then earliest release date, then id."""
    return (not album["is_studio"], album["release_date"] or _FAR_FUTURE, album["album_id"])


def resolve_album_id(
    albums: Iterable[Mapping],
    release_group_id: str | None = None,
    title: str | None = None,
) -> tuple[str | None, str]:
    """Album id for a seed release: by MusicBrainz release group id first, then by `normalize_title`.

    Returns `(album_id, method)` with method `id`, `title` or `unresolved` (album_id None).
    A release group id that is not among `albums` falls back to the title.
    """
    albums = list(albums)
    rg_id = (release_group_id or "").strip().lower()
    if rg_id:
        for a in albums:
            if a["album_id"].lower() == rg_id:
                return a["album_id"], "id"
    key = normalize_title(title)
    if key:
        hits = [a for a in albums if normalize_title(a["title"]) == key]
        if hits:
            return min(hits, key=album_rank)["album_id"], "title"
    return None, "unresolved"


def synthetic_song_id(song_key: str) -> str:
    """Song id of a U2 original without a MusicBrainz work (SPEC-03 §3.2)."""
    return f"u2:{song_key}"


def resolve_track_song_id(
    track_title: str,
    override_target: str | None = None,
    release_work_ids_by_key: Mapping[str, Sequence[str]] | None = None,
    work_ids_by_key: Mapping[str, Sequence[str]] | None = None,
) -> tuple[str, str]:
    """Song id for a release track. Returns `(song_id, method)`.

    Order (same precedence as `nb_silver_song_map`, so played and released versions get the same id):
    1. `override`: the song-alias override for the track's key (a work id, or `original` = `u2:<key>`;
       `ignore` is skipped);
    2. `release_work`: a work recorded on the track's own release whose title has the same key;
    3. `work`: any U2 work with the same key (callers pass candidates already ordered by preference);
    4. `synthetic`: `u2:<key>`.
    """
    key = normalize_title(track_title)
    if not key:
        raise ValueError(f"Track title has an empty song key: {track_title!r}")
    target = (override_target or "").strip()
    if target.lower() == OVERRIDE_ORIGINAL:
        return synthetic_song_id(key), "override"
    if target and target.lower() != OVERRIDE_IGNORE:
        return target, "override"
    for method, index in (("release_work", release_work_ids_by_key), ("work", work_ids_by_key)):
        candidates = (index or {}).get(key) or ()
        if candidates:
            return candidates[0], method
    return synthetic_song_id(key), "synthetic"


@dataclass(frozen=True)
class SingleInfo:
    """Singles history of one song: first single date and its order among its album's singles (1 = first)."""

    single_date: dt.date | None
    single_order: int


def earliest_single_by_key(
    singles: Iterable[tuple[str, dt.date | None]],
    excluded_titles: Collection[str] = (),
) -> dict[str, dt.date | None]:
    """Earliest release date per normalised single title. Undated singles count only when no dated one exists.

    `singles` are `(title, first_release_date)` of `album_type = 'single'` release groups; titles in
    `excluded_titles` (compared with `normalize_title`) are ignored.
    """
    excluded = {normalize_title(t) for t in excluded_titles}
    earliest: dict[str, dt.date | None] = {}
    for title, date in singles:
        key = normalize_title(title)
        if not key or key in excluded:
            continue
        current = earliest.get(key)
        if key not in earliest or (date is not None and (current is None or date < current)):
            earliest[key] = date
    return earliest


def singles_history(
    songs: Iterable[Mapping],
    singles: Iterable[tuple[str, dt.date | None]],
    excluded_titles: Collection[str] = (),
) -> dict[str, SingleInfo]:
    """Singles history for album songs (SPEC-09 §9.2).

    `songs` are mappings with `song_id`, `title` and `album_id` (the song's first studio album; pass only the songs
    that should get the flag). A song is a single when a single's normalised title equals its normalised title;
    `single_date` is that single's earliest release date and `single_order` ranks the album's singles by date
    (undated last), then song key, then id. Returns only the songs that are singles.
    """
    earliest = earliest_single_by_key(singles, excluded_titles)
    by_album: dict[str, list[tuple]] = defaultdict(list)
    for s in songs:
        key = normalize_title(s["title"])
        if key in earliest and s["album_id"]:
            date = earliest[key]
            by_album[s["album_id"]].append((date or _FAR_FUTURE, key, s["song_id"], date))
    result: dict[str, SingleInfo] = {}
    for rows in by_album.values():
        for order, (_, _, song_id, date) in enumerate(sorted(rows), start=1):
            result[song_id] = SingleInfo(single_date=date, single_order=order)
    return result
