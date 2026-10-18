"""Reproduce one Phase 5 witness-to-test round trip without publishing raw paths/logs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from dataproof.doppel_replay import validate_serialized
from dataproof.report import versions


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def invoke(args: list[str], *, target: Path | None = None) -> dict[str, Any]:
    env = os.environ.copy()
    if target is not None:
        env["DATAPROOF_TARGET_SQL"] = str(target)
    start = perf_counter()
    result = subprocess.run(args, capture_output=True, text=True, check=False, timeout=40, env=env)
    return {
        "exit_code": result.returncode,
        "elapsed_seconds": perf_counter() - start,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def run(
    spec: Path,
    contract: Path,
    defective: Path,
    corrected: Path,
    run_dir: Path,
    record_path: Path,
    dbt_bin: Path | None = None,
) -> dict[str, Any]:
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
    if dirty:
        raise RuntimeError("research run requires a clean committed source tree")
    run_dir.mkdir(parents=True, exist_ok=False)
    checked = invoke(
        [
            sys.executable,
            "-m",
            "dataproof",
            "doppelganger",
            "check",
            str(spec),
            "--output",
            str(run_dir / "witness"),
        ]
    )
    witness = run_dir / "witness" / "witness.json"
    if checked["exit_code"] != 0 or not witness.exists() or not validate_serialized(witness).valid:
        raise RuntimeError("fresh witness failed independent serialized replay")
    replay = invoke([sys.executable, "-m", "dataproof", "doppelganger", "replay", str(witness)])
    if replay["exit_code"] != 0 or "BLIND_SPOT_FOUND" not in replay["stdout"]:
        raise RuntimeError("fresh CLI replay failed")
    output = run_dir / "export"
    export_args = [
        sys.executable,
        "-m",
        "dataproof",
        "proof2test",
        "export",
        str(witness),
        "--target",
        str(contract),
        "--format",
        "pytest",
        "--output",
        str(output),
    ]
    exported = invoke(export_args)
    if exported["exit_code"] != 0 or "EXPORTED" not in exported["stdout"]:
        raise RuntimeError("pytest export failed")
    test_path = next(output.glob("test_*.py"))
    before = {p.name: digest(p) for p in output.iterdir()}
    repeated = invoke(export_args)
    if repeated["exit_code"] != 0 or before != {p.name: digest(p) for p in output.iterdir()}:
        raise RuntimeError("regeneration was not deterministic")
    bad = invoke([sys.executable, "-m", "pytest", "-q", str(test_path)], target=defective)
    good = invoke([sys.executable, "-m", "pytest", "-q", str(test_path)], target=corrected)
    if bad["exit_code"] != 1 or "target output bag differs" not in bad["stdout"]:
        raise RuntimeError("defective implementation was not caught for the expected reason")
    if good["exit_code"] != 0 or "1 passed" not in good["stdout"]:
        raise RuntimeError("corrected implementation did not pass the same test")
    fixture = output / "fixture.json"
    fixture.write_text(fixture.read_text().replace("clean_orders", "tampered_orders"))
    tampered = invoke([sys.executable, "-m", "pytest", "-q", str(test_path)], target=corrected)
    if tampered["exit_code"] != 1 or "fixture integrity mismatch" not in tampered["stdout"]:
        raise RuntimeError("tampered generated fixture was not rejected")
    dbt_result: dict[str, Any] = {"status": "NOT_RUN", "reason": "dbt executable not supplied"}
    if dbt_bin is not None:
        env = os.environ.copy()
        env["DATAPROOF_DBT_BIN"] = str(dbt_bin)
        start = perf_counter()
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/test_proof2test.py::test_dbt_adapter_executes_defective_then_corrected",
            ],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        dbt_result = {
            "status": "PASS"
            if completed.returncode == 0 and "1 passed" in completed.stdout
            else "FAIL",
            "exit_code": completed.returncode,
            "elapsed_seconds": perf_counter() - start,
            "dbt_core": subprocess.check_output(
                [
                    str(dbt_bin.parent / "python"),
                    "-c",
                    "import importlib.metadata as m; print(m.version('dbt-core'))",
                ],
                text=True,
            ).strip(),
            "dbt_duckdb": subprocess.check_output(
                [
                    str(dbt_bin.parent / "python"),
                    "-c",
                    "import importlib.metadata as m; print(m.version('dbt-duckdb'))",
                ],
                text=True,
            ).strip(),
        }
        if dbt_result["status"] != "PASS":
            raise RuntimeError("dbt real-execution round trip failed")
    record: dict[str, Any] = {
        "schema_version": 1,
        "record_kind": "proof2test_synthetic_round_trip",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "git_sha": sha,
        "git_dirty_before_run": dirty,
        "inputs": {
            "spec_sha256": digest(spec),
            "target_contract_sha256": digest(contract),
            "defective_sql_sha256": digest(defective),
            "corrected_sql_sha256": digest(corrected),
        },
        "versions": versions(),
        "environment": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "logical_cpus": os.cpu_count(),
        },
        "witness": {
            "status": "BLIND_SPOT_FOUND",
            "serialized_replay_valid": True,
            "sha256": digest(witness),
            "check_seconds": checked["elapsed_seconds"],
            "replay_seconds": replay["elapsed_seconds"],
        },
        "export": {
            "status": "EXPORTED",
            "exit_code": exported["exit_code"],
            "elapsed_seconds": exported["elapsed_seconds"],
            "repeat_elapsed_seconds": repeated["elapsed_seconds"],
            "deterministic": True,
            "test_sha256": before[test_path.name],
        },
        "generated_pytest": {
            "defective": {
                "exit_code": bad["exit_code"],
                "elapsed_seconds": bad["elapsed_seconds"],
                "failure_reason": "target output bag differs",
            },
            "corrected": {
                "exit_code": good["exit_code"],
                "elapsed_seconds": good["elapsed_seconds"],
                "passed_tests": 1,
            },
            "tampered_fixture": {
                "exit_code": tampered["exit_code"],
                "elapsed_seconds": tampered["elapsed_seconds"],
                "failure_reason": "fixture integrity mismatch",
            },
        },
        "dbt": dbt_result,
        "measurement_scope": (
            "One synthetic fixture and sequential local executions; "
            "timings are not comparative performance evidence."
        ),
    }
    record_path.parent.mkdir(parents=True, exist_ok=True)
    with record_path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--defective", type=Path, required=True)
    parser.add_argument("--corrected", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--dbt-bin", type=Path)
    args = parser.parse_args()
    result = run(
        args.spec,
        args.target,
        args.defective,
        args.corrected,
        args.run_dir,
        args.record,
        args.dbt_bin,
    )
    print(result["generated_pytest"])


if __name__ == "__main__":
    main()
