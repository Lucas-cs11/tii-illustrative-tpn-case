# SCG successor fix — status after the first patch attempt

Branch/commit: `scg-urgency-fix` merged into `main`; run 42322143218.

## What was done

A minimal intersection was inserted at the top of `_compute_successor`
(`src/scg/builder.py`): the current zone is intersected with

    earliest(t) <= x_t <= latest(t)
    x_w - x_t <= latest(w) - earliest(t)      for every other enabled w

then closed, and emptiness is checked before the shift.

## Result: the patch is NOT sufficient (Test A still fails)

| Test | Expectation | Observed | Verdict |
|---|---|---|---|
| A urgent conflict (`normal=[2,3]`, `fault=[0,1]`) | no successor via `t_normal` | **1 successor via `t_normal`** | **FAIL** |
| B valid conflict (`normal=[2,3]`, `fault=[1,3]`) | both successors | 1 + 1 | PASS |
| C persistent clocks | >= 2 classes | 3 classes / 3 edges | PASS |
| E fault completion | feasible | feasible | PASS |
| F first-entry completion | normal + partial | both, 10 observables | PASS |
| Industrial model SCG | finite | **50,001 classes / 57,072 edges (cap)** | FAIL |

## Why the intersection is insufficient — formal reason

The delay `d` between the class reference and the firing instant is not a variable of the
current zone: the zone constrains the ages `x_u` (time since each transition's enabling),
not the class time. Firing `t` after a delay `d` moves the ages to `x_u + d`, and the
strong-time rule is

    x_u + d <= latest(u)   for every enabled u   and   earliest(t) <= x_t + d <= latest(t).

Those constraints involve `d`, which does not exist in the zone. Adding
`x_w - x_t <= latest(w) - earliest(t)` is a *necessary but not sufficient* relaxation
because it silently replaces `d` by `earliest(t)`. In model A it admits the point
`x_normal = 2, x_fault = 1`, which has already passed the fault's deadline and is therefore
not a legal firing point.

## Correct algorithm required

1. Introduce the auxiliary variable `d` (delay from the class reference) into the zone.
2. Intersect with `d <= latest(u) - x_u` for all `u in E` and
   `earliest(t) - x_t <= d <= latest(t) - x_t`.
3. Substitute `x_u := x_u + d` for persistent `u`, `x_v := 0` for newly enabled `v`.
4. **Project out `d`** (Fourier-Motzkin / DBM variable elimination with closure), then
   normalize, then check emptiness.
5. Recompute the enabled set from the new marking and keep the persistent/newly-enabled
   distinction for the clocks.

The current `_compute_successor` has neither the auxiliary variable nor a projection step;
its "shift" copies differences instead. That is the structural defect, not a missing
`latest` comparison.

## Consequence

`SCG_CORRECTNESS_PASS = FAIL`; `INDUSTRIAL_MODEL_VERDICT_PASS = FAIL` (still INC at the
class cap); `READY_FOR_IEEE_TII = NOT_READY`. No VER/AMB result may be reported from this
engine.

## Coordination with Scalability v5/v6

The Scalability repositories use a copy of the same `src/scg/builder.py`. They must not be
patched by copying this branch: the patch is demonstrated insufficient by Test A. The shared
regression tests (`scripts/scg_regression.py`, tests A-F) are the contract to run in both
repositories once a correct fire-and-project implementation exists.
