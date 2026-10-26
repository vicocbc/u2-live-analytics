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
