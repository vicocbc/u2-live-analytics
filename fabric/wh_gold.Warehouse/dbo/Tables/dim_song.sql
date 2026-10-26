CREATE TABLE [dbo].[dim_song] (
    [song_key]           BIGINT        NOT NULL,
    [song_id]            VARCHAR (200) NOT NULL,
    [song_title]         VARCHAR (200) NOT NULL,
    [album_key]          BIGINT        NOT NULL,
    [first_release_year] INT           NULL,
    [is_original]        BIT           NOT NULL,
    [cover_artist]       VARCHAR (200) NULL,
    [live_debut_date]    DATE          NULL,
    [last_played_date]   DATE          NULL,
    [full_performances]  INT           NOT NULL,
    [_built_at]          DATETIME2 (6) NOT NULL,
    [release_role_2027]  VARCHAR (30)  NULL,
    [is_single]          BIT           NULL
);


GO