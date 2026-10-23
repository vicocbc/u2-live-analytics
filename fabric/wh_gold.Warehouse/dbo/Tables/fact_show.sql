CREATE TABLE [dbo].[fact_show] (
    [show_key]    BIGINT        NOT NULL,
    [date_key]    INT           NOT NULL,
    [tour_key]    BIGINT        NOT NULL,
    [venue_key]   BIGINT        NOT NULL,
    [song_count]  INT           NOT NULL,
    [has_setlist] BIT           NOT NULL,
    [_built_at]   DATETIME2 (6) NOT NULL
);


GO