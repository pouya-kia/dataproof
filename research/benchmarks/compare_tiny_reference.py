"""Repeat the exact finite NoUndo obligation against its exhaustive reference."""

from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import statistics
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dataproof.models import load_spec
from dataproof.parser import parse_query
from dataproof.reference_enumerator import reference_search
from dataproof.replay import validate
from dataproof.report import sha256_file, versions
from dataproof.solver import search


def _git(*args: str) -> str:
    run = subprocess.run(["git", *args], capture_output=True, text=True, check=True)
    return run.stdout.strip()


def _timed(function: Any) -> tuple[Any, float]:
    start = time.perf_counter()
    result = function()
    return result, time.perf_counter() - start


def compare(spec_path: Path, repeats: int) -> dict[str, Any]:
    if not 1 <= repeats <= 20:
        raise ValueError("repeats must be 1..20")
    spec = load_spec(spec_path)
    view = parse_query(spec.views[0], spec, metric=False)
    metric = parse_query(spec.metric, spec, metric=True)
    samples: list[dict[str, Any]] = []
    for _ in range(repeats):
        reference, reference_seconds = _timed(lambda: reference_search(spec, view, metric))
        solver, solver_seconds = _timed(lambda: search(spec, view, metric))
        if solver.status == "INCONCLUSIVE":
            raise RuntimeError(f"solver inconclusive: {solver.reason_code}")
        if (reference.witness is None) != (solver.worlds is None):
            raise RuntimeError("solver/reference existence disagreement")
        if solver.worlds is not None and not validate(spec, *solver.worlds).valid:
            raise RuntimeError("solver candidate failed DuckDB replay")
        samples.append(
            {
                "reference_seconds": reference_seconds,
                "solver_seconds": solver_seconds,
                "reference_status": reference.status,
                "solver_status": solver.status,
                "reference_worlds_checked": reference.worlds_checked,
                "duckdb_validated": solver.worlds is not None,
            }
        )
    solver_times = [item["solver_seconds"] for item in samples]
    reference_times = [item["reference_seconds"] for item in samples]
    repo = Path(__file__).resolve().parents[2]
    spec_relative = spec_path.resolve().relative_to(repo).as_posix()
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "schema_version": 1,
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "git_sha": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "input_path": spec_relative,
        "input_sha256": sha256_file(spec_path),
        "input_size_bytes": spec_path.stat().st_size,
        "seed": spec.seed,
        "max_rows": spec.max_rows,
        "timeout_ms": spec.timeout_ms,
        "max_memory_mb": spec.max_memory_mb,
        "versions": versions(),
        "environment": {
            "os": platform.platform(),
            "machine": platform.machine(),
            "cpu_model": platform.processor() or None,
            "cpu_count": os.cpu_count(),
            "peak_rss_raw": usage.ru_maxrss,
            "peak_rss_unit": "bytes" if platform.system() == "Darwin" else "KiB",
        },
        "protocol": (
            "paired warm in-process repeats, reference then solver; no cache or CPU isolation"
        ),
        "samples": samples,
        "summary": {
            "repeats": repeats,
            "solver_median_seconds": statistics.median(solver_times),
            "solver_min_seconds": min(solver_times),
            "solver_max_seconds": max(solver_times),
            "reference_median_seconds": statistics.median(reference_times),
            "reference_min_seconds": min(reference_times),
            "reference_max_seconds": max(reference_times),
            "solver_unknown_or_timeout_count": 0,
            "mismatch_count": 0,
        },
        "limitations": (
            "Tiny synthetic obligation only; Python/Z3/DuckDB overheads differ; "
            "no external-tool or scalability claim."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.spec, args.repeats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"paired_repeats={args.repeats} mismatches=0 output={args.output}")


if __name__ == "__main__":
    main()
