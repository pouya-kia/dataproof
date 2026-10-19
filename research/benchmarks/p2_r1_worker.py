"""One isolated P2-R1 trial. Never import this module to start a search."""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

from dataproof.doppel_model import load_doppel_spec
from dataproof.doppel_reference import reference_search
from dataproof.doppel_replay import validate
from dataproof.doppel_solver import search
from research.benchmarks.run_doppelganger import random_baseline


def trial(spec_path: Path, method: str, seed: int | None = None) -> dict[str, Any]:
    """Run an explicitly requested trial; the parent enforces the hard wall cap."""
    started = perf_counter()
    if method == "random":
        if seed is None:
            raise ValueError("random method requires a seed")
        sampled = random_baseline(
            spec_path, seed, 200, checkpoints=(20, 100, 200), deadline_seconds=11.0
        )
        result: dict[str, Any] = {
            "status": (
                "BLIND_SPOT_FOUND"
                if sampled["found"]
                else "SOFT_TIMEOUT"
                if sampled["deadline_reached"]
                else "NO_WITNESS_WITHIN_BUDGET"
            ),
            "seed": seed,
            "draws": sampled["draws"],
            "legal_draws": sampled["legal_draws"],
            "test_passing_draws": sampled["test_passing_draws"],
            "duckdb_evaluations": sampled["legal_draws"],
            "first_hit_draw": sampled["first_hit_draw"],
            "witness_rows": sampled["witness_size"],
            "checkpoints": sampled["checkpoints"],
            "confirmed": sampled["found"],
        }
    elif method == "z3":
        spec = load_doppel_spec(spec_path)
        found = search(spec)
        result = {
            "status": found.status,
            "reason_code": found.reason_code,
            "row_minimal_verified": found.row_minimal_verified,
            "witness_rows": len(found.rows) if found.rows is not None else None,
            "duckdb_evaluations": 0,
            "confirmed": False,
        }
        if found.status == "CANDIDATE":
            if found.rows is None:
                result["status"] = "FALSE_CLAIM"
            else:
                result["duckdb_evaluations"] = 1
                result["confirmed"] = validate(spec, found.rows).valid
                result["status"] = "BLIND_SPOT_FOUND" if result["confirmed"] else "FALSE_CLAIM"
    elif method == "reference":
        spec = load_doppel_spec(spec_path)
        found_ref = reference_search(spec)
        result = {
            "status": found_ref.status,
            "worlds_checked": found_ref.worlds_checked,
            "test_passing_worlds": found_ref.test_passing_worlds,
            "witness_rows": len(found_ref.rows) if found_ref.rows is not None else None,
            "duckdb_evaluations": found_ref.worlds_checked,
            "confirmed": found_ref.rows is not None,
        }
        if found_ref.rows is not None and not validate(spec, found_ref.rows).valid:
            result["status"] = "FALSE_CLAIM"
            result["confirmed"] = False
            result["duckdb_evaluations"] += 1
    else:
        raise ValueError("unknown trial method")
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result["elapsed_seconds"] = perf_counter() - started
    result["peak_rss_raw"] = usage.ru_maxrss
    result["peak_rss_unit"] = "bytes" if sys.platform == "darwin" else "KiB"
    return result


def main() -> None:
    if os.environ.get("DATAPROOF_P2R1_EXECUTE") != "YES":
        raise SystemExit("P2-R1 worker requires explicit study execution")
    parser = argparse.ArgumentParser()
    parser.add_argument("method", choices=("reference", "z3", "random"))
    parser.add_argument("spec", type=Path)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    try:
        print(json.dumps(trial(args.spec, args.method, args.seed), sort_keys=True))
    except Exception as exc:
        # No exception string, traceback, path or raw SQL enters a study record.
        print(json.dumps({"status": "EXCEPTION", "error_type": type(exc).__name__}))


if __name__ == "__main__":
    main()
