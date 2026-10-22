-- dim_tour (SPEC-04): one row per lk_silver.dbo.tour (incl. "(No tour)") + Unknown (-1).
IF OBJECT_ID('dbo.dim_tour') IS NULL
CREATE TABLE dbo.dim_tour
(
    tour_key            bigint       NOT NULL,
    tour_name           varchar(100) NOT NULL,
    tour_name_display   varchar(100) NOT NULL,
    album_promoted_key  bigint       NOT NULL,  -- → dim_album (inactive relationship in SPEC-05); -1 when none
    is_residency        bit          NOT NULL,
    era                 varchar(100) NULL,
    first_show_date     date         NULL,
    last_show_date      date         NULL,
    tour_order          int          NOT NULL,  -- chronological; "(No tour)" and Unknown last
    _built_at           datetime2(6) NOT NULL
);
