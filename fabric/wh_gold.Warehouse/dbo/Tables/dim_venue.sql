CREATE TABLE [dbo].[dim_venue] (
    [venue_key]    BIGINT         NOT NULL,
    [venue_id]     VARCHAR (20)   NOT NULL,
    [venue_name]   VARCHAR (200)  NULL,
    [city_name]    VARCHAR (100)  NULL,
    [state_code]   VARCHAR (20)   NULL,
    [country_code] VARCHAR (10)   NULL,
    [country_name] VARCHAR (100)  NULL,
    [continent]    VARCHAR (30)   NULL,
    [_built_at]    DATETIME2 (6)  NOT NULL,
    [latitude]     DECIMAL (9, 6) NULL,
    [longitude]    DECIMAL (9, 6) NULL
);


GO