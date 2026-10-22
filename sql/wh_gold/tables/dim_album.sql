-- dim_album (SPEC-04): one row per lk_silver.dbo.album + Unknown (-1).
IF OBJECT_ID('dbo.dim_album') IS NULL
CREATE TABLE dbo.dim_album
(
    album_key     bigint       NOT NULL,
    album_id      varchar(50)  NOT NULL,
    album_title   varchar(200) NOT NULL,
    release_date  date         NULL,
    release_year  int          NULL,
    album_type    varchar(20)  NOT NULL,  -- studio, live, compilation, re-recording, ep, single (unknown for -1)
    is_studio     bit          NOT NULL,
    album_order   int          NOT NULL,  -- chronological sort; Unknown last
    _built_at     datetime2(6) NOT NULL
);
