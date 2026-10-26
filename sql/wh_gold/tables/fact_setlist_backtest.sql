-- fact_setlist_backtest (SPEC-09 9.6/9.7, T-49): backtest metrics of the setlist model and the baselines.
-- Grain: (tour_key, method, metric). From lk_silver.dbo.setlist_backtest.
-- method: 'model', 'B1', 'B2', 'B3', 'context'; metric: precision_at_n, jaccard_first_show, brier_play_rate,
-- new_count_error, and for method 'context' songs_per_show_predicted/_actual, core_size_actual, new_per_show_predicted/_actual.
IF OBJECT_ID('dbo.fact_setlist_backtest') IS NULL
CREATE TABLE dbo.fact_setlist_backtest
(
    tour_key       bigint       NOT NULL,  -- -> dim_tour (backtest tour)
    method         varchar(10)  NOT NULL,
    metric         varchar(30)  NOT NULL,
    value          float        NOT NULL,
    model_version  varchar(20)  NOT NULL,
    _built_at      datetime2(6) NOT NULL
);
