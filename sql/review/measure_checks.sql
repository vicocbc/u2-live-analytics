-- T-SQL side of the DAX measure tests in tests/dax/ (T-28). Read-only, wh_gold.
--   sqlcmd -S $env:U2_SQL_SERVER -d wh_gold --authentication-method ActiveDirectoryDefault -W -s "|" -i sql/review/measure_checks.sql
-- "Default performances" = fact_performance rows with is_tape = 0 AND is_snippet = 0 AND is_fragment = 0.
SET NOCOUNT ON;

PRINT '== Totals (whole model)';
WITH p AS (SELECT * FROM dbo.fact_performance WHERE is_tape = 0 AND is_snippet = 0 AND is_fragment = 0),
song_n AS (SELECT song_key, COUNT(*) AS n FROM p WHERE song_key <> -1 GROUP BY song_key),
promo AS (
    SELECT COUNT(*) AS perf, SUM(CASE WHEN s.album_key = t.album_promoted_key THEN 1 ELSE 0 END) AS from_promoted
    FROM p JOIN dbo.dim_tour t ON t.tour_key = p.tour_key JOIN dbo.dim_song s ON s.song_key = p.song_key
    WHERE t.album_promoted_key <> -1)
SELECT
    (SELECT COUNT(*) FROM dbo.fact_show) AS shows,
    (SELECT COUNT(*) FROM dbo.fact_show WHERE has_setlist = 1) AS shows_with_setlist,
    (SELECT COUNT(DISTINCT d.[year]) FROM dbo.fact_show f JOIN dbo.dim_date d ON d.date_key = f.date_key) AS years_active,
    (SELECT COUNT(*) FROM p) AS performances,
    (SELECT COUNT(*) FROM dbo.fact_performance) AS all_performances,
    (SELECT COUNT(*) FROM song_n) AS distinct_songs,
    CAST((SELECT COUNT(*) FROM p) * 1.0 / (SELECT COUNT(*) FROM dbo.fact_show WHERE has_setlist = 1) AS decimal(9, 4)) AS avg_songs_per_show,
    (SELECT COUNT(*) FROM p WHERE is_live_debut = 1) AS live_debuts,
    (SELECT COUNT(*) FROM song_n WHERE n <= 2) AS rarities,
    (SELECT CAST(from_promoted * 1.0 / perf AS decimal(9, 6)) FROM promo) AS promoted_share,
    (SELECT COUNT(*) FROM p WHERE is_cover = 1) AS covers,
    (SELECT COUNT(*) FROM p WHERE has_guest = 1) AS guests,
    (SELECT COUNT(*) FROM p WHERE is_opener = 1) AS openers,
    (SELECT COUNT(*) FROM p WHERE is_closer = 1) AS closers,
    (SELECT COUNT(*) FROM p WHERE is_encore = 1) AS encores,
    (SELECT CAST(SUM(CASE WHEN song_key = -1 THEN 1.0 ELSE 0 END) / COUNT(*) AS decimal(9, 6)) FROM p) AS unmapped_share,
    (SELECT CAST(SUM(CASE WHEN a.album_title = 'Achtung Baby' AND a.is_studio = 1 THEN 1.0 ELSE 0 END) / COUNT(*) AS decimal(9, 6))
       FROM p JOIN dbo.dim_song s ON s.song_key = p.song_key JOIN dbo.dim_album a ON a.album_key = s.album_key) AS achtung_baby_share;

PRINT '== Per tour: songs per show, distinct songs, variety, promoted share, Achtung Baby share';
WITH p AS (SELECT * FROM dbo.fact_performance WHERE is_tape = 0 AND is_snippet = 0 AND is_fragment = 0)
SELECT t.tour_order, t.tour_name,
       (SELECT COUNT(*) FROM dbo.fact_show f WHERE f.tour_key = t.tour_key AND f.has_setlist = 1) AS shows_with_setlist,
       COUNT(p.song_key) AS performances,
       COUNT(DISTINCT CASE WHEN p.song_key <> -1 THEN p.song_key END) AS distinct_songs,
       CAST(COUNT(p.song_key) * 1.0 / NULLIF((SELECT COUNT(*) FROM dbo.fact_show f WHERE f.tour_key = t.tour_key AND f.has_setlist = 1), 0) AS decimal(9, 4)) AS avg_songs_per_show,
       CAST(SUM(CASE WHEN s.album_key = t.album_promoted_key AND t.album_promoted_key <> -1 THEN 1.0 ELSE 0 END) / NULLIF(COUNT(p.song_key), 0) AS decimal(9, 6)) AS promoted_share,
       CAST(SUM(CASE WHEN a.album_title = 'Achtung Baby' AND a.is_studio = 1 THEN 1.0 ELSE 0 END) / NULLIF(COUNT(p.song_key), 0) AS decimal(9, 6)) AS achtung_baby_share
FROM dbo.dim_tour t
LEFT JOIN p ON p.tour_key = t.tour_key
LEFT JOIN dbo.dim_song s ON s.song_key = p.song_key
LEFT JOIN dbo.dim_album a ON a.album_key = s.album_key
WHERE t.tour_key <> -1
GROUP BY t.tour_order, t.tour_name, t.tour_key, t.album_promoted_key
ORDER BY t.tour_order;

PRINT '== Q10: residency vs. touring 2015-2019 (era "2015-2019 Innocence and Experience")';
WITH p AS (SELECT * FROM dbo.fact_performance WHERE is_tape = 0 AND is_snippet = 0 AND is_fragment = 0),
g AS (
    SELECT CASE WHEN t.is_residency = 1 THEN 'residency' ELSE 'touring_2015_2019' END AS grp, t.tour_key
    FROM dbo.dim_tour t WHERE t.is_residency = 1 OR t.era = '2015-2019 Innocence and Experience')
SELECT g.grp,
       (SELECT COUNT(*) FROM dbo.fact_show f JOIN g g2 ON g2.tour_key = f.tour_key WHERE g2.grp = g.grp AND f.has_setlist = 1) AS shows_with_setlist,
       COUNT(*) AS performances,
       COUNT(DISTINCT CASE WHEN p.song_key <> -1 THEN p.song_key END) AS distinct_songs,
       CAST(SUM(CASE WHEN a.album_title = 'Achtung Baby' AND a.is_studio = 1 THEN 1.0 ELSE 0 END) / COUNT(*) AS decimal(9, 6)) AS achtung_baby_share
FROM p JOIN g ON g.tour_key = p.tour_key
JOIN dbo.dim_song s ON s.song_key = p.song_key JOIN dbo.dim_album a ON a.album_key = s.album_key
GROUP BY g.grp;

PRINT '== Songs: I Will Follow and Pride (first/last played, shows played, openers, closers, encores)';
WITH p AS (SELECT * FROM dbo.fact_performance WHERE is_tape = 0 AND is_snippet = 0 AND is_fragment = 0)
SELECT s.song_title, COUNT(*) AS performances, COUNT(DISTINCT p.show_key) AS shows_played,
       MIN(d.[date]) AS first_played, MAX(d.[date]) AS last_played,
       SUM(CAST(p.is_opener AS int)) AS openers, SUM(CAST(p.is_closer AS int)) AS closers, SUM(CAST(p.is_encore AS int)) AS encores
FROM p JOIN dbo.dim_song s ON s.song_key = p.song_key JOIN dbo.dim_date d ON d.date_key = p.date_key
WHERE s.song_title IN ('I Will Follow', 'Pride (In the Name of Love)')
GROUP BY s.song_title;

PRINT '== Busiest year and shows in 1987';
SELECT TOP 3 d.[year], COUNT(*) AS shows FROM dbo.fact_show f JOIN dbo.dim_date d ON d.date_key = f.date_key
GROUP BY d.[year] ORDER BY COUNT(*) DESC;

PRINT '== Album share by album (studio albums, whole model)';
WITH p AS (SELECT * FROM dbo.fact_performance WHERE is_tape = 0 AND is_snippet = 0 AND is_fragment = 0)
SELECT a.album_order, a.album_title, COUNT(*) AS performances,
       CAST(COUNT(*) * 1.0 / (SELECT COUNT(*) FROM p) AS decimal(9, 6)) AS album_share
FROM p JOIN dbo.dim_song s ON s.song_key = p.song_key JOIN dbo.dim_album a ON a.album_key = s.album_key
WHERE a.is_studio = 1
GROUP BY a.album_order, a.album_title ORDER BY a.album_order;
