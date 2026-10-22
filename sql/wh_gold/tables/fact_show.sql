-- fact_show (SPEC-04): one row per real show.
IF OBJECT_ID('dbo.fact_show') IS NULL
CREATE TABLE dbo.fact_show
(
    show_key     bigint       NOT NULL,
    date_key     int          NOT NULL,
    tour_key     bigint       NOT NULL,
    venue_key    bigint       NOT NULL,
    song_count   int          NOT NULL,  -- full performances: no tapes, no snippets, no fragments
    has_setlist  bit          NOT NULL,
    _built_at    datetime2(6) NOT NULL
);
