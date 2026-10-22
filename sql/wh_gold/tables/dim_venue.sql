-- dim_venue (SPEC-04): one row per venue_id in lk_silver.dbo.show (attributes from its latest show) + Unknown (-1).
IF OBJECT_ID('dbo.dim_venue') IS NULL
CREATE TABLE dbo.dim_venue
(
    venue_key     bigint       NOT NULL,
    venue_id      varchar(20)  NOT NULL,
    venue_name    varchar(200) NULL,
    city_name     varchar(100) NULL,
    state_code    varchar(20)  NULL,
    country_code  varchar(10)  NULL,
    country_name  varchar(100) NULL,
    continent     varchar(30)  NULL,
    latitude      decimal(9,6) NULL,   -- decimal, not float (model BPA; alter_002 converts existing tables)
    longitude     decimal(9,6) NULL,
    _built_at     datetime2(6) NOT NULL
);
