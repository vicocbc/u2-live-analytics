-- report_image (SPEC-04 "Report presentation assets"): one row per photo; hidden in the model, no relationships
-- to the star schema. Empty until T-32 delivers seeds/report_images.csv and the files.
IF OBJECT_ID('dbo.report_image') IS NULL
CREATE TABLE dbo.report_image
(
    image_id       varchar(100) NOT NULL,
    file_name      varchar(200) NOT NULL,
    mime_type      varchar(50)  NOT NULL,
    bytes          int          NOT NULL,
    base64_length  int          NOT NULL,
    chunk_count    int          NOT NULL,
    credit_text    varchar(400) NULL,
    license        varchar(50)  NULL,
    source_url     varchar(400) NULL,
    _built_at      datetime2(6) NOT NULL
);
