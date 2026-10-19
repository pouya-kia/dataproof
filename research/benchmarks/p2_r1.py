"""Guarded P2-R1 study harness; validation mode never executes an obligation."""

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

from dataproof.doppel_model import load_doppel_spec
from dataproof.report import versions

ROOT = Path(__file__).resolve().parents[2]
CASE_DIR = ROOT / "research/p2_r1/cases"
LOCAL_RUNS = ROOT / "research/runs/local"
CASE_IDS = ("E1", "R1", "R2", "N1", "N2", "B1", "C1", "A1", "M1", "I1")
SEEDS = tuple(range(50))
CHECKPOINTS = (20, 100, 200)
SEARCH_WALL_SECONDS = 12.0
REFERENCE_WALL_SECONDS = 60.0
MAX_DRAWS = 200
VALID_STATUSES = frozenset(
    {
        "BLIND_SPOT_FOUND",
        "BOUNDED_NO_BLIND_SPOT",
        "INCONSISTENT_TESTS",
        "INCONCLUSIVE",
        "NO_WITNESS_WITHIN_BUDGET",
        "SOFT_TIMEOUT",
        "HARD_TIMEOUT",
        "EXCEPTION",
        "FALSE_CLAIM",
    }
)
FROZEN_CASE_SHA256 = {
    "E1": "cc235178543958f01b5177f4e988356bdb722ffd0a470afa424c186947a82e9f",
    "R1": "af4771d2cf786cf776ba7094c410beb11cc86436d3c6dcf447c498309d58f991",
    "R2": "14b6c5fc93035bfcef5d50bac50349bab8f7327e2f31d412e0fb05fe8b17eefe",
    "N1": "9ec3be472aa457b73d0c860b0f36ed0df83946bbd263db6cb1838eb52c852d05",
    "N2": "4e9bda84616419a5384895351cb87d7f1fadf35cf6eecb1f051aafb4ba3f8107",
    "B1": "ea95fd65eb68f244fe82960c076928aa8328437838bb2f5237e1af5b848e38e2",
    "C1": "036a0abd9777dda29ba552a9ebd0e9dcf7a9b9274b1dd3fb79b5ffde9593f52a",
    "A1": "1feeffcb8a4cff87e623ce5402c67386bab32c032a26648bd1cb581593180c46",
    "M1": "02aaac0adff8c43079101ed49cd1df4a968f2449258deb4c17af2b34b8bab17d",
    "I1": "c3c3b159dbed96689d530142345accdfa864a530d73dc93ae41496d378828dc2",
}
PUBLIC_TRIAL_FIELDS = frozenset(
    {
        "case_id",
        "case_sha256",
        "method",
        "trial_index",
        "seed",
        "status",
        "reason_code",
        "error_type",
        "elapsed_seconds",
        "outer_elapsed_seconds",
        "peak_rss_raw",
        "peak_rss_unit",
        "draws",
        "legal_draws",
        "test_passing_draws",
        "duckdb_evaluations",
        "first_hit_draw",
        "witness_rows",
        "checkpoints",
        "confirmed",
        "row_minimal_verified",
        "worlds_checked",
        "test_passing_worlds",
        "oracle_status",
        "oracle_agreement",
    }
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def case_inventory(case_dir: Path = CASE_DIR) -> list[dict[str, Any]]:
    """Parse and bound the frozen inputs only; do not enumerate or search."""
    actual = {p.name for p in case_dir.iterdir() if p.is_file()}
    expected = {f"{case_id}.json" for case_id in CASE_IDS}
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"case file set differs: missing={missing} extra={extra}")
    inventory = []
    for case_id in CASE_IDS:
        path = case_dir / f"{case_id}.json"
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"{case_id} must be a regular case file")
        digest = _sha(path)
        if digest != FROZEN_CASE_SHA256[case_id]:
            raise ValueError(f"{case_id} differs from reviewed frozen input")
        spec = load_doppel_spec(path)
        possibilities = math.prod(len(col.domain) for col in spec.table.columns)
        upper = math.comb(possibilities + spec.table.max_rows, spec.table.max_rows)
        if upper > 10000:
            raise ValueError(f"{case_id} exceeds enumerator world cap")
        inventory.append({"case_id": case_id, "sha256": digest, "world_upper_bound": upper})
    return inventory


def sanitize_trial(raw: dict[str, Any]) -> dict[str, Any]:
    """Allow-list trial metrics; never copy worker logs, paths, SQL or free text."""
    clean = {key: raw[key] for key in PUBLIC_TRIAL_FIELDS if key in raw}
    required = {
        "case_id",
        "case_sha256",
        "method",
        "trial_index",
        "seed",
        "status",
        "oracle_status",
        "oracle_agreement",
    }
    if not required <= clean.keys():
        raise ValueError("missing trial identity or status")
    if type(clean["case_id"]) is not str or clean["case_id"] not in CASE_IDS:
        raise ValueError("unsafe case_id")
    if (
        not isinstance(clean["case_sha256"], str)
        or re.fullmatch(r"[0-9a-f]{64}", clean["case_sha256"]) is None
    ):
        raise ValueError("unsafe case_sha256")
    method = clean["method"]
    index = clean["trial_index"]
    seed = clean["seed"]
    if type(method) is not str or method not in {"reference", "z3", "random"}:
        raise ValueError("unsafe method")
    if type(index) is not int or not 0 <= index < len(SEEDS):
        raise ValueError("unsafe trial_index")
    if (
        (method == "reference" and index != 0)
        or (method == "random" and (type(seed) is not int or seed != SEEDS[index]))
        or (method != "random" and seed is not None)
    ):
        raise ValueError("unsafe seed or trial index")
    if type(clean["status"]) is not str or clean["status"] not in VALID_STATUSES:
        raise ValueError("invalid trial status")
    if type(clean["oracle_status"]) is not str or clean["oracle_status"] not in VALID_STATUSES:
        raise ValueError("invalid oracle status")
    if clean["oracle_agreement"] is not None and type(clean["oracle_agreement"]) is not bool:
        raise ValueError("unsafe oracle agreement")
    for name in ("reason_code", "error_type"):
        value = clean.get(name)
        if value is not None and (
            type(value) is not str
            or len(value) > 64
            or re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", value) is None
        ):
            raise ValueError(f"unsafe {name}")
    if clean.get("reason_code") not in (None, "MEMORY_LIMIT", "SOLVER_ERROR", "TIMEOUT", "UNKNOWN"):
        raise ValueError("unsafe reason_code")
    for name in ("elapsed_seconds", "outer_elapsed_seconds"):
        if name in clean and (
            type(clean[name]) not in (int, float)
            or not math.isfinite(clean[name])
            or clean[name] < 0
        ):
            raise ValueError(f"unsafe {name}")
    counter_caps = {
        "peak_rss_raw": 2**63 - 1,
        "draws": MAX_DRAWS,
        "legal_draws": MAX_DRAWS,
        "test_passing_draws": MAX_DRAWS,
        "duckdb_evaluations": 10001,
        "worlds_checked": 10000,
        "test_passing_worlds": 10000,
    }
    for name, cap in counter_caps.items():
        if name in clean and (type(clean[name]) is not int or not 0 <= clean[name] <= cap):
            raise ValueError(f"unsafe {name}")
    if "peak_rss_unit" in clean and clean["peak_rss_unit"] not in ("bytes", "KiB"):
        raise ValueError("unsafe peak_rss_unit")
    for name in ("first_hit_draw", "witness_rows"):
        value = clean.get(name)
        cap = MAX_DRAWS if name == "first_hit_draw" else 3
        if value is not None and (type(value) is not int or not 1 <= value <= cap):
            raise ValueError(f"unsafe {name}")
    for name in ("confirmed", "row_minimal_verified"):
        if name in clean and clean[name] is not None and type(clean[name]) is not bool:
            raise ValueError(f"unsafe {name}")
    if "draws" in clean and (
        clean.get("legal_draws", 0) > clean["draws"]
        or clean.get("first_hit_draw") is not None
        and clean["first_hit_draw"] > clean["draws"]
    ):
        raise ValueError("inconsistent draw counters")
    if "legal_draws" in clean and clean.get("test_passing_draws", 0) > clean["legal_draws"]:
        raise ValueError("inconsistent random counters")
    if "worlds_checked" in clean and clean.get("test_passing_worlds", 0) > clean["worlds_checked"]:
        raise ValueError("inconsistent reference counters")
    if "checkpoints" in clean:
        points = clean["checkpoints"]
        if not isinstance(points, dict) or set(points) != {str(x) for x in CHECKPOINTS}:
            raise ValueError("checkpoint set differs from protocol")
        for checkpoint, value in points.items():
            if not isinstance(value, dict) or not (
                set(value) == {"not_reached"}
                and value["not_reached"] is True
                or set(value) == {"draws", "legal_draws", "test_passing_draws", "found"}
                and all(
                    type(value[key]) is int
                    for key in ("draws", "legal_draws", "test_passing_draws")
                )
                and type(value["found"]) is bool
                and 0
                <= value["test_passing_draws"]
                <= value["legal_draws"]
                <= value["draws"]
                <= int(checkpoint)
                and value["draws"] <= clean.get("draws", MAX_DRAWS)
            ):
                raise ValueError("unsafe checkpoint payload")
    json.dumps(clean, allow_nan=False)
    return clean


def _worker(path: Path, method: str, seed: int | None, wall: float) -> dict[str, Any]:
    env = os.environ.copy()
    env["DATAPROOF_P2R1_EXECUTE"] = "YES"
    env["PYTHONPATH"] = os.pathsep.join((str(ROOT / "src"), str(ROOT)))
    command = [sys.executable, "-m", "research.benchmarks.p2_r1_worker", method, str(path)]
    if seed is not None:
        command.extend(("--seed", str(seed)))
    started = perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=wall,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"status": "HARD_TIMEOUT", "outer_elapsed_seconds": perf_counter() - started}
    except Exception as exc:
        return {
            "status": "EXCEPTION",
            "error_type": type(exc).__name__,
            "outer_elapsed_seconds": perf_counter() - started,
        }
    outer = perf_counter() - started
    if completed.returncode != 0:
        return {"status": "EXCEPTION", "error_type": "WORKER_EXIT", "outer_elapsed_seconds": outer}
    try:
        payload = json.loads(completed.stdout)
        if not isinstance(payload, dict) or payload.get("status") not in VALID_STATUSES:
            raise ValueError("invalid worker payload")
    except (ValueError, TypeError):
        return {
            "status": "EXCEPTION",
            "error_type": "WORKER_PROTOCOL",
            "outer_elapsed_seconds": outer,
        }
    payload["outer_elapsed_seconds"] = outer
    return payload


def _agreement(method: str, status: str, oracle: str) -> bool | None:
    if oracle not in {"BLIND_SPOT_FOUND", "BOUNDED_NO_BLIND_SPOT", "INCONSISTENT_TESTS"}:
        return None
    if status in {"EXCEPTION", "INCONCLUSIVE", "SOFT_TIMEOUT", "HARD_TIMEOUT"}:
        return None
    if status == "FALSE_CLAIM":
        return False
    if method == "random":
        if status == "BLIND_SPOT_FOUND":
            return oracle == "BLIND_SPOT_FOUND"
        return None
    return status == oracle


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _write_trial(
    stream: TextIO,
    case_id: str,
    case_sha256: str,
    oracle: str,
    method: str,
    trial_index: int,
    seed: int | None,
    raw: dict[str, Any],
) -> None:
    record = sanitize_trial(
        {
            **raw,
            "case_id": case_id,
            "case_sha256": case_sha256,
            "method": method,
            "trial_index": trial_index,
            "seed": seed,
            "oracle_status": oracle,
            "oracle_agreement": _agreement(method, raw["status"], oracle),
        }
    )
    stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
    stream.flush()


def verify_recording(path: Path, inventory: list[dict[str, Any]]) -> dict[str, Any]:
    """Verify the immutable stream before creating its separate completion marker."""
    hashes = {item["case_id"]: item["sha256"] for item in inventory}
    if set(hashes) != set(CASE_IDS) or any(
        hashes[case_id] != FROZEN_CASE_SHA256[case_id] for case_id in CASE_IDS
    ):
        raise ValueError("case inventory differs from reviewed inputs")
    expected = {
        (case_id, method, index)
        for case_id in CASE_IDS
        for method in ("reference", "z3", "random")
        for index in (range(1) if method == "reference" else range(len(SEEDS)))
    }
    seen: set[tuple[str, str, int]] = set()
    oracle_by_case: dict[str, str] = {}
    records: list[dict[str, Any]] = []
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for line in stream:
            digest.update(line)
            try:
                raw = json.loads(line)
                if not isinstance(raw, dict) or sanitize_trial(raw) != raw:
                    raise ValueError("invalid recorded trial")
                case_id = raw["case_id"]
                key = (case_id, raw["method"], raw["trial_index"])
                if key not in expected or key in seen or raw["case_sha256"] != hashes[case_id]:
                    raise ValueError("duplicate or invalid trial identity/hash")
                if raw["method"] == "reference":
                    if raw["oracle_status"] != raw["status"]:
                        raise ValueError("reference oracle status differs")
                    oracle_by_case[case_id] = raw["status"]
                seen.add(key)
                records.append(raw)
            except (json.JSONDecodeError, UnicodeDecodeError, TypeError, KeyError) as exc:
                raise ValueError("malformed recorded trial") from exc
    if seen != expected:
        raise ValueError(f"incomplete recording: {len(seen)} of {len(expected)} trials")
    for raw in records:
        if raw["oracle_status"] != oracle_by_case[raw["case_id"]]:
            raise ValueError("trial oracle status differs from reference")
        if raw["oracle_agreement"] != _agreement(
            raw["method"], raw["status"], raw["oracle_status"]
        ):
            raise ValueError("trial oracle agreement differs")
    return {
        "recording_state": "RECORDING_COMPLETE",
        "trial_count": len(seen),
        "trials_sha256": digest.hexdigest(),
    }


def _complete_recording(output: Path, inventory: list[dict[str, Any]]) -> None:
    completion = verify_recording(output / "trials.jsonl", inventory)
    if case_inventory() != inventory:
        raise ValueError("frozen input changed during recording")
    completion["case_inventory"] = inventory
    marker = output / "completion.json"
    temporary = output / "completion.json.tmp"
    with temporary.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(completion, indent=2, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.link(temporary, marker)
    temporary.unlink()


def run_study(output: Path, case_dir: Path = CASE_DIR) -> None:
    """Execute only after a clean committed protocol and explicit CLI --execute."""
    if case_dir.resolve() != CASE_DIR.resolve():
        raise ValueError("study execution requires the frozen case directory")
    inventory = case_inventory(case_dir)
    if _git("status", "--porcelain"):
        raise RuntimeError("study execution requires a clean committed worktree")
    destination = output.resolve()
    if not destination.is_relative_to(LOCAL_RUNS.resolve()) or destination == LOCAL_RUNS.resolve():
        raise ValueError("raw study output must be a new directory under research/runs/local")
    if output.exists() or output.is_symlink():
        raise FileExistsError("study output already exists")
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "schema_version": 1,
        "record_kind": "p2_r1_raw_trials",
        "recording_state": "INCOMPLETE",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "git_sha": _git("rev-parse", "HEAD"),
        "git_dirty_before_run": False,
        "case_inventory": inventory,
        "seeds": list(SEEDS),
        "random_draw_cap": MAX_DRAWS,
        "random_checkpoints": list(CHECKPOINTS),
        "search_wall_seconds": SEARCH_WALL_SECONDS,
        "reference_wall_seconds": REFERENCE_WALL_SECONDS,
        "z3_solver_timeout_ms": 10000,
        "z3_solver_memory_mb": 256,
        "random_memory_cap": None,
        "versions": versions(),
        "environment": {
            "os": platform.system(),
            "machine": platform.machine(),
            "logical_cpus": os.cpu_count(),
        },
        "note": "Raw local record; no result analysis or scientific conclusion.",
    }
    with (output / "manifest.json").open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    with (output / "trials.jsonl").open("x", encoding="utf-8") as stream:
        for item in inventory:
            case_id = item["case_id"]
            path = case_dir / f"{case_id}.json"
            oracle_raw = _worker(path, "reference", None, REFERENCE_WALL_SECONDS)
            oracle = oracle_raw["status"]
            _write_trial(stream, case_id, item["sha256"], oracle, "reference", 0, None, oracle_raw)
            for trial_index, seed in enumerate(SEEDS):
                order = ("z3", "random") if trial_index % 2 == 0 else ("random", "z3")
                for method in order:
                    trial_seed = seed if method == "random" else None
                    raw = _worker(path, method, trial_seed, SEARCH_WALL_SECONDS)
                    _write_trial(
                        stream,
                        case_id,
                        item["sha256"],
                        oracle,
                        method,
                        trial_index,
                        trial_seed,
                        raw,
                    )
        stream.flush()
        os.fsync(stream.fileno())
    _complete_recording(output, inventory)


def main() -> None:
    parser = argparse.ArgumentParser(description="P2-R1: parser validation only unless --execute")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.execute:
        if args.output is None:
            parser.error("--execute requires --output under research/runs/local")
        run_study(args.output)
    else:
        if args.output is not None:
            parser.error("--output requires --execute")
        print(json.dumps({"validated_cases": case_inventory()}, sort_keys=True))


if __name__ == "__main__":
    main()
