---
name: source-apis
description: How to call the setlist.fm and MusicBrainz APIs correctly for U2 Live Analytics — endpoints, auth, rate limits, pagination, response quirks and terms of use. Use when writing or debugging Bronze ingestion notebooks.
---

# Source APIs

## setlist.fm

- Base: `https://api.setlist.fm/rest/1.0`. Docs: https://api.setlist.fm/docs/1.0/index.html
- Headers: `x-api-key: <key>`, `Accept: application/json` (default is XML), `Accept-Language: en`.
- U2 artist MBID: `a3cb23fc-acd3-4ce0-8f36-1e5aa6a18432`. Always validate with `GET /artist/{mbid}` that the name is "U2" (tribute bands exist).
- Setlists: `GET /artist/{mbid}/setlists?p={page}`; 20 per page; response has `total`, `itemsPerPage`, `page`, `setlist[]`.
- Dates: `eventDate` is `dd-MM-yyyy`; `lastUpdated` is `yyyy-MM-dd'T'HH:mm:ss.SSSZ`.
- Structure: `setlist.sets.set[]` → each set has optional `name`, optional `encore` (int), `song[]`. Song: `name`, `info`, `tape` (bool), `cover{mbid,name}`, `with{mbid,name}`.
- Songs have no ids, only names: mapping to MusicBrainz works happens in Silver.
- `versionId` changes when fans edit a setlist; the site is crowd-sourced and old shows change.
- Rate limiting: on HTTP 429, back off (honour `Retry-After` when present) and retry; keep ~0.5 s between calls.
- Terms: free for non-commercial use only. Credit setlist.fm. Do not redistribute bulk extracts.

## MusicBrainz

- Base: `https://musicbrainz.org/ws/2/`, add `fmt=json`. Docs: https://musicbrainz.org/doc/MusicBrainz_API
- No key. A meaningful `User-Agent` is mandatory, e.g. `U2LiveAnalytics/0.1 ( https://github.com/<user>/u2-live-analytics )`; requests without one get blocked.
- Rate limit: average of 1 request per second per client. Sleep ≥ 1.0 s between calls; on 503 back off and retry.
- Browse (paginated with `limit` ≤ 100 and `offset`): `release-group?artist=<mbid>&type=album`, `release?release-group=<id>&status=official`, `work?artist=<mbid>`.
- Lookup with includes: `release/<id>?inc=recordings+recording-level-rels+work-rels+artist-credits` returns media → tracks → recording → relations (type `performance`) → work.
- Release groups: `primary-type` (Album, Single, EP…) and `secondary-types` (Live, Compilation, Soundtrack, Remix…). A studio album = primary Album with no secondary types.
- Data is CC0 for core data; still credit MusicBrainz.

## Shared patterns

- Save every raw response to `Files/bronze/<source>/u2/<run_id>/page_NNNN.json` before parsing.
- Reference implementation: `nb_u2_load_bronze` (setlist.fm) — artist validation, `api_get` with backoff, flatten, write.
- Use a `requests.Session`, timeout 30 s, max 5 retries with exponential backoff.
- Log progress every 10 pages, not every call.
