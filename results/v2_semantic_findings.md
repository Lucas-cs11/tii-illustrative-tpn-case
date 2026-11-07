# v2 semantic findings (P0-A / P0-B / P0-C)

Run 42320268951 (GitHub Actions), model commit as pushed.

## P0-A the fault really was forced

| Test | Model | Result |
|---|---|---|
| A urgent conflict | `t_normal=[2,3]`, `t_fault=[0,1]`, both enabled from `p_loading` | normal-without-fault **infeasible**, fault **forced** |
| B valid conflict | `t_normal=[2,3]`, `t_fault=[1,3]` | normal feasible (fires at 2) and fault feasible (fires at 1) |

The independent strong-time executor (fractional clocks, urgency rule "no enabled transition
may pass its latest firing time") reproduces exactly the defect that the report described:
with the v1 interval the normal loading branch cannot fire before the fault deadline.

Fix applied in `scripts/model_case.py`: `t_GripperSlipFault = [1,3]`, fault remains
unobservable, robot token released by the fault and re-acquired by the recovery transition.

## P0-C first-entry completion

Completion marking reduced to the two-workpiece marking only
(`p_completed=2`, robot/machine/inspection free); `p_completed=1` is now an ordinary progress
marking. The executor confirms:

| Property | Result |
|---|---|
| normal completion feasible | yes, 20 firings, **10 observable events** |
| fault completion feasible | yes, 22 firings |
| rework path reachable | yes |
| partial completion reachable (but not terminal) | yes |

The 10 observable events match the structural minimum of the two-workpiece no-rework run, so
the formal `L` must be at least 10; the earlier `L = 3..6` sweep was meaningless.

## P0-B SCG builder accepts infeasible successors

`build_scg` on the A model returns 3 classes and 2 edges from the initial class, i.e. it
accepts the `t_normal` successor even though the strong-time executor proves that firing
infeasible. The same happens on B (where both are genuinely feasible, so B alone would not
reveal the defect). `_compute_successor` therefore lacks the urgency check (the
latest-firing-time constraint of the other enabled transitions is not enforced when the
successor zone is built).

This must be repaired with regression tests A-F before any VER/AMB verdict is produced; the
current verifier results on the industrial model (`INC` at the class cap) remain unpublished
for that reason.

## Status of the v2 gates

| Gate | Verdict |
|---|---|
| MODEL_SEMANTICS_PASS | **PASS WITH LIMITATIONS** (fault forced defect fixed and witnessed; SCG successor defect identified) |
| NORMAL_AND_FAULT_COMPLETION_PASS | **PASS** (10-observable normal run, fault run, rework reachable) |
| SCG_CORRECTNESS_PASS | **FAIL** (builder over-approximates; not yet patched) |
| SCG_FINITE_AND_ANALYZABLE | **FAIL** (class cap at 50,001) |
| BOUNDED_VERDICT_PASS | **FAIL** (INC only) |
| ADJUSTMENT_DEMONSTRATED | **NOT_DEMONSTRATED** |
| READY_FOR_IEEE_TII | **NOT_READY** |

Next steps in order: patch `_compute_successor` in an isolated branch, add tests A-F,
re-run structural + bounded verdicts at `L >= 10`, then the V0-V3 controlled variants.
