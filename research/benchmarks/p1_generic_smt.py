"""Research-only, generic bounded bag-relational SMT interpreter for NoUndo.

This module deliberately does not import the production NoUndo solver. Input
parsing is shared; relational and aggregate semantics are encoded separately.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import z3

from dataproof.ir import Aggregate, Query
from dataproof.models import Row, Spec, Value


@dataclass(frozen=True)
class Result:
    status: str
    worlds: tuple[tuple[Row, ...], tuple[Row, ...]] | None = None
    reason_code: str | None = None


@dataclass(frozen=True)
class Cell:
    null: z3.BoolRef
    value: z3.ArithRef


@dataclass(frozen=True)
class TupleSlot:
    present: z3.BoolRef
    fields: tuple[Cell, ...]


@dataclass(frozen=True)
class World:
    slots: tuple[TupleSlot, ...]


def _or(parts: list[z3.BoolRef]) -> z3.BoolRef:
    return z3.Or(*parts) if parts else z3.BoolVal(False)


def _sum(parts: list[z3.ArithRef]) -> z3.ArithRef:
    return z3.Sum(*parts) if parts else z3.IntVal(0)


def _value(value: Value) -> int:
    if isinstance(value, date):
        return value.toordinal()
    if type(value) is int:
        return value
    raise ValueError("non-null domain value must be INTEGER or DATE")


def _same(a: Cell, b: Cell) -> z3.BoolRef:
    return z3.And(a.null == b.null, z3.Implies(z3.Not(a.null), a.value == b.value))


def _different(a: Cell, b: Cell) -> z3.BoolRef:
    return z3.Not(_same(a, b))


def _row_equal(a: TupleSlot, b: TupleSlot) -> z3.BoolRef:
    return z3.And(*(_same(x, y) for x, y in zip(a.fields, b.fields, strict=True)))


def _domain_rank(spec: Spec, column_index: int, cell: Cell) -> z3.ArithRef:
    """Objective-only rank in the input domain's order, including NULL."""
    rank: z3.ArithRef = z3.IntVal(0)
    for index, entry in reversed(list(enumerate(spec.columns[column_index].domain))):
        hit = cell.null if entry is None else z3.And(z3.Not(cell.null), cell.value == _value(entry))
        rank = z3.If(hit, index, rank)
    return rank


def _world(engine: Any, spec: Spec, label: str) -> World:
    slots: list[TupleSlot] = []
    for i in range(spec.max_rows):
        present = z3.Bool(f"{label}_present_{i}")
        if i:
            engine.add(z3.Implies(present, slots[-1].present))
        fields: list[Cell] = []
        for j, column in enumerate(spec.columns):
            cell = Cell(z3.Bool(f"{label}_{i}_{j}_null"), z3.Int(f"{label}_{i}_{j}_value"))
            allowed = [
                cell.null
                if entry is None
                else z3.And(z3.Not(cell.null), cell.value == _value(entry))
                for entry in column.domain
            ]
            engine.add(z3.Implies(present, _or(allowed)))
            first = column.domain[0]
            engine.add(z3.Implies(z3.Not(present), cell.null == (first is None)))
            engine.add(
                z3.Implies(z3.Not(present), cell.value == (0 if first is None else _value(first)))
            )
            engine.add(z3.Implies(z3.And(present, cell.null), cell.value == 0))
            fields.append(cell)
        slots.append(TupleSlot(present, tuple(fields)))
    for key in ((spec.primary_key,) if spec.primary_key else ()) + spec.unique:
        indices = tuple(spec.names.index(name) for name in key)
        for i, left in enumerate(slots):
            for right in slots[i + 1 :]:
                both_nonnull = z3.And(
                    left.present,
                    right.present,
                    *(z3.Not(left.fields[k].null) for k in indices),
                    *(z3.Not(right.fields[k].null) for k in indices),
                )
                engine.add(
                    z3.Implies(
                        both_nonnull,
                        _or([left.fields[k].value != right.fields[k].value for k in indices]),
                    )
                )
    return World(tuple(slots))


def _select(spec: Spec, world: World, query: Query) -> tuple[TupleSlot, ...]:
    if query.predicate is None:
        return world.slots
    pred = query.predicate
    idx = spec.names.index(pred.column)
    selected: list[TupleSlot] = []
    for slot in world.slots:
        cell = slot.fields[idx]
        if pred.kind == "eq":
            assert type(pred.value) is int
            keep = z3.And(z3.Not(cell.null), cell.value == pred.value)
        elif pred.kind == "is_null":
            keep = cell.null
        elif pred.kind == "is_not_null":
            keep = z3.Not(cell.null)
        else:
            raise ValueError("unsupported predicate IR")
        selected.append(TupleSlot(z3.And(slot.present, keep), slot.fields))
    return tuple(selected)


def _aggregate(spec: Spec, rows: tuple[TupleSlot, ...], agg: Aggregate) -> Cell:
    if agg.kind == "count_star":
        return Cell(z3.BoolVal(False), _sum([z3.If(row.present, 1, 0) for row in rows]))
    assert agg.column is not None
    idx = spec.names.index(agg.column)
    nonnull = [z3.And(row.present, z3.Not(row.fields[idx].null)) for row in rows]
    if agg.kind == "count":
        return Cell(z3.BoolVal(False), _sum([z3.If(on, 1, 0) for on in nonnull]))
    if agg.kind == "count_distinct":
        firsts = [
            z3.And(
                on,
                *(
                    z3.Not(z3.And(nonnull[j], row.fields[idx].value == rows[j].fields[idx].value))
                    for j in range(i)
                ),
            )
            for i, (row, on) in enumerate(zip(rows, nonnull, strict=True))
        ]
        return Cell(z3.BoolVal(False), _sum([z3.If(on, 1, 0) for on in firsts]))
    any_value = _or(nonnull)
    if agg.kind == "sum":
        return Cell(
            z3.Not(any_value),
            _sum(
                [z3.If(on, row.fields[idx].value, 0) for row, on in zip(rows, nonnull, strict=True)]
            ),
        )
    if agg.kind in {"min", "max"}:
        current: z3.ArithRef = z3.IntVal(0)
        seen: z3.BoolRef = z3.BoolVal(False)
        for row, on in zip(rows, nonnull, strict=True):
            value = row.fields[idx].value
            better = value < current if agg.kind == "min" else value > current
            current = z3.If(
                on, z3.If(z3.And(seen, better), value, z3.If(seen, current, value)), current
            )
            seen = z3.Or(seen, on)
        return Cell(z3.Not(seen), current)
    raise ValueError("unsupported aggregate IR")


def _group(spec: Spec, rows: tuple[TupleSlot, ...], query: Query) -> tuple[TupleSlot, ...]:
    assert query.group_by is not None
    group_idx = spec.names.index(query.group_by)
    output: list[TupleSlot] = []
    for i, anchor in enumerate(rows):
        group_key = anchor.fields[group_idx]
        first = z3.And(
            anchor.present,
            *(
                z3.Not(z3.And(prior.present, _same(prior.fields[group_idx], group_key)))
                for prior in rows[:i]
            ),
        )
        members = tuple(
            TupleSlot(z3.And(row.present, _same(row.fields[group_idx], group_key)), row.fields)
            for row in rows
        )
        fields = tuple(
            group_key
            if projection.aggregate is None
            else _aggregate(spec, members, projection.aggregate)
            for projection in query.projections
        )
        output.append(TupleSlot(first, fields))
    return tuple(output)


def _bag_equal(left: tuple[TupleSlot, ...], right: tuple[TupleSlot, ...]) -> z3.BoolRef:
    clauses: list[z3.BoolRef] = []
    for anchor in (*left, *right):
        lcount = _sum([z3.If(z3.And(row.present, _row_equal(row, anchor)), 1, 0) for row in left])
        rcount = _sum([z3.If(z3.And(row.present, _row_equal(row, anchor)), 1, 0) for row in right])
        clauses.append(z3.Implies(anchor.present, lcount == rcount))
    return z3.And(*clauses)


def _objectives(engine: z3.Optimize, spec: Spec, left: World, right: World) -> None:
    engine.set("priority", "lex")
    engine.minimize(
        _sum([z3.If(slot.present, 1, 0) for world in (left, right) for slot in world.slots])
    )
    engine.minimize(_sum([z3.If(slot.present, 1, 0) for slot in left.slots]))
    for world in (left, right):
        for slot in world.slots:
            for j, cell in enumerate(slot.fields):
                engine.minimize(_domain_rank(spec, j, cell))


def search(spec: Spec, view: Query, metric: Query, *, optimize: bool = True) -> Result:
    """Return only bounded SAT/UNSAT or fail closed; no replay claim is made here."""
    try:
        return _search(spec, view, metric, optimize=optimize)
    except MemoryError:
        return Result("INCONCLUSIVE", reason_code="MEMORY_LIMIT")
    except Exception:
        return Result("INCONCLUSIVE", reason_code="SOLVER_ERROR")


def _search(spec: Spec, view: Query, metric: Query, *, optimize: bool) -> Result:
    z3.set_param("memory_max_size", spec.max_memory_mb)
    engine: Any = z3.Optimize() if optimize else z3.Solver()
    engine.set("timeout", spec.timeout_ms)
    left = _world(engine, spec, "generic_left")
    right = _world(engine, spec, "generic_right")
    engine.add(
        _bag_equal(
            _group(spec, _select(spec, left, view), view),
            _group(spec, _select(spec, right, view), view),
        )
    )
    metric_agg = metric.projections[0].aggregate
    assert metric_agg is not None
    engine.add(
        _different(
            _aggregate(spec, _select(spec, left, metric), metric_agg),
            _aggregate(spec, _select(spec, right, metric), metric_agg),
        )
    )
    if optimize:
        _objectives(engine, spec, left, right)
    outcome = engine.check()
    if outcome == z3.unsat:
        return Result("BOUNDED_NO_COUNTEREXAMPLE")
    if outcome == z3.unknown:
        reason = engine.reason_unknown().lower()
        code = (
            "MEMORY_LIMIT"
            if "memory" in reason
            else "TIMEOUT"
            if "timeout" in reason or "canceled" in reason
            else "UNKNOWN"
        )
        return Result("INCONCLUSIVE", reason_code=code)
    if outcome != z3.sat:
        return Result("INCONCLUSIVE", reason_code="SOLVER_ERROR")
    model = engine.model()

    def decode(world: World) -> tuple[Row, ...]:
        decoded: list[Row] = []
        for slot in world.slots:
            if not z3.is_true(model.eval(slot.present, model_completion=True)):
                continue
            values: list[Value] = []
            for col, cell in zip(spec.columns, slot.fields, strict=True):
                if z3.is_true(model.eval(cell.null, model_completion=True)):
                    values.append(None)
                else:
                    integer = model.eval(cell.value, model_completion=True).as_long()
                    values.append(date.fromordinal(integer) if col.type == "DATE" else integer)
            decoded.append(tuple(values))
        return tuple(decoded)

    return Result("CANDIDATE", (decode(left), decode(right)))
