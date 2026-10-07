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
                    targets, magnitude class one step up / same / down, new onset and draw); 25 %: random (also the first round).
                    The error of an experiment is the evaluator's item error (PROTOCOL 5.1): the squared effect error over rows 1..h
                    of the primary horizon divided by max(true effect energy, n_t n_y f_s^2), f_s = 0.05 x the pooled training sd
                    of y (from the loop's passive training records), capped at 10 (review H, minor 5); it is computed on a fresh
                    copy of the model, so the designer never changes the learner's model
    structural      targets ranked by public connectivity (out-weight of a unit onto observed / readout units in the public graph;
                    without a graph, by passive-data variance), highest first, cycling families and magnitude classes
    passive         observational trajectories only (stimulus schedules, initial states, weight-noise draws, parameter draws)
    fixed           a pre-registered design independent of the loop seed: every (family, target) at the moderate magnitude with a
                    fixed onset (0.3 T), then the weak and strong classes, in a fixed order

Control (PROTOCOL 5.17, reported beside the success rule, never part of it):
    random_matched  the random design with its magnitudes MATCHED to a profile: the relative magnitudes (|amplitude| / the
                    capability's moderate magnitude of the kind) of the experiments another designer ran on the same system and loop
                    seed (`magnitude_profile`, `load_profile` from that loop's experiments.jsonl). Family, targets and onset are drawn
                    as by `random`; each event's magnitude is drawn from the profile's values of the same event kind (pooled over
                    kinds when the kind has none; the random magnitude classes when the profile is empty, counted as unmatched).
                    A control for large-effect selection: an active design that only chose large magnitudes does not beat it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from . import protocol as P
from .api import Designer, register_designer
from .evalio import FLOOR_FRAC, HORIZON_FRACTIONS, ITEM_CAP, PRIMARY, pooled_y_sd
from .sampling import MAG_CLASSES, N_TARGETS_NEEDED, FamilySampler, feasible, intervention_families, normalize_capability, public_seed_of

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


def effect_floor_sq(data: list) -> float:
    """f_s^2 of the evaluator (PROTOCOL 5.1: f_s = 0.05 x the pooled training sd of y) from the loop's training records: the records of
    split 'train' that are not twins (as the evaluator's public 'train' split), blow-ups excluded (`evalio.pooled_y_sd`)."""
    recs = [r for r in data if getattr(r, "split", "train") == "train" and not (getattr(r, "meta", None) or {}).get("twin_of")]
    if not recs:
        return 0.0
    return float((FLOOR_FRAC * pooled_y_sd([np.asarray(r.y, float) for r in recs], [np.asarray(r.x, float) for r in recs])) ** 2)


def _fresh(model):
    """A copy of the learner's model for the designer's own calls (the loop hands the same object back to the learner)."""
    from .fresh import Fresh
    try:
        return Fresh(model).get()
    except Exception:  # noqa: BLE001 - an uncopyable model is used as is (its own responsibility)
        return model


def effect_errors(model, system_id: str, data: list, max_items: int = 100, *, sysrec: dict | None = None) -> list[tuple[float, object]]:
    """(error, record) of the most recent intervention trajectories with a twin: the evaluator's item error (PROTOCOL 5.1; review H,
    minor 5) of the model's predicted effect over rows 1..h of the primary horizon (h = 12.5 % of the system's default duration),
    num / max(sum of the true effect energy, h n_y f_s^2), capped at ITEM_CAP; a failed prediction scores the cap."""
    twins = {r.meta.get("twin_of"): r for r in data if getattr(r, "meta", {}).get("twin_of")}
    items = [r for r in data if r.protocol.get("events") and r.key in twins][-max_items:]
    if not items:
        return []
    f2 = effect_floor_sq(data)
    m = _fresh(model)
    out = []
    for r in items:
        tw = twins[r.key]
        dt = float(r.protocol["dt"])
        onset = min(P.event_start(e) for e in r.protocol["events"])
        i0 = round(onset / dt)
        t_def = float((sysrec or {}).get("t_end_default") or r.protocol["t_end"])
        h = max(1, round(HORIZON_FRACTIONS[PRIMARY] * t_def / dt))
        h = min(h, len(r.t) - 1 - i0)
        if h < 1:
            continue
        ev = [dict(e) for e in P.validate(dict(r.protocol))["events"]]
        for e in ev:
            for key in ("t", "t0", "t1"):
                if e.get(key) is not None:
                    e[key] = round(float(e[key]) - float(r.t[i0]), 9)
        true = (np.asarray(r.y, float) - np.asarray(tw.y, float))[i0 + 1: i0 + h + 1]
        n_y = true.shape[1] if true.ndim == 2 else 1
        den = max(float(np.sum(true ** 2)), h * n_y * f2, 1e-300)
        try:
            pred = m.intervention_effect(system_id, r.x[: i0 + 1], r.u[: i0 + 1], r.u[i0: i0 + h + 1], ev, dt)
            eff = np.asarray(pred["effect"], float)[1: h + 1]
            num = float(np.sum((eff.reshape(true.shape) - true) ** 2))
            err = min(num, ITEM_CAP * den) / den if np.isfinite(num) else ITEM_CAP
        except Exception:  # noqa: BLE001 - a failing prediction scores the cap
            err = ITEM_CAP
        out.append((float(err), r))
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
        scored = effect_errors(model, system_id, data, sysrec=system) if model is not None else []
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
    """Two passive trajectories per requested experiment (the same simulator calls as an intervention and its twin). 'obs.init' is
    a restart from a nominal passive trajectory (LOG P4-D36), which a designer cannot plan without a source: it is left out."""
    name = "passive"

    def propose(self, system_id, system, model, data, n, budget_left, rng):
        s = self.sampler(system_id, system, rng)
        fams = [f for f in ("obs.stim", "obs.wnoise", "obs.nominal") if f in system["split"]["families_train"]]
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


def _moderate(cap: dict, kind: str, fld: str | None = None) -> float:
    if kind == "param":
        return float(cap["param"]["moderate"][fld])
    return float(cap[kind if kind != "current_seq" else "current"]["moderate"])


def event_magnitudes(protocol: dict, sysrec: dict) -> list[dict]:
    """The relative magnitudes {"kind", "rel"} of the events of one protocol: rel = |amplitude| / the capability's moderate magnitude
    of the kind (kicks: the largest |delta|; currents and current sequences: the largest |I| over the current moderate; edge scalings:
    the depth 1 - factor over the edge moderate (removals have no magnitude); parameter changes: |g - 1|, |c - 1| or |d| over the
    field's moderate). Silencing has no magnitude (skipped)."""
    q = P.validate(protocol)
    cap = normalize_capability(sysrec.get("capability"), t_end=float(sysrec.get("t_end_default") or q["t_end"]), dt=float(q["dt"]),
                               input_dim=int(sysrec.get("input_dim", 1)))
    out = []
    for e in q["events"]:
        k = e["kind"]
        if k == "kick":
            out.append({"kind": k, "rel": max(abs(float(v)) for v in e["delta"].values()) / _moderate(cap, k)})
        elif k == "current":
            out.append({"kind": k, "rel": max(abs(float(v)) for v in e["targets"].values()) / _moderate(cap, k)})
        elif k == "current_seq":
            out.append({"kind": k, "rel": max(abs(float(v)) for lst in e["targets"].values() for v in lst) / _moderate(cap, k)})
        elif k == "edge_scale" and float(e["factor"]) > 0:
            out.append({"kind": k, "rel": abs(1.0 - float(e["factor"])) / _moderate(cap, k)})
        elif k == "param":
            for v in e["targets"].values():
                for fld, x in v.items():
                    dev = abs(float(x) - 1.0) if fld in ("gain", "tau") else abs(float(x))
                    out.append({"kind": k, "rel": dev / _moderate(cap, k, fld)})
    return out


def magnitude_profile(protocols: list[dict], sysrec: dict) -> list[dict]:
    """The relative magnitudes of every event of the INTERVENTION protocols a designer ran (the profile of `random_matched`)."""
    out = []
    for q in protocols:
        if q and (q.get("events") or []):
            out += event_magnitudes(q, sysrec)
    return out


def load_profile(loop_dir: Path | str, sysrec: dict) -> list[dict]:
    """The magnitude profile of a finished loop from its experiments.jsonl (written by `loop.run_loop`)."""
    rows = [json.loads(line) for line in (Path(loop_dir) / "experiments.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    return magnitude_profile([r["protocol"] for r in rows if r.get("protocol") and not r.get("twin_of")], sysrec)


@register_designer
class MagnitudeMatchedDesigner(RandomDesigner):
    """The random design with magnitudes matched to a profile (see the module docstring). `MagnitudeMatchedDesigner(profile)`; the
    registry's no-argument instance has an empty profile and behaves like `random` (every event counted as unmatched)."""
    name = "random_matched"

    def __init__(self, profile: list[dict] | None = None):
        super().__init__()
        self.profile = [dict(p) for p in (profile or []) if p.get("rel") is not None and np.isfinite(float(p["rel"]))]
        self.n_matched = 0
        self.n_unmatched = 0

    @classmethod
    def from_loop(cls, loop_dir: Path | str, sysrec: dict) -> MagnitudeMatchedDesigner:
        return cls(load_profile(loop_dir, sysrec))

    def _draw(self, kind: str, rng: np.random.Generator) -> float | None:
        same = [p["rel"] for p in self.profile if p["kind"] == kind]
        pool = same or [p["rel"] for p in self.profile]
        if not pool:
            return None
        return float(pool[int(rng.integers(len(pool)))])

    def _rescale(self, q: dict, s: FamilySampler, rng: np.random.Generator) -> dict:
        cap = s.cap
        q = json.loads(json.dumps(q))
        for e in q["events"]:
            k = e["kind"]
            if k == "silence" or (k == "edge_scale" and float(e["factor"]) == 0.0):
                continue
            rel = self._draw(k, rng)
            if rel is None:
                self.n_unmatched += 1
                continue
            self.n_matched += 1
            if k == "kick":
                a = min(rel * _moderate(cap, k), float(cap["kick"]["max"]))
                e["delta"] = {u: round(float(np.sign(v) or 1.0) * a, 6) for u, v in e["delta"].items()}
            elif k == "current":
                a = min(rel * _moderate(cap, k), float(cap["current"]["max"]))
                e["targets"] = {u: round(float(np.sign(v) or 1.0) * a, 6) for u, v in e["targets"].items()}
            elif k == "current_seq":
                peak = max(abs(float(v)) for lst in e["targets"].values() for v in lst)
                if peak > 0:
                    f = min(rel * _moderate(cap, k), float(cap["current"]["max"])) / peak
                    e["targets"] = {u: [round(float(v) * f, 6) for v in lst] for u, lst in e["targets"].items()}
            elif k == "edge_scale":
                depth = min(rel * _moderate(cap, k), 3.0 * _moderate(cap, k), 0.95)
                e["factor"] = round(1.0 - depth, 6)
            elif k == "param":
                for u, v in list(e["targets"].items()):
                    new = {}
                    for fld, x in v.items():
                        dev = min(rel * _moderate(cap, k, fld), 3.0 * _moderate(cap, k, fld))
                        if fld in ("gain", "tau"):
                            new[fld] = round(max(0.05, 1.0 + (1.0 if float(x) >= 1.0 else -1.0) * dev), 6)
                        else:
                            new[fld] = round((1.0 if float(x) >= 0.0 else -1.0) * dev, 6)
                    e["targets"][u] = new
        return P.validate(q)

    def propose(self, system_id, system, model, data, n, budget_left, rng):
        s = self.sampler(system_id, system, rng)
        fams = self.families(system)
        if not fams:
            return []
        out = []
        for _ in range(n):
            fam = fams[int(rng.integers(len(fams)))]
            q = self._one(s, fam, mclass=MAG_CLASSES[int(rng.integers(len(MAG_CLASSES)))])
            out.append(self._rescale(q, s, rng) if self.profile else q)
            if not self.profile:
                self.n_unmatched += sum(1 for e in q["events"] if e["kind"] != "silence")
        return out


REFERENCE_DESIGNERS = ("random", "uniform", "magnitude_sweep", "greedy_error", "structural", "passive", "fixed")
CONTROL_DESIGNERS = ("random_matched",)
