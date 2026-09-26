"""Reference experiment designers (research/phase4/INTERFACES.md section 7; benchmarks/causal_state_v1/PROTOCOL.md section 5.17).

Every designer proposes protocols (format p4-protocol-1) for ONE system within its PUBLIC development policy: the split record's
families_train on the system's public targets and edges, magnitudes up to the development maximum (`brainir_causal.suites`
magnitude classes), public parameter / noise seeds. The experiment loop (`brainir_causal.loop`) re-checks every proposal against the
policy, adds the counterfactual twin of every intervention, simulates, and charges the budget: one EXPERIMENT = one intervention
trajectory (plus its twin); the `passive` designer spends the same simulator calls on two passive trajectories per experiment.

Designers are stateful within ONE loop run (a new instance per run) and deterministic given the rng the loop passes.

    random          uniform over families_train x public targets x magnitude classes x onsets
    uniform         coverage: cycles through every (family, first target, magnitude class) cell in a seeded order before repeating
    magnitude_sweep for each (family, target) in a seeded order, the magnitude classes in increasing order
    greedy_error    75 %: near the experiments with the largest effect-prediction error of the current model (same family and
                    targets, magnitude class one step up / same / down, new onset and draw); 25 %: random (also the first round)
    structural      targets ranked by public connectivity (out-weight of a unit onto observed / readout units in the public graph;
                    without a graph, by passive-data variance), highest first, cycling families and magnitude classes
    passive         observational trajectories only (stimulus schedules, initial states, weight-noise draws, parameter draws)
    fixed           a pre-registered design independent of the loop seed: every (family, target) at the moderate magnitude with a
                    fixed onset (0.3 T), then the weak and strong classes, in a fixed order
"""

from __future__ import annotations

import hashlib

import numpy as np

from . import protocol as P
from .api import Designer, register_designer
from .suites import MAG_CLASSES, N_TARGETS_NEEDED, FamilySampler, feasible, intervention_families, public_seed_of

ORDERED_CLASSES = ("below", "weak", "moderate", "strong")


def _seed_fn(tag: str, sid: str, rng: np.random.Generator):
    base = int(rng.integers(0, 2**31))
    counter = [0]

    def fn() -> int:
        counter[0] += 1
        return public_seed_of("designer", tag, sid, base, counter[0])
    return fn


class _Base(Designer):
    name = "base"

    def __init__(self):
        self._sampler: FamilySampler | None = None
        self._sid = None

    def sampler(self, sid: str, system: dict, rng: np.random.Generator) -> FamilySampler:
        if self._sampler is None or self._sid != sid:
            self._sampler = FamilySampler(system, rng, _seed_fn(self.name, sid, rng), targets=system.get("targets_public") or [],
                                          edges=[list(e) for e in system.get("edges_public") or []])
            self._sid = sid
        self._sampler.rng = rng
        return self._sampler

    @staticmethod
    def families(system: dict) -> list[str]:
        return [f for f in intervention_families(system["split"])
                if feasible(f, system.get("targets_public") or [], system.get("edges_public") or [])]

    def _one(self, s: FamilySampler, fam: str, *, targets=None, mclass=None, onset=None) -> dict:
        p, _ = s.make(fam, targets=targets, mclass=mclass, onset=onset)
        return P.validate(p)


@register_designer
class RandomDesigner(_Base):
    name = "random"

    def propose(self, system_id, system, model, data, n, budget_left, rng):
        s = self.sampler(system_id, system, rng)
        fams = self.families(system)
        if not fams:
            return []
        out = []
        for _ in range(n):
            fam = fams[int(rng.integers(len(fams)))]
            out.append(self._one(s, fam, mclass=MAG_CLASSES[int(rng.integers(len(MAG_CLASSES)))]))
        return out


@register_designer
class UniformDesigner(_Base):
    name = "uniform"

    def __init__(self):
        super().__init__()
        self._cells: list | None = None
        self._pos = 0

    def propose(self, system_id, system, model, data, n, budget_left, rng):
        s = self.sampler(system_id, system, rng)
        fams = self.families(system)
        if not fams:
            return []
        if self._cells is None:
            cells = [(f, t, m) for f in fams for t in (s.targets if f not in ("edge.w", "edge.rm") else [None]) for m in MAG_CLASSES]
            self._cells = [cells[i] for i in rng.permutation(len(cells))]
        out = []
        for _ in range(n):
            fam, t, mc = self._cells[self._pos % len(self._cells)]
            self._pos += 1
            need = N_TARGETS_NEEDED.get(fam, 1)
            targets = None
            if t is not None:
                others = [u for u in s.targets if u != t]
                extra = list(rng.choice(others, size=need - 1, replace=False)) if need > 1 else []
                targets = sorted([int(t)] + [int(u) for u in extra])
            out.append(self._one(s, fam, targets=targets, mclass=mc))
        return out


@register_designer
class MagnitudeSweepDesigner(_Base):
    name = "magnitude_sweep"

    def __init__(self):
        super().__init__()
        self._order: list | None = None
        self._pos = 0

    def propose(self, system_id, system, model, data, n, budget_left, rng):
        s = self.sampler(system_id, system, rng)
        fams = self.families(system)
        if not fams:
            return []
        if self._order is None:
            pairs = [(f, t) for f in fams for t in (s.targets if f not in ("edge.w", "edge.rm") else [None])]
            pairs = [pairs[i] for i in rng.permutation(len(pairs))]
            self._order = [(f, t, m) for f, t in pairs for m in ORDERED_CLASSES]
        out = []
        for _ in range(n):
            fam, t, mc = self._order[self._pos % len(self._order)]
            self._pos += 1
            need = N_TARGETS_NEEDED.get(fam, 1)
            targets = None
            if t is not None:
                others = [u for u in s.targets if u != t]
                targets = sorted([int(t)] + [int(u) for u in (rng.choice(others, size=need - 1, replace=False) if need > 1 else [])])
            out.append(self._one(s, fam, targets=targets, mclass=mc))
        return out


def effect_errors(model, system_id: str, data: list, max_items: int = 100) -> list[tuple[float, object]]:
    """(error, record) of the most recent intervention trajectories with a twin: the model's effect-prediction error over the
    primary horizon (squared error over the true effect power, floored), from the history up to the onset."""
    twins = {r.meta.get("twin_of"): r for r in data if getattr(r, "meta", {}).get("twin_of")}
    items = [r for r in data if r.protocol.get("events") and r.key in twins][-max_items:]
    out = []
    for r in items:
        tw = twins[r.key]
        dt = float(r.protocol["dt"])
        onset = min(P.event_start(e) for e in r.protocol["events"])
        i0 = round(onset / dt)
        h = max(1, round(0.125 * float(r.protocol["t_end"]) / dt))
        h = min(h, len(r.t) - 1 - i0)
        if h < 1:
            continue
        ev = [dict(e) for e in P.validate(dict(r.protocol))["events"]]
        for e in ev:
            for key in ("t", "t0", "t1"):
                if e.get(key) is not None:
                    e[key] = round(float(e[key]) - float(r.t[i0]), 9)
        try:
            pred = model.intervention_effect(system_id, r.x[: i0 + 1], r.u[: i0 + 1], r.u[i0: i0 + h + 1], ev, dt)
            eff = np.asarray(pred["effect"], float)[: h + 1]
            true = (np.asarray(r.y, float) - np.asarray(tw.y, float))[i0: i0 + h + 1]
            err = float(np.sum((eff - true) ** 2) / max(float(np.sum(true ** 2)), 1e-12 + 1e-6 * true.size))
            if not np.isfinite(err):
                err = 1e6
        except Exception:  # noqa: BLE001 - a failing prediction is the largest error
            err = 1e6
        out.append((err, r))
    return out


@register_designer
class GreedyErrorDesigner(_Base):
    name = "greedy_error"
    explore = 0.25

    def propose(self, system_id, system, model, data, n, budget_left, rng):
        s = self.sampler(system_id, system, rng)
        fams = self.families(system)
        if not fams:
            return []
        scored = effect_errors(model, system_id, data) if model is not None else []
        scored.sort(key=lambda er: -er[0])
        out = []
        for j in range(n):
            if not scored or rng.random() < self.explore:
                fam = fams[int(rng.integers(len(fams)))]
                out.append(self._one(s, fam, mclass=MAG_CLASSES[int(rng.integers(len(MAG_CLASSES)))]))
                continue
            _, r = scored[j % min(len(scored), max(1, n))]
            fam = r.family if r.family in fams else fams[int(rng.integers(len(fams)))]
            mc0 = (r.meta or {}).get("mclass", "moderate")
            i = ORDERED_CLASSES.index(mc0) if mc0 in ORDERED_CLASSES else 2
            mc = ORDERED_CLASSES[int(np.clip(i + int(rng.integers(-1, 2)), 0, len(ORDERED_CLASSES) - 1))]
            tg = sorted(P.intervened_units(r.protocol)) if fam not in ("edge.w", "edge.rm") else None
            try:
                out.append(self._one(s, fam, targets=tg, mclass=mc))
            except ValueError:
                out.append(self._one(s, fam, mclass=mc))
        return out


def structural_ranking(system: dict, data: list | None = None) -> list[int]:
    """Public targets ranked by connectivity: total |signed synapse count| from the unit onto observed / readout units in the public
    graph; without a graph, by the variance of the unit's activity in the passive data (units not observed rank last)."""
    targets = [int(u) for u in system.get("targets_public") or []]
    g = system.get("public_graph") or {}
    edges = g.get("edges_post_pre_signed_count") or []
    score = {u: 0.0 for u in targets}
    if edges:
        for post, pre, w in edges:
            if int(pre) in score and int(post) != int(pre):
                score[int(pre)] += abs(float(w))
    elif data:
        obs = {int(u): i for i, u in enumerate(system.get("observed") or [])}
        X = [r.x for r in data if not r.protocol.get("events")]
        if X:
            var = np.concatenate([np.asarray(x, float) for x in X]).var(axis=0)
            for u in targets:
                score[u] = float(var[obs[u]]) if u in obs else -1.0
    return sorted(targets, key=lambda u: (-score[u], u))


@register_designer
class StructuralDesigner(_Base):
    name = "structural"

    def __init__(self):
        super().__init__()
        self._order: list | None = None
        self._pos = 0

    def propose(self, system_id, system, model, data, n, budget_left, rng):
        s = self.sampler(system_id, system, rng)
        fams = self.families(system)
        if not fams:
            return []
        if self._order is None:
            ranked = structural_ranking(system, data)
            classes = ("moderate", "strong", "weak", "below")
            self._order = [(t, f, m) for m in classes for t in ranked for f in fams]
        out = []
        for _ in range(n):
            t, fam, mc = self._order[self._pos % len(self._order)]
            self._pos += 1
            need = N_TARGETS_NEEDED.get(fam, 1)
            targets = None
            if fam not in ("edge.w", "edge.rm"):
                ranked = structural_ranking(system, data)
                others = [u for u in ranked if u != t][: need - 1]
                if len(others) < need - 1:
                    continue
                targets = sorted([int(t)] + [int(u) for u in others])
            out.append(self._one(s, fam, targets=targets, mclass=mc))
        return out


@register_designer
class PassiveDesigner(_Base):
    """Two passive trajectories per requested experiment (the same simulator calls as an intervention and its twin)."""
    name = "passive"

    def propose(self, system_id, system, model, data, n, budget_left, rng):
        s = self.sampler(system_id, system, rng)
        fams = [f for f in ("obs.stim", "obs.init", "obs.wnoise", "obs.nominal") if f in system["split"]["families_train"]]
        out = []
        for j in range(2 * n):
            out.append(P.validate(s.obs(fams[j % len(fams)])))
        return out


@register_designer
class FixedDesigner(_Base):
    """A pre-registered design, independent of the loop seed."""
    name = "fixed"

    def __init__(self):
        super().__init__()
        self._pos = 0
        self._order: list | None = None

    def propose(self, system_id, system, model, data, n, budget_left, rng):
        frng = np.random.default_rng(int(hashlib.sha256(f"fixed|{system_id}".encode()).hexdigest()[:12], 16))
        s = self.sampler(system_id, system, frng)
        fams = self.families(system)
        if not fams:
            return []
        if self._order is None:
            pairs = [(f, t) for f in fams for t in (s.targets if f not in ("edge.w", "edge.rm") else [None])]
            self._order = [(f, t, m) for m in ("moderate", "weak", "strong", "below") for f, t in pairs]
        onset = s.snap(0.3 * s.T)
        out = []
        for _ in range(n):
            fam, t, mc = self._order[self._pos % len(self._order)]
            self._pos += 1
            need = N_TARGETS_NEEDED.get(fam, 1)
            targets = None
            if t is not None:
                others = [u for u in s.targets if u != t]
                targets = sorted([int(t)] + [int(u) for u in others[: need - 1]])
            out.append(self._one(s, fam, targets=targets, mclass=mc, onset=onset))
        return out


REFERENCE_DESIGNERS = ("random", "uniform", "magnitude_sweep", "greedy_error", "structural", "passive", "fixed")
