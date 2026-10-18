# DataProof

**Can your saved daily summaries still answer a monthly question?** Two synthetic order tables can have the same daily order count, revenue and distinct-customer count while their monthly distinct-customer counts are **1 and 2**. DataProof's first NoUndo slice searches for such a pair, then independently runs the original SQL in DuckDB and writes a replayable witness.

```text
V(D1) == V(D2)   but   Q(D1) != Q(D2)
```

The witness shows that the declared retained view does not determine the KPI under the stated schema and constraints. It does not show that backups or source records have been deleted. This is an early, deliberately limited research implementation.

## Run the local example

Python 3.11 or newer is required. Package acquisition may require a network once; the installed core runs locally without an account, API key, cloud service or LLM.

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/dataproof check examples/no_undo/daily_distinct.json --output artifacts/demo
.venv/bin/dataproof replay artifacts/demo/witness.json
```

Representative output from the tested macOS/Python 3.11 environment:

```text
COUNTEREXAMPLE_FOUND
witness: artifacts/demo/witness.json
replay SQL: artifacts/demo/replay.sql
COUNTEREXAMPLE_FOUND
```

The JSON reports both world tables, equal retained view rows, monthly metrics `1` and `2`, assumptions, bounds, seed, versions and a world hash. `replay.sql` can also run directly in DuckDB and ends with `REPLAY_OK`. The included [example specification](examples/no_undo/daily_distinct.json) and [versioned witness](examples/no_undo/evidence/witness.json) are entirely synthetic. `dataproof check ... --json` prints the machine-readable result.

Repeated checks may use the same `--output` directory. DataProof records hashes of its own fixed-name artifacts in `.dataproof-owned.json`; before a new run it clears only unchanged, recorded files. A non-counterexample run leaves no `witness.json` or `replay.sql`, and unrelated files are preserved. If a reserved artifact name is unowned or modified, the check refuses that directory rather than deleting the file. For output directories created by earlier DataProof versions without the ownership record, choose a fresh directory and archive the old evidence separately. For a malformed specification whose embedded `output_dir` cannot be parsed, pass `--output` explicitly if the previous artifacts should be cleared; otherwise DataProof cannot safely infer which directory to touch. Do not run simultaneous checks against one output directory.

Two counterchecks are included:

```sh
.venv/bin/dataproof check examples/no_undo/constrained_customer.json
.venv/bin/dataproof check examples/no_undo/daily_sum.json
```

Both currently return `BOUNDED_NO_COUNTEREXAMPLE` (exit code 3). The first forbids a customer appearing twice; the second retains daily SUM values. These are finite-bound findings, **not universal preservation proofs**. No `PROVEN_WITHIN_FRAGMENT` implementation ships.

## Find a declared test blind spot

Doppelgänger is a separate, one-dataset check. The example explicitly declares that settled orders must not have negative amounts, while its existing test checks only that at least one order exists. DataProof searches for a *synthetic* dataset where that test is SQL TRUE and the independent invariant is SQL FALSE:

```sh
.venv/bin/dataproof doppelganger check examples/doppelganger/nonnegative_amount.json --output artifacts/doppel-demo
.venv/bin/dataproof doppelganger replay artifacts/doppel-demo/witness.json
```

The admitted witness is one row with `amount = -1`; DuckDB independently checks the source assertions and the generated SQL ends in `REPLAY_OK`. A [versioned synthetic witness](examples/doppelganger/evidence/witness.json) and [replay SQL](examples/doppelganger/evidence/replay.sql) are included. The rationale is supplied by the user, not inferred by DataProof. See the [Doppelgänger contract and acceptance matrix](docs/doppelganger.md). A bounded miss (`BOUNDED_NO_BLIND_SPOT`, exit 3) is not proof of test adequacy; `INCONSISTENT_TESTS` (exit 9) means the declared tests have no legal passing dataset in this finite scope. SQL UNKNOWN is neither a passing test nor a confirmed invariant failure. Unsupported SQL and failed replay never produce a successful finding.

## Scope and evidence

The admitted fragment is a single synthetic table with finite `INTEGER`/`DATE` domains, at most three rows per world, one grouped aggregate view and one scalar aggregate metric. Aggregates are `COUNT(*)`, `COUNT(column)`, `COUNT(DISTINCT column)`, exact integer `SUM`, and direct integer `MIN`/`MAX`. Each query may have one guarded row filter: integer-column equality to a signed integer literal, `IS NULL`, or `IS NOT NULL`. NULL, duplicate bags and empty inputs are handled in this fragment. SQLGlot parses and checks the guarded IR; Z3 searches; independent DuckDB execution accepts or rejects the serialized candidate. Unsupported joins, compound filters, windows, UDFs, approximate arithmetic, other dialects and data-changing SQL fail closed. See [semantics](docs/semantics.md), [limitations](docs/limitations.md), and [architecture](docs/architecture.md).

Statuses and exit codes: `COUNTEREXAMPLE_FOUND` 0; `BOUNDED_NO_COUNTEREXAMPLE` 3; `INCONCLUSIVE` timeout or solver-memory limit 4, other solver/backend errors or UNKNOWN 8 (distinguished by `reason_code`); `UNSUPPORTED` 5; malformed SQL or other `INVALID_INPUT` 6; `INVALID_CANDIDATE` 7. `PROVEN_WITHIN_FRAGMENT` is reserved and is never emitted by this slice. The JSON result uses `schema_version: 1`.

Run the tests and reproduce a local research manifest:

```sh
.venv/bin/python -m pip install '.[dev]'
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src
.venv/bin/pytest -q
.venv/bin/pip-audit --local --skip-editable --progress-spinner off
PYTHONPATH=src .venv/bin/python research/benchmarks/run_phase1.py examples/no_undo/daily_distinct.json --run-dir research/runs/local/my-run
PYTHONPATH=src .venv/bin/python research/benchmarks/compare_tiny_reference.py examples/no_undo/daily_distinct.json --repeats 5 --output research/runs/local/paired.json
```

The run manifest records exact input hash, seed, versions, Git state, machine metadata, elapsed time, exit code and replay paths. The [public evidence index](research/README.md) links the sanitized, commit-pinned Phase 2 and Phase 3 records, the benchmark protocol, and the limited claims they support. These records are not external performance comparisons. The [research protocol](research/protocols/phase1.md), [claims ledger](research/claims_ledger.md), and [prior art](docs/prior-art.md) document the evidence and open limitations. VeriEQL and query-identifiability already address related verification or identifiability problems; DataProof's scientific originality remains unverified.

## Project stage

Phases 0–3 established the NoUndo verifier; the Phase 4 Doppelgänger slice adds the explicitly declared test-blind-spot workflow above. Other analyses are not part of the installed tool. See the [roadmap](docs/roadmap.md). Contributions and review are welcome under the [MIT license](LICENSE) and [contributor guide](CONTRIBUTING.md).

For a short live walkthrough after installation, use the [offline demo cue sheet](docs/demo.md); it calls only the shipped CLI and does not rely on a staged recording.
