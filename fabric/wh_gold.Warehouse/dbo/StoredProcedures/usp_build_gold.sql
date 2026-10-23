-- Entry point of the Gold build (SPEC-04, SPEC-07): rebuilds every Gold table from lk_silver in ONE transaction,
-- runs the Gold checks (dbo.usp_dq_gold), commits only if no hard check failed, then appends the check results to
-- dq_run_log (also after a rollback or an error) and returns them as result sets.
-- It does NOT throw: in Fabric Warehouse an error raised inside the procedure undoes the whole EXEC statement,
-- including the dq_run_log rows. Run dbo.usp_assert_gold as a SEPARATE statement afterwards to fail the caller:
--   EXEC dbo.usp_build_gold @run_id = '<run id>';
--   EXEC dbo.usp_assert_gold @run_id = '<run id>';                -- THROWs if a hard Gold check failed
--   EXEC dbo.usp_build_gold @run_id = '...', @force_fail = 1;   -- rollback test: Gold must stay as it was
CREATE   PROCEDURE dbo.usp_build_gold
    @run_id     varchar(100),
    @force_fail bit = 0
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @built_at datetime2(6) = SYSUTCDATETIME();
    DECLARE @hard int = 0;
    DECLARE @dq_json varchar(max);   -- check results; a variable survives the ROLLBACK (temp table rows would not)
    DECLARE @error varchar(200);

    BEGIN TRY
        BEGIN TRANSACTION;
        EXEC dbo.usp_build_dimensions @built_at = @built_at;
        EXEC dbo.usp_build_facts @built_at = @built_at;
        EXEC dbo.usp_dq_gold @run_id = @run_id, @force_fail = @force_fail, @dq_json = @dq_json OUTPUT;

        SELECT @hard = COUNT(*)
        FROM OPENJSON(@dq_json) WITH (status varchar(10))
        WHERE status = 'fail';
        IF @hard > 0
            ROLLBACK TRANSACTION;
        ELSE
            COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        SET @error = LEFT(ERROR_MESSAGE(), 200);
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        SET @hard = @hard + 1;
    END CATCH;

    -- Outside the transaction: always logged, after commit, rollback or error. One checked_at per build attempt
    -- (usp_assert_gold judges the latest attempt of a run id).
    DECLARE @logged_at datetime2(6) = SYSUTCDATETIME();
    INSERT INTO dbo.dq_run_log (run_id, layer, check_name, value, status, checked_at)
    SELECT @run_id, 'gold', check_name, value, status, @logged_at
    FROM OPENJSON(ISNULL(@dq_json, '[]')) WITH (check_name varchar(200), value varchar(200), status varchar(10))
    UNION ALL
    SELECT @run_id, 'gold', 'gold_build_error', @error, 'fail', @logged_at
    WHERE @error IS NOT NULL;

    SELECT check_name, value, status
    FROM OPENJSON(ISNULL(@dq_json, '[]')) WITH (check_name varchar(200), value varchar(200), status varchar(10))
    ORDER BY check_name;
    SELECT CASE WHEN @hard > 0 THEN 'rolled back' ELSE 'committed' END AS gold_build_result, @hard AS hard_failures,
           @error AS build_error;
END;

GO