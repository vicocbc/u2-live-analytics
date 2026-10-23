CREATE TABLE [dbo].[dq_run_log] (
    [run_id]     VARCHAR (100) NOT NULL,
    [layer]      VARCHAR (20)  NOT NULL,
    [check_name] VARCHAR (200) NOT NULL,
    [value]      VARCHAR (200) NULL,
    [status]     VARCHAR (10)  NOT NULL,
    [checked_at] DATETIME2 (6) NOT NULL
);


GO