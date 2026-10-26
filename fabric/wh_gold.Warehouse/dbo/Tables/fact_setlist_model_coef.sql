CREATE TABLE [dbo].[fact_setlist_model_coef] (
    [tour_key]          BIGINT        NOT NULL,
    [model_part]        VARCHAR (10)  NOT NULL,
    [feature]           VARCHAR (40)  NOT NULL,
    [coef_standardized] FLOAT (53)    NULL,
    [coef_raw]          FLOAT (53)    NULL,
    [n_train]           INT           NOT NULL,
    [n_positive]        INT           NOT NULL,
    [model_version]     VARCHAR (20)  NOT NULL,
    [_built_at]         DATETIME2 (6) NOT NULL
);


GO