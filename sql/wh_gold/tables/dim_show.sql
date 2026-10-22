-- dim_show (SPEC-04): one row per real show (lk_silver.dbo.show) + Unknown member (-1).
IF OBJECT_ID('dbo.dim_show') IS NULL
CREATE TABLE dbo.dim_show
(
    show_key     bigint        NOT NULL,
    setlist_id   varchar(20)   NOT NULL,
    show_label   varchar(300)  NOT NULL,  -- "1987-09-11 · Philadelphia · JFK Stadium"
    setlist_url  varchar(400)  NULL,
    show_info    varchar(2000) NULL,
    _built_at    datetime2(6)  NOT NULL
);
