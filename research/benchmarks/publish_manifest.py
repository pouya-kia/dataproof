"""Publish a verified, portable record of a real clean Phase 1 harness run."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publish(raw_path: Path, repo: Path, golden: Path) -> dict[str, Any]:
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    if raw.get("git_dirty") is not False or not re.fullmatch(
        r"[0-9a-f]{40}", raw.get("git_sha") or ""
    ):
        raise ValueError("publication requires a clean, full-SHA source run")
    if raw.get("status") != "COUNTEREXAMPLE_FOUND" or raw.get("exit_code") != 0:
        raise ValueError("this published witness record requires a successful run")
    command = raw["command"]
    if len(command) < 5 or command[1:4] != ["-m", "dataproof", "check"]:
        raise ValueError("unexpected run command")
    spec = (repo / command[4]).resolve()
    spec_relative = spec.relative_to(repo.resolve()).as_posix()
    if _sha(spec) != raw["input_sha256"] or spec.stat().st_size != raw["input_size_bytes"]:
        raise ValueError("input no longer matches recorded run")
    artifact = raw["artifact_paths"]
    witness_path = Path(artifact["witness"])
    replay_path = Path(artifact["replay_sql"])
    result_path = Path(artifact["result"])
    witness = json.loads(witness_path.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    golden_data = json.loads(golden.read_text(encoding="utf-8"))
    golden_replay = golden.with_name("replay.sql")
    if (
        witness["worlds_sha256"] != golden_data["worlds_sha256"]
        or _sha(replay_path) != _sha(golden_replay)
        or result["status"] != raw["status"]
        or result["metric_values"] != golden_data["metric_values"]
    ):
        raise ValueError("run artifact does not match versioned independent evidence")
    golden_relative = golden.resolve().relative_to(repo.resolve()).as_posix()
    replay_relative = golden_replay.resolve().relative_to(repo.resolve()).as_posix()
    stdout = Path(raw["stdout_path"])
    stderr = Path(raw["stderr_path"])
    return {
        "schema_version": 1,
        "record_kind": "sanitized_clean_run",
        "timestamp_utc": raw["timestamp_utc"],
        "git_sha": raw["git_sha"],
        "git_dirty": False,
        "input_path": spec_relative,
        "input_sha256": raw["input_sha256"],
        "input_size_bytes": raw["input_size_bytes"],
        "configuration": {
            key: raw[key] for key in ("seed", "max_rows", "timeout_ms", "max_memory_mb")
        },
        "versions": raw["versions"],
        "environment": raw["environment"],
        "outcome": {
            "status": raw["status"],
            "exit_code": raw["exit_code"],
            "elapsed_seconds": raw["elapsed_seconds"],
            "metric_values": result["metric_values"],
            "worlds_sha256": witness["worlds_sha256"],
        },
        "published_evidence": {"witness": golden_relative, "replay_sql": replay_relative},
        "raw_log_hashes": {
            "manifest_sha256": _sha(raw_path),
            "stdout_sha256": _sha(stdout),
            "stderr_sha256": _sha(stderr),
            "stdout_path_dependent": True,
            "stderr_empty": stderr.stat().st_size == 0,
        },
        "reproduction": [
            "python3.11 -m venv .venv",
            ".venv/bin/python -m pip install '.[dev]'",
            "PYTHONPATH=src .venv/bin/python research/benchmarks/run_phase1.py "
            f"{spec_relative} --run-dir research/runs/local/new-run",
            "Compare status, metrics, worlds_sha256 and published replay; "
            "elapsed time is not deterministic.",
        ],
        "sanitization": (
            "Absolute executable, workspace, run-artifact and stdout/stderr paths are omitted; "
            "hashes preserve provenance. No values or timings were changed."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_manifest", type=Path)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--golden-witness", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    record = publish(args.raw_manifest, args.repo, args.golden_witness)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"published clean run {record['git_sha']} at {args.output}")


if __name__ == "__main__":
    main()
