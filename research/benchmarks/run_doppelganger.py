"""Local, exact-obligation Z3/reference/random comparison; raw output stays ignored."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import resource
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from dataproof.doppel_model import load_doppel_spec
from dataproof.doppel_reference import reference_search
from dataproof.doppel_replay import validate, validate_serialized
from dataproof.doppel_solver import search
from dataproof.models import Row, legal_world
from dataproof.report import versions


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def random_baseline(
    spec_path: Path,
    seed: int,
    attempts: int,
    *,
    checkpoints: tuple[int, ...] = (),
    deadline_seconds: float | None = None,
) -> dict[str, object]:
    """Preserve the original sampler; optional P2-R1 controls only observe/stop it."""
    if attempts < 1 or any(cap < 1 or cap > attempts for cap in checkpoints):
        raise ValueError("invalid random draw budget or checkpoint")
    if deadline_seconds is not None and deadline_seconds <= 0:
        raise ValueError("random deadline must be positive")
    spec = load_doppel_spec(spec_path)
    rng = random.Random(seed)
    legal = 0
    passing = 0
    found = False
    draws = 0
    witness_size: int | None = None
    snapshots: dict[str, dict[str, object]] = {}
    deadline_reached = False
    start = perf_counter()
    for _ in range(attempts):
        if deadline_seconds is not None and perf_counter() - start >= deadline_seconds:
            deadline_reached = True
            break
        draws += 1
        rows: tuple[Row, ...] = tuple(
            tuple(rng.choice(column.domain) for column in spec.table.columns)
            for _ in range(rng.randrange(spec.table.max_rows + 1))
        )
        if legal_world(spec.table, rows):
            legal += 1
            checked = validate(spec, rows)
            if all(test.truth is True for test in checked.tests):
                passing += 1
            if checked.valid:
                found = True
                witness_size = len(rows)
        if draws in checkpoints:
            snapshots[str(draws)] = {
                "draws": draws,
                "legal_draws": legal,
                "test_passing_draws": passing,
                "found": found,
            }
        if found:
            break
    for cap in checkpoints:
        key = str(cap)
        if key not in snapshots:
            snapshots[key] = (
                {
                    "draws": draws,
                    "legal_draws": legal,
                    "test_passing_draws": passing,
                    "found": True,
                }
                if found and draws < cap
                else {"not_reached": True}
            )
    return {
        "seed": seed,
        "attempt_cap": attempts,
        "draws": draws,
        "legal_draws": legal,
        "test_passing_draws": passing,
        "found": found,
        "first_hit_draw": draws if found else None,
        "witness_size": witness_size,
        "checkpoints": snapshots,
        "deadline_reached": deadline_reached,
        "elapsed_seconds": perf_counter() - start,
    }


def run(spec_path: Path, directory: Path, repeats: int, attempts: int) -> dict[str, object]:
    if not 1 <= repeats <= 20 or not 1 <= attempts <= 10000:
        raise ValueError("repeats must be 1..20 and attempts 1..10000")
    spec = load_doppel_spec(spec_path)
    start_usage = resource.getrusage(resource.RUSAGE_SELF)
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
    results = []
    for index in range(repeats):
        start = perf_counter()
        solver = search(spec)
        solver_seconds = perf_counter() - start
        start = perf_counter()
        reference = reference_search(spec)
        reference_seconds = perf_counter() - start
        expected = "BLIND_SPOT_FOUND" if solver.status == "CANDIDATE" else solver.status
        if expected != reference.status or (
            solver.rows is not None and not validate(spec, solver.rows).valid
        ):
            raise RuntimeError("solver/reference/DuckDB disagreement")
        results.append(
            {
                "solver_status": expected,
                "solver_seconds": solver_seconds,
                "solver_rows": len(solver.rows) if solver.rows is not None else None,
                "row_minimal_verified": solver.row_minimal_verified,
                "reference_status": reference.status,
                "reference_seconds": reference_seconds,
                "reference_worlds": reference.worlds_checked,
                "reference_test_passing_worlds": reference.test_passing_worlds,
                "random": random_baseline(spec_path, spec.table.seed + index, attempts),
            }
        )
    directory.mkdir(parents=True, exist_ok=False)
    artifact_dir = directory / "artifact"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "dataproof",
            "doppelganger",
            "check",
            str(spec_path),
            "--output",
            str(artifact_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    (directory / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (directory / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
    witness = artifact_dir / "witness.json"
    replay = artifact_dir / "replay.sql"
    if completed.returncode != 0 or not witness.exists() or not validate_serialized(witness).valid:
        raise RuntimeError("CLI witness or serialized replay failed")
    end_usage = resource.getrusage(resource.RUSAGE_SELF)
    record: dict[str, object] = {
        "schema_version": 1,
        "record_kind": "doppelganger_local_exact_obligation",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "git_sha": sha,
        "git_dirty_before_run": dirty,
        "input_path": str(spec_path),
        "input_sha256": digest(spec_path),
        "configuration": {
            "repeats": repeats,
            "random_attempt_cap": attempts,
            "seed": spec.table.seed,
            "max_rows": spec.table.max_rows,
            "timeout_ms": spec.table.timeout_ms,
            "max_memory_mb": spec.table.max_memory_mb,
        },
        "versions": versions(),
        "environment": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "logical_cpus": os.cpu_count(),
        },
        "resource": {
            "parent_user_cpu_seconds": end_usage.ru_utime - start_usage.ru_utime,
            "parent_system_cpu_seconds": end_usage.ru_stime - start_usage.ru_stime,
            "parent_peak_rss_raw": end_usage.ru_maxrss,
            "peak_rss_unit": "bytes" if sys.platform == "darwin" else "kilobytes",
            "scope": "cumulative parent process, not a per-backend measurement",
        },
        "runs": results,
        "cli": {
            "exit_code": completed.returncode,
            "status": json.loads((artifact_dir / "result.json").read_text())["status"],
            "rows_sha256": json.loads(witness.read_text())["rows_sha256"],
            "witness_sha256": digest(witness),
            "replay_sql_sha256": digest(replay),
        },
    }
    (directory / "manifest.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--attempts", type=int, default=20)
    args = parser.parse_args()
    record = run(args.spec, args.run_dir, args.repeats, args.attempts)
    print(record["cli"])


if __name__ == "__main__":
    main()
