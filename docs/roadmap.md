# Roadmap and gate boundaries

Completed Phases 0–3: semantics and baseline feasibility; the limited NoUndo pair-world CLI with an independently replayed witness; replay/error hardening and broader differential testing; and guarded row filters plus direct integer `MIN`/`MAX`. See [semantics](semantics.md) for the exact admitted fragment and [research evidence](../research/README.md) for the scoped results.

Phase 4 added a separate, bounded Doppelgänger workflow for a user-declared invariant and finite existing-test set. It uses one synthetic dataset, not NoUndo's two-world determinacy formula. See its [contract](doppelganger.md). Phase 5 adds [Proof2Test](proof2test.md): a guarded pytest exporter and a small dbt Core unit-test YAML adapter for a separately declared expected output. Neither module infers business truth. TimeProof (Phase 6) and later modules require separate authorization.

No scoped positive theorem or scientific originality claim has been established. A research or software submission remains `NOT_READY` without the applicable proof, comparison, representative evaluation and human review. A working demo is useful on its own, independent of novelty or publication. Future scope requires a separate decision and acceptance criteria.
