# Current limitations

- One table, one grouped retained view, one scalar aggregate metric, at most three rows per world and at most four finite values per column. A result applies only to those explicit bounds and values.
- One direct grouping column and at most one guarded row predicate (`INTEGER =` signed integer literal, `IS NULL`, or `IS NOT NULL`) per query. `MIN`/`MAX` accept only one direct INTEGER column, not DATE or scalar two-argument forms. No compound or other `WHERE` conditions, joins, subqueries, `ORDER BY`, windows, UDFs, arithmetic expressions, multiple views, foreign keys, strings, decimals, floating point or timestamps. SQL must use DuckDB semantics.
- The current optimizer minimizes total synthetic source rows within the finite model and chooses a stable lexicographic witness. This is **not** a globally minimal SQL counterexample or a minimum among unrestricted databases.
- `BOUNDED_NO_COUNTEREXAMPLE` never means universal determinacy. SUM roll-up is not a theorem here; the included daily SUM case is checked only in its finite domain.
- No PostgreSQL or other engine differential claim, no dbt integration, no production data access, no cloud adapter, no profiler, and no performance benchmark comparison.
- Replayed synthetic data may still encode user-entered identifiers in a spec. Use only synthetic or approved non-sensitive domains. Artifact directories are user-selected; review them before sharing.
- Python and DuckDB version changes may affect SQL behavior. The exact tested environment is recorded in each result and CI exercises Linux/macOS on Python 3.11/3.12 once its workflow runs.

The strongest open correctness risks are a SQLGlot AST change not caught by the guard, an SMT/DuckDB mismatch in an untested boundary case, and an untested platform-specific DuckDB behavior. Adversarial, exhaustive and replay tests reduce these risks but do not eliminate them.
