# Project charter

## Purpose

Show, with real data, how U2 has played live from 1976 to today: what they play, where, and how the
setlist evolved across eras and tours. The deliverable is a Power BI report backed by a Fabric lakehouse,
published on GitHub as a portfolio piece.

## Audience

- Recruiters and hiring managers for data roles: they skim the README and screenshots in under two minutes.
- U2 fans: they explore the report and want to find "their" show or song.

## Business questions

Each question has an id used by specs, measures and report pages.

| Id | Question | Main data |
| --- | --- | --- |
| Q1 | How many shows, songs, countries and cities across the career, and how did activity vary by year and decade? | fact_show, dim_date, dim_venue |
| Q2 | Which songs were played most, and which only once or twice (rarities)? | fact_performance, dim_song |
| Q3 | When did each song debut live and when was it last played? Which songs are "retired"? | fact_performance, dim_date |
| Q4 | For each tour, what share of the setlist came from the album being promoted vs. older material? | fact_performance, dim_song, dim_album, dim_tour |
| Q5 | Which albums "survive" on stage: share of each album in setlists over the decades? | fact_performance, dim_album, dim_date |
| Q6 | How stable or varied were setlists within a tour (distinct songs per tour, avg setlist similarity)? | fact_performance, dim_tour |
| Q7 | Where did they play: countries, continents, most-visited cities and venues, first and last visits? | fact_show, dim_venue |
| Q8 | How long are shows (songs per show) and how is a typical show structured (openers, encores, closers)? | fact_performance |
| Q9 | Which covers and guest appearances happened, and when? | fact_performance (cover/guest columns) |
| Q10 | Residency vs. tour: how did the Sphere residency (2023–24) differ from touring years? | fact_show, fact_performance, dim_tour |

Optional (phase 8): Q11 Do the most-played live songs match the most-streamed/listened songs today?

## Success criteria

- Every question Q1–Q10 is answered by at least one visual, and the README states three concrete findings.
- Report loads in under 5 seconds per page on Direct Lake.
- Totals reconcile: shows in the report = shows in `wh_gold.dbo.fact_show` = setlist.fm total minus cancelled shows (documented).
- A new visitor can reproduce the pipeline from the README with their own Fabric workspace and API keys.

## Out of scope

- Song lyrics (copyright): no lyric text stored or displayed.
- Copyrighted album art, band photos and logos: not used anywhere in the report or repo. Concert photos and tour
  logos/icons are allowed only when freely licensed (Wikimedia Commons, CC BY / CC BY-SA, CC0 or public domain),
  credited on the report's "About" page and in the README (decision by Vini, 2026-10-21; rules in the `u2-design-system` skill).
- Ticket sales and box office (no reliable open source); may be revisited later.

## Known data limitations (to be quantified in Silver)

- setlist.fm is crowd-sourced: early shows (1976–1980) often have no recorded setlist.
- Some performances are snippets or tapes; they are flagged, not counted as full performances by default.
- Song names vary across entries; mapping to MusicBrainz works is partly manual (`seeds/song_alias_overrides.csv`).
