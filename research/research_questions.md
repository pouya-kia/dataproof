# Evaluated research questions

These questions describe completed, finite NoUndo evaluations. The results are scoped empirical checks, not universal theorems or claims of scientific novelty. Detailed working hypotheses and future publication planning are kept outside the public repository.

| ID | Public question | Observed status | Evidence and limit |
| --- | --- | --- | --- |
| N1 | Can a bounded offline search find a legal pair of worlds with equal retained daily aggregates but different monthly distinct-customer metrics? | `SUPPORTED_WITHIN_SCOPE` | The [Phase 1 witness](../examples/no_undo/evidence/witness.json) replays in DuckDB for the declared synthetic schema. A bounded miss would not prove determinacy. |
| N5 | Do selected NULL, bag, key and aggregate cases agree across Z3, exhaustive enumeration and DuckDB, and does an injected evaluator fault get detected? | `SUPPORTED_WITHIN_SCOPE` | [Phase 2 checkpoint](checkpoints/phase2.md) and tests; finite generated cases cannot rule out a shared semantic bug. |
| N6 | Do guarded row filters and integer extrema preserve three-way agreement in the tested tiny domains? | `SUPPORTED_WITHIN_SCOPE` | [Phase 3 checkpoint](checkpoints/phase3.md) and tests; no general SQL or cross-engine guarantee follows. |
| N7 | Can one legal dataset pass the declared tests while falsifying a separate user-supplied invariant in the admitted finite fragment? | `SUPPORTED_WITHIN_SCOPE` | [Phase 4 checkpoint](checkpoints/phase4.md), [clean run](runs/published/phase4-e584070.json) and tests; one synthetic example does not establish broader test adequacy or novelty. |

The competing explanation for any distinct research contribution remains open: existing verification and identifiability systems already cover related obligations. No same-obligation external comparison establishes novelty or superiority. See the [claims ledger](claims_ledger.md), [related work](literature/related_work.csv), and [limitations](../docs/limitations.md).
