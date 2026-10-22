-- Rebuilds every Gold dimension (and the report image tables) from lk_silver (SPEC-04).
-- Called by dbo.usp_build_gold inside its transaction; does not open or commit a transaction itself.
-- Surrogate keys: CAST(HASHBYTES('SHA2_256', CAST(<natural id> AS varchar(400))) AS bigint) (deterministic);
-- Unknown member key = -1 with natural id '(unknown)'. dim_date has no Unknown member (see tables/dim_date.sql).
CREATE OR ALTER PROCEDURE dbo.usp_build_dimensions
    @built_at datetime2(6)
AS
BEGIN
    SET NOCOUNT ON;

    ---------------------------------------------------------------- dim_date
    DECLARE @first_day date = '1976-01-01';
    DECLARE @last_day  date = DATEFROMPARTS(YEAR(SYSUTCDATETIME()) + 1, 12, 31);

    DELETE FROM dbo.dim_date;
    WITH digits AS (SELECT d FROM (VALUES (0),(1),(2),(3),(4),(5),(6),(7),(8),(9)) AS v(d)),
    numbers AS (
        SELECT a.d + 10 * b.d + 100 * c.d + 1000 * e.d + 10000 * f.d AS n
        FROM digits AS a CROSS JOIN digits AS b CROSS JOIN digits AS c CROSS JOIN digits AS e CROSS JOIN digits AS f
    ),
    days AS (
        SELECT DATEADD(day, n, @first_day) AS d
        FROM numbers
        WHERE n <= DATEDIFF(day, @first_day, @last_day)
    )
    INSERT INTO dbo.dim_date (date_key, [date], [year], decade, [quarter], [month], month_name, day_of_week, day_name, _built_at)
    SELECT YEAR(d) * 10000 + MONTH(d) * 100 + DAY(d),
           d,
           YEAR(d),
           CAST(YEAR(d) / 10 * 10 AS varchar(4)) + 's',
           DATEPART(quarter, d),
           MONTH(d),
           CAST(DATENAME(month, d) AS varchar(20)),
           DATEDIFF(day, CAST('1900-01-01' AS date), d) % 7 + 1,      -- 1900-01-01 was a Monday
           CAST(DATENAME(weekday, d) AS varchar(20)),
           @built_at
    FROM days;

    ---------------------------------------------------------------- dim_album
    DELETE FROM dbo.dim_album;
    -- album_label (T-27): title for studio albums, else "title (type, year)"; " #n" by album_order if still shared.
    -- release_decade_group (T-28): "1980s albums" … for studio albums, else "Not on a studio album".
    WITH ordered AS (
        SELECT a.*, ROW_NUMBER() OVER (ORDER BY a.release_date, a.album_id) AS album_order,
               CASE WHEN a.is_studio = 1 THEN a.title
                    ELSE CONCAT(a.title, ' (', a.album_type, ', ', ISNULL(CAST(a.release_year AS varchar(4)), 'n.d.'), ')')
               END AS label0
        FROM lk_silver.dbo.album AS a
    ),
    labelled AS (
        SELECT o.*, COUNT(*) OVER (PARTITION BY label0) AS n_same,
               ROW_NUMBER() OVER (PARTITION BY label0 ORDER BY album_order) AS n_in_label
        FROM ordered AS o
    )
    INSERT INTO dbo.dim_album (album_key, album_id, album_title, album_label, release_date, release_year, album_type,
                               is_studio, album_order, release_decade_group, _built_at)
    SELECT CAST(HASHBYTES('SHA2_256', CAST(album_id AS varchar(400))) AS bigint),
           album_id, title,
           CASE WHEN n_same > 1 THEN CONCAT(label0, ' #', n_in_label) ELSE label0 END,
           release_date, release_year, album_type, is_studio, album_order,
           CASE WHEN is_studio = 1 AND release_year IS NOT NULL THEN CONCAT(release_year / 10 * 10, 's albums')
                ELSE 'Not on a studio album' END,
           @built_at
    FROM labelled
    UNION ALL
    SELECT -1, '(unknown)', 'Unknown', 'Unknown', NULL, NULL, 'unknown', 0, 999999, 'Not on a studio album', @built_at;

    ---------------------------------------------------------------- dim_song
    DELETE FROM dbo.dim_song;
    WITH perf AS (
        SELECT m.song_id, p.event_date
        FROM lk_silver.dbo.performance AS p
        JOIN lk_silver.dbo.song_map AS m
          ON m.song_key = p.song_key AND ISNULL(m.cover_artist, '') = ISNULL(p.cover_artist, '')
        WHERE m.song_id IS NOT NULL AND m.match_method <> 'ignore' AND p.is_tape = 0 AND p.is_snippet = 0
    ),
    stats AS (
        SELECT song_id, MIN(event_date) AS debut, MAX(event_date) AS last_played, COUNT(*) AS full_performances
        FROM perf
        GROUP BY song_id
    )
    INSERT INTO dbo.dim_song (song_key, song_id, song_title, album_key, first_release_year, is_original, cover_artist,
                              live_debut_date, last_played_date, full_performances, _built_at)
    SELECT CAST(HASHBYTES('SHA2_256', CAST(s.song_id AS varchar(400))) AS bigint),
           s.song_id, s.title,
           CASE WHEN s.first_album_id IS NULL THEN -1
                ELSE CAST(HASHBYTES('SHA2_256', CAST(s.first_album_id AS varchar(400))) AS bigint) END,
           s.first_release_year, s.is_original, s.cover_artist,
           st.debut, st.last_played, ISNULL(st.full_performances, 0),
           @built_at
    FROM lk_silver.dbo.song AS s
    LEFT JOIN stats AS st ON st.song_id = s.song_id
    UNION ALL
    SELECT -1, '(unknown)', 'Unknown', -1, NULL, 0, NULL, NULL, NULL, 0, @built_at;

    ---------------------------------------------------------------- dim_tour
    DELETE FROM dbo.dim_tour;
    INSERT INTO dbo.dim_tour (tour_key, tour_name, tour_name_display, album_promoted_key, is_residency, show_type, era,
                              first_show_date, last_show_date, tour_order, _built_at)
    SELECT CAST(HASHBYTES('SHA2_256', CAST(t.tour_name AS varchar(400))) AS bigint),
           t.tour_name, t.tour_name_display,
           CASE WHEN t.album_promoted_id IS NULL THEN -1
                ELSE CAST(HASHBYTES('SHA2_256', CAST(t.album_promoted_id AS varchar(400))) AS bigint) END,
           t.is_residency,
           CASE WHEN t.is_residency = 1 THEN 'Residency' ELSE 'Touring' END,            -- T-28
           t.era, t.first_show_date, t.last_show_date,
           ROW_NUMBER() OVER (ORDER BY CASE WHEN t.tour_name = '(No tour)' THEN 1 ELSE 0 END, t.first_show_date, t.tour_name),
           @built_at
    FROM lk_silver.dbo.tour AS t
    UNION ALL
    SELECT -1, '(unknown)', 'Unknown', -1, 0, 'Touring', NULL, NULL, NULL, 999999, @built_at;

    ---------------------------------------------------------------- dim_venue
    DELETE FROM dbo.dim_venue;
    WITH latest AS (
        SELECT s.*, ROW_NUMBER() OVER (PARTITION BY s.venue_id ORDER BY s.event_date DESC, s.setlist_id DESC) AS rn
        FROM lk_silver.dbo.show AS s
        WHERE s.venue_id IS NOT NULL
    )
    INSERT INTO dbo.dim_venue (venue_key, venue_id, venue_name, city_name, state_code, country_code, country_name,
                               continent, latitude, longitude, _built_at)
    SELECT CAST(HASHBYTES('SHA2_256', CAST(venue_id AS varchar(400))) AS bigint),
           venue_id, venue_name, city_name, state_code, country_code, country_name, continent,
           CAST(latitude AS decimal(9,6)), CAST(longitude AS decimal(9,6)),
           @built_at
    FROM latest
    WHERE rn = 1
    UNION ALL
    SELECT -1, '(unknown)', 'Unknown', NULL, NULL, NULL, NULL, 'Unknown', NULL, NULL, @built_at;

    ---------------------------------------------------------------- dim_show
    -- show_label unique (T-27): same date and venue (early/late shows) get " · show n", numbered by setlist_id.
    DELETE FROM dbo.dim_show;
    WITH numbered AS (
        SELECT s.*,
               COUNT(*) OVER (PARTITION BY s.event_date, s.venue_id) AS n_same,
               ROW_NUMBER() OVER (PARTITION BY s.event_date, s.venue_id ORDER BY s.setlist_id) AS n_in_pair
        FROM lk_silver.dbo.show AS s
    )
    INSERT INTO dbo.dim_show (show_key, setlist_id, show_label, setlist_url, show_info, _built_at)
    SELECT CAST(HASHBYTES('SHA2_256', CAST(s.setlist_id AS varchar(400))) AS bigint),
           s.setlist_id,
           CONVERT(varchar(10), s.event_date, 23) + ' · ' + ISNULL(s.city_name, '?') + ' · ' + ISNULL(s.venue_name, '?')
             + CASE WHEN s.n_same > 1 THEN CONCAT(' · show ', s.n_in_pair) ELSE '' END,
           s.setlist_url, s.show_info,
           @built_at
    FROM numbered AS s
    UNION ALL
    SELECT -1, '(unknown)', 'Unknown', NULL, NULL, @built_at;

    ---------------------------------------------------------------- report images (presentation assets, no keys)
    DELETE FROM dbo.report_image;
    INSERT INTO dbo.report_image (image_id, file_name, mime_type, bytes, base64_length, chunk_count, credit_text,
                                  license, source_url, _built_at)
    SELECT image_id, file_name, mime_type, bytes, base64_length, chunk_count, credit_text, license, source_url, @built_at
    FROM lk_silver.dbo.report_image;

    DELETE FROM dbo.report_image_chunk;
    INSERT INTO dbo.report_image_chunk (image_id, chunk_no, chunk, _built_at)
    SELECT image_id, chunk_no, chunk, @built_at
    FROM lk_silver.dbo.report_image_chunk;
END;
