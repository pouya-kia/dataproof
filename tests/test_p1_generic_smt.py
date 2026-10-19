"""Development-only Paper 1 tests; frozen P1 case outcomes are never searched here."""

from __future__ import annotations

import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import z3

from dataproof.models import parse_spec
from dataproof.parser import parse_query
from dataproof.replay import validate
from research.benchmarks import p1_duckdb_oracle as oracle
from research.benchmarks import p1_generic_smt as generic
from research.benchmarks import p1_generic_smt_run as runner


def _spec(
    columns: list[dict[str, Any]],
    view: str,
    metric: str,
    *,
    rows: int = 2,
    primary: list[str] | None = None,
    unique: list[list[str]] | None = None,
) -> Any:
    return parse_spec(
        {
            "table": {
                "name": "dev",
                "columns": columns,
                "primary_key": primary or [],
                "unique": unique or [],
            },
            "views": [view],
            "metric": metric,
            "max_rows": rows,
        }
    )


def _col(
    name: str, values: list[Any], *, nullable: bool = False, typ: str = "INTEGER"
) -> dict[str, Any]:
    return {"name": name, "type": typ, "nullable": nullable, "domain": values}


def _check(spec: Any, status: str, minimum: int | None) -> None:
    view = parse_query(spec.views[0], spec, metric=False)
    metric = parse_query(spec.metric, spec, metric=True)
    actual = generic.search(spec, view, metric)
    reference = oracle.evaluate(spec)
    assert reference.status == status
    assert reference.minimum_rows == minimum
    assert actual.status == ("CANDIDATE" if status == "COUNTEREXAMPLE_FOUND" else status)
    if actual.worlds is not None:
        assert validate(spec, *actual.worlds).valid
        assert sum(map(len, actual.worlds)) == minimum


def test_development_sum_and_empty_world() -> None:
    spec = _spec(
        [_col("g", [7, 8]), _col("x", [3, 4])],
        "SELECT g, COUNT(*) AS n FROM dev GROUP BY g",
        "SELECT SUM(x) AS q FROM dev",
        rows=1,
    )
    _check(spec, "COUNTEREXAMPLE_FOUND", 2)


def test_development_all_null_negative() -> None:
    spec = _spec(
        [_col("g", [7]), _col("x", [None], nullable=True)],
        "SELECT g, COUNT(*) AS n FROM dev GROUP BY g",
        "SELECT SUM(x) AS q FROM dev",
        rows=1,
    )
    _check(spec, "BOUNDED_NO_COUNTEREXAMPLE", None)


def test_development_nullable_group_and_metric_guard() -> None:
    spec = _spec(
        [_col("g", [9, None], nullable=True), _col("x", [5, 6])],
        "SELECT g, COUNT(*) AS n FROM dev GROUP BY g",
        "SELECT SUM(x) AS q FROM dev WHERE g IS NULL",
        rows=1,
    )
    _check(spec, "COUNTEREXAMPLE_FOUND", 2)


def test_development_duplicate_bag_and_count_distinct() -> None:
    spec = _spec(
        [_col("g", [9]), _col("x", [4, 5])],
        "SELECT g, COUNT(DISTINCT x) AS d FROM dev GROUP BY g",
        "SELECT COUNT(*) AS q FROM dev",
    )
    _check(spec, "COUNTEREXAMPLE_FOUND", 3)


def test_development_nullable_unique() -> None:
    spec = _spec(
        [_col("g", [9]), _col("u", [4, None], nullable=True)],
        "SELECT g, COUNT(DISTINCT u) AS d FROM dev GROUP BY g",
        "SELECT COUNT(*) AS q FROM dev",
        unique=[["u"]],
    )
    _check(spec, "COUNTEREXAMPLE_FOUND", 3)


def test_development_primary_key_and_count_column() -> None:
    spec = _spec(
        [_col("g", [9, 10]), _col("x", [5, None], nullable=True)],
        "SELECT g, COUNT(*) AS n FROM dev GROUP BY g",
        "SELECT COUNT(x) AS q FROM dev",
        primary=["g"],
    )
    _check(spec, "COUNTEREXAMPLE_FOUND", 2)


@pytest.mark.parametrize("agg", ["MIN", "MAX"])
def test_development_extrema(agg: str) -> None:
    spec = _spec(
        [_col("g", [9]), _col("x", [-5, 5, None], nullable=True)],
        "SELECT g, COUNT(*) AS n FROM dev GROUP BY g",
        f"SELECT {agg}(x) AS q FROM dev",
        rows=1,
    )
    _check(spec, "COUNTEREXAMPLE_FOUND", 2)


def test_development_date_and_equality_filter() -> None:
    spec = _spec(
        [_col("g", ["2026-02-01"], typ="DATE"), _col("x", [5, 6])],
        "SELECT g, COUNT(*) AS n FROM dev WHERE x = 5 GROUP BY g",
        "SELECT COUNT(*) AS q FROM dev",
        rows=1,
    )
    _check(spec, "COUNTEREXAMPLE_FOUND", 1)


def test_canonical_bag_preserves_types_nulls_and_duplicates() -> None:
    left = ((None, 1), (None, 1), (date(2026, 2, 1), 2))
    reordered = ((date(2026, 2, 1), 2), (None, 1), (None, 1))
    assert oracle.canonical_bag(left) == oracle.canonical_bag(reordered)
    assert oracle.canonical_bag(left) != oracle.canonical_bag(((None, 1), (date(2026, 2, 1), 2)))
    assert oracle.canonical_bag(((None,),)) != oracle.canonical_bag(((0,),))


def test_objective_order_and_domain_rank() -> None:
    spec = _spec(
        [_col("g", [9]), _col("x", [5, None], nullable=True)],
        "SELECT g, COUNT(*) AS n FROM dev GROUP BY g",
        "SELECT COUNT(x) AS q FROM dev",
        rows=2,
    )
    engine = z3.Optimize()
    left = generic._world(engine, spec, "test_left")
    right = generic._world(engine, spec, "test_right")
    generic._objectives(engine, spec, left, right)
    objectives = engine.objectives()
    assert len(objectives) == 2 + 2 * spec.max_rows * len(spec.columns)
    assert "test_left" in str(objectives[1]) and "test_right" not in str(objectives[1])
    assert "test_left_0_0" in str(objectives[2])
    assert "test_left_0_1" in str(objectives[3])
    assert "test_right_0_0" in str(objectives[2 + spec.max_rows * len(spec.columns)])
    cell = left.slots[0].fields[1]
    rank = generic._domain_rank(spec, 1, cell)
    assert z3.simplify(z3.substitute(rank, (cell.null, z3.BoolVal(True)))).as_long() == 1
    assert (
        z3.simplify(
            z3.substitute(rank, (cell.null, z3.BoolVal(False)), (cell.value, z3.IntVal(5)))
        ).as_long()
        == 0
    )


def test_oracle_failure_is_never_bounded_negative(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = _spec(
        [_col("g", [9]), _col("x", [5])],
        "SELECT g, COUNT(*) AS n FROM dev GROUP BY g",
        "SELECT COUNT(*) AS q FROM dev",
        rows=1,
    )

    def broken(_: Any) -> list[Any]:
        raise ValueError("reference cap")

    monkeypatch.setattr(oracle, "all_worlds", broken)
    result = oracle.evaluate(spec)
    assert result.status == "INCONCLUSIVE"
    assert result.minimum_rows is None


def test_frozen_inventory_parses_without_search() -> None:
    inventory = runner.case_inventory()
    assert len(inventory) == 15
    assert [item["case_id"] for item in inventory] == list(runner.CASE_IDS)
    assert {item["case_id"]: item["sha256"] for item in inventory} == runner.FROZEN_CASE_SHA256


def _mocked_records() -> list[dict[str, Any]]:
    """Synthetic observations only; no frozen-case obligations are evaluated."""
    records = []
    for case_id in runner.CASE_IDS:
        for method in ("oracle", *runner.PRIMARY_METHODS):
            for index in range(1 if method == "oracle" else runner.REPEATS):
                records.append(
                    {
                        "case_id": case_id,
                        "case_sha256": runner.FROZEN_CASE_SHA256[case_id],
                        "method": method,
                        "trial_index": index,
                        "status": "INCONCLUSIVE",
                        "oracle_status": "INCONCLUSIVE",
                        "oracle_minimum_rows": None,
                        "status_agreement": None,
                        "minimum_agreement": None,
                        "outer_elapsed_seconds": 0.1,
                        "formulation_seconds": None,
                        "solver_check_seconds": None,
                    }
                )
    return records


def _write_mocked(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")


def test_harness_schedule_completeness_and_duplicates(tmp_path: Path) -> None:
    records = _mocked_records()
    assert len(records) == 315
    path = tmp_path / "synthetic.jsonl"
    _write_mocked(path, records)
    inventory = [
        {"case_id": name, "sha256": digest} for name, digest in runner.FROZEN_CASE_SHA256.items()
    ]
    result = runner.verify_recording(path, inventory)
    assert result["trial_count"] == 315
    assert result["recording_state"] == "RECORDING_COMPLETE"
    _write_mocked(path, records[:-1])
    with pytest.raises(ValueError, match="incomplete"):
        runner.verify_recording(path, inventory)
    assert not (tmp_path / "completion.json").exists()
    _write_mocked(path, records + [records[0]])
    with pytest.raises(ValueError, match="duplicate"):
        runner.verify_recording(path, inventory)


def test_harness_timeout_and_exception_are_recorded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "mock.json"

    def timeout(*args: Any, **kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired("mock", 20)

    monkeypatch.setattr(runner.subprocess, "run", timeout)
    timed = runner._worker(path, "generic_optimize", 20)
    assert timed["status"] == "HARD_TIMEOUT"
    assert timed["outer_elapsed_seconds"] >= 0

    def failed(*args: Any, **kwargs: Any) -> Any:
        raise OSError("synthetic private path is not recorded")

    monkeypatch.setattr(runner.subprocess, "run", failed)
    error = runner._worker(path, "generic_optimize", 20)
    assert error["status"] == "EXCEPTION" and error["error_type"] == "OSError"
    assert "private path" not in json.dumps(error)

    class BrokenProtocol:
        returncode = 0
        stdout = "not-json"
        stderr = "/Users/example/private"

    monkeypatch.setattr(runner.subprocess, "run", lambda *args, **kwargs: BrokenProtocol())
    malformed = runner._worker(path, "generic_optimize", 20)
    assert malformed["status"] == "EXCEPTION"
    assert malformed["error_type"] == "WORKER_PROTOCOL"
    assert "private" not in json.dumps(malformed)


def test_harness_status_accounting_and_privacy() -> None:
    raw = _mocked_records()[0] | {
        "status": "EXCEPTION",
        "error_type": "OSError",
        "stderr": "/Users/example/secret/token",
        "worlds": [[[None, 1]], [[None, 2]]],
    }
    clean = runner.sanitize_trial(raw)
    assert clean["status"] == "EXCEPTION"
    assert "stderr" not in clean
    assert "/Users" not in json.dumps(clean)
    assert runner._agreement("INCONCLUSIVE", "COUNTEREXAMPLE_FOUND", None, 2) == (None, None)
    assert runner._agreement("BOUNDED_NO_COUNTEREXAMPLE", "COUNTEREXAMPLE_FOUND", None, 2) == (
        False,
        None,
    )
    assert runner._agreement("COUNTEREXAMPLE_FOUND", "COUNTEREXAMPLE_FOUND", 3, 2) == (True, False)
    with pytest.raises(ValueError, match="unsafe witness"):
        runner.sanitize_trial(raw | {"worlds": [[["/Users/example/private"]], []]})
    with pytest.raises(ValueError, match="phase timings"):
        runner.sanitize_trial(raw | {"formulation_seconds": 0.001})


def test_solver_decision_mode_is_secondary_on_development_case() -> None:
    spec = _spec(
        [_col("g", [1]), _col("x", [1, 2])],
        "SELECT g, COUNT(*) AS n FROM dev GROUP BY g",
        "SELECT SUM(x) AS q FROM dev",
        rows=1,
    )
    view = parse_query(spec.views[0], spec, metric=False)
    metric = parse_query(spec.metric, spec, metric=True)
    candidate = generic.search(spec, view, metric, optimize=False)
    assert candidate.status == "CANDIDATE"
    assert candidate.worlds is not None and validate(spec, *candidate.worlds).valid
