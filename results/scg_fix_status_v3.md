# SCG fire-and-project repair — completion status (v3)

Branch/commit: `main` (this commit).

## What was completed

1. Restored the `SCG` container class that the firing-domain rewrite had
   removed (`classes`, `edges`, `initial_id`, `completion_ids`,
   `scg_state_limit_reached`, `has_zero_time_unobservable_cycle`,
   `_get_or_add_class`, `successors`, `build_truncated`).
2. Fixed the successor's newly-enabled set: a transition that fires always
   restarts its clock, so if it is still enabled after firing it belongs to
   the **newly enabled** set (not to the persistent set).  The previous code
   left such a transition in neither set, giving it an unconstrained variable.
3. Fixed class keying so zero-token places do not split otherwise equal
   classes.

## Regression contract

| test | expectation | result |
|---|---|---|
| A urgent conflict (`normal=[2,3]`, `fault=[0,1]`) | no normal successor | **PASS** |
| B valid conflict (`normal=[2,3]`, `fault=[1,3]`) | both successors | **PASS** |
| C persistent clocks | >= 2 classes | **PASS** |
| E fault completion | feasible | **PASS** |
| F first-entry completion | normal + partial | **PASS** |
| industrial 17P/15T SCG | 160 classes / 245 edges | **PASS** (was 50,001 cap) |

`python3 scripts/scg_regression.py` → all required regression tests passed.
`python3 -m unittest tests.test_scg_fire_project -v` → 7 tests OK.

## External reference (independent, not used as authority)

* TINA 4.0.0 `-W` on the exported 17P/15T net: **160 classes / 245 edges**.
* Full class-by-class equivalence (marking + canonical DBM + transition-labelled
  edge multiset) between this builder, the independent engine and TINA `-W`:
  **all match** (see `../industrial_final_verification/results/equivalence.json`).
* Wang/Mahulea/Silva (IEEE TAC 2015) benchmark, Table 4.1 classes and
  Example 4.1 domain `[4,7]`: reproduced by the independent engine; this
  builder now implements the same semantics (A/B/C + clock reset).

## Verifier consequence

The bounded verifier now terminates on the frozen model: `(L,H)=(10,45)` →
**AMB** with a paired-LP certificate; COMPLETE_SET enumerates the bounded
critical-pair set.  See `../industrial_final_verification/`.
