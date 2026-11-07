# SCG successor defect — root cause (v2, branch `scg-urgency-fix`)

## Symptom

Model A (`t_normal=[2,3]`, `t_fault=[0,1]`, both enabled from the same marking):
the independent strong-time executor proves that firing `t_normal` first is infeasible,
while `build_scg` returns a class reachable by `t_normal` (3 classes, 2 edges).

## Where the defect lives

`src/scg/builder.py::_compute_successor` (the shifted-DBM block starting at the
`for u in persistent:` loop). The docstring states the correct intent, but the
implementation only shifts the persistent-variable differences:

    new_dbm[u][0] = old_dbm[u][t]
    new_dbm[0][u] = old_dbm[t][u]

and then builds newly-enabled constraints. What is missing is the **firing-time
window of the fired transition itself**, and with it the urgency of the transitions
that stay enabled.

## Formal statement

Let `E` be the set of transitions enabled in the state class with DBM `Z` over
variables `{0} ∪ E`, where `x_u` is the age of `u` since it became enabled and
`x_0 = 0` is the class reference.

Firing `t ∈ E` at a time point where `x_t = d` is legal under strong-time semantics iff

    (1)  earliest(t) ≤ d ≤ latest(t)                        (t may fire)
    (2)  for every w ∈ E, w ≠ t:  x_w(d) ≤ latest(w)          (no other enabled
                                                                transition is forced
                                                                past its deadline)

Constraint (2) is what "strong time" adds on top of weak time. In the DBM, `x_w(d)`
is `x_w - x_t + d` with `x_t = d`, so (2) is the difference constraint

    x_w - x_t ≤ latest(w) - d,   which combined with (1) gives, for the new reference,
    x_w' = x_w - x_t ≤ latest(w) - earliest(t).

Equivalently: before the shift, intersect `Z` with

    -x_t ≤ -earliest(t)          (x_t ≥ earliest(t))
    x_t ≤ latest(t)              (x_t ≤ latest(t))
    x_w - x_t ≤ latest(w) - earliest(t)   for all persistent w   (urgency)

and only then project/eliminate `x_t` by the shift. The current code performs the
shift on `Z` **without** these intersections, so any successor whose firing would
have violated (2) still yields a non-empty shifted zone and is accepted.

This is also why `t_fault` in model A had to fire first (its deadline 1 < earliest of
`t_normal` = 2): the executor sees the urgency, the SCG does not.

## Minimal patch (to be applied and regression-tested)

```python
# before building new_dbm
z = cls.dbm.copy()
z.set(t_name, "0", t_obj.interval.latest)          # x_t <= latest(t)
z.set("0", t_name, -t_obj.interval.earliest)        # x_t >= earliest(t)
for w in cls.enabled:
    if w == t_name:
        continue
    lw = tpn.transitions[w].interval.latest
    if lw is not None and lw != float("inf"):
        # x_w - x_t <= latest(w) - earliest(t)
        z.set(w, t_name, Fraction(lw) - t_obj.interval.earliest)
z.close()                                          # Floyd-Warshall closure
if z.is_empty():
    return None
```

Then the rest of the shift uses `z` instead of `cls.dbm`, followed by the existing
normalization. The closure must be recomputed after the added constraints (the code
must call the same `close()` used when the DBM is built) and emptiness must be checked
both before and after projection.

## Why a local `latest` test is not enough

Adding only `x_t ≤ latest(t)` does not remove the model-A successor, because the
infeasibility comes from the *other* transition's deadline (constraint (2)). Likewise,
checking emptiness only after normalization cannot recover the constraint that was
never inserted. Both the urgency intersection and a closure before projection are
required.

## Status

Patch not yet applied in this branch: it needs the DBM API (`copy`, `set`, `close`,
`is_empty`, projection) to be exercised by tests A–F and an independent exact oracle
before it can be trusted. The current verifier results on the industrial model must
therefore remain unpublished.
