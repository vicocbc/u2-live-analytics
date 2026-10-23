-- Rebuilds fact_performance and fact_show from lk_silver (SPEC-04). Run after usp_build_dimensions, inside the
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
END;

GO