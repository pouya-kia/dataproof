# Changelog

## Unreleased

- Phase 2: prevent replay/source table-name collisions and fail closed on Z3 and backend errors; add regression and fault-injection tests.
- Phase 0: explicit NoUndo semantics, research hypothesis, baseline notes and test gates.
- Phase 1: guarded finite NoUndo CLI, Z3 search, independent DuckDB replay, tiny exhaustive reference and reproducible run manifest. This is an early research slice, not a general SQL verifier.
