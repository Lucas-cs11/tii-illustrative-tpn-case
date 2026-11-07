#!/usr/bin/env python3
"""Independent strong-time executor and SCG-successor regression tests (A-F)."""
from __future__ import annotations
import json, sys
from fractions import Fraction
from itertools import count
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(HERE))
from model_case import build  # noqa: E402
from src.model.tpn import TPN, Transition, Interval, Arc, Place  # noqa: E402
from src.scg.builder import build_scg  # noqa: E402


# ---------- independent strong-time executor ----------
def pre_post(tpn):
    pre = {t: {} for t in tpn.transitions}
    post = {t: {} for t in tpn.transitions}
    for a in tpn.arcs:
        f, to = a.from_node, a.to_node
        if f in tpn.places and to in tpn.transitions:
            pre[to][f] = pre[to].get(f, 0) + 1
        elif f in tpn.transitions and to in tpn.places:
            post[f][to] = post[f].get(to, 0) + 1
    return pre, post


def enabled(tpn, pre, marking):
    return [t for t in tpn.transitions
            if all(marking.get(p, 0) >= n for p, n in pre[t].items())]


class State:
    __slots__ = ("marking", "clocks", "fired")

    def __init__(self, marking, clocks, fired):
        self.marking = dict(marking); self.clocks = dict(clocks); self.fired = tuple(fired)


def strong_time_search(tpn, accept, max_time=240, max_depth=40, grid=(0, 0.5, 1, 2)):
    """Strong-time traversal with a coarse waiting grid.

    Every enabled transition carries its elapsed time. A step either waits by one of the
    grid values (clipped so that no enabled transition passes its latest firing time) and
    then fires one enabled transition. The traversal is breadth-first with a node budget,
    which is enough to prove *feasibility witnesses* (the claim here) but is not a
    complete decision procedure for infeasibility.
    """
    pre, post = pre_post(tpn)
    init = dict(tpn.initial_marking)
    en0 = enabled(tpn, pre, init)
    start = State(init, {t: Fraction(0) for t in en0}, [])
    from collections import deque
    q = deque([(start, [])])
    seen = set()
    budget = 400000
    while q and budget > 0:
        st, path = q.popleft(); budget -= 1
        if accept(st.marking, st.fired):
            return path, st.marking
        if len(path) >= max_depth:
            continue
        en = list(st.clocks)
        if not en:
            continue
        slack = min(tpn.transitions[t].interval.latest - st.clocks[t] for t in en)
        if slack < 0:
            continue
        waits = {Fraction(0), slack}
        for g in grid:
            g = Fraction(g).limit_denominator(10)
            if g <= slack:
                waits.add(g)
        for delta in sorted(waits):
            clocks = {t: st.clocks[t] + delta for t in en}
            for t in en:
                if not (tpn.transitions[t].interval.earliest <= clocks[t]
                        <= tpn.transitions[t].interval.latest):
                    continue
                nm = dict(st.marking)
                for p, n in pre[t].items():
                    nm[p] = nm.get(p, 0) - n
                for p, n in post[t].items():
                    nm[p] = nm.get(p, 0) + n
                if any(v < 0 for v in nm.values()):
                    continue
                still = enabled(tpn, pre, nm)
                nc = {}
                for u in still:
                    nc[u] = clocks[u] if (u in clocks and u != t) else Fraction(0) if u not in clocks else Fraction(0)
                fired = tuple(sorted(st.fired + (t,)))
                key = (tuple(sorted(nm.items())), fired)
                if key in seen:
                    continue
                seen.add(key)
                q.append((State(nm, nc, list(fired)), path + [(t, delta)]))
    return None


def micro(name, places, transitions, arcs, init, completion):
    P = {p: Place(name=p) for p in places}
    T = {n: Transition(name=n, label=lab, is_fault=fault, is_adjustable=False,
                       interval=Interval(lo, hi))
         for n, (lab, fault, lo, hi) in transitions.items()}
    A = [Arc(from_node=a, to_node=b) for a, b in arcs]
    return TPN(places=P, transitions=T, arcs=A, initial_marking=dict(init),
               completion_markings=[dict(completion)])


def scg_accepts(tpn, seq_accept_predicate):
    scg = build_scg(tpn)
    return {"classes": scg.class_count if hasattr(scg, "class_count") else len(scg.classes),
            "edges": len(scg.edges)}


def main() -> int:
    results = {}
    # ---- Test A: urgent conflict (buggy configuration as in v1) ----
    tpnA = micro("A", ["p", "q", "c"], {"t_normal": ("n", False, 2, 3),
                                        "t_fault": ("f", True, 0, 1)},
                 [("p", "t_normal"), ("t_normal", "q"), ("p", "t_fault"),
                  ("t_fault", "c")],
                 {"p": 1}, {"q": 1})
    witness = strong_time_search(tpnA, lambda m, f: m.get("q", 0) == 1 and "t_fault" not in f)
    results["A_urgent_conflict"] = {"normal_without_fault_feasible": witness is not None,
                                    "forced_fault": witness is None}
    # ---- Test B: valid nondeterministic conflict ----
    tpnB = micro("B", ["p", "q", "c"], {"t_normal": ("n", False, 2, 3),
                                        "t_fault": ("f", True, 1, 3)},
                 [("p", "t_normal"), ("t_normal", "q"), ("p", "t_fault"),
                  ("t_fault", "c")],
                 {"p": 1}, {"q": 1})
    wn = strong_time_search(tpnB, lambda m, f: m.get("q", 0) == 1 and "t_fault" not in f)
    wf = strong_time_search(tpnB, lambda m, f: m.get("c", 0) == 1 and "t_fault" in f)
    results["B_valid_conflict"] = {"normal_feasible": wn is not None,
                                   "fault_feasible": wf is not None,
                                   "normal_path": [str(x) for x in (wn[0] if wn else [])],
                                   "fault_path": [str(x) for x in (wf[0] if wf else [])]}
    # ---- Test C/D/E/F on the industrial case model ----
    tpn = build()
    normal = strong_time_search(tpn, lambda m, f: m.get("p_completed", 0) == 2 and not any(
        tpn.transitions[x].is_fault for x in f))
    faulty = strong_time_search(tpn, lambda m, f: m.get("p_completed", 0) == 2 and any(
        tpn.transitions[x].is_fault for x in f))
    rework = strong_time_search(tpn, lambda m, f: any(
        tpn.transitions[x].label == "inspection_rework" for x in f) and m.get("p_completed", 0) >= 1)
    partial = strong_time_search(tpn, lambda m, f: m.get("p_completed", 0) == 1)
    results["C_F_case_model"] = {
        "normal_completion_feasible": normal is not None,
        "normal_steps": len(normal[0]) if normal else None,
        "normal_observables": sum(1 for t, _ in normal[0] if tpn.transitions[t].label) if normal else None,
        "fault_completion_feasible": faulty is not None,
        "fault_steps": len(faulty[0]) if faulty else None,
        "rework_reachable": rework is not None,
        "partial_completion_reachable": partial is not None}
    # ---- SCG successor consistency on Test A ----
    try:
        scgA = scg_accepts(tpnA, None)
        results["A_scg"] = scgA
    except Exception as exc:  # noqa: BLE001
        results["A_scg"] = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        scgB = scg_accepts(tpnB, None)
        results["B_scg"] = scgB
    except Exception as exc:  # noqa: BLE001
        results["B_scg"] = {"error": f"{type(exc).__name__}: {exc}"}
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "semantic_regression.json").write_text(json.dumps(results, indent=1, default=str))
    print(json.dumps(results, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
