#!/usr/bin/env python3
"""A-F regression tests for the SCG successor fix, plus an independent oracle."""
from __future__ import annotations
import json, sys
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent; ROOT = HERE.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(HERE))
from model_case import build  # noqa: E402
from src.model.tpn import TPN, Transition, Interval, Arc, Place  # noqa: E402
from src.scg.builder import build_scg  # noqa: E402
from semantic_regression import strong_time_search, micro  # noqa: E402


def classes_after(tpn, trans):
    scg = build_scg(tpn)
    init = None
    out = []
    for a, t, b in scg.edges:
        if t == trans:
            out.append(b)
    return {"classes": len(scg.classes), "edges": len(scg.edges),
            "successors_via": trans, "n_successors": len(out)}


def main() -> int:
    r = {}
    # A: urgent conflict -> t_normal must have no successor
    A = micro("A", ["p", "q", "c"], {"t_normal": ("n", False, 2, 3),
                                     "t_fault": ("f", True, 0, 1)},
              [("p", "t_normal"), ("t_normal", "q"), ("p", "t_fault"), ("t_fault", "c")],
              {"p": 1}, {"q": 1})
    a = classes_after(A, "t_normal")
    r["A_urgent_conflict"] = {"scg_successor_via_normal": a["n_successors"],
                              "expected": 0, "pass": a["n_successors"] == 0,
                              "classes": a["classes"], "edges": a["edges"]}
    # B: valid conflict -> both successors exist
    B = micro("B", ["p", "q", "c"], {"t_normal": ("n", False, 2, 3),
                                     "t_fault": ("f", True, 1, 3)},
              [("p", "t_normal"), ("t_normal", "q"), ("p", "t_fault"), ("t_fault", "c")],
              {"p": 1}, {"q": 1})
    bn, bf = classes_after(B, "t_normal"), classes_after(B, "t_fault")
    r["B_valid_conflict"] = {"normal_successors": bn["n_successors"],
                             "fault_successors": bf["n_successors"],
                             "pass": bn["n_successors"] >= 1 and bf["n_successors"] >= 1,
                             "classes": bn["classes"], "edges": bn["edges"]}
    # C/D: persistent vs newly enabled clocks on a small two-branch model
    C = micro("C", ["p", "q", "r"], {"t_a": ("a", False, 0, 0), "t_b": ("b", False, 2, 4),
                                     "t_c": ("c", False, 0, 10)},
              [("p", "t_a"), ("t_a", "q"), ("q", "t_b"), ("t_b", "r"),
               ("p", "t_c"), ("t_c", "r")], {"p": 1}, {"r": 1})
    try:
        c = classes_after(C, "t_a")
        r["C_persistent_clocks"] = {"classes": c["classes"], "edges": c["edges"],
                                    "pass": c["classes"] >= 2}
    except Exception as exc:  # noqa: BLE001
        r["C_persistent_clocks"] = {"error": f"{type(exc).__name__}: {exc}", "pass": False}
        print("C raised:", exc)
    # E/F: industrial model witnesses still reachable after the fix
    tpn = build()
    normal = strong_time_search(tpn, lambda m, f: m.get("p_completed", 0) == 2
                                and not any(tpn.transitions[x].is_fault for x in f))
    faulty = strong_time_search(tpn, lambda m, f: m.get("p_completed", 0) == 2
                                and any(tpn.transitions[x].is_fault for x in f))
    partial = strong_time_search(tpn, lambda m, f: m.get("p_completed", 0) == 1)
    r["E_recovery"] = {"fault_completion": faulty is not None, "pass": faulty is not None}
    r["F_completion"] = {"normal_completion": normal is not None,
                         "partial_reachable": partial is not None,
                         "pass": normal is not None and partial is not None,
                         "normal_observables": sum(1 for t, _ in normal[0]
                                                   if tpn.transitions[t].label) if normal else None}
    try:
        scg = build_scg(tpn)
        r["industrial_scg"] = {"classes": len(scg.classes), "edges": len(scg.edges)}
    except Exception as exc:  # noqa: BLE001
        r["industrial_scg"] = {"error": f"{type(exc).__name__}: {exc}"}
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "scg_regression.json").write_text(json.dumps(r, indent=1, default=str))
    print(json.dumps(r, indent=1, default=str)[:2500])
    required = ["A_urgent_conflict", "B_valid_conflict", "C_persistent_clocks",
                "E_recovery", "F_completion"]
    failed = [k for k in required if not r.get(k, {}).get("pass")]
    if failed:
        print("REGRESSION FAILURE:", ", ".join(failed))
        return 1
    print("all required regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
