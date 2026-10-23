CREATE TABLE [dbo].[report_image] (
    [image_id]      VARCHAR (100) NOT NULL,
    [file_name]     VARCHAR (200) NOT NULL,
    [mime_type]     VARCHAR (50)  NOT NULL,
    [bytes]         INT           NOT NULL,
    [base64_length] INT           NOT NULL,
    [chunk_count]   INT           NOT NULL,
    [credit_text]   VARCHAR (400) NULL,
    [license]       VARCHAR (50)  NULL,
    [source_url]    VARCHAR (400) NULL,
    [_built_at]     DATETIME2 (6) NOT NULL
);


GO