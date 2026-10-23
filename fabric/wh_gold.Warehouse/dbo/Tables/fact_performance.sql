CREATE TABLE [dbo].[fact_performance] (
    [show_key]            BIGINT        NOT NULL,
    [date_key]            INT           NOT NULL,
    [song_key]            BIGINT        NOT NULL,
    [tour_key]            BIGINT        NOT NULL,
    [venue_key]           BIGINT        NOT NULL,
    [setlist_position]    INT           NOT NULL,
    [set_name]            VARCHAR (50)  NULL,
    [is_encore]           BIT           NOT NULL,
    [is_opener]           BIT           NOT NULL,
    [is_closer]           BIT           NOT NULL,
    [is_snippet]          BIT           NOT NULL,
    [is_tape]             BIT           NOT NULL,
    [is_fragment]         BIT           NOT NULL,
    [is_cover]            BIT           NOT NULL,
    [has_guest]           BIT           NOT NULL,
    [guest_artist]        VARCHAR (200) NULL,
    [is_live_debut]       BIT           NOT NULL,
    [is_only_performance] BIT           NOT NULL,
    [_built_at]           DATETIME2 (6) NOT NULL
);


GO