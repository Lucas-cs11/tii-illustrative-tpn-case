"""
Build normalized State Class Graph (SCG) using DBM representation.

A state class C = (M, Z) where:
- M: marking (dict[str, int])
- Z: normalized DBM over enabled transitions

DBM representation:
  Variables: x_0 (reference clock, always 0), x_t for each enabled transition t.
  Entry DBM[i][j] = upper bound on (x_i - x_j).
  Normalized via Floyd-Warshall.

Following Berthomieu & Menasche (1983) / Berthomieu & Vernadat (2006):
The zone Z for state class (M, enu) encodes the set of valid ages
(time-since-enabled) for all transitions enabled at M.

The reference variable x_0 represents the current time (= 0 at the class entry).
For enabled transition u, x_u is its age (clock value).

Key DBM entries:
  DBM[u][0] = upper bound on x_u - 0 = x_u   => x_u <= DBM[u][0]  (latest)
  DBM[0][u] = upper bound on 0 - x_u = -x_u  => x_u >= -DBM[0][u] (earliest)

For the initial state class:
  All transitions enabled at M0 have age 0.
  x_u = 0 for all u in E(M0).

After firing transition t with delay d:
  New ages for persistently enabled u: x_u' = x_u + d
  New ages for newly enabled v: x_v' = 0
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Dict, FrozenSet, List, Optional, Tuple

from ..model.tpn import INF, TPN


# Sentinel for infinity in DBM bounds
DBM_INF = float("inf")


def _frac_or_inf(v) -> object:
    if math.isinf(v):
        return DBM_INF
    return Fraction(v)


def _leq(a, b) -> bool:
    """a <= b where either may be inf."""
    if math.isinf(b):
        return True
    if math.isinf(a):
        return False
    return a <= b


def _add(a, b) -> object:
    """a + b where either may be inf."""
    if math.isinf(a) or math.isinf(b):
        return DBM_INF
    return a + b


class DBM:
    """Difference Bound Matrix over a set of variable names plus reference '0'.

    Variables: {'0'} | enabled_transition_names
    DBM[i][j] = upper bound on x_i - x_j  (Fraction or float('inf'))
    """

    def __init__(self, variables: FrozenSet[str]):
        # variables includes the reference '0' and all enabled transition names
        self.variables = variables
        self._vars_list: List[str] = sorted(variables)
        self._idx: Dict[str, int] = {v: i for i, v in enumerate(self._vars_list)}
        n = len(self._vars_list)
        # Initialize: diagonal = 0, off-diagonal = inf
        self._mat: List[List[object]] = [
            [DBM_INF] * n for _ in range(n)
        ]
        for i in range(n):
            self._mat[i][i] = Fraction(0)

    def get(self, i: str, j: str) -> object:
        return self._mat[self._idx[i]][self._idx[j]]

    def set(self, i: str, j: str, val: object):
        self._mat[self._idx[i]][self._idx[j]] = val

    def normalize(self) -> "DBM":
        """Return a new normalized DBM via Floyd-Warshall."""
        n = len(self._vars_list)
        # Copy
        mat = [row[:] for row in self._mat]
        # Floyd-Warshall: tighten all pairs through intermediate k
        for k in range(n):
            for i in range(n):
                for j in range(n):
                    candidate = _add(mat[i][k], mat[k][j])
                    if _leq(candidate, mat[i][j]):
                        mat[i][j] = candidate
        result = DBM(self.variables)
        result._mat = mat
        result._vars_list = self._vars_list
        result._idx = self._idx
        return result

    def is_empty(self) -> bool:
        """Return True if DBM is inconsistent (negative diagonal entry)."""
        for i in range(len(self._vars_list)):
            if not math.isinf(self._mat[i][i]) and self._mat[i][i] < 0:
                return True
        return False

    def __eq__(self, other) -> bool:
        if not isinstance(other, DBM):
            return False
        if self.variables != other.variables:
            return False
        for i in self._vars_list:
            for j in self._vars_list:
                a = self.get(i, j)
                b = other.get(i, j)
                if math.isinf(a) and math.isinf(b):
                    continue
                if math.isinf(a) or math.isinf(b):
                    return False
                if a != b:
                    return False
        return True

    def __hash__(self) -> int:
        h = hash(self.variables)
        for i in self._vars_list:
            for j in self._vars_list:
                v = self.get(i, j)
                if math.isinf(v):
                    h = hash((h, i, j, "inf"))
                else:
                    h = hash((h, i, j, v))
        return h

    def __repr__(self) -> str:
        lines = []
        for i in self._vars_list:
            row = []
            for j in self._vars_list:
                v = self.get(i, j)
                row.append("inf" if math.isinf(v) else str(v))
            lines.append(f"  {i}: {row}")
        return "DBM{\n" + "\n".join(lines) + "\n}"


@dataclass(frozen=True)
class StateClass:
    """A normalized state class C = (M, Z).

    marking_key: frozenset of (place, count) pairs for hashing
    marking: dict[place_name -> token_count]
    dbm: normalized DBM
    enabled: frozenset of enabled transition names (excluding reference '0')
    """

    marking_key: FrozenSet[Tuple[str, int]]
    marking: Dict[str, int]
    dbm: DBM
    enabled: FrozenSet[str]

    def __eq__(self, other) -> bool:
        if not isinstance(other, StateClass):
            return False
        return self.marking_key == other.marking_key and self.dbm == other.dbm

    def __hash__(self) -> int:
        return hash((self.marking_key, self.dbm))


@dataclass
class SCG:
    """Normalized state-class graph.

    classes: id -> StateClass
    edges:   list of (source class id, transition name, target class id)
    Completion classes are stored but not expanded (first-entry completion).
    """

    classes: Dict[int, StateClass] = field(default_factory=dict)
    edges: List[Tuple[int, str, int]] = field(default_factory=list)
    initial_id: int = -1
    completion_ids: FrozenSet[int] = frozenset()
    scg_state_limit_reached: bool = False
    has_zero_time_unobservable_cycle: bool = False
    _index: Dict[StateClass, int] = field(default_factory=dict, repr=False)

    def _get_or_add_class(self, cls: StateClass) -> Tuple[int, bool]:
        existing = self._index.get(cls)
        if existing is not None:
            return existing, False
        cid = len(self.classes)
        self.classes[cid] = cls
        self._index[cls] = cid
        return cid, True

    @property
    def class_count(self) -> int:
        return len(self.classes)

    def __len__(self) -> int:
        return len(self.classes)

    def successors(self, class_id: int) -> List[Tuple[str, int]]:
        """Return the list of (transition, successor class id) edges."""
        return [(t, dst) for (src, t, dst) in self.edges if src == class_id]

    def build_truncated(self) -> "SCG":
        """Completion-truncated SCG: completion classes are kept as leaves.

        ``build_scg`` already avoids expanding completion classes; this method
        returns an explicit copy with any edge leaving a completion class
        removed, so downstream consumers can rely on the first-entry rule even
        if the graph is later extended.
        """
        trunc = SCG()
        trunc.classes = dict(self.classes)
        trunc._index = dict(self._index)
        trunc.initial_id = self.initial_id
        trunc.completion_ids = frozenset(self.completion_ids)
        trunc.scg_state_limit_reached = self.scg_state_limit_reached
        trunc.has_zero_time_unobservable_cycle = self.has_zero_time_unobservable_cycle
        trunc.edges = [(src, t, dst) for (src, t, dst) in self.edges
                       if src not in self.completion_ids]
        return trunc


def _marking_to_key(marking: Dict[str, int]) -> FrozenSet[Tuple[str, int]]:
    return frozenset((p, c) for p, c in marking.items() if c > 0)


def _build_initial_class(tpn: TPN) -> StateClass:
    """Compute the initial state class C0 = (M0, Z0).

    Follows Berthomieu & Menasche (1983) / Berthomieu & Vernadat (2006).

    In the SCG zone, x_u represents the age of transition u at the moment
    the NEXT transition fires (not the current elapsed time).  The initial
    zone encodes valid firing-age ranges for all enabled transitions assuming
    they were all enabled at time 0:

      DBM[u][0]  = latest(u)    x_u <=  latest(u)   (can't exceed deadline)
      DBM[0][u]  = -earliest(u) x_u >= earliest(u)  (not yet fireable before earliest)
      DBM[u][v]  = latest(u) - earliest(v)           (cross-difference, tightened by FW)

    The cross-differences encode strong-time urgency: if latest(u) < earliest(v),
    then DBM[u][v] < 0 which (after normalization) may make the zone infeasible
    for certain combinations of concurrent transitions.
    """
    marking = dict(tpn.initial_marking)
    enabled = frozenset(tpn.enabled_set(marking))
    variables = frozenset({"0"} | enabled)

    dbm = DBM(variables)

    for u in enabled:
        t_u = tpn.transitions[u]
        latest_u = t_u.interval.latest
        earliest_u = t_u.interval.earliest

        dbm.set(u, "0", latest_u)       # x_u <= latest(u)
        dbm.set("0", u, -earliest_u)    # x_u >= earliest(u)

    for u in enabled:
        for v in enabled:
            if u != v:
                t_u = tpn.transitions[u]
                t_v = tpn.transitions[v]
                # x_u - x_v <= latest(u) - earliest(v)
                diff = _add(t_u.interval.latest, -t_v.interval.earliest)
                dbm.set(u, v, diff)

    normalized = dbm.normalize()
    marking_key = _marking_to_key(marking)
    return StateClass(
        marking_key=marking_key,
        marking=marking,
        dbm=normalized,
        enabled=enabled,
    )


def _compute_successor(tpn: TPN, cls: StateClass, t_name: str) -> Optional[StateClass]:
    """Successor state class in the firing-domain representation.

    Variable theta_t of a class is the remaining time until t fires, constrained to
    [earliest(t), latest(t)].  Firing t first is legal iff theta_t <= theta_u for every
    other enabled u (strong time: no other enabled transition may be forced past its
    deadline before t fires).  After firing, persistent transitions keep their remaining
    time shifted by theta_t, newly enabled transitions get a fresh interval, and the
    fired variable is projected out.
    """
    if t_name not in cls.enabled:
        return None
    t_obj = tpn.transitions[t_name]

    # ---- 1. firing-domain constraints, intersected with tighten semantics ----
    z = DBM(cls.dbm.variables)
    for i in cls.dbm.variables:
        for j in cls.dbm.variables:
            z.set(i, j, cls.dbm.get(i, j))

    def tighten(i: str, j: str, bound):
        old = z.get(i, j)
        z.set(i, j, bound if _leq(bound, old) else old)

    for u in cls.enabled:
        if u == t_name:
            continue
        tighten(t_name, u, Fraction(0))          # theta_t - theta_u <= 0
    z = z.normalize()
    if z.is_empty():
        return None

    # ---- 2. new marking and enabled sets ----
    new_marking = tpn.fire(cls.marking, t_name)
    after_set = frozenset(tpn.enabled_set(new_marking))
    # A transition that fires always restarts its clock: if it is still
    # enabled after firing it belongs to the newly-enabled set, not to the
    # persistent set.  (This is the convention required for Wang Example 4.1,
    # see reports/wang_reproduction.md.)
    persistent = frozenset(u for u in after_set if u in cls.enabled and u != t_name)
    newly = frozenset(u for u in after_set if u not in cls.enabled or u == t_name)

    # ---- 3. shifted DBM with projection of theta_t ----
    new_variables = frozenset({"0"} | after_set)
    nd = DBM(new_variables)
    for u in persistent:
        nd.set(u, "0", z.get(u, t_name))         # theta_u - theta_t <= ...
        nd.set("0", u, z.get(t_name, u))
    for u1 in persistent:
        for u2 in persistent:
            if u1 != u2:
                nd.set(u1, u2, z.get(u1, u2))
    for v in newly:
        tv = tpn.transitions[v]
        nd.set(v, "0", tv.interval.latest)
        nd.set("0", v, -tv.interval.earliest)
    for u in persistent:
        for v in newly:
            tv = tpn.transitions[v]
            nd.set(u, v, z.get(u, t_name) - tv.interval.earliest)
            nd.set(v, u, tv.interval.latest + z.get(t_name, u))
    nd = nd.normalize()
    if nd.is_empty():
        return None
    return StateClass(
        marking_key=frozenset((p, c) for p, c in new_marking.items() if c > 0),
        marking=new_marking,
        dbm=nd,
        enabled=after_set,
    )

def _transition_has_zero_time(tpn: TPN, t_name: str) -> bool:
    """Return True if transition t_name has a zero upper bound (can fire at time 0)."""
    t = tpn.transitions[t_name]
    latest = t.interval.latest
    return not math.isinf(latest) and latest == 0


def _transition_can_fire_at_zero(tpn: TPN, t_name: str) -> bool:
    """Return True if transition can fire with zero delay (earliest == 0)."""
    return tpn.transitions[t_name].interval.earliest == 0


def detect_zero_time_unobservable_cycle(tpn: TPN, scg: "SCG") -> bool:
    """Return True if the SCG contains a reachable unresolved zero-time unobservable cycle.

    A zero-time unobservable cycle is a cycle where:
    - All transitions on the cycle are unobservable
    - All transitions on the cycle have zero upper bound (latest == 0)
    - The cycle does not pass through a completion marking
    - The cycle is reachable from the initial state

    Detection: find any back-edge in DFS from initial class where all edges
    on the cycle path satisfy the above conditions.
    """
    # Build adjacency: only zero-delay unobservable edges not from completion classes
    adj: Dict[int, List[Tuple[str, int]]] = {cid: [] for cid in scg.classes}
    for (src, t_name, dst) in scg.edges:
        if src in scg.completion_ids:
            continue
        t_obj = tpn.transitions[t_name]
        if not t_obj.is_observable and _transition_can_fire_at_zero(tpn, t_name):
            adj[src].append((t_name, dst))

    # DFS from initial, track path to detect back-edges (cycles)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {cid: WHITE for cid in scg.classes}

    def dfs(node: int) -> bool:
        color[node] = GRAY
        for (t_name, succ) in adj.get(node, []):
            if succ in scg.completion_ids:
                continue
            if color[succ] == GRAY:
                return True  # back-edge: zero-time unobservable cycle found
            if color[succ] == WHITE:
                if dfs(succ):
                    return True
        color[node] = BLACK
        return False

    return dfs(scg.initial_id)


def build_scg(tpn: TPN) -> SCG:
    """Build the normalized State Class Graph for tpn.

    Uses BFS over state classes.
    Sets scg.has_zero_time_unobservable_cycle = True if a reachable zero-time
    unobservable cycle is detected during construction (early termination).
    """
    scg = SCG()

    # Pre-compute: which transitions are zero-delay and unobservable
    # (earliest == 0 means can fire with zero delay)
    zero_delay_unobs_transitions = frozenset(
        name for name, t in tpn.transitions.items()
        if not t.is_observable and _transition_can_fire_at_zero(tpn, name)
    )

    # Initial class
    c0 = _build_initial_class(tpn)
    c0_id, _ = scg._get_or_add_class(c0)
    scg.initial_id = c0_id

    completion_ids = set()
    if tpn.in_completion(c0.marking):
        completion_ids.add(c0_id)

    queue = deque([c0_id])
    visited = {c0_id}

    MAX_CLASSES = 50_000  # safety cap
    found_zero_time_cycle = False
    state_limit_reached = False

    while queue and not found_zero_time_cycle:
        curr_id = queue.popleft()
        curr_cls = scg.classes[curr_id]

        if len(scg.classes) > MAX_CLASSES:
            # Exceeded cap: state limit, not a cycle
            state_limit_reached = True
            break

        for t_name in sorted(curr_cls.enabled):
            succ = _compute_successor(tpn, curr_cls, t_name)
            if succ is None:
                continue

            succ_id, is_new = scg._get_or_add_class(succ)
            scg.edges.append((curr_id, t_name, succ_id))

            # Zero-delay unobservable edge: check for immediate marking cycle
            if t_name in zero_delay_unobs_transitions:
                if succ.marking_key == curr_cls.marking_key and not tpn.in_completion(succ.marking):
                    # Same marking reached via zero-delay unobs step -> self-loop cycle
                    found_zero_time_cycle = True
                    break

            if is_new:
                if tpn.in_completion(succ.marking):
                    completion_ids.add(succ_id)
                    # DO NOT enqueue completion classes: truncate here
                elif succ_id not in visited:
                    visited.add(succ_id)
                    queue.append(succ_id)

        if found_zero_time_cycle:
            break

    scg.completion_ids = frozenset(completion_ids)
    scg.scg_state_limit_reached = state_limit_reached

    if found_zero_time_cycle:
        scg.has_zero_time_unobservable_cycle = True
    elif state_limit_reached:
        # State limit exhausted: not a cycle, report separately
        scg.has_zero_time_unobservable_cycle = False
    else:
        # Post-hoc graph analysis for multi-step zero-delay unobservable cycles
        scg.has_zero_time_unobservable_cycle = detect_zero_time_unobservable_cycle(tpn, scg)

    return scg
