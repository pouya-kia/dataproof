"""Publication refuses dirty or unverified runs and removes local paths."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import ROOT


def test_publish_only_verified_sanitized_run(tmp_path: Path) -> None:
    run_dir = tmp_path / "raw"
    process = subprocess.run(
        [
            sys.executable,
            str(ROOT / "research/benchmarks/run_phase1.py"),
            str(ROOT / "examples/no_undo/daily_distinct.json"),
            "--run-dir",
            str(run_dir),
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    raw_path = run_dir / "manifest.json"
    golden = ROOT / "examples/no_undo/evidence/witness.json"
    # Force a dirty *unit fixture* so this regression is independent of whether
    # the checkout running pytest is clean. This is never published as a run.
    raw = json.loads(raw_path.read_text())
    raw["git_dirty"] = True
    raw_path.write_text(json.dumps(raw), encoding="utf-8")
    output = tmp_path / "published.json"
    publish_command = [
        sys.executable,
        str(ROOT / "research/benchmarks/publish_manifest.py"),
        str(raw_path),
        "--repo",
        str(ROOT),
        "--golden-witness",
        str(golden),
        "--output",
        str(output),
    ]
    rejected = subprocess.run(publish_command, cwd=ROOT, capture_output=True, text=True)
    assert rejected.returncode != 0
    assert "clean" in rejected.stderr

    # Synthetic unit fixture: never published as an experiment.
    raw["git_dirty"] = False
    raw["git_sha"] = "a" * 40
    raw_path.write_text(json.dumps(raw), encoding="utf-8")
    accepted = subprocess.run(publish_command, cwd=ROOT, capture_output=True, text=True)
    assert accepted.returncode == 0, accepted.stderr
    record = json.loads(output.read_text())
    serialized = json.dumps(record)
    assert record["git_sha"] == "a" * 40
    assert record["outcome"]["status"] == "COUNTEREXAMPLE_FOUND"
    assert record["outcome"]["metric_values"] == [1, 2]
    assert record["published_evidence"]["witness"] == "examples/no_undo/evidence/witness.json"
    assert str(tmp_path) not in serialized
    assert str(ROOT) not in serialized

    raw["input_sha256"] = "0" * 64
    raw_path.write_text(json.dumps(raw), encoding="utf-8")
    rejected = subprocess.run(publish_command, cwd=ROOT, capture_output=True, text=True)
    assert rejected.returncode != 0
    assert "input" in rejected.stderr


def test_paired_tiny_reference_benchmark_records_all_repeats(tmp_path: Path) -> None:
    output = tmp_path / "paired.json"
    run = subprocess.run(
        [
            sys.executable,
            str(ROOT / "research/benchmarks/compare_tiny_reference.py"),
            str(ROOT / "examples/no_undo/daily_distinct.json"),
            "--repeats",
            "3",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    record = json.loads(output.read_text())
    assert record["summary"]["repeats"] == 3
    assert record["summary"]["mismatch_count"] == 0
    assert len(record["samples"]) == 3
    assert all(sample["duckdb_validated"] for sample in record["samples"])
    assert all(sample["reference_worlds_checked"] == 15 for sample in record["samples"])


def test_published_phase2_records_match_versioned_evidence() -> None:
    published = ROOT / "research/runs/published"
    manifest = json.loads((published / "phase2-35b2001.json").read_text())
    paired = json.loads((published / "phase2-35b2001-paired.json").read_text())
    witness = json.loads((ROOT / manifest["published_evidence"]["witness"]).read_text())
    replay_sql = ROOT / manifest["published_evidence"]["replay_sql"]
    assert replay_sql.is_file()
    assert manifest["git_dirty"] is False
    assert paired["git_dirty"] is False
    assert manifest["git_sha"] == paired["git_sha"]
    assert manifest["outcome"]["worlds_sha256"] == witness["worlds_sha256"]
    assert manifest["outcome"]["metric_values"] == witness["metric_values"]
    assert paired["summary"]["repeats"] == len(paired["samples"]) == 5
    assert paired["summary"]["mismatch_count"] == 0
    assert str(ROOT) not in json.dumps(manifest)
