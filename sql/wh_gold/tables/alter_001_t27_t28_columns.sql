-- Columns added during T-27/T-28 (SPEC-04, data-analyst): ALTER, never drop/recreate (the model binds to the tables).
-- Idempotent: each column is added only if missing (sys.columns; COL_LENGTH is not supported in Fabric Warehouse).
-- Filled by dbo.usp_build_dimensions.
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.dim_album') AND name = 'album_label')
    ALTER TABLE dbo.dim_album ADD album_label varchar(300) NULL;          -- unique display name
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.dim_album') AND name = 'release_decade_group')
    ALTER TABLE dbo.dim_album ADD release_decade_group varchar(30) NULL; -- '1980s albums' … / 'Not on a studio album'
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.dim_tour') AND name = 'show_type')
    ALTER TABLE dbo.dim_tour ADD show_type varchar(20) NULL;             -- 'Residency' / 'Touring'
-- dim_show.show_label already exists; T-27 only makes it unique (logic in usp_build_dimensions).
