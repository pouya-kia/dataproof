# Paper 1: independent generic SMT baseline — frozen candidate protocol

Status: implementation-only preregistration candidate. **No comparison has run.**
The case-status and minimum-row entries below are hypotheses, never selection rules.
The study requires separate explicit authorization after independent code review and
a clean, committed, hash-verified source snapshot. It is not Phase 6.

## Obligation and comparison

For each specification, both methods solve exactly
`Sigma(D1) AND Sigma(D2) AND V(D1)=bag V(D2) AND Q(D1)!=NULL-aware Q(D2)`.
Each world is an independent 0–`max_rows` source-row bag over the declared finite
INTEGER/DATE domains and constraints. The primary pair is deployed NoUndo
`Optimize` against an independently implemented generic bag-relational
`Optimize`. Both use the same ordered lexicographic objectives: total active
rows; left active rows; each finite-domain cell index in left/right, row-slot,
column order. Inactive cells rank as domain index zero. The optional generic
plain `Solver` is a *separate, secondary* decision-only diagnostic and is
not in the primary scheduled comparison. It cannot be used to claim a NoUndo
speedup over an optimizing method. Shared input parsing and schema validation
are correlated-error risks; original SQL is executed independently in DuckDB.

## Frozen candidate case matrix

`I` means INTEGER, `D` means DATE, `?` means nullable; domains are **ordered**
and explicitly include NULL where present. Every case uses table `t`, one view
and one scalar KPI. `n` is maximum rows **per world**. `M` is the product of
effective domain sizes, and `W=comb(M+n,n)` is an analytical bag-world upper
bound; PK/UNIQUE can reduce the legal count. All W values are below the
10,000-world enumerator cutoff. SQL strings below are literal fixture text.

| ID | Ordered columns; constraint; n; M; W | Retained view SQL | KPI SQL | Hypothesized status/minimum total rows; purpose |
| --- | --- | --- | --- | --- |
| P1 | `g I[1,2], x I[1,2]`; none; 1; 4; 5 | `SELECT g, COUNT(*) AS n FROM t GROUP BY g` | `SELECT SUM(x) AS q FROM t` | SAT/2; easy control. |
| A1 | `g I[1], x I?[NULL]`; none; 2; 1; 3 | `SELECT g, COUNT(*) AS n FROM t GROUP BY g` | `SELECT SUM(x) AS q FROM t` | bounded-negative; empty/all-NULL control. |
| N1 | `g I[1], x I?[1,NULL]`; none; 1; 2; 3 | `SELECT g, COUNT(*) AS n FROM t GROUP BY g` | `SELECT SUM(x) AS q FROM t` | SAT/2; NULL-aware KPI. |
| B1 | `g I[1], x I[1,2]`; none; 2; 2; 6 | `SELECT g, COUNT(DISTINCT x) AS d FROM t GROUP BY g` | `SELECT COUNT(*) AS q FROM t` | SAT/3; duplicate bags. |
| E1 | `g I[1], x I[1,2]`; none; 1; 2; 3 | `SELECT g, COUNT(*) AS n FROM t WHERE x = 1 GROUP BY g` | `SELECT COUNT(*) AS q FROM t` | SAT/1; empty versus filtered row. |
| NG | `g I?[1,NULL], x I[1,2], a I[-1,0,1,2]`; none; 3; 16; 969 | `SELECT g, COUNT(*) AS n, SUM(a) AS s FROM t GROUP BY g` | `SELECT SUM(x) AS q FROM t WHERE g IS NULL` | SAT/2; necessary NULL grouping. |
| DA | `g D['2026-01-01','2026-01-02'], x I[1,2,3,4], a I[0,1]`; none; 3; 16; 969 | `SELECT g, COUNT(*) AS n, SUM(a) AS s FROM t GROUP BY g` | `SELECT COUNT(DISTINCT x) AS q FROM t` | SAT/4; DATE and distinctness. |
| SR | `g I[1,2], x I?[-1,1,NULL], a I[0,1]`; none; 3; 12; 455 | `SELECT g, SUM(x) AS s FROM t GROUP BY g` | `SELECT SUM(x) AS q FROM t` | bounded-negative; SUM roll-up. |
| MP | `g I[1,2], x I[-2,-1,1,2], a I[0,1]`; none; 3; 16; 969 | `SELECT g, COUNT(*) AS n FROM t GROUP BY g` | `SELECT MIN(x) AS q FROM t` | SAT/2; MIN. |
| XR | `g I[1,2], x I?[-1,0,2,NULL], a I[0,1]`; none; 3; 16; 969 | `SELECT g, MAX(x) AS m FROM t WHERE x IS NOT NULL GROUP BY g` | `SELECT MAX(x) AS q FROM t WHERE x IS NOT NULL` | bounded-negative; MAX and `IS NOT NULL`. |
| PK | `g I[1,2,3], x I[1,2], a I[0,1]`; `PK(g)`; 3; 12; ≤455 | `SELECT g, COUNT(*) AS n, SUM(a) AS s FROM t GROUP BY g` | `SELECT SUM(x) AS q FROM t` | SAT/2; primary key in both worlds. |
| UQ | `g I[1,2], u I?[1,2,NULL], a I[0,1]`; `UNIQUE(u)`; 3; 12; ≤455 | `SELECT g, COUNT(DISTINCT u) AS d FROM t GROUP BY g` | `SELECT COUNT(*) AS q FROM t` | SAT/3; nullable UNIQUE. |
| GE | `g I[1,2], x I[1,2,3,4], a I[0,1]`; none; 3; 16; 969 | `SELECT g, COUNT(*) AS n FROM t WHERE x = 1 GROUP BY g` | `SELECT SUM(a) AS q FROM t WHERE x = 1` | SAT/2; matched equality guards. |
| IN | `g I[1,2], x I?[1,2,NULL], a I[0,1,2]`; none; 3; 18; 1330 | `SELECT g, COUNT(*) AS n FROM t WHERE x IS NULL GROUP BY g` | `SELECT COUNT(*) AS q FROM t WHERE x IS NULL` | bounded-negative; `IS NULL` roll-up. |
| CH | `g D['2026-01-01','2026-01-02'], x I[1,2,3], a I?[-1,0,1,NULL]`; none; 3; 24; 2925 | `SELECT g, COUNT(*) AS n, SUM(a) AS s, COUNT(DISTINCT x) AS d FROM t GROUP BY g` | `SELECT COUNT(DISTINCT a) AS q FROM t` | SAT/4; combined largest case. |

The five small cases are correctness controls. The other ten are the
prespecified medium/larger performance stratum. A larger world bound does
not imply a hard SMT instance. No hypothesis may be used to alter, exclude
or select a case after observing an outcome. Parser/schema validation is
allowed before execution; solver or exhaustive outcomes are not.

## Execution schedule and resources — only after separate authorization

First verify source commit, clean tracked tree, protocol/case SHA-256, and a
new output directory under ignored `research/runs/local/`. The run writes
one DuckDB-exhaustive oracle trial per case, then ten fresh-process trials
per primary method per case: 15 oracle + 150 NoUndo + 150 generic = **315**
records. Repetition indices 0–9 pair the two methods on the same case.
Even indices run NoUndo then generic; odd indices reverse the order.
The runs are deterministic timing repetitions, **not independent discovery
trials**. No runs are selected for omission or replacement.

Both primary methods receive the same 10,000 ms Z3 timeout and 256 MiB
Z3 memory setting from each fixture, plus an enforced 20 s process wall
deadline. An OS-level RSS ceiling is **not currently enforced** and must
not be claimed. The reference process has a separate 300 s wall deadline;
it is not part of either solver timing. Its full world count, status and
failure reason remain in the record. Both methods use the same worker
boundary: parent clock starts immediately before a fresh child launch and
ends after parsing, `Optimize`, model decoding, DuckDB validation of any
SAT candidate, and child result receipt. This is research-worker end-to-end
latency, not packaged CLI latency. NoUndo does not expose formulation or
check phase times: these fields are `NOT_MEASURED` (JSON null) for both
primary methods, never inferred via monkeypatching. Peak RSS is observed,
not an equivalent enforced limit.

Every positive witness must pass DuckDB replay. Exhaustive ground truth
executes original SQL on every enumerated legal world, compares complete
typed view bags with multiplicities, and compares NULL-aware scalar KPI
values. It completes all worlds before claiming bounded UNSAT or a minimum
total row cost. Existing independent-Python `reference_search` is a further
cross-check. A failed/incomplete oracle makes ground truth unresolved.
SAT/UNSAT disagreement, invalid candidate, wrong minimum, timeout, unknown,
exception, or replay/reference disagreement remains in the raw stream.
Recording completeness is not scientific validity. No case or repetition is
excluded from raw or descriptive reports.

## Primary endpoints and prespecified interpretation

For each method/case: exact status, confirmed witness rate (out of ten
deterministic repetitions), minimum total witness rows versus oracle,
end-to-end time distribution and all failures. For every repetition index
`i`, pair generic and NoUndo times and define `delta_i = generic_i - noundo_i`.
`median_delta = median(delta_i)`, and paired-difference
`MAD = median(abs(delta_i - median_delta))`; calculate medians by the
ordinary midpoint rule for even sample sizes. The per-case relative ratio
is `median(generic_i)/median(noundo_i)`; do not use the median of individual
ratios. A NoUndo qualifying win requires this ratio ≥1.5, median_delta ≥
`max(0.020 seconds, 3*MAD)`, and at least 8 of ten `delta_i > 0`.
Generic wins use the exactly symmetric rule. Ratios are undefined if a
required run failed or timed out; such cases cannot qualify and are reported
separately. The corpus-level within-study gate requires qualifying NoUndo
wins on at least four of the ten medium/larger cases, including a bounded-
negative case, **no opposing qualifying win**, and no correctness failure.
The same gate applies symmetrically to generic. Failure to meet a gate is
`NO_DEMONSTRATED_ADVANTAGE`, not a statistical equivalence result.

These are proposed practical engineering thresholds, not inferred effects,
population confidence claims, or proof of algorithmic novelty. If generic
matches correctness and NoUndo has no prespecified advantage, set aside the
present algorithmic-paper claim. A qualifying result still needs broader
sampling, exact external-tool baselines, and mathematical contribution
analysis before any publication claim.

## Recording, privacy and threats

Record source and protocol/case digests, software versions, method/order,
all 315 outcomes, sanitized synthetic witness rows, full statuses, reason
codes, timings, RSS units and minimum-row checks as JSONL. Never copy child
stdout/stderr, traceback, machine-specific identifiers, absolute paths,
credentials, or private notes into records. Raw local output is ignored by
Git; publication requires a separate sanitation/review step. A completion
marker is written atomically only after identity/hash/coverage validation.
If interrupted, preserve the partial stream and do not silently rerun.

Threats: shared parsing and legality checks, finite synthetic hand selection,
small row/domain caps, deterministic repetition, order/cache/OS noise,
DuckDB version dependence, Z3 optimization heuristics, unenforced outer
memory cap, and unequal package-CLI overhead outside the common worker.
VeriEQL compatibility and wider SQL are outside this study.
