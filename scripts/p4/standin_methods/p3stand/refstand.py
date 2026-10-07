"""STAND-IN method for the dry runs of the post-lock drivers (fork P3; never a candidate, never in a room).

The benchmark's PCA-k reference learner (`brainir_causal.refs.ProjectionStateModel`, trusted benchmark code a method may import: it
is a public module) wrapped as a CausalStateMethod with FAKE ablation switches that follow the contract of `api.ABLATION_SWITCHES`:
every name is declared in info()["ablation_switches"] (honoured, or "not_applicable" with a reason), `config["ablate"]` is applied
and info()["ablated"] repeats the applied list. The switches only exercise the drivers; they are not a scientific ablation of this
learner (e.g. `mediation_loss` switches off the reference's effect calibration, which is the nearest objective term it has).

    honoured          interventional_training   every record with events and every twin dropped before fitting
                      mediation_loss            the effect-calibration term off (LearnerConfig.effect_shrinkage = False)
                      closure_loss              the paired multi-step phase off (LearnerConfig.steps_multi = 0)
                      native_lift               lift() returns []
                      multiple_lift_consistency lift() returns one candidate only
                      dimension_penalty         k from the unpenalised criterion (99.9 % instead of 95 % explained variance)
                      state_bottleneck          the FULL-STATE reference (observed microstate + delay traces) instead of PCA-k
    not applicable    active_design, history_delay, uncertainty_ensemble, shared_dynamics (reasons in NOT_APPLICABLE)

`p3stand_broken` declares every switch honoured but applies none (the drivers' negative test: they must fail loudly on it).
The training budget is small (FAST) so the dry runs measure the drivers, not the learner.
"""

from __future__ import annotations

import numpy as np

from brainir_causal import refs
from brainir_causal.api import ABLATION_SWITCHES, CausalStateMethod, CausalStateModel, register

HONOURED = ("interventional_training", "mediation_loss", "closure_loss", "native_lift", "multiple_lift_consistency",
            "dimension_penalty", "state_bottleneck")
NOT_APPLICABLE = {
    "active_design": "the stand-in has no designer of its own",
    "history_delay": "the stand-in's compact encoder reads the current sample only",
    "uncertainty_ensemble": "the stand-in reports no uncertainty and has no ensemble",
    "shared_dynamics": "the stand-in fits every system independently",
}
FAST = {"steps_one": 600, "steps_multi": 100, "readout_steps": 500, "shrink_pairs": 24}
K_RULE = (0.95, 2, 8)             # explained-variance threshold, k_min, k_max (the "penalised" dimension rule)
K_RULE_UNPENALISED = (0.999, 2, 16)


def declaration() -> dict:
    out = {n: "honoured" for n in HONOURED}
    out.update({n: {"status": "not_applicable", "reason": r} for n, r in NOT_APPLICABLE.items()})
    assert set(out) == set(ABLATION_SWITCHES), "the stand-in must declare every switch of the API vocabulary"
    return out


def pca_k(records: list, frac: float, k_min: int, k_max: int) -> int:
    X = np.concatenate([np.asarray(r.x, np.float64) for r in records])
    X = X[:: max(1, len(X) // 40_000)]
    s = np.linalg.svd(X - X.mean(0), compute_uv=False) ** 2
    if not np.isfinite(s).all() or s.sum() <= 0:
        return k_min
    k = int(np.searchsorted(np.cumsum(s) / s.sum(), frac) + 1)
    return int(min(max(k, k_min), k_max, X.shape[1]))


class StandinModel(CausalStateModel):
    """The wrapped reference model (every API call delegated) with the lift switches and the declarations."""

    def __init__(self, inner, sid: str, ablated: list[str], method: str, declare: dict, k_rule: tuple):
        self.inner = inner
        self.sid = sid
        self.k = dict(inner.k)
        self._ablated = sorted(ablated)
        self._method = method
        self._declare = dict(declare)
        self._k_rule = tuple(k_rule)

    def encode(self, system_id, x_hist, u_hist, dt):
        return self.inner.encode(system_id, x_hist, u_hist, dt)

    def rollout(self, system_id, z0, u_future, events, dt):
        return self.inner.rollout(system_id, z0, u_future, events, dt)

    def readout(self, system_id, z, u):
        return self.inner.readout(system_id, z, u)

    def supports(self, system_id, event_kind):
        return self.inner.supports(system_id, event_kind)

    def step(self, system_id, z, u, events_active, dt):
        return self.inner.step(system_id, z, u, events_active, dt)

    def read_in(self, system_id, z, event):
        return self.inner.read_in(system_id, z, event)

    def intervention_effect(self, system_id, x_hist, u_hist, u_future, events, dt):
        out = self.inner.intervention_effect(system_id, x_hist, u_hist, u_future, events, dt)
        out["validity"] = self.validity(system_id, x_hist, u_hist, events)
        return out

    def validity(self, system_id, x_hist, u_hist, events):
        kinds_ok = all(self.inner.supports(system_id, e["kind"]) for e in events)
        cov = bool(getattr(self.inner, "covers", lambda s, e: True)(system_id, events))
        ok = bool(kinds_ok and cov)
        return {"in_domain": ok, "score": 1.0 if ok else 0.0,
                "reasons": [] if ok else (["event kind never seen in training"] if not kinds_ok else ["target never intervened"])}

    def lift(self, system_id, x_hist, u_hist, delta_z, n_candidates=3, constraints=None):
        if "native_lift" in self._ablated:
            return []
        n = 1 if "multiple_lift_consistency" in self._ablated else n_candidates
        return self.inner.lift(system_id, x_hist, u_hist, delta_z, n_candidates=n, constraints=constraints)

    def info(self):
        inf = dict(self.inner.info() or {})
        inf.update({"method": self._method, "method_version": "standin-1", "ablation_switches": dict(self._declare),
                    "ablated": list(self._ablated), "k_rule": f"explained variance >= {self._k_rule[0]} (k in [{self._k_rule[1]}, "
                                                              f"{self._k_rule[2]}])"})
        return inf


class _StandinBase(CausalStateMethod):
    version = "standin-1"
    default_config: dict = {}
    supported_sharing = ("auto", "independent")
    supports_adaptation = False
    apply_switches = True

    def fit(self, data, *, systems, config=None, seed=0):
        cfg = dict(config or {})
        ablate = [str(a) for a in (cfg.get("ablate") or [])]
        unknown = sorted(set(ablate) - set(ABLATION_SWITCHES))
        if unknown:
            raise ValueError(f"unknown ablation switches {unknown}")
        na = sorted(set(ablate) & set(NOT_APPLICABLE))
        if na and self.apply_switches:
            raise ValueError(f"ablation switches {na} are declared not applicable (nothing to switch off)")
        if len(systems) != 1:
            raise NotImplementedError("the stand-in fits one system at a time")
        sid = next(iter(systems))
        sysrec = systems[sid]
        on = set(ablate) if self.apply_switches else set()
        recs = [r for r in data if r.system_id == sid]
        if "interventional_training" in on:
            recs = [r for r in recs if not r.events() and not (r.meta or {}).get("twin_of")]
        if not recs:
            raise ValueError("no training records")
        lc = dict(FAST, seed=int(seed), threads=int(cfg.get("threads", 3)))
        if "mediation_loss" in on:
            lc["effect_shrinkage"] = False
        if "closure_loss" in on:
            lc["steps_multi"] = 0
        rule = K_RULE_UNPENALISED if "dimension_penalty" in on else K_RULE
        lcfg = refs.LearnerConfig(**lc)
        if "state_bottleneck" in on:
            inner = refs.fit_reference("full_state", sid, recs, sysrec, cfg=lcfg)
        else:
            k = int(cfg["k"]) if cfg.get("k") else pca_k(recs, *rule)
            inner = refs.fit_reference("pca_k", sid, recs, sysrec, k=k, cfg=lcfg)
        applied = sorted(on) if self.apply_switches else []
        return StandinModel(inner, sid, applied, self.name, declaration(), rule)


@register
class StandinRef(_StandinBase):
    """PCA-k reference with contract-conforming fake ablation switches."""
    name = "p3stand_ref"


@register
class StandinBroken(_StandinBase):
    """Declares every switch honoured-or-not-applicable but APPLIES NONE (info()['ablated'] stays empty): the negative test."""
    name = "p3stand_broken"
    apply_switches = False


@register
class StandinFullState(CausalStateMethod):
    """A FULL-STATE baseline stand-in (the reference's full-state learner, FAST budget), for the bounds / self-audit dry runs."""
    name = "p3stand_fullstate"
    version = "standin-1"

    def fit(self, data, *, systems, config=None, seed=0):
        sid = next(iter(systems))
        lcfg = refs.LearnerConfig(**dict(FAST, seed=int(seed), threads=int((config or {}).get("threads", 3))))
        return refs.fit_reference("full_state", sid, [r for r in data if r.system_id == sid], systems[sid], cfg=lcfg)


@register
class StandinIdShortcut(CausalStateMethod):
    """An ID-SHORTCUT baseline stand-in (the reference's ID learner: readout history + intervention identity, no state)."""
    name = "p3stand_idshortcut"
    version = "standin-1"

    def fit(self, data, *, systems, config=None, seed=0):
        sid = next(iter(systems))
        return refs.fit_reference("id_shortcut", sid, [r for r in data if r.system_id == sid], systems[sid],
                                  cfg=refs.LearnerConfig(seed=int(seed)))


@register
class StandinNoEffect(CausalStateMethod):
    """An INPUT-ONLY / no-effect baseline stand-in (the reference's passive full-state model with every event ignored)."""
    name = "p3stand_noeffect"
    version = "standin-1"

    def fit(self, data, *, systems, config=None, seed=0):
        sid = next(iter(systems))
        lcfg = refs.LearnerConfig(**dict(FAST, seed=int(seed), threads=int((config or {}).get("threads", 3))))
        return refs.fit_reference("no_effect", sid, [r for r in data if r.system_id == sid], systems[sid], cfg=lcfg)
