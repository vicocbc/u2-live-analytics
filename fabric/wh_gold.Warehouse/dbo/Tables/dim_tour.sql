CREATE TABLE [dbo].[dim_tour] (
    [tour_key]           BIGINT        NOT NULL,
    [tour_name]          VARCHAR (100) NOT NULL,
    [tour_name_display]  VARCHAR (100) NOT NULL,
    [album_promoted_key] BIGINT        NOT NULL,
    [is_residency]       BIT           NOT NULL,
    [era]                VARCHAR (100) NULL,
    [first_show_date]    DATE          NULL,
    [last_show_date]     DATE          NULL,
    [tour_order]         INT           NOT NULL,
    [_built_at]          DATETIME2 (6) NOT NULL,
    [show_type]          VARCHAR (20)  NULL,
    [tour_type]          VARCHAR (20)  NULL,
    [is_planned]         BIT           NULL
);


GO