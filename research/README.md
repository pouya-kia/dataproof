# Public research evidence

DataProof publishes only evidence needed to understand and reproduce the shipped, bounded NoUndo implementation. A counterexample is validated against the original SQL in DuckDB; a bounded miss is not a universal proof. Scientific originality and publication readiness remain unverified.

| Stage | Public evidence | Scope |
| --- | --- | --- |
| Phase 1 | [checkpoint](checkpoints/phase1.md), [synthetic witness](../examples/no_undo/evidence/witness.json), [replay SQL](../examples/no_undo/evidence/replay.sql) | One finite daily-aggregate example and core regressions |
| Phase 2 | [checkpoint](checkpoints/phase2.md), [clean run](runs/published/phase2-35b2001.json), [paired tiny-reference run](runs/published/phase2-35b2001-paired.json) | Hardening and a small, non-comparative correctness baseline |
| Phase 3 | [checkpoint](checkpoints/phase3.md), [filter run](runs/published/phase3-filter-fb94148.json), [integer-extrema run](runs/published/phase3-extrema-8076042.json) | Guarded filters and direct integer extrema in tested finite domains |

The [protocol](protocols/phase1.md), [claims ledger](claims_ledger.md), [related-work matrix](literature/related_work.csv), [benchmark scripts](benchmarks) and [run instructions](runs/README.md) remain public. Published records use synthetic inputs and identify exact code commits. They do not establish a theorem, scale result, or fair external-tool performance comparison. Unsupported cases and negative evidence are retained in the checkpoints and [limitations](../docs/limitations.md).

Raw machine-specific runs belong in the ignored `research/runs/local/` directory. Unreleased scientific working notes, drafts and paper plans belong outside the repository in access-controlled storage. The ignored `research/private/`, `research/drafts/` and `research/papers/` paths are only a guard against accidental staging, not a private backup. Existing public Git history remains public even if current files are later shortened or removed.
