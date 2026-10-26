CREATE TABLE [dbo].[fact_setlist_backtest] (
    [tour_key]      BIGINT        NOT NULL,
    [method]        VARCHAR (10)  NOT NULL,
    [metric]        VARCHAR (30)  NOT NULL,
    [value]         FLOAT (53)    NOT NULL,
    [model_version] VARCHAR (20)  NOT NULL,
    [_built_at]     DATETIME2 (6) NOT NULL
);


GO