-- Gold data quality checks (SPEC-04, SPEC-07). Returns one JSON object per check in @dq_json (OUTPUT):
--   [{"check_name": "...", "value": "...", "status": "pass|warning|fail"}, ...]   (fail = hard failure)
-- Why JSON in a variable and not a #temp table: in Fabric Warehouse, rows written to a temp table inside the build
-- transaction are undone by its ROLLBACK, and a temp table can neither be filled from nor copied into user tables
-- (Msg 15816). A variable survives the rollback, so usp_build_gold can log the results after it.
-- @force_fail = 1 adds a failing check on purpose (rollback test, SPEC-04 acceptance / T-24).
CREATE   PROCEDURE dbo.usp_dq_gold
    @run_id     varchar(100),
    @force_fail bit = 0,
    @dq_json    varchar(max) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @dq varchar(max) = '';
    DECLARE @n_fp int, @n_fs int, @n_dim_show int, @n_silver_show int, @n_silver_perf int, @n_ignore int;
    DECLARE @v1 int, @v2 int, @frag varchar(max);

    SELECT @n_fp = COUNT(*) FROM dbo.fact_performance;
    SELECT @n_fs = COUNT(*) FROM dbo.fact_show;
    SELECT @n_dim_show = COUNT(*) FROM dbo.dim_show;
    SELECT @n_silver_show = COUNT(*) FROM lk_silver.dbo.show;
    SELECT @n_silver_perf = COUNT(*) FROM lk_silver.dbo.performance;
    SELECT @n_ignore = COUNT(*)
    FROM lk_silver.dbo.performance AS p
    JOIN lk_silver.dbo.song_map AS m
      ON m.song_key = p.song_key AND ISNULL(m.cover_artist, '') = ISNULL(p.cover_artist, '')
    WHERE m.match_method = 'ignore';

    -- SQL endpoint synced: Silver holds the current run (SPEC-07)
    SELECT @v1 = COUNT(*) FROM lk_silver.dbo.show WHERE _run_id = @run_id;
    SET @dq += CONCAT(',{"check_name":"gold_silver_show_has_current_run","value":"', @v1,
                      '","status":"', CASE WHEN @v1 > 0 THEN 'pass' ELSE 'fail' END, '"}');

    -- Reconciliation
    SET @dq += CONCAT(',{"check_name":"gold_fact_show_eq_dim_show_minus_unknown","value":"', @n_fs, '/', @n_dim_show - 1,
                      '","status":"', CASE WHEN @n_fs = @n_dim_show - 1 THEN 'pass' ELSE 'fail' END, '"}');
    SET @dq += CONCAT(',{"check_name":"gold_fact_show_eq_silver_show","value":"', @n_fs, '/', @n_silver_show,
                      '","status":"', CASE WHEN @n_fs = @n_silver_show THEN 'pass' ELSE 'fail' END, '"}');
    SET @dq += CONCAT(',{"check_name":"gold_fact_performance_eq_silver_minus_ignore","value":"', @n_fp, '/', @n_silver_perf,
                      '-', @n_ignore, '","status":"', CASE WHEN @n_fp = @n_silver_perf - @n_ignore THEN 'pass' ELSE 'fail' END, '"}');
    SELECT @v1 = SUM(song_count) FROM dbo.fact_show;
    SELECT @v2 = COUNT(*) FROM dbo.fact_performance WHERE is_tape = 0 AND is_snippet = 0 AND is_fragment = 0;
    SET @dq += CONCAT(',{"check_name":"gold_song_count_eq_default_performances","value":"', @v1, '/', @v2,
                      '","status":"', CASE WHEN @v1 = @v2 THEN 'pass' ELSE 'fail' END, '"}');

    -- No null foreign keys
    SELECT @v1 = COUNT(*) FROM dbo.fact_performance
    WHERE show_key IS NULL OR date_key IS NULL OR song_key IS NULL OR tour_key IS NULL OR venue_key IS NULL;
    SELECT @v2 = COUNT(*) FROM dbo.fact_show
    WHERE show_key IS NULL OR date_key IS NULL OR tour_key IS NULL OR venue_key IS NULL;
    SET @dq += CONCAT(',{"check_name":"gold_no_null_fks","value":"', @v1 + @v2,
                      '","status":"', CASE WHEN @v1 + @v2 = 0 THEN 'pass' ELSE 'fail' END, '"}');

    -- Every fact date exists in dim_date (dim_date has no Unknown member)
    SELECT @v1 = COUNT(*) FROM dbo.fact_performance AS f WHERE NOT EXISTS (SELECT 1 FROM dbo.dim_date AS d WHERE d.date_key = f.date_key);
    SELECT @v2 = COUNT(*) FROM dbo.fact_show AS f WHERE NOT EXISTS (SELECT 1 FROM dbo.dim_date AS d WHERE d.date_key = f.date_key);
    SET @dq += CONCAT(',{"check_name":"gold_fact_dates_in_dim_date","value":"', @v1 + @v2,
                      '","status":"', CASE WHEN @v1 + @v2 = 0 THEN 'pass' ELSE 'fail' END, '"}');

    -- Unknown share < 1% per foreign key (value logged)
    SELECT @frag = STRING_AGG(CAST(CONCAT('{"check_name":"', check_name, '","value":"',
                       CAST(CAST(ISNULL(unknown_rows, 0) AS float) / NULLIF(total_rows, 0) AS varchar(30)), '","status":"',
                       CASE WHEN total_rows > 0 AND CAST(ISNULL(unknown_rows, 0) AS float) / total_rows < 0.01
                            THEN 'pass' ELSE 'fail' END, '"}') AS varchar(max)), ',')
    FROM (
        SELECT 'gold_unknown_share_fact_performance_song' AS check_name, SUM(CASE WHEN song_key = -1 THEN 1 ELSE 0 END) AS unknown_rows, COUNT(*) AS total_rows FROM dbo.fact_performance
        UNION ALL SELECT 'gold_unknown_share_fact_performance_show', SUM(CASE WHEN show_key = -1 THEN 1 ELSE 0 END), COUNT(*) FROM dbo.fact_performance
        UNION ALL SELECT 'gold_unknown_share_fact_performance_tour', SUM(CASE WHEN tour_key = -1 THEN 1 ELSE 0 END), COUNT(*) FROM dbo.fact_performance
        UNION ALL SELECT 'gold_unknown_share_fact_performance_venue', SUM(CASE WHEN venue_key = -1 THEN 1 ELSE 0 END), COUNT(*) FROM dbo.fact_performance
        UNION ALL SELECT 'gold_unknown_share_fact_show_tour', SUM(CASE WHEN tour_key = -1 THEN 1 ELSE 0 END), COUNT(*) FROM dbo.fact_show
        UNION ALL SELECT 'gold_unknown_share_fact_show_venue', SUM(CASE WHEN venue_key = -1 THEN 1 ELSE 0 END), COUNT(*) FROM dbo.fact_show
    ) AS fk;
    SET @dq += ',' + @frag;

    -- Surrogate keys unique and only the Unknown row uses -1
    SELECT @frag = STRING_AGG(CAST(CONCAT('{"check_name":"', check_name, '","value":"', dup_keys, ' dup, ', bad_minus_one,
                       ' bad -1","status":"', CASE WHEN dup_keys = 0 AND bad_minus_one = 0 THEN 'pass' ELSE 'fail' END, '"}')
                       AS varchar(max)), ',')
    FROM (
        SELECT 'gold_keys_dim_show' AS check_name, COUNT(*) - COUNT(DISTINCT show_key) AS dup_keys, SUM(CASE WHEN show_key = -1 AND setlist_id <> '(unknown)' THEN 1 ELSE 0 END) AS bad_minus_one FROM dbo.dim_show
        UNION ALL SELECT 'gold_keys_dim_song', COUNT(*) - COUNT(DISTINCT song_key), SUM(CASE WHEN song_key = -1 AND song_id <> '(unknown)' THEN 1 ELSE 0 END) FROM dbo.dim_song
        UNION ALL SELECT 'gold_keys_dim_album', COUNT(*) - COUNT(DISTINCT album_key), SUM(CASE WHEN album_key = -1 AND album_id <> '(unknown)' THEN 1 ELSE 0 END) FROM dbo.dim_album
        UNION ALL SELECT 'gold_keys_dim_tour', COUNT(*) - COUNT(DISTINCT tour_key), SUM(CASE WHEN tour_key = -1 AND tour_name <> '(unknown)' THEN 1 ELSE 0 END) FROM dbo.dim_tour
        UNION ALL SELECT 'gold_keys_dim_venue', COUNT(*) - COUNT(DISTINCT venue_key), SUM(CASE WHEN venue_key = -1 AND venue_id <> '(unknown)' THEN 1 ELSE 0 END) FROM dbo.dim_venue
        UNION ALL SELECT 'gold_keys_dim_date', COUNT(*) - COUNT(DISTINCT date_key), 0 FROM dbo.dim_date
    ) AS k;
    SET @dq += ',' + @frag;

    -- Display labels unique (T-27: the model uses them as visible keys)
    SELECT @v1 = COUNT(*) - COUNT(DISTINCT album_label) FROM dbo.dim_album;
    SELECT @v2 = COUNT(*) - COUNT(DISTINCT show_label) FROM dbo.dim_show;
    SET @dq += CONCAT(',{"check_name":"gold_labels_unique","value":"album ', @v1, ', show ', @v2,
                      '","status":"', CASE WHEN @v1 = 0 AND @v2 = 0 THEN 'pass' ELSE 'fail' END, '"}');

    -- dim_song / dim_tour reference existing albums
    SELECT @v1 = COUNT(*) FROM dbo.dim_song AS s WHERE NOT EXISTS (SELECT 1 FROM dbo.dim_album AS a WHERE a.album_key = s.album_key);
    SELECT @v2 = COUNT(*) FROM dbo.dim_tour AS t WHERE NOT EXISTS (SELECT 1 FROM dbo.dim_album AS a WHERE a.album_key = t.album_promoted_key);
    SET @dq += CONCAT(',{"check_name":"gold_dim_album_refs_exist","value":"', @v1 + @v2,
                      '","status":"', CASE WHEN @v1 + @v2 = 0 THEN 'pass' ELSE 'fail' END, '"}');

    -- Report images (presentation assets)
    SELECT @v1 = COUNT(*) FROM dbo.report_image AS i
    WHERE i.chunk_count <> (SELECT COUNT(*) FROM dbo.report_image_chunk AS c WHERE c.image_id = i.image_id)
       OR i.chunk_count <> (SELECT COUNT(DISTINCT c.chunk_no) FROM dbo.report_image_chunk AS c WHERE c.image_id = i.image_id)
       OR EXISTS (SELECT 1 FROM dbo.report_image_chunk AS c
                  WHERE c.image_id = i.image_id AND (c.chunk_no < 1 OR c.chunk_no > i.chunk_count));
    SELECT @v2 = COUNT(*) FROM dbo.report_image_chunk AS c
    WHERE NOT EXISTS (SELECT 1 FROM dbo.report_image AS i WHERE i.image_id = c.image_id);
    SET @dq += CONCAT(',{"check_name":"gold_report_image_chunks_no_gaps","value":"', @v1 + @v2,
                      '","status":"', CASE WHEN @v1 + @v2 = 0 THEN 'pass' ELSE 'fail' END, '"}');
    SELECT @v1 = COUNT(*) FROM dbo.report_image_chunk WHERE LEN(chunk) > 8000;
    SET @dq += CONCAT(',{"check_name":"gold_report_image_chunk_le_8000","value":"', @v1,
                      '","status":"', CASE WHEN @v1 = 0 THEN 'pass' ELSE 'fail' END, '"}');
    SELECT @v1 = COUNT(*) FROM dbo.report_image AS i
    WHERE i.base64_length <> ISNULL((SELECT SUM(CAST(LEN(c.chunk) AS bigint)) FROM dbo.report_image_chunk AS c
                                     WHERE c.image_id = i.image_id), 0);
    SET @dq += CONCAT(',{"check_name":"gold_report_image_length_matches","value":"', @v1,
                      '","status":"', CASE WHEN @v1 = 0 THEN 'pass' ELSE 'fail' END, '"}');
    SELECT @v1 = COUNT(*), @v2 = ISNULL(SUM(base64_length), 0) FROM dbo.report_image;
    SET @dq += CONCAT(',{"check_name":"gold_report_image_count","value":"', @v1,
                      '","status":"', CASE WHEN @v1 > 0 THEN 'pass' ELSE 'warning' END, '"}');
    SET @dq += CONCAT(',{"check_name":"gold_report_image_total_base64_le_600000","value":"', @v2,
                      '","status":"', CASE WHEN @v2 <= 600000 THEN 'pass' ELSE 'warning' END, '"}');

    -- Counts for the run log
    SET @dq += CONCAT(',{"check_name":"gold_count_fact_performance","value":"', @n_fp, '","status":"pass"}');
    SET @dq += CONCAT(',{"check_name":"gold_count_fact_show","value":"', @n_fs, '","status":"pass"}');

    IF @force_fail = 1
        SET @dq += ',{"check_name":"gold_forced_failure","value":"forced by @force_fail = 1","status":"fail"}';

    SET @dq_json = '[' + STUFF(@dq, 1, 1, '') + ']';
END;

GO