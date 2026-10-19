"""Guarded, lossless Paper 1 recording harness; default mode only parses cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, TextIO

from dataproof.models import load_spec
from dataproof.parser import parse_query
from dataproof.report import versions

ROOT = Path(__file__).resolve().parents[2]
CASE_DIR = ROOT / "research/p1_generic_smt/cases"
PROTOCOL = ROOT / "research/protocols/p1_generic_smt.md"
LOCAL_RUNS = ROOT / "research/runs/local"
CASE_IDS = (
    "P1",
    "A1",
    "N1",
    "B1",
    "E1",
    "NG",
    "DA",
    "SR",
    "MP",
    "XR",
    "PK",
    "UQ",
    "GE",
    "IN",
    "CH",
)
MEDIUM_IDS = frozenset(CASE_IDS[5:])
HYPOTHESIS = {
    "P1": ("COUNTEREXAMPLE_FOUND", 2, 5),
    "A1": ("BOUNDED_NO_COUNTEREXAMPLE", None, 3),
    "N1": ("COUNTEREXAMPLE_FOUND", 2, 3),
    "B1": ("COUNTEREXAMPLE_FOUND", 3, 6),
    "E1": ("COUNTEREXAMPLE_FOUND", 1, 3),
    "NG": ("COUNTEREXAMPLE_FOUND", 2, 969),
    "DA": ("COUNTEREXAMPLE_FOUND", 4, 969),
    "SR": ("BOUNDED_NO_COUNTEREXAMPLE", None, 455),
    "MP": ("COUNTEREXAMPLE_FOUND", 2, 969),
    "XR": ("BOUNDED_NO_COUNTEREXAMPLE", None, 969),
    "PK": ("COUNTEREXAMPLE_FOUND", 2, 455),
    "UQ": ("COUNTEREXAMPLE_FOUND", 3, 455),
    "GE": ("COUNTEREXAMPLE_FOUND", 2, 969),
    "IN": ("BOUNDED_NO_COUNTEREXAMPLE", None, 1330),
    "CH": ("COUNTEREXAMPLE_FOUND", 4, 2925),
}
FROZEN_CASE_SHA256 = {
    "P1": "a41753c64193cdbbdf4bdd5352c260d3a46a24d2867993ba04d141b33d3f94ed",
    "A1": "419c5fc4e1503f34694376a3f64d013d84998f768b180eae64751a8b15c2d7e9",
    "N1": "d3ee3c7ae04063bf14b7b08309ca7abd23da38a337073793e0564d8359c016bd",
    "B1": "85b06aac433e81deb6cb18da640876e466f6797194accad99bdb9e84845182aa",
    "E1": "c3bcac43c5a2e53603cf72ad9c175c72741a4d253f67925b5d148a933d394902",
    "NG": "b58956ffb9e34d086f6bb521c98ea243b406f10b45f79fd31d9d83ce03525bae",
    "DA": "462507bc9c37281218d1466493a70f1933b59a2f5479dfe071c75abb935d7956",
    "SR": "f56b24471bd8e2ab25a107d07178f5e1338741766bcfee694d0df190a1fcbe9f",
    "MP": "9199a46f1013c523fdc517aebd9d2552c6d84da06328ef8b5999d58ad7050a92",
    "XR": "2c017a3c759f176c8cd1059901f4a25df7e00ee7a287d7ab6ba140e49c2ddc99",
    "PK": "55fce35c29aee1f7b062950857f7ffbb5f4d8dea7918a70e963c4b4c4ebea583",
    "UQ": "83be4adf492ef03704c4edd97664624d8e426f0cf7021681722a8614ad55bab7",
    "GE": "9952f26034f231072dcb8f89bf7b698b901dcd1dc5cba414b774c6f84d08b3e6",
    "IN": "c29eb234a5d4dc8d6a0a5bb22e12839cd02f6fdfb17728ab232d7aa312d20aef",
    "CH": "03546056a6b5cc011cb610cd7ee507c5096e48eb6fc57f72cdb8eb29d124bb93",
}
REPEATS = 10
SEARCH_WALL_SECONDS = 20.0
ORACLE_WALL_SECONDS = 300.0
SOLVER_TIMEOUT_MS = 10000
SOLVER_MEMORY_MB = 256
PRIMARY_METHODS = ("noundo_optimize", "generic_optimize")
STATUSES = frozenset(
    {
        "COUNTEREXAMPLE_FOUND",
        "BOUNDED_NO_COUNTEREXAMPLE",
        "INCONCLUSIVE",
        "INVALID_CANDIDATE",
        "DISAGREEMENT",
        "HARD_TIMEOUT",
        "EXCEPTION",
    }
)
PUBLIC_FIELDS = frozenset(
    {
        "case_id",
        "case_sha256",
        "method",
        "trial_index",
        "status",
        "reason_code",
        "error_type",
        "outer_elapsed_seconds",
        "peak_rss_raw",
        "peak_rss_unit",
        "worlds_checked",
        "witness_rows",
        "worlds",
        "confirmed",
        "minimum_rows",
        "oracle_status",
        "oracle_minimum_rows",
        "status_agreement",
        "minimum_agreement",
        "python_reference_status",
        "formulation_seconds",
        "solver_check_seconds",
    }
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def case_inventory(case_dir: Path = CASE_DIR) -> list[dict[str, Any]]:
    """Only validate files, schemas, SQL and analytical bounds; never search."""
    if case_dir.is_symlink() or not case_dir.is_dir():
        raise ValueError("case directory must be a real directory")
    actual = {p.name for p in case_dir.iterdir()}
    expected = {f"{case_id}.json" for case_id in CASE_IDS}
    if actual != expected:
        raise ValueError("frozen case inventory differs")
    inventory = []
    for case_id in CASE_IDS:
        path = case_dir / f"{case_id}.json"
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"{case_id} must be a regular file")
        digest = sha256(path)
        if digest != FROZEN_CASE_SHA256[case_id]:
            raise ValueError(f"{case_id} differs from frozen file hash")
        spec = load_spec(path)
        parse_query(spec.views[0], spec, metric=False)
        parse_query(spec.metric, spec, metric=True)
        if spec.timeout_ms != SOLVER_TIMEOUT_MS or spec.max_memory_mb != SOLVER_MEMORY_MB:
            raise ValueError(f"{case_id} solver limits differ")
        possible_rows = math.prod(len(col.domain) for col in spec.columns)
        bound = math.comb(possible_rows + spec.max_rows, spec.max_rows)
        if bound != HYPOTHESIS[case_id][2] or bound > 10000:
            raise ValueError(f"{case_id} analytical world bound differs")
        inventory.append(
            {
                "case_id": case_id,
                "sha256": digest,
                "world_upper_bound": bound,
                "hypothesis_status": HYPOTHESIS[case_id][0],
                "hypothesis_minimum_rows": HYPOTHESIS[case_id][1],
            }
        )
    return inventory


def _safe_worlds(value: Any) -> bool:
    if value is None:
        return True
    if not isinstance(value, list) or len(value) != 2:
        return False
    for world in value:
        if not isinstance(world, list) or len(world) > 3:
            return False
        for row in world:
            if not isinstance(row, list) or not 1 <= len(row) <= 4:
                return False
            for cell in row:
                if cell is None or type(cell) is int and -(2**31) <= cell < 2**31:
                    continue
                if type(cell) is str and re.fullmatch(r"\d{4}-\d{2}-\d{2}", cell):
                    continue
                return False
    return True


def sanitize_trial(raw: dict[str, Any]) -> dict[str, Any]:
    """Allow-list observations; reject paths, logs, free text and malformed data."""
    clean = {key: raw[key] for key in PUBLIC_FIELDS if key in raw}
    required = {"case_id", "case_sha256", "method", "trial_index", "status", "oracle_status"}
    if not required <= clean.keys() or clean["case_id"] not in CASE_IDS:
        raise ValueError("missing or invalid trial identity")
    if clean["case_sha256"] != FROZEN_CASE_SHA256[clean["case_id"]]:
        raise ValueError("case hash differs")
    method = clean["method"]
    index = clean["trial_index"]
    if (
        method not in ("oracle", *PRIMARY_METHODS)
        or type(index) is not int
        or not 0 <= index < REPEATS
    ):
        raise ValueError("invalid method or trial index")
    if method == "oracle" and index != 0:
        raise ValueError("oracle has exactly one trial per case")
    for name in ("status", "oracle_status"):
        if clean[name] not in STATUSES:
            raise ValueError("invalid status")
    for name in ("reason_code", "error_type"):
        value = clean.get(name)
        if value is not None and (
            type(value) is not str or not re.fullmatch(r"[A-Z_]{1,40}|[A-Za-z_]{1,40}", value)
        ):
            raise ValueError(f"unsafe {name}")
    elapsed = clean.get("outer_elapsed_seconds")
    if (
        not isinstance(elapsed, (int, float))
        or isinstance(elapsed, bool)
        or not math.isfinite(elapsed)
        or elapsed < 0
    ):
        raise ValueError("invalid elapsed time")
    for name, upper in (
        ("worlds_checked", 10000),
        ("witness_rows", 6),
        ("minimum_rows", 6),
        ("oracle_minimum_rows", 6),
        ("peak_rss_raw", 2**63 - 1),
    ):
        value = clean.get(name)
        if value is not None and (type(value) is not int or not 0 <= value <= upper):
            raise ValueError(f"invalid {name}")
    if clean.get("peak_rss_unit") not in (None, "bytes", "KiB"):
        raise ValueError("invalid RSS unit")
    for name in ("confirmed", "status_agreement", "minimum_agreement"):
        value = clean.get(name)
        if value is not None and type(value) is not bool:
            raise ValueError(f"invalid {name}")
    if not _safe_worlds(clean.get("worlds")):
        raise ValueError("unsafe witness cells")
    for name in ("formulation_seconds", "solver_check_seconds"):
        if clean.get(name) is not None:
            raise ValueError("phase timings are not measured comparably")
    if clean.get("python_reference_status") not in (
        None,
        "COUNTEREXAMPLE_FOUND",
        "BOUNDED_NO_COUNTEREXAMPLE",
    ):
        raise ValueError("invalid Python reference status")
    json.dumps(clean, allow_nan=False)
    return clean


def _worker(path: Path, method: str, wall: float) -> dict[str, Any]:
    env = os.environ.copy()
    env["DATAPROOF_P1_EXECUTE"] = "YES"
    env["PYTHONPATH"] = os.pathsep.join((str(ROOT / "src"), str(ROOT)))
    command = [sys.executable, "-m", "research.benchmarks.p1_generic_smt_worker", method, str(path)]
    started = perf_counter()
    try:
        completed = subprocess.run(
            command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=wall, check=False
        )
    except subprocess.TimeoutExpired:
        return {"status": "HARD_TIMEOUT", "outer_elapsed_seconds": perf_counter() - started}
    except Exception as exc:
        return {
            "status": "EXCEPTION",
            "error_type": type(exc).__name__,
            "outer_elapsed_seconds": perf_counter() - started,
        }
    elapsed = perf_counter() - started
    if completed.returncode != 0:
        return {
            "status": "EXCEPTION",
            "error_type": "WORKER_EXIT",
            "outer_elapsed_seconds": elapsed,
        }
    try:
        payload = json.loads(completed.stdout)
        if not isinstance(payload, dict) or payload.get("status") not in STATUSES:
            raise ValueError("invalid worker payload")
    except (ValueError, TypeError):
        return {
            "status": "EXCEPTION",
            "error_type": "WORKER_PROTOCOL",
            "outer_elapsed_seconds": elapsed,
        }
    payload["outer_elapsed_seconds"] = elapsed
    if payload.get("worlds") is not None:
        payload["witness_rows"] = sum(map(len, payload["worlds"]))
    return payload


def _agreement(
    status: str, oracle: str, rows: int | None, minimum: int | None
) -> tuple[bool | None, bool | None]:
    if oracle not in ("COUNTEREXAMPLE_FOUND", "BOUNDED_NO_COUNTEREXAMPLE"):
        return None, None
    if status not in ("COUNTEREXAMPLE_FOUND", "BOUNDED_NO_COUNTEREXAMPLE"):
        return False if status in ("INVALID_CANDIDATE", "DISAGREEMENT") else None, None
    status_match = status == oracle
    minimum_match = rows == minimum if status == oracle == "COUNTEREXAMPLE_FOUND" else None
    return status_match, minimum_match


def _record(
    stream: TextIO,
    item: dict[str, Any],
    oracle_status: str,
    oracle_minimum: int | None,
    method: str,
    index: int,
    raw: dict[str, Any],
) -> None:
    status_match, minimum_match = _agreement(
        raw["status"], oracle_status, raw.get("witness_rows"), oracle_minimum
    )
    trial = sanitize_trial(
        {
            **raw,
            "case_id": item["case_id"],
            "case_sha256": item["sha256"],
            "method": method,
            "trial_index": index,
            "oracle_status": oracle_status,
            "oracle_minimum_rows": oracle_minimum,
            "status_agreement": status_match,
            "minimum_agreement": minimum_match,
            "formulation_seconds": None,
            "solver_check_seconds": None,
        }
    )
    stream.write(json.dumps(trial, sort_keys=True, allow_nan=False) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def verify_recording(path: Path, inventory: list[dict[str, Any]]) -> dict[str, Any]:
    expected = {
        (item["case_id"], method, index)
        for item in inventory
        for method in ("oracle", *PRIMARY_METHODS)
        for index in (range(1) if method == "oracle" else range(REPEATS))
    }
    if len(inventory) != len(CASE_IDS) or len(expected) != 315:
        raise ValueError("unexpected schedule")
    hashes = {item["case_id"]: item["sha256"] for item in inventory}
    if hashes != FROZEN_CASE_SHA256:
        raise ValueError("inventory hashes differ")
    seen: set[tuple[str, str, int]] = set()
    records: list[dict[str, Any]] = []
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for line in stream:
            digest.update(line)
            try:
                raw = json.loads(line)
                if not isinstance(raw, dict) or sanitize_trial(raw) != raw:
                    raise ValueError("invalid recorded trial")
                key = (raw["case_id"], raw["method"], raw["trial_index"])
                if key not in expected or key in seen:
                    raise ValueError("duplicate or invalid trial")
                seen.add(key)
                records.append(raw)
            except (json.JSONDecodeError, UnicodeDecodeError, TypeError, KeyError) as exc:
                raise ValueError("malformed trial stream") from exc
    if seen != expected:
        raise ValueError(f"incomplete trial stream: {len(seen)} of {len(expected)}")
    oracle = {raw["case_id"]: raw for raw in records if raw["method"] == "oracle"}
    if set(oracle) != set(CASE_IDS):
        raise ValueError("missing oracle record")
    for raw in records:
        ref = oracle[raw["case_id"]]
        if raw["oracle_status"] != ref["status"] or raw["oracle_minimum_rows"] != ref.get(
            "minimum_rows"
        ):
            raise ValueError("oracle metadata differs")
        if raw["method"] != "oracle":
            status_match, minimum_match = _agreement(
                raw["status"], ref["status"], raw.get("witness_rows"), ref.get("minimum_rows")
            )
            if (
                raw.get("status_agreement") != status_match
                or raw.get("minimum_agreement") != minimum_match
            ):
                raise ValueError("agreement accounting differs")
    return {
        "recording_state": "RECORDING_COMPLETE",
        "trial_count": len(seen),
        "trials_sha256": digest.hexdigest(),
    }


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def run_study(output: Path) -> None:
    """Future execution requires a clean committed snapshot and explicit CLI flag."""
    inventory = case_inventory()
    if not PROTOCOL.is_file() or PROTOCOL.is_symlink():
        raise ValueError("protocol missing or symlinked")
    if _git("status", "--porcelain"):
        raise RuntimeError("study requires a clean committed worktree")
    destination = output.resolve()
    if destination == LOCAL_RUNS.resolve() or not destination.is_relative_to(LOCAL_RUNS.resolve()):
        raise ValueError("raw output must be a new directory under research/runs/local")
    if output.exists() or output.is_symlink():
        raise FileExistsError("output already exists")
    source_sha = _git("rev-parse", "HEAD")
    branch = _git("branch", "--show-current")
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "schema_version": 1,
        "record_kind": "p1_generic_smt_raw_trials",
        "recording_state": "INCOMPLETE",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "git_sha": source_sha,
        "branch": branch,
        "protocol_sha256": sha256(PROTOCOL),
        "case_inventory": inventory,
        "primary_methods": list(PRIMARY_METHODS),
        "timing_repetitions_per_method": REPEATS,
        "solver_timeout_ms": SOLVER_TIMEOUT_MS,
        "solver_memory_mb": SOLVER_MEMORY_MB,
        "search_outer_wall_seconds": SEARCH_WALL_SECONDS,
        "oracle_outer_wall_seconds": ORACLE_WALL_SECONDS,
        "outer_memory_limit": "NOT_ENFORCED",
        "versions": versions(),
        "environment": {
            "os": platform.system(),
            "machine": platform.machine(),
            "logical_cpus": os.cpu_count(),
        },
        "note": "Recording completeness does not establish correctness or scientific validity.",
    }
    with (output / "manifest.json").open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    with (output / "trials.jsonl").open("x", encoding="utf-8") as stream:
        for item in inventory:
            path = CASE_DIR / f"{item['case_id']}.json"
            raw_ref = _worker(path, "oracle", ORACLE_WALL_SECONDS)
            oracle_status = raw_ref["status"]
            oracle_minimum = raw_ref.get("minimum_rows")
            _record(stream, item, oracle_status, oracle_minimum, "oracle", 0, raw_ref)
            for index in range(REPEATS):
                order = PRIMARY_METHODS if index % 2 == 0 else PRIMARY_METHODS[::-1]
                for method in order:
                    raw = _worker(path, method, SEARCH_WALL_SECONDS)
                    _record(stream, item, oracle_status, oracle_minimum, method, index, raw)
    completion = verify_recording(output / "trials.jsonl", inventory)
    if (
        case_inventory() != inventory
        or sha256(PROTOCOL) != manifest["protocol_sha256"]
        or _git("rev-parse", "HEAD") != source_sha
        or _git("status", "--porcelain")
    ):
        raise RuntimeError("source snapshot changed during recording")
    completion["case_inventory"] = inventory
    temporary = output / "completion.json.tmp"
    marker = output / "completion.json"
    with temporary.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(completion, indent=2, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.link(temporary, marker)
    temporary.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper 1: parser validation unless --execute")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.execute:
        if args.output is None:
            parser.error("--execute requires --output")
        run_study(args.output)
    else:
        if args.output is not None:
            parser.error("--output requires --execute")
        print(json.dumps({"validated_cases": case_inventory()}, sort_keys=True))


if __name__ == "__main__":
    main()
