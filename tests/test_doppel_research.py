"""Research harness records real exact-obligation outcomes without publishing dirty runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from dataproof.doppel_model import load_doppel_spec
from dataproof.doppel_replay import validate_serialized
from research.benchmarks.run_doppelganger import random_baseline, run


def test_random_baseline_is_seeded_and_bounded() -> None:
    path = Path("examples/doppelganger/nonnegative_amount.json")
    a = random_baseline(path, 7, 20)
    b = random_baseline(path, 7, 20)
    assert {key: value for key, value in a.items() if key != "elapsed_seconds"} == {
        key: value for key, value in b.items() if key != "elapsed_seconds"
    }
    assert 1 <= a["draws"] <= 20
    assert a["legal_draws"] <= a["draws"]


def test_local_run_records_code_and_verified_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PYTHONPATH", "src")
    spec_path = Path("examples/doppelganger/nonnegative_amount.json")
    assert load_doppel_spec(spec_path).table.max_rows == 2
    record = run(spec_path, tmp_path / "run", 1, 5)
    assert record["cli"]["status"] == "BLIND_SPOT_FOUND"
    assert record["runs"][0]["solver_status"] == "BLIND_SPOT_FOUND"
    assert record["runs"][0]["reference_status"] == "BLIND_SPOT_FOUND"
    assert record["runs"][0]["row_minimal_verified"] is True
    assert (
        json.loads((tmp_path / "run" / "manifest.json").read_text())["git_sha"] == record["git_sha"]
    )


def test_published_record_is_scoped_and_input_pinned() -> None:
    record = json.loads(Path("research/runs/published/phase4-e584070.json").read_text())
    source = Path(record["input_path"])
    assert record["git_dirty_before_run"] is False
    assert record["input_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert len(record["runs"]) == record["configuration"]["repeats"] == 5
    assert all(run["solver_status"] == run["reference_status"] for run in record["runs"])
    assert all(run["row_minimal_verified"] for run in record["runs"])
    assert all(run["random"]["found"] for run in record["runs"])
    assert "/Users/" not in json.dumps(record)


def test_versioned_golden_witness_replays_the_recorded_rows() -> None:
    evidence = Path("examples/doppelganger/evidence/witness.json")
    record = json.loads(Path("research/runs/published/phase4-e584070.json").read_text())
    witness = json.loads(evidence.read_text())
    assert validate_serialized(evidence).valid
    assert witness["rows"] == [[-1]]
    assert witness["rows_sha256"] == record["cli"]["rows_sha256"]
