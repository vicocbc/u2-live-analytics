-- dim_song (SPEC-04): one row per lk_silver.dbo.song (MusicBrainz works, u2: originals, cover: songs) + Unknown (-1).
IF OBJECT_ID('dbo.dim_song') IS NULL
CREATE TABLE dbo.dim_song
(
    song_key            bigint       NOT NULL,
    song_id             varchar(200) NOT NULL,
    song_title          varchar(200) NOT NULL,
    album_key           bigint       NOT NULL,  -- first album → dim_album; -1 when none
    first_release_year  int          NULL,
    is_original         bit          NOT NULL,
    cover_artist        varchar(200) NULL,
    live_debut_date     date         NULL,      -- first full performance
    last_played_date    date         NULL,      -- last full performance
    full_performances   int          NOT NULL,  -- non-tape, non-snippet (sorting helper)
    _built_at           datetime2(6) NOT NULL
);
