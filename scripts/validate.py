#!/usr/bin/env python3
"""Formal validation of the illustrative industrial TPN.

Structural checks are performed on the untimed reachability graph; the timed verdicts
come from the paper's own bounded verifier.
"""
from __future__ import annotations
import json, sys
from collections import deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(HERE))
from model_case import build, PLACES  # noqa: E402
from src.verifier import verify  # noqa: E402

JOB_PLACES = ["p_raw", "p_loading", "p_wait_machine", "p_processing", "p_wait_transfer",
              "p_transferring", "p_wait_inspection", "p_inspecting", "p_rework_queue",
              "p_rework_transfer", "p_wait_unload", "p_unloading", "p_completed",
              "p_grip_recovery"]


def pre_post(tpn):
    pre, post = {}, {}
    for t in tpn.transitions:
        pre[t] = {}
        post[t] = {}
    for a in tpn.arcs:
        f, to = a.from_node, a.to_node
        if f in tpn.places and to in tpn.transitions:
            pre[to][f] = pre[to].get(f, 0) + 1
        elif f in tpn.transitions and to in tpn.places:
            post[f][to] = post[f].get(to, 0) + 1
    return pre, post


def explore(tpn, cap=200000):
    pre, post = pre_post(tpn)
    init = dict(tpn.initial_marking)
    key = lambda m: tuple(sorted((p, v) for p, v in m.items() if v))
    seen = {key(init)}
    q = deque([init])
    edges = {}
    deadlocks = []
    violations = []
    completion_hits = 0
    comp_keys = {key(m) for m in tpn.completion_markings}
    while q:
        m = q.popleft()
        mk = key(m)
        if mk in comp_keys:
            completion_hits += 1
        enabled = []
        for t in tpn.transitions:
            if all(m.get(p, 0) >= n for p, n in pre[t].items()):
                enabled.append(t)
        if not enabled and mk not in comp_keys:
            deadlocks.append(dict(m))
        for t in enabled:
            nm = dict(m)
            for p, n in pre[t].items():
                nm[p] = nm.get(p, 0) - n
            for p, n in post[t].items():
                nm[p] = nm.get(p, 0) + n
            # invariants
            jobs = sum(nm.get(p, 0) for p in JOB_PLACES)
            if jobs != 2:
                violations.append({"marking": dict(nm), "rule": "workpiece_conservation", "value": jobs})
            if nm.get("p_robot_free", 0) + sum(nm.get(p, 0) for p in
                    ("p_loading", "p_transferring", "p_rework_transfer", "p_unloading")) > 1:
                violations.append({"marking": dict(nm), "rule": "robot_single_server"})
            if nm.get("p_machine_free", 0) + nm.get("p_processing", 0) > 1:
                violations.append({"marking": dict(nm), "rule": "machine_single_server"})
            if nm.get("p_inspection_free", 0) + nm.get("p_inspecting", 0) > 1:
                violations.append({"marking": dict(nm), "rule": "inspection_single_server"})
            if nm.get("p_completed", 0) > 2:
                violations.append({"marking": dict(nm), "rule": "completion_bound"})
            k2 = key(nm)
            edges.setdefault(mk, set()).add((k2, t))
            if k2 not in seen:
                if len(seen) >= cap:
                    return {"capped": True, "markings": len(seen), "deadlocks": deadlocks,
                            "violations": violations, "completion_hits": completion_hits}
                seen.add(k2)
                q.append(nm)
    # zero-time cycle detection: cycle in the untimed graph whose every transition has lo == 0
    zero_ts = {t for t, tr in tpn.transitions.items() if tr.interval.earliest == 0}
    # simple check: any transition with lo==0 that appears in a cycle of zero-time edges only
    zero_edges = {(a, b) for a, outs in edges.items() for b, t in outs if t in zero_ts}
    zseen = set()
    zero_cycle = False
    adjacency = {}
    for a, b in zero_edges:
        adjacency.setdefault(a, set()).add(b)
    for start in adjacency:
        stack = [(start, [start])]
        while stack:
            node, path = stack.pop()
            for nxt in adjacency.get(node, ()):
                if nxt == start and len(path) > 0:
                    zero_cycle = True; break
                if nxt not in path:
                    stack.append((nxt, path + [nxt]))
            if zero_cycle:
                break
        if zero_cycle:
            break
    return {"capped": False, "markings": len(seen), "deadlocks": deadlocks,
            "violations": violations, "completion_hits": completion_hits,
            "zero_time_cycle": zero_cycle}


def main() -> int:
    tpn = build()
    struct = explore(tpn)
    grid = []
    for H in (60.0, 120.0, 240.0):
        for L in (4, 6, 8):
            out = verify(tpn, L=L, H=H, complete_set=True)
            grid.append({"L": L, "H": H, "verdict": out.get("result"),
                         "certificate_mode": out.get("certificate_mode"),
                         "enumeration_complete": out.get("enumeration_complete"),
                         "certificates": len(out.get("certificates", []) or []),
                         "stats": out.get("stats", {})})
    result = {"model": {"places": len(tpn.places), "transitions": len(tpn.transitions),
                        "arcs": len(tpn.arcs),
                        "observable_alphabet": sorted(tpn.observable_alphabet),
                        "faults": [n for n, t in tpn.transitions.items() if t.is_fault]},
              "structural": {k: (v if k in ("capped", "markings", "completion_hits",
                                            "zero_time_cycle") else len(v))
                             for k, v in struct.items()},
              "deadlocks": struct["deadlocks"][:5],
              "violations": struct["violations"][:10],
              "verifier_grid": grid}
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "validation.json").write_text(json.dumps(result, indent=1, default=str))
    print(json.dumps({k: result[k] for k in ("model", "structural")}, indent=1, default=str))
    for g in grid:
        print(f"  L={g['L']} H={g['H']}: {g['verdict']} certs={g['certificates']} "
              f"scg={g['stats'].get('scg_classes')} words={g['stats'].get('candidate_words')} "
              f"lp={g['stats'].get('lp_calls')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
