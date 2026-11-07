#!/usr/bin/env python3
"""Illustrative medium-size industrial TPN: 17 places, 15 transitions.

Two anonymous workpieces, one shared robot, one machine, one inspection station,
a rework loop with strictly positive time, and an unobservable gripper-slip fault
with a recovery branch.

All time intervals are ILLUSTRATIVE_ENGINEERING_PARAMETER values in seconds.
"""
from __future__ import annotations
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from src.model.tpn import TPN, Transition, Interval, Arc, Place  # noqa: E402

PLACES = ["p_raw", "p_loading", "p_wait_machine", "p_processing", "p_wait_transfer",
          "p_transferring", "p_wait_inspection", "p_inspecting", "p_rework_queue",
          "p_rework_transfer", "p_wait_unload", "p_unloading", "p_completed",
          "p_grip_recovery", "p_robot_free", "p_machine_free", "p_inspection_free"]

# name: (label, is_fault, (lo, hi))
TRANSITIONS = {
    "t_StartLoading":       ("", False, (1, 2)),
    "t_FinishLoading":      ("load_done", False, (2, 3)),
    "t_GripperSlipFault":   ("", True, (1, 3)),
    "t_RecoverLoading":     ("", False, (3, 5)),
    "t_StartProcessing":    ("", False, (0, 1)),
    "t_FinishProcessing":   ("machining_done", False, (8, 12)),
    "t_StartTransfer":      ("", False, (1, 2)),
    "t_FinishTransfer":     ("transfer_done", False, (2, 3)),
    "t_StartInspection":    ("", False, (0, 1)),
    "t_InspectionPass":     ("inspection_pass", False, (4, 6)),
    "t_InspectionRework":   ("inspection_rework", False, (4, 6)),
    "t_StartReworkTransfer":("", False, (1, 2)),
    "t_FinishReworkTransfer":("rework_returned", False, (2, 3)),
    "t_StartUnloading":     ("", False, (1, 2)),
    "t_FinishUnloading":    ("unload_done", False, (2, 3)),
}
# (source, target, multiplicity)
ARCS = [
    ("p_raw", "t_StartLoading", 1), ("p_robot_free", "t_StartLoading", 1),
    ("t_StartLoading", "p_loading", 1),
    ("p_loading", "t_FinishLoading", 1),
    ("t_FinishLoading", "p_wait_machine", 1), ("t_FinishLoading", "p_robot_free", 1),
    ("p_loading", "t_GripperSlipFault", 1), ("t_GripperSlipFault", "p_grip_recovery", 1),
    ("t_GripperSlipFault", "p_robot_free", 1),  # robot released when the gripper slips
    ("p_grip_recovery", "t_RecoverLoading", 1), ("p_robot_free", "t_RecoverLoading", 1),
    ("t_RecoverLoading", "p_loading", 1),
    ("p_wait_machine", "t_StartProcessing", 1), ("p_machine_free", "t_StartProcessing", 1),
    ("t_StartProcessing", "p_processing", 1),
    ("p_processing", "t_FinishProcessing", 1),
    ("t_FinishProcessing", "p_wait_transfer", 1), ("t_FinishProcessing", "p_machine_free", 1),
    ("p_wait_transfer", "t_StartTransfer", 1), ("p_robot_free", "t_StartTransfer", 1),
    ("t_StartTransfer", "p_transferring", 1),
    ("p_transferring", "t_FinishTransfer", 1),
    ("t_FinishTransfer", "p_wait_inspection", 1), ("t_FinishTransfer", "p_robot_free", 1),
    ("p_wait_inspection", "t_StartInspection", 1), ("p_inspection_free", "t_StartInspection", 1),
    ("t_StartInspection", "p_inspecting", 1),
    ("p_inspecting", "t_InspectionPass", 1),
    ("t_InspectionPass", "p_wait_unload", 1), ("t_InspectionPass", "p_inspection_free", 1),
    ("p_inspecting", "t_InspectionRework", 1),
    ("t_InspectionRework", "p_rework_queue", 1), ("t_InspectionRework", "p_inspection_free", 1),
    ("p_rework_queue", "t_StartReworkTransfer", 1), ("p_robot_free", "t_StartReworkTransfer", 1),
    ("t_StartReworkTransfer", "p_rework_transfer", 1),
    ("p_rework_transfer", "t_FinishReworkTransfer", 1),
    ("t_FinishReworkTransfer", "p_wait_machine", 1), ("t_FinishReworkTransfer", "p_robot_free", 1),
    ("p_wait_unload", "t_StartUnloading", 1), ("p_robot_free", "t_StartUnloading", 1),
    ("t_StartUnloading", "p_unloading", 1),
    ("p_unloading", "t_FinishUnloading", 1),
    ("t_FinishUnloading", "p_completed", 1), ("t_FinishUnloading", "p_robot_free", 1),
]
INITIAL = {"p_raw": 2, "p_robot_free": 1, "p_machine_free": 1, "p_inspection_free": 1}
COMPLETION = [{"p_completed": 1, "p_raw": 1, "p_robot_free": 1,
               "p_machine_free": 1, "p_inspection_free": 1},
              {"p_completed": 2, "p_robot_free": 1, "p_machine_free": 1,
               "p_inspection_free": 1}]


def build() -> TPN:
    places = {name: Place(name=name) for name in PLACES}
    transitions = {}
    for name, (label, fault, (lo, hi)) in TRANSITIONS.items():
        transitions[name] = Transition(name=name, label=label, is_fault=fault,
                                       is_adjustable=False,
                                       interval=Interval(lo, hi))
    arcs = []
    for a, b, w in ARCS:
        for _ in range(w):
            arcs.append(Arc(from_node=a, to_node=b))
    return TPN(places=places, transitions=transitions, arcs=arcs,
               initial_marking=dict(INITIAL), completion_markings=[dict(m) for m in COMPLETION])


if __name__ == "__main__":
    tpn = build()
    print(f"places={len(tpn.places)} transitions={len(tpn.transitions)} arcs={len(tpn.arcs)}")
