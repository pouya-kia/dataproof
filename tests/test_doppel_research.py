"""Research harness records real exact-obligation outcomes without publishing dirty runs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dataproof.doppel_model import load_doppel_spec
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
