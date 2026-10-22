import pytest

from u2lib.quality import DQ_RUN_LOG_COLUMNS, DataQualityError, Results, check


def test_check_statuses():
    assert check("a", True, "hard").status == "pass"
    assert check("b", False, "hard").status == "fail"
    assert check("c", False, "warning").status == "warning"


def test_check_rejects_unknown_severity():
    with pytest.raises(ValueError):
        check("a", True, "fatal")


def test_check_str():
    assert str(check("rows", True, "hard", value=10)) == "[PASS] rows (value=10)"
    assert str(check("rows", False, "warning")) == "[WARNING] rows"


def test_results_collect_print_and_summarise(capsys):
    dq = Results(run_id="r1", layer="silver")
    dq.check("ok", True, "hard", value=5)
    dq.check("low_share", False, "warning", value=0.97)
    assert "[PASS] ok (value=5)" in capsys.readouterr().out
    assert dq.summary() == {"checks": 2, "failed": 0, "warnings": 1}
    dq.raise_on_hard_failures()  # warnings never raise


def test_results_raise_on_hard_failure():
    dq = Results(run_id="r1", layer="gold")
    dq.check("no_null_fk", False, "hard", value=3)
    with pytest.raises(DataQualityError, match="no_null_fk"):
        dq.raise_on_hard_failures()


def test_rows_match_dq_run_log_columns():
    dq = Results(run_id="r1", layer="bronze")
    dq.check("count", True, "hard", value=1234)
    dq.check("no_value", True, "warning")
    rows = dq.rows()
    assert len(rows[0]) == len(DQ_RUN_LOG_COLUMNS)
    assert rows[0][:5] == ("r1", "bronze", "count", "1234", "pass")
    assert rows[1][3] is None


class _FakeWriter:
    def __init__(self, log):
        self.log = log

    def mode(self, mode):
        self.log["mode"] = mode
        return self

    def synapsesql(self, table):
        self.log["table"] = table


class _FakeDataFrame:
    def __init__(self, log):
        self.write = _FakeWriter(log)


class _FakeSpark:
    def __init__(self):
        self.log = {}

    def createDataFrame(self, rows, schema):
        self.log["rows"] = rows
        self.log["schema"] = schema
        return _FakeDataFrame(self.log)


def test_write_appends_to_dq_run_log():
    spark = _FakeSpark()
    dq = Results(run_id="r1", layer="gold")
    dq.check("count", True, "hard", value=1)
    dq.write(spark)
    assert spark.log["mode"] == "append"
    assert spark.log["table"] == "wh_gold.dbo.dq_run_log"
    assert spark.log["rows"] == dq.rows()
    assert [c.split()[0] for c in spark.log["schema"].split(", ")] == list(DQ_RUN_LOG_COLUMNS)
