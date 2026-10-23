CREATE TABLE [dbo].[dim_album] (
    [album_key]            BIGINT        NOT NULL,
    [album_id]             VARCHAR (50)  NOT NULL,
    [album_title]          VARCHAR (200) NOT NULL,
    [release_date]         DATE          NULL,
    [release_year]         INT           NULL,
    [album_type]           VARCHAR (20)  NOT NULL,
    [is_studio]            BIT           NOT NULL,
    [album_order]          INT           NOT NULL,
    [_built_at]            DATETIME2 (6) NOT NULL,
    [album_label]          VARCHAR (300) NULL,
    [release_decade_group] VARCHAR (30)  NULL
);


GO