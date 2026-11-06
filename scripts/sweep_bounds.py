#!/usr/bin/env python3
"""Find (L, H) configurations where the illustrative model is decidable within the class cap."""
from __future__ import annotations
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(HERE))
from model_case import build  # noqa: E402
from src.verifier import verify  # noqa: E402

tpn = build()
rows = []
for H in (24.0, 28.0, 32.0, 36.0, 40.0, 48.0):
    for L in (3, 4, 5, 6):
        for complete in (False, True):
            out = verify(tpn, L=L, H=H, complete_set=complete)
            st = out.get("stats", {})
            rows.append({"L": L, "H": H, "complete_set": complete,
                         "verdict": out.get("result"),
                         "enumeration_complete": out.get("enumeration_complete"),
                         "scg_classes": st.get("scg_classes"),
                         "candidate_words": st.get("candidate_words"),
                         "lp_calls": st.get("lp_calls"),
                         "certificates": len(out.get("certificates", []) or []),
                         "runtime_s": st.get("runtime_total")})
    print("H", H, "done", flush=True)
(ROOT / "results").mkdir(exist_ok=True)
(ROOT / "results" / "bounds_sweep.json").write_text(json.dumps(rows, indent=1))
for r in rows:
    print(f"L={r['L']} H={r['H']} complete={r['complete_set']}: {r['verdict']} "
          f"scg={r['scg_classes']} cand={r['candidate_words']} lp={r['lp_calls']} certs={r['certificates']}")
