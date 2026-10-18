"""The public Phase 5 record must describe real pinned and reproducible inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "research/runs/published/phase5-6c1fd5e.json"


def test_published_round_trip_is_scoped_and_input_pinned() -> None:
    data = json.loads(RECORD.read_text())
    assert data["record_kind"] == "proof2test_synthetic_round_trip"
    assert data["git_sha"] == "6c1fd5eb0c0fe2405755c702feaaa6c7f7557e73"
    assert data["git_dirty_before_run"] is False
    inputs = {
        "spec_sha256": ROOT / "examples/doppelganger/nonnegative_amount.json",
        "target_contract_sha256": ROOT / "examples/proof2test/clamp_amount.contract.json",
        "defective_sql_sha256": ROOT / "examples/proof2test/defective.sql",
        "corrected_sql_sha256": ROOT / "examples/proof2test/corrected.sql",
    }
    for key, path in inputs.items():
        assert data["inputs"][key] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert data["witness"]["serialized_replay_valid"] is True
    assert data["export"]["status"] == "EXPORTED"
    assert data["export"]["deterministic"] is True
    assert data["generated_pytest"]["defective"]["exit_code"] == 1
    assert data["generated_pytest"]["defective"]["failure_reason"] == ("target output bag differs")
    assert data["generated_pytest"]["corrected"]["exit_code"] == 0
    assert data["generated_pytest"]["corrected"]["passed_tests"] == 1
    assert data["generated_pytest"]["tampered_fixture"]["exit_code"] == 1
    assert data["dbt"]["status"] == "PASS"
    assert data["dbt"]["dbt_core"] == "1.10.23"
    assert data["dbt"]["dbt_duckdb"] == "1.10.0"
    assert "/Users/" not in json.dumps(data)
    assert "research/private" not in json.dumps(data)
