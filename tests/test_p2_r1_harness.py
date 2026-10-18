"""P2-R1 implementation tests: parse frozen inputs, never search them."""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from dataproof.doppel_model import load_doppel_spec
from research.benchmarks import p2_r1, p2_r1_worker, run_doppelganger


def test_all_frozen_cases_parse_without_search(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("outcome-producing function called during parser validation")

    monkeypatch.setattr(p2_r1, "_worker", forbidden)
    inventory = p2_r1.case_inventory()
    assert tuple(item["case_id"] for item in inventory) == p2_r1.CASE_IDS
    assert {item["case_id"]: item["sha256"] for item in inventory} == p2_r1.FROZEN_CASE_SHA256
    assert [item["world_upper_bound"] for item in inventory] == [
        10,
        455,
        84,
        10,
        4,
        10,
        10,
        15,
        10,
        6,
    ]
    assert all(item["world_upper_bound"] < 10000 for item in inventory)
    for case_id in p2_r1.CASE_IDS:
        spec = load_doppel_spec(p2_r1.CASE_DIR / f"{case_id}.json")
        assert spec.invariant.rationale
        assert 1 <= len(spec.tests) <= 4
        assert spec.table.max_rows <= 3


def test_case_inventory_rejects_extra_or_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="case file set differs"):
        p2_r1.case_inventory(tmp_path)
    (tmp_path / "surprise.json").write_text("{}")
    with pytest.raises(ValueError, match="case file set differs"):
        p2_r1.case_inventory(tmp_path)


def test_frozen_hash_gate_rejects_content_change(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(p2_r1, "_sha", lambda _path: "0" * 64)
    with pytest.raises(ValueError, match="reviewed frozen input"):
        p2_r1.case_inventory()


def _development_spec(tmp_path: Path) -> Path:
    path = tmp_path / "development_only.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "table": {
                    "name": "toy",
                    "columns": [{"name": "x", "type": "INTEGER", "domain": [0]}],
                },
                "max_rows": 1,
                "tests": [
                    {"id": "t", "sql": "SELECT COUNT(*) AS n FROM toy", "op": ">=", "value": 0}
                ],
                "invariant": {
                    "id": "i",
                    "sql": "SELECT COUNT(*) AS n FROM toy",
                    "op": "=",
                    "value": 0,
                    "rationale": "Development-only harness fixture, not a research case.",
                },
            }
        )
    )
    return path


def test_random_instrumentation_preserves_seed_and_checkpoints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _development_spec(tmp_path)
    monkeypatch.setattr(
        run_doppelganger,
        "validate",
        lambda _spec, rows: SimpleNamespace(
            valid=len(rows) == 1, tests=(SimpleNamespace(truth=True),)
        ),
    )
    first = run_doppelganger.random_baseline(path, 7, 200, checkpoints=(20, 100, 200))
    second = run_doppelganger.random_baseline(path, 7, 200, checkpoints=(20, 100, 200))
    assert {k: v for k, v in first.items() if k != "elapsed_seconds"} == {
        k: v for k, v in second.items() if k != "elapsed_seconds"
    }
    assert first["found"] is True
    assert first["witness_size"] == 1
    assert first["first_hit_draw"] == first["draws"]
    assert set(first["checkpoints"]) == {"20", "100", "200"}
    assert first["legal_draws"] <= first["draws"] <= 200


def test_random_deadline_and_invalid_budgets(tmp_path: Path) -> None:
    path = _development_spec(tmp_path)
    with pytest.raises(ValueError, match="budget"):
        run_doppelganger.random_baseline(path, 0, 0)
    with pytest.raises(ValueError, match="checkpoint"):
        run_doppelganger.random_baseline(path, 0, 10, checkpoints=(20,))
    with pytest.raises(ValueError, match="deadline"):
        run_doppelganger.random_baseline(path, 0, 10, deadline_seconds=0)
    result = run_doppelganger.random_baseline(
        path, 0, 200, checkpoints=(20, 100, 200), deadline_seconds=1e-12
    )
    assert result["deadline_reached"] is True
    assert result["draws"] == 0
    assert all(point == {"not_reached": True} for point in result["checkpoints"].values())


def test_worker_z3_false_candidate_is_not_confirmed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _development_spec(tmp_path)
    monkeypatch.setattr(
        p2_r1_worker,
        "search",
        lambda _spec: SimpleNamespace(
            status="CANDIDATE", rows=((0,),), reason_code=None, row_minimal_verified=True
        ),
    )
    monkeypatch.setattr(p2_r1_worker, "validate", lambda *_: SimpleNamespace(valid=False))
    record = p2_r1_worker.trial(path, "z3")
    assert record["status"] == "FALSE_CLAIM"
    assert record["confirmed"] is False
    assert record["duckdb_evaluations"] == 1


def test_worker_reference_and_random_accounting_are_mocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _development_spec(tmp_path)
    monkeypatch.setattr(
        p2_r1_worker,
        "reference_search",
        lambda _spec: SimpleNamespace(
            status="INCONSISTENT_TESTS", worlds_checked=2, test_passing_worlds=0, rows=None
        ),
    )
    reference = p2_r1_worker.trial(path, "reference")
    assert reference["status"] == "INCONSISTENT_TESTS"
    assert reference["duckdb_evaluations"] == 2

    def fake_random(_path: Path, seed: int, attempts: int, **kwargs: Any) -> dict[str, Any]:
        assert seed == 3 and attempts == 200
        assert kwargs["checkpoints"] == (20, 100, 200)
        return {
            "found": False,
            "deadline_reached": False,
            "draws": 200,
            "legal_draws": 70,
            "test_passing_draws": 10,
            "first_hit_draw": None,
            "witness_size": None,
            "checkpoints": {str(n): {"not_reached": True} for n in (20, 100, 200)},
        }

    monkeypatch.setattr(p2_r1_worker, "random_baseline", fake_random)
    random = p2_r1_worker.trial(path, "random", seed=3)
    assert random["status"] == "NO_WITNESS_WITHIN_BUDGET"
    assert random["duckdb_evaluations"] == random["legal_draws"] == 70
    assert p2_r1._agreement("random", random["status"], reference["status"]) is None


def test_parent_budget_and_worker_protocol(monkeypatch: pytest.MonkeyPatch) -> None:
    def hard_timeout(*args: Any, **kwargs: Any) -> None:
        assert kwargs["timeout"] == p2_r1.SEARCH_WALL_SECONDS
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr(p2_r1.subprocess, "run", hard_timeout)
    assert (
        p2_r1._worker(Path("development_only.json"), "random", 0, 12.0)["status"] == "HARD_TIMEOUT"
    )
    monkeypatch.setattr(
        p2_r1.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="not json"),
    )
    assert p2_r1._worker(Path("development_only.json"), "z3", None, 12.0) == {
        "status": "EXCEPTION",
        "error_type": "WORKER_PROTOCOL",
        "outer_elapsed_seconds": pytest.approx(0, abs=1),
    }
    monkeypatch.setattr(
        p2_r1.subprocess, "run", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError())
    )
    assert p2_r1._worker(Path("development_only.json"), "z3", None, 12.0)["error_type"] == "OSError"


def test_sanitizer_excludes_paths_logs_and_rejects_nested_leaks() -> None:
    raw = {
        "status": "BLIND_SPOT_FOUND",
        "case_id": "E1",
        "case_sha256": p2_r1.FROZEN_CASE_SHA256["E1"],
        "method": "random",
        "trial_index": 0,
        "seed": 0,
        "oracle_status": "BLIND_SPOT_FOUND",
        "oracle_agreement": True,
        "confirmed": True,
        "private_path": "/Users/someone/secret",
        "stdout": "private SQL",
        "checkpoints": {str(n): {"not_reached": True} for n in (20, 100, 200)},
    }
    clean = p2_r1.sanitize_trial(raw)
    assert "private_path" not in clean and "stdout" not in clean
    assert "/Users/" not in json.dumps(clean)
    raw["reason_code"] = "/Users/someone/secret"
    with pytest.raises(ValueError, match="unsafe reason_code"):
        p2_r1.sanitize_trial(raw)
    raw.pop("reason_code")
    raw["checkpoints"]["20"] = {"path": "/Users/someone/secret"}
    with pytest.raises(ValueError, match="unsafe checkpoint"):
        p2_r1.sanitize_trial(raw)


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("case_id", "/private/path"),
        ("case_sha256", "/private/path"),
        ("method", {"path": "/private/path"}),
        ("trial_index", True),
        ("seed", 50),
        ("oracle_status", ["BLIND_SPOT_FOUND"]),
        ("oracle_agreement", "True"),
        ("elapsed_seconds", math.nan),
        ("elapsed_seconds", math.inf),
        ("outer_elapsed_seconds", -1),
        ("peak_rss_raw", "/private/path"),
        ("peak_rss_unit", "/private/path"),
        ("draws", 201),
        ("legal_draws", -1),
        ("test_passing_draws", {"private": "note"}),
        ("duckdb_evaluations", "1"),
        ("first_hit_draw", 0),
        ("witness_rows", 4),
        ("worlds_checked", 10001),
        ("test_passing_worlds", -1),
        ("confirmed", "yes"),
        ("row_minimal_verified", [True]),
        ("reason_code", "/private/path"),
        ("error_type", "Private error: /private/path"),
        ("checkpoints", {"20": {"path": "/private/path"}}),
    ],
)
def test_sanitizer_rejects_unsafe_retained_fields(field: str, bad: object) -> None:
    record: dict[str, Any] = {
        "case_id": "E1",
        "case_sha256": p2_r1.FROZEN_CASE_SHA256["E1"],
        "method": "random",
        "trial_index": 0,
        "seed": 0,
        "status": "NO_WITNESS_WITHIN_BUDGET",
        "oracle_status": "BLIND_SPOT_FOUND",
        "oracle_agreement": None,
    }
    record[field] = bad
    with pytest.raises(ValueError):
        p2_r1.sanitize_trial(record)


@pytest.mark.parametrize(
    ("status", "oracle", "expected"),
    [
        ("BLIND_SPOT_FOUND", "BLIND_SPOT_FOUND", True),
        ("BLIND_SPOT_FOUND", "BOUNDED_NO_BLIND_SPOT", False),
        ("BLIND_SPOT_FOUND", "INCONSISTENT_TESTS", False),
        ("NO_WITNESS_WITHIN_BUDGET", "BLIND_SPOT_FOUND", None),
        ("NO_WITNESS_WITHIN_BUDGET", "BOUNDED_NO_BLIND_SPOT", None),
        ("BLIND_SPOT_FOUND", "HARD_TIMEOUT", None),
    ],
)
def test_random_oracle_agreement(status: str, oracle: str, expected: bool | None) -> None:
    assert p2_r1._agreement("random", status, oracle) is expected


def test_execution_rejects_dirty_or_wrong_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(p2_r1, "case_inventory", lambda _dir: [])
    monkeypatch.setattr(p2_r1, "_git", lambda *_args: "dirty")
    with pytest.raises(RuntimeError, match="clean committed"):
        p2_r1.run_study(tmp_path / "output")
    monkeypatch.setattr(p2_r1, "_git", lambda *_args: "")
    forbidden = p2_r1.ROOT / "artifacts" / "p2-r1-test-must-not-exist"
    with pytest.raises(ValueError, match="under research/runs/local"):
        p2_r1.run_study(forbidden)
    assert not forbidden.exists()


def test_full_schedule_and_disagreements_use_only_mocked_workers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inventory = [
        {"case_id": name, "sha256": p2_r1.FROZEN_CASE_SHA256[name], "world_upper_bound": 10}
        for name in p2_r1.CASE_IDS
    ]
    monkeypatch.setattr(p2_r1, "case_inventory", lambda _dir=p2_r1.CASE_DIR: inventory)
    monkeypatch.setattr(
        p2_r1, "_git", lambda *args: "" if args == ("status", "--porcelain") else "a" * 40
    )
    calls: list[tuple[str, str, int | None, float]] = []

    def mocked_worker(path: Path, method: str, seed: int | None, wall: float) -> dict[str, Any]:
        calls.append((path.stem, method, seed, wall))
        if method == "reference":
            return {
                "status": "INCONSISTENT_TESTS"
                if path.stem == "I1"
                else "BOUNDED_NO_BLIND_SPOT"
                if path.stem == "M1"
                else "BLIND_SPOT_FOUND",
                "worlds_checked": 2,
                "test_passing_worlds": 0 if path.stem == "I1" else 1,
            }
        if method == "z3":
            return {"status": "BLIND_SPOT_FOUND", "confirmed": True}
        assert seed is not None
        return {
            "status": "NO_WITNESS_WITHIN_BUDGET",
            "draws": 200,
            "legal_draws": 80,
            "test_passing_draws": 10,
            "duckdb_evaluations": 80,
            "checkpoints": {str(n): {"not_reached": True} for n in (20, 100, 200)},
        }

    monkeypatch.setattr(p2_r1, "_worker", mocked_worker)
    monkeypatch.setattr(p2_r1, "LOCAL_RUNS", tmp_path)
    out = tmp_path / "mocked-study"
    p2_r1.run_study(out)
    records = [json.loads(line) for line in (out / "trials.jsonl").read_text().splitlines()]
    assert len(records) == 10 * (1 + 50 + 50)
    assert {record["case_id"] for record in records} == set(p2_r1.CASE_IDS)
    assert {record["status"] for record in records} == {
        "BLIND_SPOT_FOUND",
        "BOUNDED_NO_BLIND_SPOT",
        "INCONSISTENT_TESTS",
        "NO_WITNESS_WITHIN_BUDGET",
    }
    assert {record["seed"] for record in records if record["method"] == "random"} == set(range(50))
    assert sum(record["oracle_agreement"] is False for record in records) == 100
    assert sum(record["oracle_agreement"] is True for record in records) == 410
    assert all(wall == (60.0 if method == "reference" else 12.0) for _, method, _, wall in calls)
    assert [method for _, method, _, _ in calls[:5]] == [
        "reference",
        "z3",
        "random",
        "random",
        "z3",
    ]
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["recording_state"] == "INCOMPLETE"
    completion = json.loads((out / "completion.json").read_text())
    assert completion["recording_state"] == "RECORDING_COMPLETE"
    assert completion["trial_count"] == 1010
    assert completion["case_inventory"] == inventory
    assert manifest["random_draw_cap"] == 200
    assert manifest["random_checkpoints"] == [20, 100, 200]
    assert manifest["z3_solver_timeout_ms"] == 10000
    assert manifest["z3_solver_memory_mb"] == 256
    assert manifest["random_memory_cap"] is None


def _mock_inventory() -> list[dict[str, Any]]:
    return [
        {"case_id": name, "sha256": p2_r1.FROZEN_CASE_SHA256[name], "world_upper_bound": 10}
        for name in p2_r1.CASE_IDS
    ]


def _mock_records() -> list[dict[str, Any]]:
    records = []
    for case_id in p2_r1.CASE_IDS:
        for method in ("reference", "z3", "random"):
            for index in range(1) if method == "reference" else range(50):
                records.append(
                    {
                        "case_id": case_id,
                        "case_sha256": p2_r1.FROZEN_CASE_SHA256[case_id],
                        "method": method,
                        "trial_index": index,
                        "seed": index if method == "random" else None,
                        "status": "BLIND_SPOT_FOUND"
                        if method != "random"
                        else "NO_WITNESS_WITHIN_BUDGET",
                        "oracle_status": "BLIND_SPOT_FOUND",
                        "oracle_agreement": True if method != "random" else None,
                    }
                )
    return records


@pytest.mark.parametrize("damage", ("missing", "duplicate", "wrong_hash", "wrong_seed"))
def test_recording_gate_rejects_damaged_mock_stream(tmp_path: Path, damage: str) -> None:
    records = _mock_records()
    if damage == "missing":
        records.pop()
    elif damage == "duplicate":
        records[-1] = records[-2].copy()
    elif damage == "wrong_hash":
        records[-1]["case_sha256"] = "0" * 64
    else:
        records[-1]["seed"] = 0
    path = tmp_path / "mocked-trials.jsonl"
    path.write_text("".join(json.dumps(record) + "\n" for record in records))
    with pytest.raises(ValueError):
        p2_r1.verify_recording(path, _mock_inventory())
    assert not (tmp_path / "completion.json").exists()


def test_recording_gate_accepts_complete_mock_stream(tmp_path: Path) -> None:
    records = _mock_records()
    records[1]["status"] = "EXCEPTION"
    records[1]["error_type"] = "WORKER_EXIT"
    records[1]["oracle_agreement"] = None
    records[2]["status"] = "HARD_TIMEOUT"
    records[2]["oracle_agreement"] = None
    path = tmp_path / "mocked-trials.jsonl"
    path.write_text("".join(json.dumps(record) + "\n" for record in records))
    result = p2_r1.verify_recording(path, _mock_inventory())
    assert result["recording_state"] == "RECORDING_COMPLETE"
    assert result["trial_count"] == 1010
    assert len(result["trials_sha256"]) == 64


def test_mocked_early_interruption_stays_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inventory = _mock_inventory()
    monkeypatch.setattr(p2_r1, "case_inventory", lambda _dir=p2_r1.CASE_DIR: inventory)
    monkeypatch.setattr(
        p2_r1, "_git", lambda *args: "" if args == ("status", "--porcelain") else "a" * 40
    )
    monkeypatch.setattr(p2_r1, "LOCAL_RUNS", tmp_path)
    calls = 0

    def interrupted_worker(*_args: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise KeyboardInterrupt("mocked interruption")
        return {"status": "HARD_TIMEOUT"}

    monkeypatch.setattr(p2_r1, "_worker", interrupted_worker)
    out = tmp_path / "interrupted-mock"
    with pytest.raises(KeyboardInterrupt, match="mocked interruption"):
        p2_r1.run_study(out)
    assert json.loads((out / "manifest.json").read_text())["recording_state"] == "INCOMPLETE"
    assert len((out / "trials.jsonl").read_text().splitlines()) == 2
    assert not (out / "completion.json").exists()
    with pytest.raises(FileExistsError):
        p2_r1.run_study(out)
