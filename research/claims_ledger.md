# Claims ledger

| ID | Candidate claim | Baseline / counterevidence | Evidence | Scope | Status | Permitted public wording |
| --- | --- | --- | --- | --- | --- | --- |
| N1 | Daily aggregates can fail to determine monthly distinct customers | Mathematical overlap example; query-identifiability studies related determinacy | `examples/no_undo/evidence/{witness.json,replay.sql}`; eight fixtures | Declared DATE/INTEGER domain, max two rows/world | SUPPORTED_WITHIN_SCOPE | The declared daily view fails to determine the monthly distinct KPI under this finite schema |
| N2 | Bounded search can produce independently valid witnesses | VeriEQL already produces SQL equivalence counterexamples | `tests/test_core.py`; `research/runs/local/smoke-1/manifest.json` (local, dirty pre-commit run) | Guarded SQL fragment only | SUPPORTED_WITHIN_SCOPE | Phase 1 can emit a DuckDB-replayed counterexample for this fragment |
| N3 | DataProof has a distinct research contribution | Query-identifiability already studies witness discovery and augmentation | No comparative experiments yet | Unknown | UNTESTED | No novelty claim |
| N4 | Complete daily SUM values determine complete disjoint roll-up SUM | NULL and integer semantics need a sound theorem | No theorem implemented | Future fragment | UNTESTED | No positive proof claim |
| N5 | Phase 2 differential checks detect selected semantic faults | Finite generated cases cannot rule out shared bugs | `tests/test_hardening.py`; paired tiny-reference harness | Admitted finite NULL/bag/key/aggregate cases only | SUPPORTED_WITHIN_SCOPE | This corpus agrees with DuckDB and detects an injected COUNT DISTINCT error |

AI collaboration audit: Codex assisted with Phase 0 document drafting and source discovery on 2026-10-18. Human review is required for formal claims, experiment reruns, authorship and venue disclosures.

Codex also assisted with Phase 1 code, tests, documentation and local validation on 2026-10-18. This does not establish independent scientific review or authorship.
