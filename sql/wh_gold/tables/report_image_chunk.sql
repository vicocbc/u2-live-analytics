-- report_image_chunk (SPEC-04): 8,000-character slices of each photo's base64, in order of chunk_no.
IF OBJECT_ID('dbo.report_image_chunk') IS NULL
CREATE TABLE dbo.report_image_chunk
(
    image_id   varchar(100)  NOT NULL,
    chunk_no   int           NOT NULL,  -- 1-based
    chunk      varchar(8000) NOT NULL,
    _built_at  datetime2(6)  NOT NULL
);
