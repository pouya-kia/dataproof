# Phase gates and test impact

## Phase 0

Review repository state, source links, exact grammar, statuses, research hypothesis, baseline feasibility and license notes. Check Markdown references and `git diff --check`. No code behavior is claimed. The baseline gate records executable attempts and failures, rather than silently treating a README as a run.

## Phase 1

After each edit, run the focused test and affected regression set. Before a commit or push run `ruff check .`, `ruff format --check .`, `mypy src`, `pytest`, `pip-audit --local --progress-spinner off`, wheel build, clean venv install, CLI example, generated SQL replay, `git diff --check`, and a file/secret/license review. CI covers Python 3.11 and 3.12 on Linux and macOS once its workflow is live. Failed, skipped without reason, flaky, or inconclusive mandatory gates stop commit and push.

| Changed contract | Focused checks | All affected regressions |
| --- | --- | --- |
| Input/schema/constraints | model and negative tests | search, legal worlds, replay, CLI, fixtures |
| Parser/IR | parser/type tests | search, oracle, replay, eight fixtures, CLI |
| Search encoding | solver tests | exhaustive reference, adversarial/property cases, replay, status mapping |
| Oracle | tiny-domain tests | solver agreement, fixtures, research harness |
| Replay/serialization | replay tests | golden JSON, SQL execution, invalid candidate, CLI |
| CLI/status/report | CLI tests | exit codes, golden output, docs commands, clean install |
| Dependencies/package/CI | build/config checks | full suite, clean install, offline demo |

The core eight scenarios are versioned in `tests/fixtures/core_cases.json`: overlapping versus disjoint customers; constrained cross-day uniqueness; complete daily SUM roll-up as bounded only; NULL COUNT distinctions; duplicate bag rows; nullable SUM; invalid key; unsupported window SQL. Additional tests cover empty source/all-NULL SUM, destructive SQL, deterministic seeds, row permutation invariance where valid, deliberately wrong candidate rejection, and timeout/unknown outcomes. Future Phase 2 hardening expands randomized and mutation coverage; it does not weaken Phase 1 acceptance.

False claim threats: bounded UNSAT promoted to proof, a bad SMT aggregate encoding, a result comparison that drops duplicates, implicit casts, and replay SQL that does not assert every stated fact. The independent DuckDB executor and exhaustive tiny-domain reference must catch these before a witness can be published.
