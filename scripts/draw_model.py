#!/usr/bin/env python3
"""Curated two-row layout of the illustrative TPN for IEEE double-column print."""
from __future__ import annotations
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch, FancyArrowPatch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT))
from model_case import build, INITIAL  # noqa: E402

matplotlib.rcParams.update({"font.family": "STIXGeneral", "font.size": 7,
                            "mathtext.fontset": "stix", "savefig.bbox": "tight"})
P = {"p_raw": (0.0, 0), "t_StartLoading": (1.0, 0), "p_loading": (2.0, 0),
     "t_FinishLoading": (3.0, 0), "t_GripperSlipFault": (2.0, -1.2),
     "p_grip_recovery": (3.0, -1.2), "t_RecoverLoading": (4.0, -1.2),
     "p_wait_machine": (4.0, 0), "t_StartProcessing": (5.0, 0), "p_processing": (6.0, 0),
     "t_FinishProcessing": (7.0, 0), "p_wait_transfer": (8.0, 0),
     "t_StartTransfer": (9.0, 0), "p_transferring": (10.0, 0),
     "t_FinishTransfer": (11.0, 0), "p_wait_inspection": (12.0, 0),
     "t_StartInspection": (13.0, 0), "p_inspecting": (14.0, 0),
     "t_InspectionPass": (15.0, 0), "p_wait_unload": (16.0, 0),
     "t_StartUnloading": (17.0, 0), "p_unloading": (18.0, 0),
     "t_FinishUnloading": (19.0, 0), "p_completed": (20.0, 0),
     "t_InspectionRework": (14.0, 1.15), "p_rework_queue": (13.0, 1.65),
     "t_StartReworkTransfer": (12.0, 1.15), "p_rework_transfer": (11.0, 1.65),
     "t_FinishReworkTransfer": (10.0, 1.15),
     "p_robot_free": (6.0, -2.3), "p_machine_free": (5.0, -2.3), "p_inspection_free": (13.0, -2.3)}
SHORT = {"p_raw": "raw", "p_loading": "loading", "p_wait_machine": "wait\nmachine",
         "p_processing": "processing", "p_wait_transfer": "wait\ntransfer",
         "p_transferring": "transfer", "p_wait_inspection": "wait\ninspect",
         "p_inspecting": "inspecting", "p_rework_queue": "rework\nqueue",
         "p_rework_transfer": "rework\ntransfer", "p_wait_unload": "wait\nunload",
         "p_unloading": "unloading", "p_completed": "completed",
         "p_grip_recovery": "grip\nrecovery", "p_robot_free": "robot\nfree",
         "p_machine_free": "machine\nfree", "p_inspection_free": "inspect\nfree"}
TNAMES = {"t_StartLoading": "T1", "t_FinishLoading": "T2", "t_GripperSlipFault": "T3",
          "t_RecoverLoading": "T4", "t_StartProcessing": "T5", "t_FinishProcessing": "T6",
          "t_StartTransfer": "T7", "t_FinishTransfer": "T8", "t_StartInspection": "T9",
          "t_InspectionPass": "T10", "t_InspectionRework": "T11",
          "t_StartReworkTransfer": "T12", "t_FinishReworkTransfer": "T13",
          "t_StartUnloading": "T14", "t_FinishUnloading": "T15"}
tpn = build()
fig, ax = plt.subplots(figsize=(7.16, 2.35))
for name, (x, y) in P.items():
    if name.startswith("p_"):
        ax.add_patch(Circle((x, y), 0.30, facecolor="#E8EEF5", edgecolor="#04182E", lw=0.7, zorder=3))
        toks = INITIAL.get(name, 0)
        ax.text(x, y + 0.05, SHORT.get(name, name), ha="center", va="center", fontsize=5.2, zorder=4)
        if toks:
            ax.text(x, y - 0.16, "•" * toks, ha="center", va="center", fontsize=6, zorder=4)
    else:
        fault = tpn.transitions[name].is_fault
        ax.add_patch(FancyBboxPatch((x - 0.20, y - 0.10), 0.40, 0.20,
                                    boxstyle="round,pad=0.01,rounding_size=0.03",
                                    facecolor="#F6E3D3" if fault else "#F2F5F9",
                                    edgecolor="#B5651D" if fault else "#04182E",
                                    lw=0.7, zorder=3))
        lab = TNAMES[name]
        lo, hi = tpn.transitions[name].interval.earliest, tpn.transitions[name].interval.latest
        obs = tpn.transitions[name].label
        ax.text(x, y + 0.02, lab, ha="center", va="center", fontsize=5.4, zorder=4)
        ax.text(x, y - 0.16, f"[{lo},{hi}]", ha="center", va="center", fontsize=4.4, color="#555", zorder=4)
        if obs:
            ax.text(x, y + 0.20, obs, ha="center", va="bottom", fontsize=4.4, style="italic", color="#1D5E9E")
for a in tpn.arcs:
    x0, y0 = P[a.from_node]
    x1, y1 = P[a.to_node]
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=5,
                                 lw=0.5, color="#333", shrinkA=13, shrinkB=11, zorder=2))
ax.set_xlim(-0.6, 20.7); ax.set_ylim(-2.9, 2.3); ax.axis("off")
for ext in ("pdf", "svg", "eps"):
    fig.savefig(ROOT / "fig" / f"tpn_illustrative_case.{ext}")
fig.savefig(ROOT / "fig" / "tpn_illustrative_case.png", dpi=600)
print("figure written")
