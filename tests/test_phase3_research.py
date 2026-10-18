from __future__ import annotations

import hashlib
import json
import re

import pytest
from conftest import ROOT


@pytest.mark.parametrize(
    "name",
    ["phase3-filter-fb94148", "phase3-extrema-8076042"],
)
def test_phase3_published_run_is_pinned_and_sanitized(name: str) -> None:
    path = ROOT / f"research/runs/published/{name}.json"
    raw_text = path.read_text(encoding="utf-8")
    record = json.loads(raw_text)
    assert record["record_kind"] == "sanitized_clean_run"
    assert record["git_dirty"] is False
    assert re.fullmatch(r"[0-9a-f]{40}", record["git_sha"])
    assert record["git_sha"].startswith(name.rsplit("-", 1)[-1])
    spec = ROOT / record["input_path"]
    assert hashlib.sha256(spec.read_bytes()).hexdigest() == record["input_sha256"]
    assert spec.stat().st_size == record["input_size_bytes"]
    assert record["outcome"]["status"] == "COUNTEREXAMPLE_FOUND"
    assert record["outcome"]["exit_code"] == 0
    assert len(record["outcome"]["metric_values"]) == 2
    assert record["outcome"]["metric_values"][0] != record["outcome"]["metric_values"][1]
    assert re.fullmatch(r"[0-9a-f]{64}", record["outcome"]["worlds_sha256"])
    for digest in record["raw_hashes"].values():
        assert re.fullmatch(r"[0-9a-f]{64}", digest)
    assert "/Users/" not in raw_text
    assert "/var/folders/" not in raw_text


@pytest.mark.parametrize(
    "name",
    ["phase3-filter-fb94148", "phase3-extrema-8076042"],
)
def test_phase3_record_matches_local_raw_when_available(name: str) -> None:
    raw_path = ROOT / "research/runs/local" / name / "manifest.json"
    if not raw_path.exists():
        pytest.skip("ignored local raw run is not available in this checkout")
    record = json.loads((ROOT / f"research/runs/published/{name}.json").read_text())
    raw = json.loads(raw_path.read_text())
    assert (
        hashlib.sha256(raw_path.read_bytes()).hexdigest() == record["raw_hashes"]["manifest_sha256"]
    )
    assert raw["git_sha"] == record["git_sha"]
    assert raw["git_dirty"] is False
    assert raw["timestamp_utc"] == record["timestamp_utc"]
    assert raw["elapsed_seconds"] == record["outcome"]["elapsed_seconds"]
    for kind, name_in_record in (
        ("witness", "witness_sha256"),
        ("replay_sql", "replay_sql_sha256"),
    ):
        artifact = ROOT / raw["artifact_paths"][kind]
        assert (
            hashlib.sha256(artifact.read_bytes()).hexdigest()
            == record["raw_hashes"][name_in_record]
        )
