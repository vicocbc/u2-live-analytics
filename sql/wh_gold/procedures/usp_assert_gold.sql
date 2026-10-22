-- Fails the caller (sqlcmd, pipeline activity) when the latest Gold build of @run_id logged a hard failure (SPEC-07).
-- Separate from dbo.usp_build_gold because an error raised inside that procedure would also undo its dq_run_log
-- rows (Fabric Warehouse rolls back the whole failed statement). Read-only, so throwing here loses nothing.
-- usp_build_gold stamps all rows of one build attempt with the same checked_at; only the latest attempt counts.
CREATE OR ALTER PROCEDURE dbo.usp_assert_gold
    @run_id varchar(100)
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @last datetime2(6), @n_logged int, @n_fail int, @msg varchar(2000);

    SELECT @last = MAX(checked_at) FROM dbo.dq_run_log WHERE run_id = @run_id AND layer = 'gold';
    IF @last IS NULL
        THROW 50002, 'usp_assert_gold: no Gold checks logged for this run id (did usp_build_gold run?)', 1;

    SELECT @n_logged = COUNT(*),
           @n_fail = SUM(CASE WHEN status = 'fail' THEN 1 ELSE 0 END)
    FROM dbo.dq_run_log
    WHERE run_id = @run_id AND layer = 'gold' AND checked_at = @last;

    IF @n_fail > 0
    BEGIN
        SELECT @msg = 'usp_assert_gold: hard Gold check(s) failed, Gold rolled back: '
                      + STRING_AGG(CAST(check_name AS varchar(max)), ', ')
        FROM dbo.dq_run_log
        WHERE run_id = @run_id AND layer = 'gold' AND checked_at = @last AND status = 'fail';
        THROW 50001, @msg, 1;
    END;

    SELECT 'gold ok' AS result, @n_logged AS checks_logged, @last AS checked_at;
END;
