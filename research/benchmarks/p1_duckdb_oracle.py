"""Exhaustive DuckDB evaluation over the existing legal-world enumerator.

The enumerator/schema parser are shared dependencies. SQL output semantics are
obtained by executing the original queries, not by the SMT or Python evaluator.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Any

import duckdb

from dataproof.models import Row, Spec
from dataproof.reference_enumerator import all_worlds


@dataclass(frozen=True)
class OracleResult:
    status: str
    worlds_checked: int
    minimum_rows: int | None
    witness: tuple[tuple[Row, ...], tuple[Row, ...]] | None
    reason_code: str | None = None


def _typed(value: Any) -> tuple[str, int | str | None]:
    if value is None:
        return ("NULL", None)
    if type(value) is int:
        return ("INTEGER", value)
    if isinstance(value, date):
        return ("DATE", value.isoformat())
    raise ValueError("DuckDB returned a value outside the admitted SQL fragment")


def canonical_bag(
    rows: tuple[tuple[Any, ...], ...],
) -> frozenset[tuple[tuple[tuple[str, int | str | None], ...], int]]:
    """A full typed multiset key; no lossy digest or set conversion."""
    occurrences = Counter(tuple(_typed(value) for value in row) for row in rows)
    return frozenset(occurrences.items())


def _create(con: duckdb.DuckDBPyConnection, spec: Spec) -> None:
    columns = [
        f'"{col.name}" {col.type}' + ("" if col.nullable else " NOT NULL") for col in spec.columns
    ]
    if spec.primary_key:
        columns.append("PRIMARY KEY (" + ", ".join(f'"{name}"' for name in spec.primary_key) + ")")
    for key in spec.unique:
        columns.append("UNIQUE (" + ", ".join(f'"{name}"' for name in key) + ")")
    con.execute(f'CREATE TABLE "{spec.table}" ({", ".join(columns)})')


def _load(con: duckdb.DuckDBPyConnection, spec: Spec, rows: tuple[Row, ...]) -> None:
    con.execute(f'DELETE FROM "{spec.table}"')
    placeholders = ", ".join("?" for _ in spec.columns)
    for row in rows:
        con.execute(f'INSERT INTO "{spec.table}" VALUES ({placeholders})', row)


def _evaluate(
    con: duckdb.DuckDBPyConnection, spec: Spec, rows: tuple[Row, ...]
) -> tuple[
    frozenset[tuple[tuple[tuple[str, int | str | None], ...], int]], tuple[str, int | str | None]
]:
    _load(con, spec, rows)
    view = tuple(tuple(row) for row in con.execute(spec.views[0]).fetchall())
    metric = con.execute(spec.metric).fetchall()
    if len(metric) != 1 or len(metric[0]) != 1:
        raise ValueError("metric did not return one scalar row")
    return canonical_bag(view), _typed(metric[0][0])


def evaluate(spec: Spec) -> OracleResult:
    """Complete every legal world before claiming SAT minimum or bounded UNSAT."""
    try:
        worlds = all_worlds(spec)  # Raises rather than silently truncating at 10,000.
    except (ValueError, MemoryError):
        return OracleResult("INCONCLUSIVE", 0, None, None, "ENUMERATION_LIMIT")
    con = duckdb.connect(":memory:", config={"enable_external_access": "false"})
    seen: dict[
        frozenset[tuple[tuple[tuple[str, int | str | None], ...], int]],
        dict[tuple[str, int | str | None], tuple[Row, ...]],
    ] = {}
    best: tuple[tuple[Row, ...], tuple[Row, ...]] | None = None
    minimum: int | None = None
    completed = 0
    try:
        _create(con, spec)
        for world in worlds:
            view_key, metric_key = _evaluate(con, spec, world)
            alternatives = seen.setdefault(view_key, {})
            for prior_metric, prior_world in alternatives.items():
                if prior_metric != metric_key:
                    cost = len(prior_world) + len(world)
                    if minimum is None or cost < minimum:
                        minimum = cost
                        best = (prior_world, world)
            if metric_key not in alternatives or len(world) < len(alternatives[metric_key]):
                alternatives[metric_key] = world
            completed += 1
    except (duckdb.Error, ValueError, MemoryError):
        return OracleResult("INCONCLUSIVE", completed, None, None, "ORACLE_ERROR")
    finally:
        con.close()
    return OracleResult(
        "COUNTEREXAMPLE_FOUND" if best is not None else "BOUNDED_NO_COUNTEREXAMPLE",
        completed,
        minimum,
        best,
    )
