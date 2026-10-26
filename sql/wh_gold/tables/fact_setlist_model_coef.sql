-- fact_setlist_model_coef (SPEC-09 9.5/9.7, T-49): logistic-regression coefficients of every fitted setlist model,
-- so the report can explain a prediction. Grain: (tour_key, model_part, feature). From lk_silver.dbo.setlist_model_coef
-- (one model per target tour: the planned tour and every backtest tour). feature 'intercept' has coef_standardized NULL.
IF OBJECT_ID('dbo.fact_setlist_model_coef') IS NULL
CREATE TABLE dbo.fact_setlist_model_coef
(
    tour_key           bigint       NOT NULL,  -- -> dim_tour (target tour of the model)
    model_part         varchar(10)  NOT NULL,  -- 'catalog' / 'new'
    feature            varchar(40)  NOT NULL,
    coef_standardized  float        NULL,      -- per standard deviation of the feature
    coef_raw           float        NULL,      -- per original unit of the feature
    n_train            int          NOT NULL,  -- training rows
    n_positive         int          NOT NULL,  -- training rows with the positive class
    model_version      varchar(20)  NOT NULL,
    _built_at          datetime2(6) NOT NULL
);
