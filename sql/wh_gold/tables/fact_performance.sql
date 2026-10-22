-- fact_performance (SPEC-04): one row per song performed at a show (snippets, tapes and fragments included, flagged).
-- Source: lk_silver.dbo.performance joined to song_map on song_key + ISNULL(cover_artist, ''); 'ignore' rows dropped.
IF OBJECT_ID('dbo.fact_performance') IS NULL
CREATE TABLE dbo.fact_performance
(
    show_key             bigint       NOT NULL,
    date_key             int          NOT NULL,
    song_key             bigint       NOT NULL,
    tour_key             bigint       NOT NULL,
    venue_key            bigint       NOT NULL,
    setlist_position     int          NOT NULL,
    set_name             varchar(50)  NULL,
    is_encore            bit          NOT NULL,
    is_opener            bit          NOT NULL,
    is_closer            bit          NOT NULL,
    is_snippet           bit          NOT NULL,
    is_tape              bit          NOT NULL,
    is_fragment          bit          NOT NULL,
    is_cover             bit          NOT NULL,
    has_guest            bit          NOT NULL,
    guest_artist         varchar(200) NULL,
    is_live_debut        bit          NOT NULL,
    is_only_performance  bit          NOT NULL,
    _built_at            datetime2(6) NOT NULL
);
