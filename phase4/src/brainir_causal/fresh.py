"""Fresh-copy isolation of fitted models during evaluation (PROTOCOL section 5, "Isolation and leakage rules").

Every model call the evaluator makes (encode, rollout, readout, intervention_effect, lift, read_in, uncertainty, validity) runs on a
FRESH copy of the model as it was when the snapshot was taken, i.e. BEFORE the evaluation's first call. Nothing a call stores in the
model object (for example the last encoded history, which for some checks is a TRUE FUTURE history) can reach another call: every
prediction is a function of that call's arguments and the fitted parameters only. Within one call the model may of course use what it
computes (intervention_effect encodes and then rolls out on the same copy).

State kept at module or class level is outside this guard; the code audit and the decoy / Markov checks cover it.

The evaluator's own reference models (`brainir_causal.refs`) are trusted and not copied (some carry large lookup tables).
Take the snapshot before anything else touches the model: `F = Fresh(model)` first, then only `F.<call>(...)`.
"""

from __future__ import annotations

import copy
import pickle
from typing import Any

import numpy as np

TRUSTED_MODULES = ("brainir_causal.refs",)


class ModelCallError(RuntimeError):
    """A model call raised; the evaluator scores the call as a failed (non-finite) prediction and records the message."""


class Fresh:
    """Snapshot of a fitted model; every method call runs on a new unpickled copy of the snapshot."""

    def __init__(self, model: Any):
        self._blob: bytes | None = None
        self._pristine: Any = None
        self._same: Any = None
        self.n_copies = 0
        mod = type(model).__module__
        if any(mod == t or mod.startswith(t + ".") for t in TRUSTED_MODULES):
            self._same = model
            return
        try:
            self._blob = pickle.dumps(model, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:  # noqa: BLE001 - unpicklable models fall back to deep copies
            self._pristine = copy.deepcopy(model)

    @property
    def trusted(self) -> bool:
        return self._same is not None

    def get(self) -> Any:
        """A new, independent copy of the model as it was at snapshot time."""
        if self._same is not None:
            return self._same
        self.n_copies += 1
        return pickle.loads(self._blob) if self._blob is not None else copy.deepcopy(self._pristine)

    # ---------------------------------------------------------------------------------------------- API calls on fresh copies
    def encode(self, sid: str, x_hist, u_hist, dt: float) -> np.ndarray:
        return np.asarray(self.get().encode(sid, x_hist, u_hist, dt), dtype=np.float64).reshape(-1)

    def rollout(self, sid: str, z0, u_future, events: list[dict], dt: float) -> dict:
        return self.get().rollout(sid, np.asarray(z0, dtype=np.float64), u_future, events, dt)

    def readout(self, sid: str, z, u):
        return self.get().readout(sid, z, u)

    def intervention_effect(self, sid: str, x_hist, u_hist, u_future, events: list[dict], dt: float) -> dict:
        return self.get().intervention_effect(sid, x_hist, u_hist, u_future, events, dt)

    def lift(self, sid: str, x_hist, u_hist, delta_z, n_candidates: int = 3, constraints: dict | None = None) -> list[dict]:
        return self.get().lift(sid, x_hist, u_hist, np.asarray(delta_z, dtype=np.float64), n_candidates, constraints)

    def read_in(self, sid: str, z, event: dict) -> dict:
        return self.get().read_in(sid, np.asarray(z, dtype=np.float64), event)

    def uncertainty(self, sid: str, x_hist, u_hist, u_future, events: list[dict], dt: float) -> dict:
        return self.get().uncertainty(sid, x_hist, u_hist, u_future, events, dt)

    def validity(self, sid: str, x_hist, u_hist, events: list[dict]) -> dict:
        return self.get().validity(sid, x_hist, u_hist, events)

    def supports(self, sid: str, kind: str) -> bool:
        return bool(self.get().supports(sid, kind))

    def info(self) -> dict:
        return dict(self.get().info() or {})

    def k(self, sid: str) -> int | None:
        m = self.get()
        ks = (m.info() or {}).get("k") or getattr(m, "k", {}) or {}
        return int(ks[sid]) if sid in ks and ks[sid] is not None else None


def as_fresh(model_or_fresh: Any) -> Fresh:
    """Accept a model or an existing Fresh wrapper (the harness creates ONE Fresh per evaluated model and passes it around)."""
    return model_or_fresh if isinstance(model_or_fresh, Fresh) else Fresh(model_or_fresh)


def safe_call(fn, *args, **kwargs) -> tuple[Any, str | None]:
    """(result, None) or (None, error message). Model errors never abort an evaluation; they are scored as failed predictions."""
    try:
        return fn(*args, **kwargs), None
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {str(exc)[:300]}"
