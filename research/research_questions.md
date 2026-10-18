# Research questions

## RQ N1, 2026-10-18

Can a restricted, offline NoUndo search produce small legal two-world counterexamples for analytical aggregate view determinacy that survive independent DuckDB execution, while accurately distinguishing finite bounded misses from fragment-level proofs? The falsifiable Phase 1 hypothesis is that the daily `COUNT(*)`, `SUM(amount)`, and `COUNT(DISTINCT customer_id)` example yields a replayable witness and that tiny-domain Z3 results agree with a separate exhaustive reference. The competing explanation is that existing query-identifiability or SQL equivalence tools already provide equivalent witnesses with equal or better support and that DataProof adds only packaging. A solver/replay mismatch, any false witness, or a baseline that subsumes the claimed workflow defeats a stronger claim. The independent oracle is DuckDB execution of serialized worlds and source SQL; the baseline is exhaustive finite enumeration plus direct competitor experiments when runnable.

Paper 1: `NOT_READY`; Papers 2–4: `NOT_READY`. Demo/software: `NOT_READY`. The cheapest next falsification is a NULL/bag counterexample and a comparable VeriEQL or query-identifiability run. No measured speed, novelty or publication claim exists yet.

Phase 1 checkpoint: the limited witness and tiny oracle agreement hypothesis is `SUPPORTED_WITHIN_SCOPE` by the versioned DuckDB replay and test matrix. The competing explanation remains open: query-identifiability already implements witness discovery, and VeriEQL already implements bounded SQL counterexamples. Its documented smoke test did not run in the tested Z3 environments, so no direct comparative conclusion follows. No scoped positive theorem, measured scalability, or novel method has been established.
