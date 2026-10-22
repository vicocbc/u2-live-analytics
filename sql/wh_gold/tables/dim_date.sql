-- dim_date (SPEC-04): one row per day from 1976-01-01 to 31 December of the current year + 1.
-- No Unknown member: SPEC-05 marks it as the date table, which needs unique, contiguous, non-blank dates; every show
-- has a date and usp_dq_gold checks that every fact date_key exists here.
IF OBJECT_ID('dbo.dim_date') IS NULL
CREATE TABLE dbo.dim_date
(
    date_key     int          NOT NULL,   -- yyyyMMdd
    [date]       date         NOT NULL,
    [year]       int          NOT NULL,
    decade       varchar(10)  NOT NULL,   -- e.g. 1980s
    [quarter]    int          NOT NULL,
    [month]      int          NOT NULL,
    month_name   varchar(20)  NOT NULL,
    day_of_week  int          NOT NULL,   -- 1 = Monday … 7 = Sunday
    day_name     varchar(20)  NOT NULL,
    _built_at    datetime2(6) NOT NULL
);
