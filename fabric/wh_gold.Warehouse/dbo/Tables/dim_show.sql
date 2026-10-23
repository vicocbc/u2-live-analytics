CREATE TABLE [dbo].[dim_show] (
    [show_key]    BIGINT         NOT NULL,
    [setlist_id]  VARCHAR (20)   NOT NULL,
    [show_label]  VARCHAR (300)  NOT NULL,
    [setlist_url] VARCHAR (400)  NULL,
    [show_info]   VARCHAR (2000) NULL,
    [_built_at]   DATETIME2 (6)  NOT NULL
);


GO