"""Write a single honest local run manifest; no performance claim is inferred."""

from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from dataproof.models import load_spec
from dataproof.report import sha256_file, versions


def git_value(*args: str) -> str | None:
    process = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    return process.stdout.strip() if process.returncode == 0 else None


def ram_bytes() -> int | None:
    if sys.platform == "darwin":
        process = subprocess.run(
            ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, check=False
        )
        return int(process.stdout) if process.returncode == 0 else None
    try:
        return os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    except (ValueError, OSError, AttributeError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    spec = load_spec(args.spec)
    args.run_dir.mkdir(parents=True, exist_ok=False)
    artifact_dir = args.run_dir / "artifact"
    command = [
        sys.executable,
        "-m",
        "dataproof",
        "check",
        str(args.spec),
        "--output",
        str(artifact_dir),
        "--json",
    ]
    start_cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter()
    process = subprocess.run(command, capture_output=True, text=True, check=False)
    elapsed = time.perf_counter() - start
    end_cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
    stdout_path = args.run_dir / "stdout.txt"
    stderr_path = args.run_dir / "stderr.txt"
    stdout_path.write_text(process.stdout, encoding="utf-8")
    stderr_path.write_text(process.stderr, encoding="utf-8")
    result_path = artifact_dir / "result.json"
    status = json.loads(result_path.read_text())["status"] if result_path.exists() else "NO_RESULT"
    git_status = git_value("status", "--porcelain")
    manifest = {
        "schema_version": 1,
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "git_sha": git_value("rev-parse", "HEAD"),
        "git_dirty": bool(git_status) if git_status is not None else None,
        "input_sha256": sha256_file(args.spec),
        "input_size_bytes": args.spec.stat().st_size,
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
            "ram_bytes": ram_bytes(),
            "child_user_cpu_seconds": end_cpu.ru_utime - start_cpu.ru_utime,
            "child_system_cpu_seconds": end_cpu.ru_stime - start_cpu.ru_stime,
            "child_peak_rss_raw": end_cpu.ru_maxrss,
            "child_peak_rss_unit": "bytes" if sys.platform == "darwin" else "KiB",
        },
        "command": command,
        "exit_code": process.returncode,
        "status": status,
        "elapsed_seconds": elapsed,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "artifact_paths": {
            "result": str(result_path) if result_path.exists() else None,
            "witness": (
                str(artifact_dir / "witness.json")
                if (artifact_dir / "witness.json").exists()
                else None
            ),
            "replay_sql": (
                str(artifact_dir / "replay.sql") if (artifact_dir / "replay.sql").exists() else None
            ),
        },
    }
    manifest_path = args.run_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"{status} exit={process.returncode} manifest={manifest_path}")


if __name__ == "__main__":
    main()
