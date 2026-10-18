# Phase 4 local evaluation protocol

The exact obligation is the versioned synthetic input in `examples/doppelganger/nonnegative_amount.json`: `COUNT(*) >= 1` must pass while the separately declared prohibition of negative amounts, expressed as `COUNT(*) WHERE amount = -1 = 0`, must be SQL FALSE. This is a user-provided business assumption, not an inference about real transactions. The declared domain is `[-1, 0, 1]`, with at most two bag rows. No production data is used.

At a clean committed SHA with dependencies installed, run:

```sh
PYTHONPATH=src .venv/bin/python research/benchmarks/run_doppelganger.py examples/doppelganger/nonnegative_amount.json --run-dir research/runs/local/phase4-<sha> --repeats 5 --attempts 20
```

The harness records the exact input hash, source SHA, dirty flag, timestamp, versions, platform, cumulative parent-process CPU and peak-RSS metadata, solver status and row count, exhaustive legal-world and test-passing counts, per-run elapsed times, a seeded random-generator result under the same bounds, and hashes of the generated witness and replay SQL. It runs the source CLI in a subprocess, validates the serialized witness again, and stores raw artifacts only in the ignored local directory. The random baseline samples row counts and declared column-domain values with replacement, rejects illegal worlds, and stops at its first confirmed witness or 20 draws. It is not exhaustive, and its timing is not directly comparable to the exhaustive search without matching work and isolation. The cumulative process RSS is not per-method memory use.

Publication requires a clean source commit, no solver/reference status disagreement, independent DuckDB acceptance of the solver dataset, and successful serialized CLI replay. Publish only a sanitized, commit-pinned summary: remove local paths and logs, keep real outcomes and limitations, never backdate or fabricate a run. Reproduction should compare statuses, row hash and legal/test/invariant evaluations, not wall time or byte hashes of path-bearing artifacts. External competitors require a separately justified mapping to the same obligation before any performance comparison. Paper 2 and software submission remain `NOT_READY`.
