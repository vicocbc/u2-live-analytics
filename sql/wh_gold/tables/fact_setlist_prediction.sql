-- fact_setlist_prediction (SPEC-09 9.7, T-49): setlist prediction of the planned / current tour.
-- Grain: (as_of_date_key, tour_key, song_key). From lk_silver.dbo.setlist_prediction WHERE is_backtest = 0:
-- the pre-tour prediction (shows_observed = 0, as_of_date = day before the first show) and, from the first show on,
-- one in-tour set per as_of_date (no position or set). Backtest predictions stay in Silver.
IF OBJECT_ID('dbo.fact_setlist_prediction') IS NULL
CREATE TABLE dbo.fact_setlist_prediction
(
    as_of_date_key        int          NOT NULL,  -- yyyyMMdd -> dim_date
    tour_key              bigint       NOT NULL,  -- -> dim_tour (target tour)
    song_key              bigint       NOT NULL,  -- -> dim_song (candidate song)
    shows_observed        int          NOT NULL,  -- shows of the tour played before as_of_date (0 = pre-tour)
    probability           float        NOT NULL,  -- 0..1
    predicted_in_setlist  bit          NOT NULL,
    predicted_position    int          NULL,      -- 1..N, pre-tour rows only
    predicted_set         varchar(10)  NULL,      -- 'main' / 'encore', pre-tour rows only
    model_part            varchar(10)  NOT NULL,  -- 'catalog' / 'new'
    model_version         varchar(20)  NOT NULL,  -- e.g. 'sl1.0-u2lib0.5.0'
    _built_at             datetime2(6) NOT NULL
);
