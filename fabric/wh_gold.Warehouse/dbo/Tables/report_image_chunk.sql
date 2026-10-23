CREATE TABLE [dbo].[report_image_chunk] (
    [image_id]  VARCHAR (100)  NOT NULL,
    [chunk_no]  INT            NOT NULL,
    [chunk]     VARCHAR (8000) NOT NULL,
    [_built_at] DATETIME2 (6)  NOT NULL
);


GO