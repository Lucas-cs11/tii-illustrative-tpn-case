# Illustrative industrial TPN — acceptance report

## Model (17 places / 15 transitions / 44 arcs)

Two anonymous workpieces, one shared robot, one machine, one inspection station,
a rework loop with strictly positive time, and one unobservable gripper-slip fault with
recovery. Plain P/T TPN under the paper's strong-time, single-server semantics.

| Item | Value |
|---|---|
| places | 17 (`results/places.csv`) |
| transitions | 15 (`results/transitions.csv`) |
| arcs | 44 (`results/arcs.csv`) |
| observable alphabet | inspection_pass, inspection_rework, load_done, machining_done, rework_returned, transfer_done, unload_done |
| fault transitions | `t_GripperSlipFault` (unobservable) |
| initial marking | `p_raw=2, p_robot_free=1, p_machine_free=1, p_inspection_free=1` |
| completion markings | first completion `p_completed=1` with `p_raw=1`; second `p_completed=2` |
| time intervals | all `ILLUSTRATIVE_ENGINEERING_PARAMETER`, seconds |

## Structural verification (GitHub Actions run 42227735951)

| Property | Result |
|---|---|
| reachable markings (untimed BFS) | 93 |
| deadlocks | **0** (a first version deadlocked because the gripper slip consumed the robot token without releasing it; found by reachability and fixed) |
| workpiece conservation (2 tokens) | 0 violations |
| robot / machine / inspection single-server | 0 violations |
| completion marking reachable | yes (2 completion markings hit) |
| zero-time cycle | none |
| state-space cap | not reached |

## Bounded verifier

Run 42227735951 and the bound sweep 42228311326 (48 configurations, `L = 3..6`,
`H = 24..48 s`, both certificate modes): **every configuration returns `INC` with the SCG
class cap reached (50,001 classes)**. No VER/AMB verdict and no critical pair can be
reported for this model as specified.

Cause: two jobs, seven observable labels, the rework loop and the fault branch produce a
combinatorial explosion of timed state classes before the horizon, and the verifier stops
at the class cap. This is a capacity limit of the bounded verifier on this structure, not a
diagnosability conclusion.

## Adjustment

Not demonstrated. All intervals are illustrative; no measurement of an authorised adjustment
range exists, so `ADJUSTMENT_NOT_ESTABLISHED` remains in force.

## Verdicts

| Gate | Verdict |
|---|---|
| model specification (17P/15T, tables, markings, labels) | **PASS** |
| structural properties (boundedness, conservation, resource safety, no deadlock, completion reachable, no zero-time cycle) | **PASS** |
| SCG / normalisation evidence | **FAIL** — class cap reached, no non-trivial normalisation evidence |
| VER/AMB verdict with critical pair | **FAIL** — INC only |
| adjustment demonstration | **NOT ATTEMPTED** (no authority) |
| IEEE-style figure | **DRAFT** — `fig/tpn_illustrative_case.pdf` (manual layout; labels need a final typographic pass) |

Overall: `PASS WITH LIMITATIONS` for the model as an illustrative structure; the bounded
verifier cannot decide it within its class cap, so it must not be presented as a verified
diagnosability example until a reduced variant (or a larger class budget) is used.
