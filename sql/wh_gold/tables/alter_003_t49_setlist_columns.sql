-- Columns added in T-49 (SPEC-09 9.7, SPEC-04): ALTER, never drop/recreate (the model binds to the tables).
-- Idempotent: each column is added only if missing (sys.columns; COL_LENGTH is not supported in Fabric Warehouse).
-- Filled by dbo.usp_build_dimensions.
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.dim_tour') AND name = 'tour_type')
    ALTER TABLE dbo.dim_tour ADD tour_type varchar(20) NULL;          -- album/anniversary/residency/promo/benefit/early; NULL for (No tour), Unknown
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.dim_tour') AND name = 'is_planned')
    ALTER TABLE dbo.dim_tour ADD is_planned bit NULL;                 -- announced tour without shows yet; 0 otherwise
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.dim_song') AND name = 'release_role_2027')
    ALTER TABLE dbo.dim_song ADD release_role_2027 varchar(30) NULL;  -- 'promoted_album' / 'companion_release' for the 25 2026 tracks; NULL for catalog
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.dim_song') AND name = 'is_single')
    ALTER TABLE dbo.dim_song ADD is_single bit NULL;                  -- released as a single (lk_silver.dbo.song); 0 otherwise
