# Run evidence

Phase 1 produces small, versioned JSON and replay SQL artifacts. Raw local runs may be ignored until reviewed. A manifest must cite its input, exact command, versioned environment and independently checked outcome. Record all failures and timeouts. Commit SHA must be captured after the code commit in a separate run record to avoid a circular hash. No precomputed result or benchmark is claimed here.

The reviewed synthetic example is `examples/no_undo/evidence/witness.json` plus `replay.sql`. The local pre-commit smoke run is `research/runs/local/smoke-1/manifest.json` and is intentionally ignored because its Git state is dirty. After the Phase 1 commit, rerun `research/benchmarks/run_phase1.py` into a new local directory so its manifest captures the exact commit SHA and clean state. Do not copy an old SHA into a new artifact.
