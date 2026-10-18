# Prior art and baseline feasibility

Checked on 2026-10-18 against project repositories and primary documentation. These are capability descriptions, not empirical comparisons or originality findings. Repository behavior and licenses must be rechecked before publication.

| Project | Established overlap | Phase 1 comparison status |
| --- | --- | --- |
| [query-identifiability](https://github.com/danielhz/query-identifiability) | Relational query identifiability, closure certificates, witness discovery and view augmentation; README documents `make mini`; MIT | The stated formal setting is relational/FD views, so a daily aggregate obligation may be unmappable. Runnable baseline attempt pending. |
| [VeriEQL](https://github.com/VeriEQL/VeriEQL) | Bounded SQL equivalence with integrity constraints and counterexamples; documented Python and Z3 workflow | An equivalence obligation is not automatically a view-determinacy obligation. Need a precise reduction and isolated run; pending. |
| [Cosette](https://github.com/uwdb/Cosette) / [SQLSolver](https://github.com/SJTU-IPADS/SQLSolver) | SQL equivalence reasoning; Cosette README identifies it as deprecated in favor of QED | Compare supported operators and proof obligations later; no run. |
| [Spec-Lock-Diff](https://github.com/miloskimatheus/spec-lock-diff) | dbt development controls, numeric diffs and mutation style test adequacy; MIT | Different invariant and workflow; no run. |
| [SQLGlot](https://github.com/tobymao/sqlglot) | SQL parser/transpiler; MIT | Dependency candidate, not a proof engine. |
| [SQLMesh](https://github.com/SQLMesh/sqlmesh), [dbt](https://docs.getdbt.com/docs/build/incremental-models) | Transformation, plans, audits, tests and incremental models | Complementary workflow, not evaluated as a determinacy baseline. |
| [SQLancer](https://github.com/sqlancer/sqlancer) | DBMS bug testing with generated SQL | Different oracle and target; no run. |
| [DuckDB profiling](https://duckdb.org/docs/stable/dev/profiling), [BigQuery plan](https://cloud.google.com/bigquery/docs/query-plan-explanation), [Databricks Query Profile](https://docs.databricks.com/aws/en/sql/user/queries/query-profile) | Resource measurements and query plans already exist | ResourceProof is a future research question; a dashboard alone has no novelty claim. |

Local baseline investigations on macOS ARM, Python 3.11, isolated outside this repository:

- query-identifiability commit `f2626f65034c5eda03fc1937c4088a5ece8b9257`: `python3 -c 'from data.utils import check_certificate; f=frozenset({0,1}); print(check_certificate(f,[frozenset({0})],[])); print(check_certificate(f,[frozenset({0})],[(frozenset({0}),1)]))'` printed `False` then `True`. This runs the actual certificate code but does not encode the daily aggregate obligation. Its full `make mini` needs substantially larger optional research dependencies and has not been run.
- VeriEQL commit `493cbb81000205e33b0623cfd1c39106fa035fae`: isolated `pip install -r requirements.txt` succeeded, but `python -m test.test_env` failed at `TypeError: And() got an unexpected keyword argument 'ctx'` with `z3-solver` 5.3.1.0, 4.12.2.0 and 4.11.2.0. No equivalence result is available. This is an environment compatibility observation, not evidence that VeriEQL's method fails.

The second runnable baseline is `research/benchmarks/exhaustive_daily_baseline.py`, a standard-library complete enumeration of the tiny two-day/two-customer case. `python3.11 research/benchmarks/exhaustive_daily_baseline.py` printed `worlds=4 witness_pairs=8`, `D1=(1, 1) D2=(1, 2)`, `daily_equal=True`, and `monthly_distinct=1,2`. Thus Phase 0 examines two runnable baseline mechanisms, but **not two directly comparable external competitors**. No direct competitor has yet been run on an identical NoUndo obligation. No speed, coverage, superiority or novelty claim is supported. Licensing of VeriEQL and SQLSolver is not verified here; do not copy their code. DuckDB replay remains a separate Phase 1 control and cannot replace a fair competitor evaluation. See `research/literature/related_work.csv` for the artifact matrix.
