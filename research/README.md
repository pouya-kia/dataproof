# Public research evidence

DataProof publishes only evidence needed to understand and reproduce its shipped, bounded modules. A counterexample is validated against the original SQL in DuckDB; a bounded miss is not a universal proof. Scientific originality and publication readiness remain unverified.

| Stage | Public evidence | Scope |
| --- | --- | --- |
| Phase 1 | [checkpoint](checkpoints/phase1.md), [synthetic witness](../examples/no_undo/evidence/witness.json), [replay SQL](../examples/no_undo/evidence/replay.sql) | One finite daily-aggregate example and core regressions |
| Phase 2 | [checkpoint](checkpoints/phase2.md), [clean run](runs/published/phase2-35b2001.json), [paired tiny-reference run](runs/published/phase2-35b2001-paired.json) | Hardening and a small, non-comparative correctness baseline |
| Phase 3 | [checkpoint](checkpoints/phase3.md), [filter run](runs/published/phase3-filter-fb94148.json), [integer-extrema run](runs/published/phase3-extrema-8076042.json) | Guarded filters and direct integer extrema in tested finite domains |
| Phase 4 | [checkpoint](checkpoints/phase4.md), [clean Doppelgänger run](runs/published/phase4-e584070.json), [versioned witness](../examples/doppelganger/evidence/witness.json), [protocol](protocols/phase4.md) | One explicit test-blind-spot obligation, tiny exhaustive and seeded random controls; no external performance claim |
| Phase 5 | [checkpoint](checkpoints/phase5.md), [clean Proof2Test run](runs/published/phase5-6c1fd5e.json), [pytest fixture](../examples/proof2test/generated_pytest/fixture.json), [dbt unit test](../examples/proof2test/generated_dbt/unit_tests.yml), [protocol](protocols/phase5.md) | One synthetic defective-FAIL/corrected-PASS round trip; no general target guarantee or external performance claim |

The [protocol](protocols/phase1.md), [claims ledger](claims_ledger.md), [related-work matrix](literature/related_work.csv), [benchmark scripts](benchmarks) and [run instructions](runs/README.md) remain public. Published records use synthetic inputs and identify exact code commits. They do not establish a theorem, scale result, or fair external-tool performance comparison. Unsupported cases and negative evidence are retained in the checkpoints and [limitations](../docs/limitations.md).

Raw machine-specific runs belong in the ignored `research/runs/local/` directory. Active unpublished research work is kept locally under the ignored `research/private/` tree, with a separate, independently maintained external backup. Neither an ignore rule nor an in-repository working copy is a backup or a confidentiality guarantee: files must be checked before staging, and previously published Git history remains public. Public benchmark code, sanitized run records, tests and reproducibility documentation remain versioned here.
