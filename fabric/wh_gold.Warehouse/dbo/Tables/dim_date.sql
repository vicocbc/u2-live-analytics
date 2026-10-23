CREATE TABLE [dbo].[dim_date] (
    [date_key]    INT           NOT NULL,
    [date]        DATE          NOT NULL,
    [year]        INT           NOT NULL,
    [decade]      VARCHAR (10)  NOT NULL,
    [quarter]     INT           NOT NULL,
    [month]       INT           NOT NULL,
    [month_name]  VARCHAR (20)  NOT NULL,
    [day_of_week] INT           NOT NULL,
    [day_name]    VARCHAR (20)  NOT NULL,
    [_built_at]   DATETIME2 (6) NOT NULL
);


GO