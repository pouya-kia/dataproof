"""One isolated Paper 1 trial; importing this module does not start a search."""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
from pathlib import Path
from typing import Any

from dataproof.models import load_spec, serial_value
from dataproof.parser import parse_query
from dataproof.reference_enumerator import reference_search
from dataproof.replay import validate
from dataproof.solver import search as noundo_search
from research.benchmarks.p1_duckdb_oracle import evaluate as duckdb_oracle
from research.benchmarks.p1_generic_smt import search as generic_search


def _worlds(rows: Any) -> list[list[list[int | str | None]]] | None:
    if rows is None:
        return None
    return [[[serial_value(value) for value in row] for row in world] for world in rows]


def trial(spec_path: Path, method: str) -> dict[str, Any]:
    """Dispatch one method only; hard wall time is enforced by the parent."""
    spec = load_spec(spec_path)
    view = parse_query(spec.views[0], spec, metric=False)
    metric = parse_query(spec.metric, spec, metric=True)
    if method == "oracle":
        actual = duckdb_oracle(spec)
        result: dict[str, Any] = {
            "status": actual.status,
            "reason_code": actual.reason_code,
            "worlds_checked": actual.worlds_checked,
            "minimum_rows": actual.minimum_rows,
            "worlds": _worlds(actual.witness),
            "confirmed": actual.witness is not None,
        }
        if actual.status in {"COUNTEREXAMPLE_FOUND", "BOUNDED_NO_COUNTEREXAMPLE"}:
            python_reference = reference_search(spec, view, metric)
            result["python_reference_status"] = python_reference.status
            if python_reference.status != actual.status:
                result["status"] = "DISAGREEMENT"
                result["reason_code"] = "REFERENCE_DISAGREEMENT"
            elif actual.witness is not None and not validate(spec, *actual.witness).valid:
                result["status"] = "DISAGREEMENT"
                result["reason_code"] = "REPLAY_DISAGREEMENT"
            if result["status"] == "DISAGREEMENT":
                result["confirmed"] = False
    else:
        if method == "noundo_optimize":
            found: Any = noundo_search(spec, view, metric)
        elif method == "generic_optimize":
            found = generic_search(spec, view, metric, optimize=True)
        elif method == "generic_solver":
            found = generic_search(spec, view, metric, optimize=False)
        else:
            raise ValueError("unknown trial method")
        result = {
            "status": found.status,
            "reason_code": found.reason_code,
            "worlds": _worlds(found.worlds),
            "witness_rows": sum(map(len, found.worlds)) if found.worlds is not None else None,
            "confirmed": False,
        }
        if found.status == "CANDIDATE":
            if found.worlds is None or not validate(spec, *found.worlds).valid:
                result["status"] = "INVALID_CANDIDATE"
                result["reason_code"] = "REPLAY_DISAGREEMENT"
            else:
                result["status"] = "COUNTEREXAMPLE_FOUND"
                result["confirmed"] = True
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result["peak_rss_raw"] = usage.ru_maxrss
    result["peak_rss_unit"] = "bytes" if sys.platform == "darwin" else "KiB"
    result["formulation_seconds"] = None
    result["solver_check_seconds"] = None
    return result


def main() -> None:
    if os.environ.get("DATAPROOF_P1_EXECUTE") != "YES":
        raise SystemExit("Paper 1 worker requires explicit study execution")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "method", choices=("oracle", "noundo_optimize", "generic_optimize", "generic_solver")
    )
    parser.add_argument("spec", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(trial(args.spec, args.method), sort_keys=True, allow_nan=False))
    except Exception as exc:
        print(json.dumps({"status": "EXCEPTION", "error_type": type(exc).__name__}))


if __name__ == "__main__":
    main()
