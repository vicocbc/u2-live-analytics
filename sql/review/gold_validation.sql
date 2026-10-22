-- Gold validation queries (SPEC-04 acceptance; task T-21). Read-only.
-- Run from the project folder:
--   $env:U2_SQL_SERVER=[Environment]::GetEnvironmentVariable('U2_SQL_SERVER','User')
--   sqlcmd -S $env:U2_SQL_SERVER -d wh_gold --authentication-method ActiveDirectoryDefault -W -s "|" -i sql/review/gold_validation.sql
-- Each section prints the value(s) to compare; "expect" comments give the value on Gold run 20261021T155954Z.
SET NOCOUNT ON;

PRINT '== 0. Gold build in use (latest Gold run in dq_run_log and _built_at of the tables)';
SELECT TOP 1 run_id, MAX(checked_at) AS last_check, COUNT(*) AS checks,
       SUM(CASE WHEN status = 'fail' THEN 1 ELSE 0 END) AS fails,
       SUM(CASE WHEN status = 'warning' THEN 1 ELSE 0 END) AS warnings
FROM dbo.dq_run_log WHERE layer = 'gold' GROUP BY run_id ORDER BY MAX(checked_at) DESC;
SELECT 'fact_performance' AS t, MIN(_built_at) AS built_min, MAX(_built_at) AS built_max FROM dbo.fact_performance
UNION ALL SELECT 'fact_show', MIN(_built_at), MAX(_built_at) FROM dbo.fact_show
UNION ALL SELECT 'dim_song', MIN(_built_at), MAX(_built_at) FROM dbo.dim_song;

PRINT '== 1. Row counts, Gold vs Silver (expect every diff = 0)';
SELECT 'fact_show = silver show' AS check_name,
       (SELECT COUNT(*) FROM dbo.fact_show) AS gold, (SELECT COUNT(*) FROM lk_silver.dbo.show) AS silver
UNION ALL SELECT 'dim_show - Unknown = silver show',
       (SELECT COUNT(*) FROM dbo.dim_show WHERE show_key <> -1), (SELECT COUNT(*) FROM lk_silver.dbo.show)
UNION ALL SELECT 'fact_performance = silver performance - ignore',
       (SELECT COUNT(*) FROM dbo.fact_performance),
       (SELECT COUNT(*) FROM lk_silver.dbo.performance p
          JOIN lk_silver.dbo.song_map m ON m.song_key = p.song_key AND ISNULL(m.cover_artist, '') = ISNULL(p.cover_artist, '')
         WHERE m.match_method <> 'ignore')
UNION ALL SELECT 'dim_tour - Unknown = silver tour',
       (SELECT COUNT(*) FROM dbo.dim_tour WHERE tour_key <> -1), (SELECT COUNT(*) FROM lk_silver.dbo.tour)
UNION ALL SELECT 'dim_album - Unknown = silver album',
       (SELECT COUNT(*) FROM dbo.dim_album WHERE album_key <> -1), (SELECT COUNT(*) FROM lk_silver.dbo.album)
UNION ALL SELECT 'dim_song - Unknown = silver song',
       (SELECT COUNT(*) FROM dbo.dim_song WHERE song_key <> -1), (SELECT COUNT(*) FROM lk_silver.dbo.song)
UNION ALL SELECT 'dim_venue - Unknown = silver distinct venues',
       (SELECT COUNT(*) FROM dbo.dim_venue WHERE venue_key <> -1), (SELECT COUNT(DISTINCT venue_id) FROM lk_silver.dbo.show)
UNION ALL SELECT 'report_image_chunk = silver',
       (SELECT COUNT(*) FROM dbo.report_image_chunk), (SELECT COUNT(*) FROM lk_silver.dbo.report_image_chunk);

PRINT '== 2. Default performances (no tape, snippet, fragment): fact rows = SUM(song_count) = Silver (expect 29,366 x3)';
SELECT (SELECT COUNT(*) FROM dbo.fact_performance WHERE is_tape = 0 AND is_snippet = 0 AND is_fragment = 0) AS fact_rows,
       (SELECT SUM(song_count) FROM dbo.fact_show) AS sum_song_count,
       (SELECT COUNT(*) FROM lk_silver.dbo.performance p
          JOIN lk_silver.dbo.song_map m ON m.song_key = p.song_key AND ISNULL(m.cover_artist, '') = ISNULL(p.cover_artist, '')
          LEFT JOIN lk_silver.dbo.song s ON s.song_id = m.song_id
         WHERE p.is_tape = 0 AND p.is_snippet = 0 AND ISNULL(s.is_fragment, 0) = 0 AND m.match_method <> 'ignore') AS silver,
       (SELECT SUM(full_performances) FROM dbo.dim_song) AS dim_song_full_performances;

PRINT '== 3. Keys: unique, never -1 for real rows, Unknown row present (expect dup = 0, unknown = 1; dim_date has no Unknown)';
SELECT 'dim_show' AS t, COUNT(*) - COUNT(DISTINCT show_key) AS dup, SUM(CASE WHEN show_key = -1 THEN 1 ELSE 0 END) AS unknown FROM dbo.dim_show
UNION ALL SELECT 'dim_song', COUNT(*) - COUNT(DISTINCT song_key), SUM(CASE WHEN song_key = -1 THEN 1 ELSE 0 END) FROM dbo.dim_song
UNION ALL SELECT 'dim_album', COUNT(*) - COUNT(DISTINCT album_key), SUM(CASE WHEN album_key = -1 THEN 1 ELSE 0 END) FROM dbo.dim_album
UNION ALL SELECT 'dim_tour', COUNT(*) - COUNT(DISTINCT tour_key), SUM(CASE WHEN tour_key = -1 THEN 1 ELSE 0 END) FROM dbo.dim_tour
UNION ALL SELECT 'dim_venue', COUNT(*) - COUNT(DISTINCT venue_key), SUM(CASE WHEN venue_key = -1 THEN 1 ELSE 0 END) FROM dbo.dim_venue
UNION ALL SELECT 'dim_date', COUNT(*) - COUNT(DISTINCT date_key), SUM(CASE WHEN date_key = -1 THEN 1 ELSE 0 END) FROM dbo.dim_date
UNION ALL SELECT 'fact_show (grain)', COUNT(*) - COUNT(DISTINCT show_key), SUM(CASE WHEN show_key = -1 THEN 1 ELSE 0 END) FROM dbo.fact_show;

PRINT '== 4. dim_date: unique, gap-free, covers every fact date (expect gaps 0, missing 0)';
SELECT MIN([date]) AS first_date, MAX([date]) AS last_date, COUNT(*) AS days,
       DATEDIFF(day, MIN([date]), MAX([date])) + 1 - COUNT(DISTINCT [date]) AS gaps,
       (SELECT COUNT(*) FROM dbo.fact_performance f WHERE NOT EXISTS (SELECT 1 FROM dbo.dim_date d WHERE d.date_key = f.date_key)) AS perf_missing_date,
       (SELECT COUNT(*) FROM dbo.fact_show f WHERE NOT EXISTS (SELECT 1 FROM dbo.dim_date d WHERE d.date_key = f.date_key)) AS show_missing_date
FROM dbo.dim_date;

PRINT '== 5. Foreign keys: null, orphan (expect 0) and Unknown share (expect < 1%)';
SELECT 'fact_performance.song_key' AS fk,
       SUM(CASE WHEN f.song_key IS NULL THEN 1 ELSE 0 END) AS nulls,
       SUM(CASE WHEN d.song_key IS NULL THEN 1 ELSE 0 END) AS orphans,
       CAST(SUM(CASE WHEN f.song_key = -1 THEN 1.0 ELSE 0 END) / COUNT(*) AS decimal(9, 6)) AS unknown_share
FROM dbo.fact_performance f LEFT JOIN dbo.dim_song d ON d.song_key = f.song_key
UNION ALL
SELECT 'fact_performance.show_key', SUM(CASE WHEN f.show_key IS NULL THEN 1 ELSE 0 END), SUM(CASE WHEN d.show_key IS NULL THEN 1 ELSE 0 END),
       CAST(SUM(CASE WHEN f.show_key = -1 THEN 1.0 ELSE 0 END) / COUNT(*) AS decimal(9, 6))
FROM dbo.fact_performance f LEFT JOIN dbo.dim_show d ON d.show_key = f.show_key
UNION ALL
SELECT 'fact_performance.tour_key', SUM(CASE WHEN f.tour_key IS NULL THEN 1 ELSE 0 END), SUM(CASE WHEN d.tour_key IS NULL THEN 1 ELSE 0 END),
       CAST(SUM(CASE WHEN f.tour_key = -1 THEN 1.0 ELSE 0 END) / COUNT(*) AS decimal(9, 6))
FROM dbo.fact_performance f LEFT JOIN dbo.dim_tour d ON d.tour_key = f.tour_key
UNION ALL
SELECT 'fact_performance.venue_key', SUM(CASE WHEN f.venue_key IS NULL THEN 1 ELSE 0 END), SUM(CASE WHEN d.venue_key IS NULL THEN 1 ELSE 0 END),
       CAST(SUM(CASE WHEN f.venue_key = -1 THEN 1.0 ELSE 0 END) / COUNT(*) AS decimal(9, 6))
FROM dbo.fact_performance f LEFT JOIN dbo.dim_venue d ON d.venue_key = f.venue_key
UNION ALL
SELECT 'fact_show.tour_key', SUM(CASE WHEN f.tour_key IS NULL THEN 1 ELSE 0 END), SUM(CASE WHEN d.tour_key IS NULL THEN 1 ELSE 0 END),
       CAST(SUM(CASE WHEN f.tour_key = -1 THEN 1.0 ELSE 0 END) / COUNT(*) AS decimal(9, 6))
FROM dbo.fact_show f LEFT JOIN dbo.dim_tour d ON d.tour_key = f.tour_key
UNION ALL
SELECT 'fact_show.venue_key', SUM(CASE WHEN f.venue_key IS NULL THEN 1 ELSE 0 END), SUM(CASE WHEN d.venue_key IS NULL THEN 1 ELSE 0 END),
       CAST(SUM(CASE WHEN f.venue_key = -1 THEN 1.0 ELSE 0 END) / COUNT(*) AS decimal(9, 6))
FROM dbo.fact_show f LEFT JOIN dbo.dim_venue d ON d.venue_key = f.venue_key
UNION ALL
SELECT 'dim_song.album_key', SUM(CASE WHEN s.album_key IS NULL THEN 1 ELSE 0 END), SUM(CASE WHEN a.album_key IS NULL THEN 1 ELSE 0 END),
       CAST(SUM(CASE WHEN s.album_key = -1 THEN 1.0 ELSE 0 END) / COUNT(*) AS decimal(9, 6))
FROM dbo.dim_song s LEFT JOIN dbo.dim_album a ON a.album_key = s.album_key
UNION ALL
SELECT 'dim_tour.album_promoted_key', SUM(CASE WHEN t.album_promoted_key IS NULL THEN 1 ELSE 0 END), SUM(CASE WHEN a.album_key IS NULL THEN 1 ELSE 0 END),
       CAST(SUM(CASE WHEN t.album_promoted_key = -1 THEN 1.0 ELSE 0 END) / COUNT(*) AS decimal(9, 6))
FROM dbo.dim_tour t LEFT JOIN dbo.dim_album a ON a.album_key = t.album_promoted_key;

PRINT '== 6. Show-level consistency: fact_performance and fact_show agree on date/tour/venue per show (expect 0)';
SELECT COUNT(*) AS mismatched_rows
FROM dbo.fact_performance p JOIN dbo.fact_show s ON s.show_key = p.show_key
WHERE p.date_key <> s.date_key OR p.tour_key <> s.tour_key OR p.venue_key <> s.venue_key;

PRINT '== 7. Flags: live debuts = songs with >= 1 default performance; only-performance = songs with exactly 1 (expect diffs 0)';
WITH d AS (
    SELECT song_key, COUNT(*) AS n FROM dbo.fact_performance
    WHERE is_tape = 0 AND is_snippet = 0 AND is_fragment = 0 AND song_key <> -1 GROUP BY song_key)
SELECT (SELECT COUNT(*) FROM d) AS songs_played,
       (SELECT COUNT(*) FROM dbo.fact_performance WHERE is_live_debut = 1) AS live_debut_rows,
       (SELECT COUNT(*) FROM d WHERE n = 1) AS songs_once,
       (SELECT COUNT(*) FROM dbo.fact_performance WHERE is_only_performance = 1) AS only_performance_rows,
       (SELECT COUNT(*) FROM dbo.fact_performance WHERE is_live_debut = 1 AND (is_tape = 1 OR is_snippet = 1 OR is_fragment = 1)) AS debut_on_excluded_row;
SELECT COUNT(*) AS debut_date_mismatch   -- dim_song.live_debut_date = date of the is_live_debut row
FROM dbo.fact_performance f JOIN dbo.dim_song s ON s.song_key = f.song_key JOIN dbo.dim_date d ON d.date_key = f.date_key
WHERE f.is_live_debut = 1 AND (s.live_debut_date IS NULL OR s.live_debut_date <> d.[date]);

PRINT '== 8. Openers/closers: one each per show with a non-tape song (expect both = shows with songs)';
SELECT (SELECT COUNT(DISTINCT show_key) FROM dbo.fact_performance WHERE is_tape = 0) AS shows_with_songs,
       (SELECT COUNT(*) FROM dbo.fact_performance WHERE is_opener = 1) AS openers,
       (SELECT COUNT(*) FROM dbo.fact_performance WHERE is_closer = 1) AS closers;

PRINT '== 9. Tours: shows per tour, Gold vs Silver tour.shows, promoted album (expect diff 0 everywhere)';
SELECT t.tour_order, t.tour_name_display, t.is_residency, t.era, a.album_title AS album_promoted,
       COUNT(f.show_key) AS gold_shows, st.shows AS silver_shows, t.first_show_date, t.last_show_date
FROM dbo.dim_tour t
LEFT JOIN dbo.fact_show f ON f.tour_key = t.tour_key
LEFT JOIN dbo.dim_album a ON a.album_key = t.album_promoted_key
LEFT JOIN lk_silver.dbo.tour st ON st.tour_name = t.tour_name
GROUP BY t.tour_order, t.tour_name_display, t.is_residency, t.era, a.album_title, st.shows, t.first_show_date, t.last_show_date
ORDER BY t.tour_order;

PRINT '== 10. Promoted album share per tour (T-SQL side of the SPEC-05 DAX check)';
SELECT t.tour_name_display, a.album_title AS album_promoted,
       COUNT(*) AS performances,
       SUM(CASE WHEN s.album_key = t.album_promoted_key THEN 1 ELSE 0 END) AS from_promoted,
       CAST(1.0 * SUM(CASE WHEN s.album_key = t.album_promoted_key THEN 1 ELSE 0 END) / COUNT(*) AS decimal(9, 4)) AS promoted_share
FROM dbo.fact_performance f
JOIN dbo.dim_tour t ON t.tour_key = f.tour_key
JOIN dbo.dim_song s ON s.song_key = f.song_key
JOIN dbo.dim_album a ON a.album_key = t.album_promoted_key
WHERE f.is_tape = 0 AND f.is_snippet = 0 AND f.is_fragment = 0 AND t.album_promoted_key <> -1
GROUP BY t.tour_order, t.tour_name_display, a.album_title
ORDER BY t.tour_order;

PRINT '== 11. Hand-check fact A: shows of The Joshua Tree Tour 1987 (compare with the setlist.fm tour page)';
SELECT t.tour_name, COUNT(*) AS shows, MIN(d.[date]) AS first_show, MAX(d.[date]) AS last_show
FROM dbo.fact_show f JOIN dbo.dim_tour t ON t.tour_key = f.tour_key JOIN dbo.dim_date d ON d.date_key = f.date_key
WHERE t.tour_name = 'The Joshua Tree'
GROUP BY t.tour_name;

PRINT '== 12. Hand-check fact B: most-played songs (default performances; compare with setlist.fm song stats)';
SELECT TOP 5 s.song_title, COUNT(*) AS performances,
       (SELECT COUNT(*) FROM dbo.fact_performance x WHERE x.song_key = s.song_key) AS all_rows_incl_snippets_tapes
FROM dbo.fact_performance f JOIN dbo.dim_song s ON s.song_key = f.song_key
WHERE f.is_tape = 0 AND f.is_snippet = 0 AND f.is_fragment = 0 AND f.song_key <> -1
GROUP BY s.song_key, s.song_title
ORDER BY COUNT(*) DESC;

PRINT '== 13. Hand-check fact C: first show and first show with a setlist (compare with the setlist.fm pages)';
SELECT TOP 1 'first show' AS what, d.[date], sh.show_label, sh.setlist_url, f.song_count
FROM dbo.fact_show f JOIN dbo.dim_date d ON d.date_key = f.date_key JOIN dbo.dim_show sh ON sh.show_key = f.show_key
ORDER BY d.[date], sh.setlist_id;
SELECT TOP 1 'first show with setlist' AS what, d.[date], sh.show_label, sh.setlist_url, f.song_count
FROM dbo.fact_show f JOIN dbo.dim_date d ON d.date_key = f.date_key JOIN dbo.dim_show sh ON sh.show_key = f.show_key
WHERE f.has_setlist = 1
ORDER BY d.[date], sh.setlist_id;

PRINT '== 14. Q1 headline numbers (for README/report titles; DAX must match in T-28)';
SELECT (SELECT COUNT(*) FROM dbo.fact_show) AS shows,
       (SELECT COUNT(*) FROM dbo.fact_show WHERE has_setlist = 1) AS shows_with_setlist,
       (SELECT COUNT(DISTINCT v.country_code) FROM dbo.fact_show f JOIN dbo.dim_venue v ON v.venue_key = f.venue_key WHERE f.venue_key <> -1) AS countries,
       (SELECT COUNT(DISTINCT v.country_code + '|' + v.city_name) FROM dbo.fact_show f JOIN dbo.dim_venue v ON v.venue_key = f.venue_key WHERE f.venue_key <> -1) AS cities,
       (SELECT COUNT(DISTINCT f.venue_key) FROM dbo.fact_show f WHERE f.venue_key <> -1) AS venues,
       (SELECT COUNT(DISTINCT song_key) FROM dbo.fact_performance WHERE is_tape = 0 AND is_snippet = 0 AND is_fragment = 0 AND song_key <> -1) AS distinct_songs;
