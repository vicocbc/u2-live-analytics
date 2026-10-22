"""Data quality checks for notebooks (SPEC-07). Usage at the end of every notebook:

dq = Results(run_id=RUN_ID, layer="silver")
dq.check("show_reconciles", n_show + n_excluded == n_bronze, "hard", value=n_show)
dq.write(spark)   # append to wh_gold.dbo.dq_run_log
dq.raise_on_hard_failures()
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

SEVERITIES = ("hard", "warning")

DQ_RUN_LOG_TABLE = "wh_gold.dbo.dq_run_log"

# Columns of wh_gold.dbo.dq_run_log, in order (DDL in sql/wh_gold/tables/dq_run_log.sql).
DQ_RUN_LOG_COLUMNS = ("run_id", "layer", "check_name", "value", "status", "checked_at")


class DataQualityError(Exception):
    """Raised when at least one hard check failed."""


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    severity: str
    value: Any = None
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def status(self) -> str:
        """`pass`, `warning` (failed warning check) or `fail` (failed hard check)."""
        if self.passed:
            return "pass"
        return "fail" if self.severity == "hard" else "warning"

    def __str__(self) -> str:
        value = "" if self.value is None else f" (value={self.value})"
        return f"[{self.status.upper()}] {self.name}{value}"


def check(name: str, condition: bool, severity: str, value: Any = None) -> CheckResult:
    """Evaluate one check. `severity` is "hard" (stops the pipeline) or "warning" (printed and logged)."""
    if severity not in SEVERITIES:
        raise ValueError(f"severity must be one of {SEVERITIES}, got {severity!r}")
    return CheckResult(name=name, passed=bool(condition), severity=severity, value=value)


class Results:
    """Collects the checks of one notebook run, prints them, writes them to dq_run_log and raises."""

    def __init__(self, run_id: str, layer: str) -> None:
        self.run_id = run_id
        self.layer = layer
        self.results: list[CheckResult] = []

    def check(self, name: str, condition: bool, severity: str, value: Any = None) -> CheckResult:
        result = check(name, condition, severity, value)
        self.results.append(result)
        print(result)
        return result

    @property
    def hard_failures(self) -> list[CheckResult]:
        return [r for r in self.results if r.status == "fail"]

    @property
    def warnings(self) -> list[CheckResult]:
        return [r for r in self.results if r.status == "warning"]

    def rows(self) -> list[tuple]:
        """One tuple per check in `DQ_RUN_LOG_COLUMNS` order; `value` as text so mixed types fit one column."""
        return [
            (
                self.run_id,
                self.layer,
                r.name,
                None if r.value is None else str(r.value),
                r.status,
                r.checked_at,
            )
            for r in self.results
        ]

    def write(self, spark: Any, table: str = DQ_RUN_LOG_TABLE) -> None:
        """Append the results to the warehouse table `table` (the only append allowed in the medallion conventions).

        Uses the Fabric Spark connector for Warehouse (`DataFrameWriter.synapsesql`), which the import below
        registers in Fabric notebooks.
        """
        with contextlib.suppress(ImportError):  # outside Fabric (local tests)
            import com.microsoft.spark.fabric  # noqa: F401
        schema = "run_id string, layer string, check_name string, value string, status string, checked_at timestamp"
        spark.createDataFrame(self.rows(), schema=schema).write.mode("append").synapsesql(table)

    def raise_on_hard_failures(self) -> None:
        failures = self.hard_failures
        if failures:
            names = ", ".join(r.name for r in failures)
            raise DataQualityError(f"{len(failures)} hard check(s) failed in {self.layer}: {names}")

    def summary(self) -> dict[str, int]:
        """Counts for the notebook exit value."""
        return {
            "checks": len(self.results),
            "failed": len(self.hard_failures),
            "warnings": len(self.warnings),
        }
