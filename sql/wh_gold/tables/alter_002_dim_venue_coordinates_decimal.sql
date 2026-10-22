-- dim_venue.latitude / longitude: float -> decimal(9,6) (docs/model-bpa.md #2, BPA "Do not use floating point data
-- types"; requested by the data-analyst 2026-10-22).
-- Fabric Warehouse cannot ALTER COLUMN to another type ("requires data validation or rewrite"), so the two columns are
-- dropped and added back with the same names (they move to the end of the table; the model binds by name). No data is
-- lost: dim_venue is rebuilt from lk_silver by usp_build_dimensions on every build.
-- Idempotent: runs only while the columns are still float.
IF EXISTS (SELECT 1 FROM sys.columns AS c JOIN sys.types AS t ON t.user_type_id = c.user_type_id
           WHERE c.object_id = OBJECT_ID('dbo.dim_venue') AND c.name = 'latitude' AND t.name = 'float')
BEGIN
    ALTER TABLE dbo.dim_venue DROP COLUMN latitude;
    ALTER TABLE dbo.dim_venue ADD latitude decimal(9,6) NULL;
END;
IF EXISTS (SELECT 1 FROM sys.columns AS c JOIN sys.types AS t ON t.user_type_id = c.user_type_id
           WHERE c.object_id = OBJECT_ID('dbo.dim_venue') AND c.name = 'longitude' AND t.name = 'float')
BEGIN
    ALTER TABLE dbo.dim_venue DROP COLUMN longitude;
    ALTER TABLE dbo.dim_venue ADD longitude decimal(9,6) NULL;
END;
