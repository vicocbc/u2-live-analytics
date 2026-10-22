-- Data quality results of every layer (SPEC-04, SPEC-07). Appended by notebooks (u2lib.quality) and usp_build_gold.
IF OBJECT_ID('dbo.dq_run_log') IS NULL
CREATE TABLE dbo.dq_run_log
(
    run_id      varchar(100) NOT NULL,
    layer       varchar(20)  NOT NULL,
    check_name  varchar(200) NOT NULL,
    value       varchar(200) NULL,
    status      varchar(10)  NOT NULL,
    checked_at  datetime2(6) NOT NULL
);
