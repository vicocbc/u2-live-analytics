-- Review queries for lk_silver.dbo.song_map (SPEC-03 §3.3; tasks T-17 and T-18). Read-only.
-- Run from the project folder (the lk_silver SQL endpoint is synced by the last cell of nb_silver_song_map):
--   $env:U2_SQL_SERVER=[Environment]::GetEnvironmentVariable('U2_SQL_SERVER','User')
--   sqlcmd -S $env:U2_SQL_SERVER -d wh_gold --authentication-method ActiveDirectoryDefault -W -s "|" -i sql/review/song_map_review.sql
-- Fix a mapping by adding a row to seeds/song_alias_overrides.csv (song_name as in setlist.fm, work_id or "ignore", note),
-- then: fab cp the seed to lk_bronze/Files/seeds/, run nb_bronze_seeds, then nb_silver_song_map.
SET NOCOUNT ON;

PRINT '== 1. Summary: map rows and full performances (non-tape, non-snippet) by match method';
SELECT match_method, COUNT(*) AS map_rows, SUM(performances) AS performances, SUM(full_performances) AS full_performances
FROM lk_silver.dbo.song_map
GROUP BY match_method
ORDER BY full_performances DESC;

PRINT '== 2. Mapped share of full performances (target >= 0.98; ignore rows excluded)';
SELECT CAST(SUM(CASE WHEN song_id IS NOT NULL THEN full_performances ELSE 0 END) AS float)
       / NULLIF(SUM(full_performances), 0) AS mapped_share,
       SUM(full_performances) AS full_performances
FROM lk_silver.dbo.song_map
WHERE match_method <> 'ignore';

PRINT '== 3. Every fuzzy match (accept, or correct with an override row)';
SELECT song_name_example, cover_artist, matched_title, match_score, song_id, performances
FROM lk_silver.dbo.song_map
WHERE match_method = 'fuzzy'
ORDER BY performances DESC, match_score;

PRINT '== 4. Unmapped keys with >= 3 performances (add an override: work_id or ignore)';
SELECT song_name_example, cover_artist, song_key, performances, full_performances
FROM lk_silver.dbo.song_map
WHERE match_method = 'unmapped' AND performances >= 3
ORDER BY performances DESC;

PRINT '== 5. Exact or fuzzy matches where several U2 works share the title (tie-break picked one)';
SELECT song_name_example, matched_title, match_candidates, song_id, performances
FROM lk_silver.dbo.song_map
WHERE match_candidates > 1
ORDER BY performances DESC;

PRINT '== 6. Covers with a U2-work match (cover_artist set but mapped to a U2 song; check these are right)';
SELECT song_name_example, cover_artist, match_method, matched_title, song_id, performances
FROM lk_silver.dbo.song_map
WHERE cover_artist IS NOT NULL AND match_method IN ('exact', 'fuzzy', 'override')
ORDER BY performances DESC;

PRINT '== 7. Override and ignore rows applied';
SELECT song_name_example, cover_artist, match_method, song_id, matched_title, performances
FROM lk_silver.dbo.song_map
WHERE match_method IN ('override', 'ignore')
ORDER BY match_method, performances DESC;

PRINT '== 8. (T-18) Shows removed as cancelled/postponed';
SELECT setlist_id, event_date, reason, venue_name, city_name, song_count, show_info
FROM lk_silver.dbo.show_excluded
ORDER BY event_date;

PRINT '== 9. (T-18) Performances flagged as snippets, with their info text';
SELECT p.event_date, p.song_name_raw, p.song_info
FROM lk_silver.dbo.performance AS p
WHERE p.is_snippet = 1
ORDER BY p.event_date;

PRINT '== 11. Fragments (song.is_fragment, from the is_fragment column of song_alias_overrides) and their performances';
SELECT s.song_id, s.title, SUM(m.performances) AS performances, SUM(m.full_performances) AS full_performances
FROM lk_silver.dbo.song AS s
LEFT JOIN lk_silver.dbo.song_map AS m ON m.song_id = s.song_id
WHERE s.is_fragment = 1
GROUP BY s.song_id, s.title;

PRINT '== 10. (T-18) Info texts that mention a snippet but are NOT flagged (check none should be)';
SELECT TOP 100 p.event_date, p.song_name_raw, p.song_info
FROM lk_silver.dbo.performance AS p
WHERE p.is_snippet = 0 AND (p.song_info LIKE '%snippet%' OR p.song_info LIKE '%partial%' OR p.song_info LIKE '%short%')
ORDER BY p.event_date;
