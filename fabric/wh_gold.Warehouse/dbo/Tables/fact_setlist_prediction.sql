CREATE TABLE [dbo].[fact_setlist_prediction] (
    [as_of_date_key]       INT           NOT NULL,
    [tour_key]             BIGINT        NOT NULL,
    [song_key]             BIGINT        NOT NULL,
    [shows_observed]       INT           NOT NULL,
    [probability]          FLOAT (53)    NOT NULL,
    [predicted_in_setlist] BIT           NOT NULL,
    [predicted_position]   INT           NULL,
    [predicted_set]        VARCHAR (10)  NULL,
    [model_part]           VARCHAR (10)  NOT NULL,
    [model_version]        VARCHAR (20)  NOT NULL,
    [_built_at]            DATETIME2 (6) NOT NULL
);


GO