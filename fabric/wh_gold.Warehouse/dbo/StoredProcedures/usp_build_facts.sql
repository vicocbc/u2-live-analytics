-- Rebuilds fact_performance, fact_show and the setlist prediction facts (SPEC-09 9.7) from lk_silver (SPEC-04). Run after usp_build_dimensions, inside the
-- transaction of dbo.usp_build_gold. Unmatched foreign keys become -1 (Unknown).
-- "Full" performance = not a tape, not a snippet (fragments are their own song, so they count for their own debut).
CREATE   PROCEDURE dbo.usp_build_facts
    @built_at datetime2(6)
AS
BEGIN
    SET NOCOUNT ON;

    ---------------------------------------------------------------- fact_performance
    DELETE FROM dbo.fact_performance;
    WITH perf AS (
        SELECT p.setlist_id, p.event_date, p.set_name, p.is_encore, p.setlist_position, p.is_tape, p.is_snippet,
               p.is_cover, p.with_artist, p.is_opener, p.is_closer, m.song_id,
               s.tour_name, s.venue_id
        FROM lk_silver.dbo.performance AS p
        JOIN lk_silver.dbo.show AS s ON s.setlist_id = p.setlist_id
        LEFT JOIN lk_silver.dbo.song_map AS m
          ON m.song_key = p.song_key AND ISNULL(m.cover_artist, '') = ISNULL(p.cover_artist, '')
        WHERE ISNULL(m.match_method, '') <> 'ignore'
    ),
    full_perf AS (
        SELECT setlist_id, setlist_position,
               ROW_NUMBER() OVER (PARTITION BY song_id ORDER BY event_date, setlist_id, setlist_position) AS rn,
               COUNT(*) OVER (PARTITION BY song_id) AS n
        FROM perf
        WHERE song_id IS NOT NULL AND is_tape = 0 AND is_snippet = 0
    )
    INSERT INTO dbo.fact_performance (show_key, date_key, song_key, tour_key, venue_key, setlist_position, set_name,
                                      is_encore, is_opener, is_closer, is_snippet, is_tape, is_fragment, is_cover,
                                      has_guest, guest_artist, is_live_debut, is_only_performance, _built_at)
    SELECT ISNULL(sh.show_key, -1),
           YEAR(p.event_date) * 10000 + MONTH(p.event_date) * 100 + DAY(p.event_date),
           ISNULL(sg.song_key, -1),
           ISNULL(t.tour_key, -1),
           ISNULL(v.venue_key, -1),
           p.setlist_position, p.set_name, p.is_encore, p.is_opener, p.is_closer, p.is_snippet, p.is_tape,
           CAST(ISNULL(ls.is_fragment, 0) AS bit),
           p.is_cover,
           CAST(CASE WHEN p.with_artist IS NOT NULL THEN 1 ELSE 0 END AS bit),
           p.with_artist,
           CAST(CASE WHEN f.rn = 1 THEN 1 ELSE 0 END AS bit),
           CAST(CASE WHEN f.n = 1 THEN 1 ELSE 0 END AS bit),
           @built_at
    FROM perf AS p
    LEFT JOIN full_perf AS f ON f.setlist_id = p.setlist_id AND f.setlist_position = p.setlist_position
    LEFT JOIN lk_silver.dbo.song AS ls ON ls.song_id = p.song_id
    LEFT JOIN dbo.dim_show  AS sh ON sh.setlist_id = p.setlist_id
    LEFT JOIN dbo.dim_song  AS sg ON sg.song_id = p.song_id
    LEFT JOIN dbo.dim_tour  AS t  ON t.tour_name = p.tour_name
    LEFT JOIN dbo.dim_venue AS v  ON v.venue_id = p.venue_id;

    ---------------------------------------------------------------- fact_show
    DELETE FROM dbo.fact_show;
    WITH counts AS (
        SELECT show_key, COUNT(*) AS song_count
        FROM dbo.fact_performance
        WHERE is_tape = 0 AND is_snippet = 0 AND is_fragment = 0
        GROUP BY show_key
    )
    INSERT INTO dbo.fact_show (show_key, date_key, tour_key, venue_key, song_count, has_setlist, _built_at)
    SELECT sh.show_key,
           YEAR(s.event_date) * 10000 + MONTH(s.event_date) * 100 + DAY(s.event_date),
           ISNULL(t.tour_key, -1),
           ISNULL(v.venue_key, -1),
           ISNULL(c.song_count, 0),
           s.has_setlist,
           @built_at
    FROM lk_silver.dbo.show AS s
    JOIN dbo.dim_show AS sh ON sh.setlist_id = s.setlist_id
    LEFT JOIN dbo.dim_tour  AS t ON t.tour_name = s.tour_name
    LEFT JOIN dbo.dim_venue AS v ON v.venue_id = s.venue_id
    LEFT JOIN counts AS c ON c.show_key = sh.show_key;

    ---------------------------------------------------------------- setlist prediction (SPEC-09 9.7, T-49)
    -- Only the planned / current tour's predictions (is_backtest = 0); backtest predictions stay in Silver.
    DELETE FROM dbo.fact_setlist_prediction;
    INSERT INTO dbo.fact_setlist_prediction (as_of_date_key, tour_key, song_key, shows_observed, probability,
                                             predicted_in_setlist, predicted_position, predicted_set, model_part,
                                             model_version, _built_at)
    SELECT YEAR(p.as_of_date) * 10000 + MONTH(p.as_of_date) * 100 + DAY(p.as_of_date),
           ISNULL(t.tour_key, -1),
           ISNULL(sg.song_key, -1),
           p.shows_observed, p.probability, p.predicted_in_setlist, p.predicted_position, p.predicted_set,
           p.model_part, p.model_version,
           @built_at
    FROM lk_silver.dbo.setlist_prediction AS p
    LEFT JOIN dbo.dim_tour AS t  ON t.tour_name = p.target_tour_name
    LEFT JOIN dbo.dim_song AS sg ON sg.song_id = p.song_id
    WHERE p.is_backtest = 0;

    DELETE FROM dbo.fact_setlist_backtest;
    INSERT INTO dbo.fact_setlist_backtest (tour_key, method, metric, value, model_version, _built_at)
    SELECT ISNULL(t.tour_key, -1), b.method, b.metric, b.value, b.model_version, @built_at
    FROM lk_silver.dbo.setlist_backtest AS b
    LEFT JOIN dbo.dim_tour AS t ON t.tour_name = b.target_tour_name;

    DELETE FROM dbo.fact_setlist_model_coef;
    INSERT INTO dbo.fact_setlist_model_coef (tour_key, model_part, feature, coef_standardized, coef_raw, n_train,
                                             n_positive, model_version, _built_at)
    SELECT ISNULL(t.tour_key, -1), c.model_part, c.feature, c.coef_standardized, c.coef_raw, c.n_train, c.n_positive,
           c.model_version, @built_at
    FROM lk_silver.dbo.setlist_model_coef AS c
    LEFT JOIN dbo.dim_tour AS t ON t.tour_name = c.target_tour_name;
END;

GO