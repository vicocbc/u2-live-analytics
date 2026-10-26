-- Independent reproduction of the setlist backtest metrics (SPEC-09 §9.6, task T-48). Read-only.
-- Recomputes precision_at_n, jaccard_first_show, brier_play_rate and new_count_error for the model and B1-B3 from
-- lk_silver.dbo.setlist_feature, setlist_prediction and the show/performance tables, and compares them with
-- lk_silver.dbo.setlist_backtest. Every row of the last query should have abs_diff < 1e-9.
-- Run after nb_silver_setlist_prediction (its last cell syncs the lk_silver SQL endpoint):
--   $env:U2_SQL_SERVER=[Environment]::GetEnvironmentVariable('U2_SQL_SERVER','User')
--   sqlcmd -S $env:U2_SQL_SERVER -d wh_gold --authentication-method ActiveDirectoryDefault -W -s "|" -i sql/review/setlist_backtest_reproduce.sql
SET NOCOUNT ON;

PRINT '== 1. Leakage evidence: latest history show per target vs its first show (every row must be history < cutoff)';
SELECT target_tour_name, MIN(target_first_show_date) AS cutoff, MAX(history_max_date) AS latest_history_show,
       MIN(history_shows) AS history_shows, COUNT(*) AS candidates,
       CASE WHEN MAX(history_max_date) < MIN(target_first_show_date) THEN 'ok' ELSE 'LEAK' END AS status
FROM lk_silver.dbo.setlist_feature
GROUP BY target_tour_name
ORDER BY cutoff;

PRINT '== 2. Metrics recomputed vs setlist_backtest';
WITH n AS (            -- N per backtest tour = the model's expected songs per show
    SELECT target_tour_name, CAST(value AS int) AS n
    FROM lk_silver.dbo.setlist_backtest
    WHERE method = 'context' AND metric = 'songs_per_show_predicted'
),
f AS (
    SELECT f.*, n.n,
           ROW_NUMBER() OVER (PARTITION BY f.target_tour_name
                              ORDER BY f.prev_album_tour_rate DESC, f.career_shows_played DESC,
                                       f.song_id COLLATE Latin1_General_100_BIN2_UTF8) AS rank_b1,
           ROW_NUMBER() OVER (PARTITION BY f.target_tour_name
                              ORDER BY f.career_shows_played DESC,
                                       f.song_id COLLATE Latin1_General_100_BIN2_UTF8) AS rank_b2,
           ROW_NUMBER() OVER (PARTITION BY f.target_tour_name
                              ORDER BY f.last_tour_rate DESC, f.career_shows_played DESC,
                                       f.song_id COLLATE Latin1_General_100_BIN2_UTF8) AS rank_b3
    FROM lk_silver.dbo.setlist_feature f
    JOIN n ON n.target_tour_name = f.target_tour_name
    WHERE f.is_planned_tour = 0
),
p AS (                 -- model pre-tour predictions of the backtest tours
    SELECT target_tour_name, song_id, probability, predicted_in_setlist, model_part
    FROM lk_silver.dbo.setlist_prediction
    WHERE is_backtest = 1 AND shows_observed = 0
),
predicted AS (         -- the N songs of every method
    SELECT p.target_tour_name, 'model' AS method, p.song_id FROM p WHERE p.predicted_in_setlist = 1
    UNION ALL SELECT target_tour_name, 'B1', song_id FROM f WHERE rank_b1 <= n
    UNION ALL SELECT target_tour_name, 'B2', song_id FROM f WHERE rank_b2 <= n
    UNION ALL SELECT target_tour_name, 'B3', song_id FROM f WHERE rank_b3 <= n
),
first_show AS (        -- earliest show with a setlist per tour (date, then setlist id)
    SELECT tour_name, setlist_id
    FROM (SELECT tour_name, setlist_id,
                 ROW_NUMBER() OVER (PARTITION BY tour_name
                                    ORDER BY event_date, setlist_id COLLATE Latin1_General_100_BIN2_UTF8) AS rn
          FROM lk_silver.dbo.show WHERE has_setlist = 1) x
    WHERE rn = 1
),
played AS (            -- full performances: no tape, no snippet, mapped, not a fragment
    SELECT DISTINCT p.setlist_id, m.song_id
    FROM lk_silver.dbo.performance p
    JOIN lk_silver.dbo.song_map m
      ON m.song_key = p.song_key AND ISNULL(m.cover_artist, '') = ISNULL(p.cover_artist, '')
    LEFT JOIN lk_silver.dbo.song s ON s.song_id = m.song_id
    WHERE p.is_tape = 0 AND p.is_snippet = 0 AND m.song_id IS NOT NULL AND ISNULL(s.is_fragment, 0) = 0
),
first_songs AS (
    SELECT fs.tour_name AS target_tour_name, pl.song_id
    FROM first_show fs JOIN played pl ON pl.setlist_id = fs.setlist_id
),
jac AS (
    SELECT pr.target_tour_name, pr.method,
           CAST(SUM(CASE WHEN fs.song_id IS NOT NULL THEN 1 ELSE 0 END) AS float) AS inter,
           COUNT(*) AS n_pred
    FROM predicted pr
    LEFT JOIN first_songs fs ON fs.target_tour_name = pr.target_tour_name AND fs.song_id = pr.song_id
    GROUP BY pr.target_tour_name, pr.method
),
first_n AS (SELECT target_tour_name, COUNT(*) AS n_first FROM first_songs GROUP BY target_tour_name),
prec AS (
    SELECT pr.target_tour_name, pr.method,
           CAST(SUM(CASE WHEN f.is_core = 1 THEN 1 ELSE 0 END) AS float) / COUNT(*) AS precision_at_n,
           SUM(CASE WHEN f.is_new_material = 1 THEN 1 ELSE 0 END) AS new_predicted
    FROM predicted pr
    JOIN lk_silver.dbo.setlist_feature f ON f.target_tour_name = pr.target_tour_name AND f.song_id = pr.song_id
    GROUP BY pr.target_tour_name, pr.method
),
brier AS (
    SELECT f.target_tour_name, 'model' AS method, AVG(SQUARE(p.probability - f.play_rate)) AS brier_play_rate
    FROM f JOIN p ON p.target_tour_name = f.target_tour_name AND p.song_id = f.song_id
    GROUP BY f.target_tour_name
    UNION ALL SELECT target_tour_name, 'B1', AVG(SQUARE(prev_album_tour_rate - play_rate)) FROM f GROUP BY target_tour_name
    UNION ALL SELECT target_tour_name, 'B2', AVG(SQUARE(ISNULL(career_rate, 0) - play_rate)) FROM f GROUP BY target_tour_name
    UNION ALL SELECT target_tour_name, 'B3', AVG(SQUARE(last_tour_rate - play_rate)) FROM f GROUP BY target_tour_name
),
tour_shows AS (        -- promoted-album songs per show of each backtest tour (shows with a setlist, zeros included)
    SELECT s.tour_name AS target_tour_name, s.setlist_id,
           SUM(CASE WHEN pa.song_id IS NOT NULL THEN 1 ELSE 0 END) AS new_songs
    FROM lk_silver.dbo.show s
    JOIN n ON n.target_tour_name = s.tour_name
    LEFT JOIN played pl ON pl.setlist_id = s.setlist_id
    LEFT JOIN lk_silver.dbo.setlist_feature pa
      ON pa.target_tour_name = s.tour_name AND pa.song_id = pl.song_id AND pa.release_role = 'promoted_album'
    WHERE s.has_setlist = 1
    GROUP BY s.tour_name, s.setlist_id
),
new_actual AS (
    SELECT DISTINCT target_tour_name,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY new_songs) OVER (PARTITION BY target_tour_name) AS new_per_show
    FROM tour_shows
),
model_new AS (
    SELECT target_tour_name, SUM(CASE WHEN predicted_in_setlist = 1 AND model_part = 'new' THEN 1 ELSE 0 END) AS n_new
    FROM p GROUP BY target_tour_name
),
recomputed AS (
    SELECT pr.target_tour_name, pr.method, v.metric, v.value
    FROM prec pr
    JOIN jac j ON j.target_tour_name = pr.target_tour_name AND j.method = pr.method
    JOIN first_n fn ON fn.target_tour_name = pr.target_tour_name
    JOIN brier b ON b.target_tour_name = pr.target_tour_name AND b.method = pr.method
    JOIN new_actual na ON na.target_tour_name = pr.target_tour_name
    JOIN model_new mn ON mn.target_tour_name = pr.target_tour_name
    CROSS APPLY (VALUES
        ('precision_at_n', pr.precision_at_n),
        ('jaccard_first_show', j.inter / (j.n_pred + fn.n_first - j.inter)),
        ('brier_play_rate', b.brier_play_rate),
        ('new_count_error', CAST(CASE WHEN pr.method = 'model' THEN mn.n_new ELSE pr.new_predicted END AS float)
                            - na.new_per_show)
    ) v(metric, value)
)
SELECT r.target_tour_name, r.method, r.metric, r.value AS recomputed, bt.value AS notebook,
       ABS(r.value - bt.value) AS abs_diff
FROM recomputed r
LEFT JOIN lk_silver.dbo.setlist_backtest bt
  ON bt.target_tour_name = r.target_tour_name AND bt.method = r.method AND bt.metric = r.metric
ORDER BY r.metric, r.target_tour_name, r.method;

PRINT '== 3. Mean precision_at_n from Elevation (acceptance: model > B1)';
SELECT bt.method, AVG(bt.value) AS mean_precision_at_n, COUNT(*) AS tours
FROM lk_silver.dbo.setlist_backtest bt
JOIN lk_silver.dbo.tour t ON t.tour_name = bt.target_tour_name
WHERE bt.metric = 'precision_at_n' AND t.first_show_date >= (SELECT first_show_date FROM lk_silver.dbo.tour WHERE tour_name = 'Elevation')
GROUP BY bt.method
ORDER BY mean_precision_at_n DESC;

PRINT '== 4. Predicted 2027 setlist (pre-tour as_of_date)';
SELECT p.predicted_position, p.predicted_set, p.model_part, ROUND(p.probability, 3) AS probability, f.song_title,
       f.release_role, p.model_version
FROM lk_silver.dbo.setlist_prediction p
JOIN lk_silver.dbo.setlist_feature f ON f.target_tour_name = p.target_tour_name AND f.song_id = p.song_id
WHERE p.is_backtest = 0 AND p.shows_observed = 0 AND p.predicted_in_setlist = 1
ORDER BY p.target_tour_name, p.predicted_position;

-- ============================================================================================================
-- 5. Independent checks (data-analyst, T-48). Sections 1-2 take is_core, play_rate and the baseline features from
--    setlist_feature (notebook output). Here they are rebuilt from show/performance/song_map/song/tour only:
--    A targets, B previous/last tour, C baseline feature columns, D N, E precision_at_n and jaccard_first_show
--    (model and B1, with B1 ranked on the raw features). Only the model set and the candidate list are read
--    from the notebook tables. Expected: every diff 0, no mismatch, raw = stored.
-- ============================================================================================================
-- Shared raw building blocks (only show, performance, song_map, song, tour)
IF OBJECT_ID('tempdb..#played') IS NOT NULL DROP TABLE #played;
SELECT DISTINCT s.setlist_id, s.event_date, s.tour_name, m.song_id
INTO #played
FROM lk_silver.dbo.show s
JOIN lk_silver.dbo.performance p ON p.setlist_id = s.setlist_id
JOIN lk_silver.dbo.song_map m ON m.song_key = p.song_key AND ISNULL(m.cover_artist, '') = ISNULL(p.cover_artist, '')
LEFT JOIN lk_silver.dbo.song so ON so.song_id = m.song_id
WHERE s.has_setlist = 1 AND p.is_tape = 0 AND p.is_snippet = 0 AND m.song_id IS NOT NULL AND ISNULL(so.is_fragment, 0) = 0;

IF OBJECT_ID('tempdb..#shows') IS NOT NULL DROP TABLE #shows;
SELECT setlist_id, event_date, tour_name INTO #shows FROM lk_silver.dbo.show WHERE has_setlist = 1;

-- backtest targets and their raw first show date
IF OBJECT_ID('tempdb..#tgt') IS NOT NULL DROP TABLE #tgt;
SELECT t.tour_name, MIN(sh.event_date) AS cutoff
INTO #tgt
FROM lk_silver.dbo.tour t JOIN #shows sh ON sh.tour_name = t.tour_name
WHERE t.tour_name IN ('Zoo TV','Popmart Tour','Elevation','Vertigo','U2 360°','iNNOCENCE + eXPERIENCE Tour','eXPERIENCE + iNNOCENCE Tour')
GROUP BY t.tour_name;

PRINT '== 5A. Targets play_rate / is_core from raw shows vs setlist_feature (all 7 backtest tours)';
WITH ts AS (SELECT tour_name, COUNT(*) AS n_shows FROM #shows GROUP BY tour_name),
raw AS (
    SELECT pl.tour_name, pl.song_id, CAST(COUNT(*) AS float) / ts.n_shows AS play_rate
    FROM #played pl JOIN ts ON ts.tour_name = pl.tour_name
    JOIN #tgt g ON g.tour_name = pl.tour_name
    GROUP BY pl.tour_name, pl.song_id, ts.n_shows
)
SELECT f.target_tour_name, COUNT(*) AS candidates,
       MAX(ABS(f.play_rate - ISNULL(r.play_rate, 0))) AS max_abs_diff_play_rate,
       SUM(CASE WHEN f.is_core <> CASE WHEN ISNULL(r.play_rate, 0) >= 0.5 THEN 1 ELSE 0 END THEN 1 ELSE 0 END) AS is_core_mismatch,
       SUM(CAST(f.is_core AS int)) AS core_feature,
       (SELECT COUNT(*) FROM raw r2 WHERE r2.tour_name = f.target_tour_name AND r2.play_rate >= 0.5) AS core_raw_all_songs
FROM lk_silver.dbo.setlist_feature f
LEFT JOIN raw r ON r.tour_name = f.target_tour_name AND r.song_id = f.song_id
WHERE f.target_tour_name IN (SELECT tour_name FROM #tgt)
GROUP BY f.target_tour_name;

-- Raw baseline features for three tours
IF OBJECT_ID('tempdb..#ctx') IS NOT NULL DROP TABLE #ctx;
SELECT g.tour_name, g.cutoff,
       (SELECT TOP 1 t.tour_name FROM lk_silver.dbo.tour t WHERE t.tour_type = 'album' AND t.first_show_date < g.cutoff
        ORDER BY t.first_show_date DESC) AS prev_album,
       (SELECT TOP 1 sh.tour_name FROM #shows sh JOIN lk_silver.dbo.tour t ON t.tour_name = sh.tour_name
        WHERE sh.event_date < g.cutoff AND t.tour_name <> '(No tour)'
        GROUP BY sh.tour_name HAVING COUNT(*) >= 10 ORDER BY MAX(sh.event_date) DESC) AS last_tour
INTO #ctx FROM #tgt g;

PRINT '== 5B. Context: previous album tour and last qualifying tour (raw)';
SELECT c.tour_name, c.cutoff, c.prev_album, c.last_tour,
       (SELECT TOP 1 prev_album_tour_name FROM lk_silver.dbo.setlist_feature f WHERE f.target_tour_name = c.tour_name) AS feat_prev,
       (SELECT TOP 1 last_tour_name FROM lk_silver.dbo.setlist_feature f WHERE f.target_tour_name = c.tour_name) AS feat_last
FROM #ctx c ORDER BY c.cutoff;

IF OBJECT_ID('tempdb..#rawf') IS NOT NULL DROP TABLE #rawf;
WITH pa AS (SELECT c.tour_name, COUNT(*) AS n FROM #ctx c JOIN #shows sh ON sh.tour_name = c.prev_album AND sh.event_date < c.cutoff GROUP BY c.tour_name),
lt AS (SELECT c.tour_name, COUNT(*) AS n FROM #ctx c JOIN #shows sh ON sh.tour_name = c.last_tour AND sh.event_date < c.cutoff GROUP BY c.tour_name)
SELECT f.target_tour_name, f.song_id, f.is_new_material,
       CAST((SELECT COUNT(*) FROM #played pl WHERE pl.song_id = f.song_id AND pl.tour_name = c.prev_album AND pl.event_date < c.cutoff) AS float) / pa.n AS raw_prev_rate,
       CAST((SELECT COUNT(*) FROM #played pl WHERE pl.song_id = f.song_id AND pl.tour_name = c.last_tour AND pl.event_date < c.cutoff) AS float) / lt.n AS raw_last_rate,
       (SELECT COUNT(*) FROM #played pl WHERE pl.song_id = f.song_id AND pl.event_date < c.cutoff) AS raw_career_played,
       f.prev_album_tour_rate, f.last_tour_rate, f.career_shows_played
INTO #rawf
FROM lk_silver.dbo.setlist_feature f
JOIN #ctx c ON c.tour_name = f.target_tour_name
JOIN pa ON pa.tour_name = c.tour_name JOIN lt ON lt.tour_name = c.tour_name;

PRINT '== 5C. Baseline feature columns: raw vs setlist_feature (all 7 tours)';
SELECT target_tour_name, COUNT(*) AS candidates,
       MAX(ABS(ISNULL(prev_album_tour_rate, 0) - raw_prev_rate)) AS max_diff_prev_rate,
       MAX(ABS(ISNULL(last_tour_rate, 0) - raw_last_rate)) AS max_diff_last_rate,
       MAX(ABS(ISNULL(career_shows_played, 0) - raw_career_played)) AS max_diff_career_played,
       SUM(CASE WHEN prev_album_tour_rate IS NULL THEN 1 ELSE 0 END) AS null_prev_rate
FROM #rawf GROUP BY target_tour_name;

PRINT '== 5D. N from raw: median of last three album tours of median played songs per show';
WITH per_show AS (SELECT setlist_id, tour_name, COUNT(*) AS n FROM #played GROUP BY setlist_id, tour_name),
med AS (SELECT DISTINCT tour_name, PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY n) OVER (PARTITION BY tour_name) AS med_n FROM per_show),
last3 AS (
    SELECT g.tour_name AS target, t.tour_name, m.med_n,
           ROW_NUMBER() OVER (PARTITION BY g.tour_name ORDER BY t.first_show_date DESC) AS rn
    FROM #tgt g JOIN lk_silver.dbo.tour t ON t.tour_type = 'album' AND t.first_show_date < g.cutoff
    JOIN med m ON m.tour_name = t.tour_name
)
SELECT l.target, STRING_AGG(CONCAT(l.tour_name, '=', l.med_n), '; ') AS last3_medians,
       (SELECT DISTINCT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY l2.med_n) OVER () FROM last3 l2 WHERE l2.target = l.target AND l2.rn <= 3) AS raw_n,
       (SELECT value FROM lk_silver.dbo.setlist_backtest b WHERE b.target_tour_name = l.target AND b.method = 'context' AND b.metric = 'songs_per_show_predicted') AS stored_n,
       (SELECT COUNT(*) FROM lk_silver.dbo.setlist_prediction p WHERE p.target_tour_name = l.target AND p.is_backtest = 1 AND p.shows_observed = 0 AND p.predicted_in_setlist = 1) AS model_set_size
FROM last3 l WHERE l.rn <= 3 GROUP BY l.target;

PRINT '== 5E. Independent precision_at_n and jaccard_first_show (model, B1) for Elevation, U2 360°, e+i';
WITH ts AS (SELECT tour_name, COUNT(*) AS n_shows FROM #shows GROUP BY tour_name),
core AS (
    SELECT pl.tour_name, pl.song_id FROM #played pl JOIN ts ON ts.tour_name = pl.tour_name
    GROUP BY pl.tour_name, pl.song_id, ts.n_shows HAVING CAST(COUNT(*) AS float) / ts.n_shows >= 0.5
),
fs AS (
    SELECT tour_name, setlist_id FROM (
        SELECT tour_name, setlist_id, ROW_NUMBER() OVER (PARTITION BY tour_name ORDER BY event_date, setlist_id COLLATE Latin1_General_100_BIN2_UTF8) rn
        FROM #shows) x WHERE rn = 1
),
first_set AS (SELECT fs.tour_name, pl.song_id FROM fs JOIN #played pl ON pl.setlist_id = fs.setlist_id),
nn AS (SELECT target_tour_name, COUNT(*) AS n FROM lk_silver.dbo.setlist_prediction
       WHERE is_backtest = 1 AND shows_observed = 0 AND predicted_in_setlist = 1 GROUP BY target_tour_name),
b1 AS (
    SELECT r.target_tour_name, r.song_id,
           ROW_NUMBER() OVER (PARTITION BY r.target_tour_name ORDER BY r.raw_prev_rate DESC, r.raw_career_played DESC,
                              r.song_id COLLATE Latin1_General_100_BIN2_UTF8) AS rk
    FROM #rawf r
),
sets AS (
    SELECT target_tour_name, 'model' AS method, song_id FROM lk_silver.dbo.setlist_prediction
    WHERE is_backtest = 1 AND shows_observed = 0 AND predicted_in_setlist = 1
    UNION ALL
    SELECT b1.target_tour_name, 'B1', b1.song_id FROM b1 JOIN nn ON nn.target_tour_name = b1.target_tour_name WHERE b1.rk <= nn.n
),
m AS (
    SELECT s.target_tour_name, s.method, COUNT(*) AS n,
           SUM(CASE WHEN c.song_id IS NOT NULL THEN 1 ELSE 0 END) AS n_core,
           SUM(CASE WHEN f1.song_id IS NOT NULL THEN 1 ELSE 0 END) AS inter,
           (SELECT COUNT(*) FROM first_set x WHERE x.tour_name = s.target_tour_name) AS n_first
    FROM sets s
    LEFT JOIN core c ON c.tour_name = s.target_tour_name AND c.song_id = s.song_id
    LEFT JOIN first_set f1 ON f1.tour_name = s.target_tour_name AND f1.song_id = s.song_id
    WHERE s.target_tour_name IN ('Elevation', 'U2 360°', 'eXPERIENCE + iNNOCENCE Tour', 'Zoo TV')
    GROUP BY s.target_tour_name, s.method
)
SELECT m.target_tour_name, m.method, m.n, m.n_core, m.inter, m.n_first,
       CAST(m.n_core AS float) / m.n AS precision_raw, bp.value AS precision_stored,
       CAST(m.inter AS float) / (m.n + m.n_first - m.inter) AS jaccard_raw, bj.value AS jaccard_stored
FROM m
LEFT JOIN lk_silver.dbo.setlist_backtest bp ON bp.target_tour_name = m.target_tour_name AND bp.method = m.method AND bp.metric = 'precision_at_n'
LEFT JOIN lk_silver.dbo.setlist_backtest bj ON bj.target_tour_name = m.target_tour_name AND bj.method = m.method AND bj.metric = 'jaccard_first_show'
ORDER BY m.target_tour_name, m.method;
