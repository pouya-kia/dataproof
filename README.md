# DataProof

**Evidence-driven verification for SQL-centric data pipelines.**

DataProof is an early-stage, research-driven open-source project exploring how executable counterexamples can expose gaps in the guarantees of analytical data pipelines.

> **Status: research and engineering setup.** No verification engine, proof results, CLI, or database integrations have been released yet. Do not interpret the roadmap as implemented functionality.

## The first problem: NoUndo

Suppose a pipeline retains a set of aggregate views `V` and later needs to calculate a KPI `Q`. Are the retained views sufficient to determine that KPI?

A *non-determinacy witness* consists of two source databases `D1` and `D2` satisfying the declared schema and constraints, such that:

```text
V(D1) == V(D2)
Q(D1) != Q(D2)
```

For example, two days can have equal daily order counts, revenue totals, and distinct-customer counts, while having different **monthly distinct-customer** counts due to cross-day overlap. This is an information-preservation question, not proof that backups or original source data have been deleted.

The first implementation milestone will investigate a deliberately limited SQL fragment, a bounded two-world search, and **independent DuckDB replay** of candidate witnesses. An unsuccessful bounded search must never be described as a universal correctness proof.

## Principles

- **Correctness before coverage:** distinguish validated counterexamples, scoped proofs, bounded negative results, unsupported inputs, and inconclusive runs.
- **Offline core:** no required cloud account, LLM API, API key, or paid service.
- **Reproducible research:** publish assumptions, seeds, versions, benchmark methods, negative results, and executable evidence when available.
- **Honest prior art:** query determinacy, SQL verification, and data-quality testing are existing research areas; novelty is a hypothesis to evaluate.
- **Real engineering:** tests, regression checks, reviewable changes, and scoped Conventional Commits.

## Planned modules (not yet implemented)

NoUndo, Doppelgänger, Proof2Test, TimeProof, ChangeProof, RepairProof, and ResourceProof.

## Project stage

The current step is to document the initial semantics and contribution/research workflow. No claim is made that this repository can yet find or prove a data pipeline defect.

Research directions and software contributions will be evaluated independently; publication and GitHub popularity are not guaranteed.
