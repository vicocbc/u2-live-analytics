"""Feature table for the setlist prediction (SPEC-09 §9.4).

One row per (candidate song, target tour). Every feature of a target tour is computed from shows dated strictly
before the tour's first show (the *cutoff*); `assert_no_leakage` turns a violation into a hard failure.

Inputs are plain mappings with the columns of the Silver tables (`show`, `performance` joined to `song_map`, `song`,
`album`, `tour`, `release_track`), so the same code runs in a Fabric notebook and in local tests.
"""

from __future__ import annotations

import bisect
import datetime as dt
import statistics
from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass

from u2lib.songs import normalize_title

NO_TOUR = "(No tour)"
MIN_TOUR_SHOWS = 10  # a "tour" for last_tour_rate and tours_since_last_played has at least this many shows
LATE_SINGLE_DAYS = 365  # a single released more than this after its album is a reissue, not a single (T-46)
CORE_RATE = 0.5  # is_core = play_rate >= CORE_RATE

ROLE_PROMOTED = "promoted_album"
ROLE_COMPANION = "companion_release"
ROLE_CATALOG = "catalog"


class LeakageError(AssertionError):
    """A feature of a target tour read a show dated on or after the tour's first show."""


def assert_no_leakage(dates: Iterable[dt.date | None], cutoff: dt.date, context: str = "") -> int:
    """Raise `LeakageError` if any date is on or after `cutoff`. Returns how many dates were checked."""
    checked = [d for d in dates if d is not None]
    late = [d for d in checked if d >= cutoff]
    if late:
        raise LeakageError(f"{context}: {len(late)} show(s) on or after {cutoff} (earliest {min(late)})")
    return len(checked)


# --------------------------------------------------------------------------------------------------------------------
# Shows and plays


@dataclass(frozen=True)
class Play:
    song_id: str
    position: float  # relative position among the show's played songs: 0 = first, 1 = last
    is_encore: bool
    is_opener: bool


@dataclass(frozen=True)
class Show:
    setlist_id: str
    event_date: dt.date
    tour_name: str
    plays: tuple[Play, ...]

    @property
    def song_ids(self) -> frozenset[str]:
        return frozenset(p.song_id for p in self.plays)


def is_played(perf: Mapping, fragment_ids: Collection[str] = ()) -> bool:
    """A full performance (SPEC-05): not a tape, not a snippet, mapped to a song that is not a fragment."""
    song_id = perf.get("song_id")
    return bool(song_id) and not perf.get("is_tape") and not perf.get("is_snippet") and song_id not in fragment_ids


def build_shows(
    shows: Iterable[Mapping],
    performances: Iterable[Mapping],
    fragment_ids: Collection[str] = (),
) -> list[Show]:
    """Shows with their played songs, sorted by (date, setlist id).

    `shows`: `setlist_id`, `event_date`, `tour_name` (pass only shows with a setlist; a null tour is `(No tour)`).
    `performances`: `setlist_id`, `setlist_position`, `song_id`, `is_tape`, `is_snippet`, `is_encore`.
    A song played twice in a show counts once, at its first position. The opener is the first played song.
    """
    by_show: dict[str, list[Mapping]] = defaultdict(list)
    for p in performances:
        if is_played(p, fragment_ids):
            by_show[p["setlist_id"]].append(p)
    result = []
    for s in shows:
        perfs = sorted(by_show.get(s["setlist_id"], ()), key=lambda p: p["setlist_position"])
        seen: dict[str, Mapping] = {}
        for p in perfs:
            seen.setdefault(p["song_id"], p)
        ordered = list(seen.values())
        last = max(len(ordered) - 1, 1)
        plays = tuple(
            Play(p["song_id"], i / last if len(ordered) > 1 else 0.0, bool(p.get("is_encore")), i == 0)
            for i, p in enumerate(ordered)
        )
        result.append(Show(s["setlist_id"], s["event_date"], s.get("tour_name") or NO_TOUR, plays))
    return sorted(result, key=lambda s: (s.event_date, s.setlist_id))


# --------------------------------------------------------------------------------------------------------------------
# Tours


@dataclass(frozen=True)
class Tour:
    name: str
    tour_type: str | None
    first_show_date: dt.date | None
    last_show_date: dt.date | None
    album_id: str | None  # album promoted
    is_planned: bool
    n_shows: int  # shows with a setlist


def build_tours(
    tours: Iterable[Mapping],
    shows: Sequence[Show],
    planned_first_show: Mapping[str, dt.date] | None = None,
) -> list[Tour]:
    """Tours from `lk_silver.dbo.tour`, with `n_shows` counted on shows with a setlist.

    A planned tour has no shows and null dates in Silver; `planned_first_show` gives its announced first show.
    """
    planned_first_show = planned_first_show or {}
    n_shows: dict[str, int] = defaultdict(int)
    for s in shows:
        n_shows[s.tour_name] += 1
    result = []
    for t in tours:
        first = t.get("first_show_date") or planned_first_show.get(t["tour_name"])
        result.append(
            Tour(
                name=t["tour_name"],
                tour_type=t.get("tour_type"),
                first_show_date=first,
                last_show_date=t.get("last_show_date"),
                album_id=t.get("album_promoted_id"),
                is_planned=bool(t.get("is_planned")),
                n_shows=n_shows.get(t["tour_name"], 0),
            )
        )
    return sorted(result, key=lambda t: (t.first_show_date or dt.date.max, t.name))


def previous_album_tour(tours: Iterable[Tour], cutoff: dt.date) -> Tour | None:
    """Latest `album` tour that started before `cutoff` and has shows."""
    prior = [
        t for t in tours if t.tour_type == "album" and t.n_shows and t.first_show_date and t.first_show_date < cutoff
    ]
    return max(prior, key=lambda t: t.first_show_date) if prior else None


def qualifying_tours(
    tours: Iterable[Tour], shows_before: Sequence[Show], min_shows: int = MIN_TOUR_SHOWS
) -> list[Tour]:
    """Tours of any type (not `(No tour)`) with at least `min_shows` shows among `shows_before`, by last show date."""
    counts: dict[str, int] = defaultdict(int)
    last: dict[str, dt.date] = {}
    for s in shows_before:
        counts[s.tour_name] += 1
        last[s.tour_name] = max(last.get(s.tour_name, s.event_date), s.event_date)
    result = [t for t in tours if t.name != NO_TOUR and counts.get(t.name, 0) >= min_shows]
    return sorted(result, key=lambda t: (last[t.name], t.name))


# --------------------------------------------------------------------------------------------------------------------
# Songs, release and singles


@dataclass(frozen=True)
class SongInfo:
    song_id: str
    title: str
    is_original: bool
    is_fragment: bool
    album_id: str | None  # release_track album for 2026 tracks, else the song's first album
    release_date: dt.date | None
    single_date: dt.date | None
    has_featured_artist: bool = False
    is_spoken_word: bool = False
    is_bonus_track: bool = False


def build_song_infos(
    songs: Iterable[Mapping],
    albums: Iterable[Mapping],
    release_tracks: Iterable[Mapping] = (),
) -> dict[str, SongInfo]:
    """Songs with the release that the features use.

    2026 trilogy tracks take release and date from `release_track` (SPEC-09 §9.3: e.g. Get Back to Now has no
    `first_album_id`). Other songs take their first album's release date, else 1 January of `first_release_year`.
    """
    album_date = {a["album_id"]: a.get("release_date") for a in albums}
    tracks = {r["song_id"]: r for r in release_tracks}
    result = {}
    for s in songs:
        rt = tracks.get(s["song_id"])
        if rt:
            album_id, release_date = rt["album_id"], rt["release_date"]
        else:
            album_id = s.get("first_album_id")
            release_date = album_date.get(album_id) if album_id else None
            if release_date is None and s.get("first_release_year"):
                release_date = dt.date(int(s["first_release_year"]), 1, 1)
        result[s["song_id"]] = SongInfo(
            song_id=s["song_id"],
            title=s["title"],
            is_original=bool(s.get("is_original")),
            is_fragment=bool(s.get("is_fragment")),
            album_id=album_id,
            release_date=release_date,
            single_date=s.get("single_date") if s.get("is_single") else None,
            has_featured_artist=bool(rt and rt.get("featured_artist")),
            is_spoken_word=bool(rt and rt.get("is_spoken_word")),
            is_bonus_track=bool(rt and rt.get("is_bonus_track")),
        )
    return result


def is_low_precision_date(d: dt.date | None) -> bool:
    """MusicBrainz year-only dates arrive in Silver as 1 January (e.g. The Unforgettable Fire single, 1984-01-01)."""
    return d is not None and d.month == 1 and d.day == 1


def single_known_before(
    single_date: dt.date | None,
    album_release_date: dt.date | None,
    cutoff: dt.date,
    late_days: int = LATE_SINGLE_DAYS,
) -> bool:
    """True when the song counts as a single for a tour starting at `cutoff` (SPEC-09 §9.4, T-46 findings).

    - A single released more than `late_days` after its album is a reissue (Running to Stand Still 2009, Red Hill
      Mining Town 2017) and never counts.
    - A precise date counts when it is before `cutoff`.
    - A 1 January date is treated as "sometime that year": an earlier year counts, a later year does not, and the
      same year counts only if the album itself was out before `cutoff`.
    """
    if single_date is None:
        return False
    if album_release_date is not None and (single_date - album_release_date).days > late_days:
        return False
    if is_low_precision_date(single_date) and single_date.year == cutoff.year:
        return album_release_date is not None and album_release_date < cutoff
    if is_low_precision_date(single_date):
        return single_date.year < cutoff.year
    return single_date < cutoff


def singles_as_of(
    songs: Mapping[str, SongInfo],
    album_release: Mapping[str, dt.date | None],
    cutoff: dt.date,
    late_days: int = LATE_SINGLE_DAYS,
) -> dict[str, int]:
    """`single_order` as known before `cutoff`: per album, the singles that count, ranked by (date, title, id)."""
    by_album: dict[str, list[tuple]] = defaultdict(list)
    for s in songs.values():
        if s.album_id and single_known_before(s.single_date, album_release.get(s.album_id), cutoff, late_days):
            by_album[s.album_id].append((s.single_date, normalize_title(s.title), s.song_id))
    return {song_id: order for rows in by_album.values() for order, (_, _, song_id) in enumerate(sorted(rows), start=1)}


def is_title_track(song_title: str, album_title: str | None, tour_name: str | None) -> bool:
    """Song title equals the album title, contains it (Go (Carnaval de Luz)), or appears in the tour name
    (The Greatest Show on Earth). Word-bounded comparison of `normalize_title` keys; callers pass only songs of the
    promoted album or a companion release."""
    song = normalize_title(song_title)
    if not song:
        return False
    padded = f" {song} "
    album = normalize_title(album_title)
    tour = normalize_title(tour_name)
    return bool(album and (song == album or f" {album} " in padded)) or bool(tour and padded in f" {tour} ")


# --------------------------------------------------------------------------------------------------------------------
# Feature rows


def _median(values: Sequence[float]) -> float | None:
    return float(statistics.median(values)) if values else None


def _rate(n: int, d: int) -> float | None:
    return n / d if d else None


def build_features(
    target: Tour,
    tours: Sequence[Tour],
    shows: Sequence[Show],
    songs: Mapping[str, SongInfo],
    album_titles: Mapping[str, str],
    album_release: Mapping[str, dt.date | None],
    companion_album_ids: Collection[str] = (),
    min_tour_shows: int = MIN_TOUR_SHOWS,
) -> list[dict]:
    """Feature rows of one target tour (SPEC-09 §9.4), with targets when the tour has shows.

    Candidates: original songs (not fragments) released before the cutoff or already played, every song of the
    promoted album or a companion release (even if released after the first show, as The Unforgettable Fire in
    1984), and covers played on the previous album tour.
    """
    cutoff = target.first_show_date
    if cutoff is None:
        raise ValueError(f"Target tour {target.name!r} has no first show date")
    history = [s for s in shows if s.event_date < cutoff]
    assert_no_leakage((s.event_date for s in history), cutoff, target.name)
    history_dates = [s.event_date for s in history]

    prior_tours = [t for t in tours if t.name != target.name]
    prev = previous_album_tour(prior_tours, cutoff)
    qualifying = qualifying_tours(prior_tours, history, min_tour_shows)
    last = qualifying[-1] if qualifying else None
    album_tours = [
        t for t in prior_tours if t.tour_type == "album" and t.first_show_date and t.first_show_date < cutoff
    ]
    promoted_before = {t.album_id for t in album_tours if t.album_id}
    first_show_of = {t.name: t.first_show_date for t in qualifying}
    last_end = max((s.event_date for s in history if s.tour_name == last.name), default=None) if last else None

    played_dates: dict[str, list[dt.date]] = defaultdict(list)
    played_tours: dict[str, set[str]] = defaultdict(set)
    career_positions: dict[str, list[float]] = defaultdict(list)
    tour_plays: dict[str, dict[str, list[Play]]] = defaultdict(lambda: defaultdict(list))
    tour_shows: dict[str, int] = defaultdict(int)
    pre_tour: dict[str, int] = defaultdict(int)
    for s in history:
        tour_shows[s.tour_name] += 1
        in_window = last_end is not None and s.event_date > last_end
        for p in s.plays:
            played_dates[p.song_id].append(s.event_date)
            played_tours[p.song_id].add(s.tour_name)
            career_positions[p.song_id].append(p.position)
            tour_plays[s.tour_name][p.song_id].append(p)
            if in_window:
                pre_tour[p.song_id] += 1

    target_shows = [s for s in shows if s.tour_name == target.name and s.event_date >= cutoff]
    first_show = target_shows[0] if target_shows else None
    target_counts: dict[str, int] = defaultdict(int)
    for s in target_shows:
        for song_id in s.song_ids:
            target_counts[song_id] += 1

    prev_plays = tour_plays.get(prev.name, {}) if prev else {}
    prev_n = tour_shows.get(prev.name, 0) if prev else 0
    last_plays = tour_plays.get(last.name, {}) if last else {}
    last_n = tour_shows.get(last.name, 0) if last else 0
    single_order = singles_as_of(songs, album_release, cutoff)

    rows = []
    for s in sorted(songs.values(), key=lambda x: x.song_id):
        if s.is_fragment:
            continue
        if s.album_id and s.album_id == target.album_id:
            role = ROLE_PROMOTED
        elif s.album_id and s.album_id in companion_album_ids:
            role = ROLE_COMPANION
        else:
            role = ROLE_CATALOG
        dates = played_dates.get(s.song_id, [])
        if s.is_original:
            released = s.release_date is not None and s.release_date < cutoff
            if role == ROLE_CATALOG and not released and not dates:
                continue
        elif s.song_id not in prev_plays:
            continue
        assert_no_leakage(dates, cutoff, f"{target.name} / {s.song_id}")

        starts = [d for d in (s.release_date, dates[0] if dates else None) if d is not None]
        start = min(starts) if starts else None
        shows_since = len(history_dates) - bisect.bisect_left(history_dates, start) if start else 0
        eligible_tours = [t for t in album_tours if start and t.last_show_date and t.last_show_date >= start]
        played_in = played_tours.get(s.song_id, set())
        last_played = dates[-1] if dates else None
        prev_song = prev_plays.get(s.song_id, [])
        is_new = role == ROLE_PROMOTED or (role == ROLE_COMPANION and s.album_id not in promoted_before)
        order = single_order.get(s.song_id)
        row = {
            "target_tour_name": target.name,
            "target_first_show_date": cutoff,
            "is_planned_tour": target.is_planned,
            "song_id": s.song_id,
            "song_title": s.title,
            "album_id": s.album_id,
            "release_date": s.release_date,
            "is_original": s.is_original,
            "prev_album_tour_name": prev.name if prev else None,
            "prev_album_tour_rate": _rate(len(prev_song), prev_n) or 0.0,
            "last_tour_name": last.name if last else None,
            "last_tour_type": last.tour_type if last else None,
            "last_tour_rate": _rate(len(last_plays.get(s.song_id, [])), last_n) or 0.0,
            "tours_played_share": _rate(sum(1 for t in eligible_tours if t.name in played_in), len(eligible_tours)),
            "career_rate": _rate(len(dates), shows_since),
            "career_shows_played": len(dates),
            "tours_since_last_played": (
                sum(1 for t in qualifying if first_show_of[t.name] > last_played) if last_played else None
            ),
            "played_pre_tour": pre_tour.get(s.song_id, 0),
            "is_new_material": is_new,
            "release_role": role,
            "days_release_to_tour": (cutoff - s.release_date).days if s.release_date else None,
            "is_single": order is not None,
            "single_order": order,
            "is_title_track": role != ROLE_CATALOG
            and is_title_track(s.title, album_titles.get(s.album_id or ""), target.name),
            "has_featured_artist": s.has_featured_artist,
            "is_spoken_word": s.is_spoken_word,
            "is_bonus_track": s.is_bonus_track,
            "prev_avg_position": _mean([p.position for p in prev_song]),
            "prev_encore_rate": _rate(sum(p.is_encore for p in prev_song), len(prev_song)),
            "prev_opener_rate": _rate(sum(p.is_opener for p in prev_song), len(prev_song)),
            "career_avg_position": _mean(career_positions.get(s.song_id, [])),
            "history_shows": len(history),
            "history_max_date": history_dates[-1] if history_dates else None,
            "play_rate": _rate(target_counts.get(s.song_id, 0), len(target_shows)),
            "is_core": (target_counts.get(s.song_id, 0) / len(target_shows) >= CORE_RATE) if target_shows else None,
            "in_first_show": (s.song_id in first_show.song_ids) if first_show else None,
        }
        rows.append(row)
    return rows


def _mean(values: Sequence[float]) -> float | None:
    """Mean relative position (None when the song was not played)."""
    return sum(values) / len(values) if values else None


# --------------------------------------------------------------------------------------------------------------------
# Tour profiles (how a past album tour was built: length, new material, opener)


@dataclass(frozen=True)
class TourProfile:
    tour_name: str
    first_show_date: dt.date
    last_show_date: dt.date
    n_shows: int
    songs_per_show: float  # median number of played songs per show
    new_share: float  # median per show of (songs from the given albums / songs played)
    new_per_show: float  # median per show of songs from the given albums
    new_opener_share: float  # share of shows opened by a song from the given albums
    new_avg_position: float | None  # mean relative position of plays of songs from the given albums


def tour_profile(
    tour: Tour, shows: Sequence[Show], songs: Mapping[str, SongInfo], album_ids: Collection[str]
) -> TourProfile:
    """Profile of `tour` measured on its own shows, with "new" = songs whose release is in `album_ids`."""
    own = [s for s in shows if s.tour_name == tour.name]
    if not own:
        raise ValueError(f"Tour {tour.name!r} has no shows with a setlist")
    albums = set(album_ids)

    def is_new(song_id: str) -> bool:
        info = songs.get(song_id)
        return bool(info and info.album_id in albums)

    counts = [len(s.plays) for s in own]
    new_counts = [sum(is_new(p.song_id) for p in s.plays) for s in own]
    shares = [n / c for n, c in zip(new_counts, counts, strict=True) if c]
    openers = [s.plays[0].song_id for s in own if s.plays]
    positions = [p.position for s in own for p in s.plays if is_new(p.song_id)]
    return TourProfile(
        tour_name=tour.name,
        first_show_date=own[0].event_date,
        last_show_date=own[-1].event_date,
        n_shows=len(own),
        songs_per_show=float(statistics.median(counts)),
        new_share=_median(shares) or 0.0,
        new_per_show=float(statistics.median(new_counts)),
        new_opener_share=sum(is_new(o) for o in openers) / len(openers) if openers else 0.0,
        new_avg_position=sum(positions) / len(positions) if positions else None,
    )
