"""Level C DRY-RUN stand-in method (scripts/p4/level_c.py --dry-run-dev; research/phase4/LEVEL_C_DRIVER.md). NOT a candidate: it
never enters a room, a tournament or a report as a method. It exists so the Level C driver can run every stage before the method
lock with a model that has what the locked method will have (a compact k with a plausible range, a read-in, a native lift, an own
designer, per-system parts).

The benchmark's PCA-k reference learner (`brainir_causal.refs`, `ProjectionStateModel("pca", k)`) fitted per system with a LIGHT
learner configuration (fewer training steps: the stand-in's speed is arbitrary, only the job structure matters). k = the number of
principal components of the public training x explaining 90 % of its variance, capped at the compact limit max(1, N_obs // 5) and
at 8, so bootstrap refits can disagree; reported range [k - 1, k + 1] within [1, cap]. Own designer: the reference `uniform` designer.
"""

from __future__ import annotations

import time

import numpy as np

from brainir_causal.api import CausalStateMethod, CausalStateModel, register

LIGHT = {"steps_one": 300, "steps_multi": 40, "readout_steps": 300, "shrink_pairs": 16, "threads": 2}
VAR_TARGET = 0.9
K_MAX = 8
CHECKPOINT_BUDGETS = (10, 25, 50, 100, 200)          # PROTOCOL 5.17 (public)


def choose_k(records: list) -> tuple[int, int]:
    """(k, cap): components explaining VAR_TARGET of the training x variance, within [1, cap]; cap = min(K_MAX, max(1, N_obs // 5))."""
    X = np.concatenate([np.asarray(r.x, np.float64) for r in records if len(r.x)])
    X = X[:: max(1, len(X) // 40_000)]
    cap = max(1, min(K_MAX, X.shape[1] // 5))
    s = np.linalg.svd(X - X.mean(0), compute_uv=False)
    frac = np.cumsum(s ** 2) / max(float((s ** 2).sum()), 1e-300)
    k = int(np.searchsorted(frac, VAR_TARGET) + 1)
    return max(1, min(k, cap)), cap


class StandinModel(CausalStateModel):
    """Per-system PCA-k reference models behind the CausalStateModel API (every call delegated to the system's part)."""

    def __init__(self, parts: dict, caps: dict, fit_s: float):
        self.parts = dict(parts)
        self.caps = dict(caps)
        self.k = {sid: int(m.k[sid]) for sid, m in self.parts.items()}
        self.fit_s = float(fit_s)

    def _p(self, sid):
        return self.parts[sid]

    def encode(self, system_id, x_hist, u_hist, dt):
        return self._p(system_id).encode(system_id, x_hist, u_hist, dt)

    def rollout(self, system_id, z0, u_future, events, dt):
        return self._p(system_id).rollout(system_id, z0, u_future, events, dt)

    def readout(self, system_id, z, u):
        return self._p(system_id).readout(system_id, z, u)

    def supports(self, system_id, event_kind):
        return bool(self._p(system_id).supports(system_id, event_kind))

    def step(self, system_id, z, u, events_active, dt):
        return self._p(system_id).step(system_id, z, u, events_active, dt)

    def read_in(self, system_id, z, event):
        return self._p(system_id).read_in(system_id, z, event)

    def lift(self, system_id, x_hist, u_hist, delta_z, n_candidates=3, constraints=None):
        return self._p(system_id).lift(system_id, x_hist, u_hist, delta_z, n_candidates, constraints)

    def intervention_effect(self, system_id, x_hist, u_hist, u_future, events, dt):
        return self._p(system_id).intervention_effect(system_id, x_hist, u_hist, u_future, events, dt)

    def uncertainty(self, system_id, x_hist, u_hist, u_future, events, dt):
        return self._p(system_id).uncertainty(system_id, x_hist, u_hist, u_future, events, dt)

    def validity(self, system_id, x_hist, u_hist, events):
        return self._p(system_id).validity(system_id, x_hist, u_hist, events)

    def info(self):
        infos = {sid: (m.info() or {}) for sid, m in self.parts.items()}
        npar = {"encoder": {}, "transition": 0, "read_in": {}, "readout": {}}
        for sid, inf in infos.items():
            n = inf.get("n_params") or {}
            npar["encoder"][sid] = (n.get("encoder") or {}).get(sid, 0)
            npar["read_in"][sid] = (n.get("read_in") or {}).get(sid, 0)
            npar["readout"][sid] = (n.get("readout") or {}).get(sid, 0)
            npar["transition"] += int(n.get("transition") or 0)
        return {"k": dict(self.k),
                "k_range": {sid: [max(1, k - 1), min(self.caps[sid], k + 1)] for sid, k in self.k.items()},
                "method": "levelc_standin_pca", "method_version": "dry-run-1", "n_params": npar,
                "history": {sid: (inf.get("history") or {}).get(sid, 1) for sid, inf in infos.items()},
                "train_cost": {"cpu_s": round(self.fit_s, 2)}, "sharing": {"mode": "independent"},
                "abstain": {sid: {"no_compact_state": False} for sid in self.k}}


@register
class StandinPCAMethod(CausalStateMethod):
    """The dry-run stand-in (module docstring)."""
    name = "levelc_standin_pca"
    version = "dry-run-1"
    default_config: dict = {}
    supported_sharing = ("auto", "independent")
    supports_adaptation = False

    def fit(self, data, *, systems, config=None, seed=0):
        from brainir_causal.refs import LearnerConfig, fit_reference
        cfg = dict(config or {})
        if cfg.get("sharing") not in (None, "auto", "independent"):
            raise NotImplementedError(f"sharing {cfg.get('sharing')!r}: the stand-in fits independent systems only")
        if cfg.get("adapt_from") is not None:
            raise NotImplementedError("the stand-in cannot adapt from a shared model")
        t0 = time.process_time()
        parts, caps = {}, {}
        for sid, rec in systems.items():
            recs = [r for r in data if r.system_id == sid]
            if cfg.get("k") is not None:
                k, cap = int(cfg["k"]), max(1, min(K_MAX, len(rec["observed"]) // 5))
            else:
                k, cap = choose_k([r for r in recs if not (r.meta or {}).get("twin_of")])
            lc = LearnerConfig(**{**LIGHT, "seed": int(seed)})
            parts[sid] = fit_reference("pca_k", sid, recs, rec, k=k, cfg=lc)
            caps[sid] = cap
        return StandinModel(parts, caps, time.process_time() - t0)

    def update(self, model, new_data, *, data_all, systems, config=None, seed=0):
        """Refit on everything only when the loop's spent budget (PROTOCOL 5.17: an intervention experiment costs 1, a passive
        proposal 1/2) reaches one of the checkpoint budgets, so every checkpoint model is fitted on all the loop's data; between
        checkpoints the current model is kept (the stand-in's cost is arbitrary: 5 refits per loop instead of one per batch)."""
        loop = [r for r in data_all if (r.meta or {}).get("designer") and not (r.meta or {}).get("twin_of")]
        spent = sum(1.0 if (r.protocol or {}).get("events") else 0.5 for r in loop)
        prev = float(getattr(model, "_spent", 0.0)) if model is not None else -1.0
        if model is None or any(prev < c <= spent + 1e-9 for c in CHECKPOINT_BUDGETS):
            model = self.fit(data_all, systems=systems, config=config, seed=seed)
        model._spent = spent
        return model

    def designer(self):
        from brainir_causal.designers import UniformDesigner
        return UniformDesigner()
