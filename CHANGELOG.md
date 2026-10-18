# Changelog

## Unreleased

- Phase 2: prevent replay/source table-name collisions and fail closed on Z3 and backend errors; add regression, fault-injection, differential, property, metamorphic, mutation and golden tests, plus a paired tiny-reference harness and clean-run publication checks.
- Phase 2 corrective milestone: prevent stale witness/replay artifacts across reused output directories with hash-checked ownership, fail-closed conflicts, and lifecycle regressions.
- Phase 0: explicit NoUndo semantics, research hypothesis, baseline notes and test gates.
- Phase 1: guarded finite NoUndo CLI, Z3 search, independent DuckDB replay, tiny exhaustive reference and reproducible run manifest. This is an early research slice, not a general SQL verifier.
