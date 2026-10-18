# Phase 0 decisions

Date: 2026-10-18. Status: proposed implementation contract, pending Phase 1 validation.

1. The first obligation is NoUndo: find legal worlds with equal retained view multisets and unequal scalar KPI values. A replayed witness establishes non-determinacy only under its declared schema and finite input domain. Bounded absence is never a global proof.
2. The first vertical slice uses one synthetic table, one daily grouped aggregate view, and one scalar monthly aggregate metric. SQLGlot parses DuckDB SQL into a guarded typed IR. Unknown AST nodes, functions, coercions, joins, windows, UDFs, and data-changing statements are rejected before search.
3. Initial types are `INTEGER` and `DATE`; nullable values and finite domains are explicit. Amounts are exact signed integers so `SUM` cannot silently use floating-point rounding. No implicit casts. Duplicate rows have bag semantics unless excluded by a declared key. Grouped results are compared as unordered multisets, including SQL NULL values.
4. A bounded Z3 candidate search encodes the admitted IR. An independently written exhaustive enumerator serves as a tiny-domain reference. DuckDB executes serialized synthetic worlds and the original SQL and is the witness acceptance oracle. A disagreement becomes `INVALID_CANDIDATE`, never a published proof.
5. Search caps include maximum rows, finite domain cardinality and timeout. Complete finite unsatisfiability gives `BOUNDED_NO_COUNTEREXAMPLE`; timeout/unknown gives `INCONCLUSIVE`. No positive theorem is implemented in Phase 1, so no case may emit `PROVEN_WITHIN_FRAGMENT`.
6. Artifact JSON records status, assumptions, versions, bounds, seed, exact input, world data and replay command. The SQL replay checks the serialized claim. Artifact paths are local and synthetic. The tool needs no cloud, account, API key, or LLM service.

Open decisions: broader SQL grammar, foreign keys, DECIMAL precision, timestamp semantics, multiple tables/views, proof of SUM roll-up, PostgreSQL differential checks, and provider adapters. These require later authorization and evidence.

Phase 0 acceptance: a falsifiable research question, prior-art matrix, explicit semantics and test impact plan, two runnable baseline investigations, and a reviewable Phase 1 design. Phase 1 acceptance: eight core fixtures, legal pair-world replay, a tiny exhaustive cross-check, bounded statuses, offline CLI, and a green full gate. Paper readiness remains `NOT_READY`.
