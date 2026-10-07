"""Read access to the Level C run (scripts/p4/level_c.py; its RunStore layout: <run_dir>/results/<job id>.pkl for every finished job,
<run_dir>/models/<job id>.bin for fitted models) and to the Level B-fixed choices (research/phase4/LEVEL_B_FIXED.json). ORCHESTRATOR
SIDE. The post-lock studies REUSE the Level C fits (the same model bytes the confirmatory evaluation scored) instead of refitting.

Job ids (levelc_lib.build_plan): the locked method's fits fit__<sid>__s<seed> (seed 0 = the primary fit), its bootstrap refits
refit__<sid>__b<b>, its evaluation eval__<sid>; baselines bfit__<sid>__<name> / beval__<sid>__<name>; references refs__<sid> (the
k-free references' results). <sid> and <name> pass through `safe`.

ROLE SOURCES (used by the self-audit configuration): "method" | "baseline:<name>" | "ref:<name>" | "fixed:full_state_bound" |
"fixed:id_comparator" (the Level B-fixed choice of each system, itself "ref:<name>" or "baseline:<method>"), or a directory of the
studies' own layout (<dir>/evals/<sid>_s<seed>.pkl, fits/<sid>_s<seed>.json, refits/<sid>_b<b>.json).
"""

from __future__ import annotations

import pickle
from pathlib import Path

from brainir_causal import suites as SU

from . import common as C

LEVEL_B_FIXED = C.ROOT / "research" / "phase4" / "LEVEL_B_FIXED.json"


def safe(s: str) -> str:
    return SU._safe(str(s)).replace("/", "_")


def unwrap(res):
    """The job's own output (iso "call" results are {"result": <fn output>, "iso": ...}; eval results {"result": evaluation, ...})."""
    return res.get("result") if isinstance(res, dict) and isinstance(res.get("result"), dict) else res


class LevelCStore:
    def __init__(self, run_dir: Path | str):
        self.dir = Path(run_dir)
        if not (self.dir / "results").is_dir():
            raise FileNotFoundError(f"{self.dir} is not a Level C run directory (no results/)")

    def get(self, job_id: str):
        p = self.dir / "results" / f"{job_id}.pkl"
        if not p.exists():
            return None
        with open(p, "rb") as fh:
            return pickle.load(fh)

    def ok(self, job_id: str):
        r = self.get(job_id)
        if r is None or isinstance(r, BaseException):
            return None
        if isinstance(r, dict) and r.get("error") and "result" not in r and "model" not in r and "side" not in r:
            return None
        return r

    def model_path(self, job_id: str) -> Path:
        return self.dir / "models" / f"{job_id}.bin"

    # ---------------------------------------------------------------- the locked method
    def fit_id(self, sid: str, seed: int = 0) -> str:
        return f"fit__{safe(sid)}__s{seed}"

    def fit_side(self, sid: str, seed: int = 0) -> dict | None:
        r = self.ok(self.fit_id(sid, seed))
        return dict(r.get("side") or {}) if isinstance(r, dict) else None

    def fit_model(self, sid: str, seed: int = 0) -> Path | None:
        p = self.model_path(self.fit_id(sid, seed))
        return p if p.exists() else None

    def refit_side(self, sid: str, b: int) -> dict | None:
        r = self.ok(f"refit__{safe(sid)}__b{b}")
        return dict(r.get("side") or {}) if isinstance(r, dict) else None

    def method_eval(self, sid: str) -> dict | None:
        ev = unwrap(self.ok(f"eval__{safe(sid)}"))
        return ev if isinstance(ev, dict) and ev.get("result") is not None else None

    # ---------------------------------------------------------------- baselines / references
    def baseline_eval(self, sid: str, name: str) -> dict | None:
        ev = unwrap(self.ok(f"beval__{safe(sid)}__{safe(name)}"))
        return ev if isinstance(ev, dict) and ev.get("result") is not None else None

    def baseline_side(self, sid: str, name: str) -> dict | None:
        r = self.ok(f"bfit__{safe(sid)}__{safe(name)}")
        return dict(r.get("side") or {}) if isinstance(r, dict) else None

    def refs(self, sid: str) -> dict:
        out = unwrap(self.ok(f"refs__{safe(sid)}"))
        return dict(out.get("results") or {}) if isinstance(out, dict) else {}

    def ref_eval(self, sid: str, name: str) -> dict | None:
        """A reference's result wrapped like an evaluation ({"sid", "result"})."""
        res = self.refs(sid).get(name)
        return {"sid": sid, "result": res} if res else None


def model_source(sid: str, seed: int, *, fits_from: str | Path | None = None, levelc_run: str | Path | None = None) -> Path | None:
    """The fitted model bytes of the locked method on one system: a Level C run (fit__<sid>__s<seed>.bin) or a directory of the
    studies' layout (<dir>/fits/<sid>_s<seed>.pkl)."""
    if levelc_run:
        return LevelCStore(levelc_run).fit_model(sid, seed)
    if fits_from:
        p = Path(fits_from) / "fits" / f"{SU._safe(sid)}_s{seed}.pkl"
        return p if p.exists() else None
    return None


def fixed() -> dict:
    return C.load_json(LEVEL_B_FIXED, {}) or {}


def fixed_choice(fx: dict, key: str, sid: str) -> str:
    """As levelc_lib.fixed_choice: the per-system choice, else the suite default, else the reference."""
    v = fx.get(key) or {}
    if isinstance(v, str):
        return v
    return (v.get("per_system") or {}).get(sid) or v.get("default") or {"full_state_bound": "ref:full_state",
                                                                          "id_comparator": "ref:id_shortcut"}[key]


def resolve_eval(store: LevelCStore | None, source: str, sid: str, fx: dict | None = None) -> dict | None:
    """The evaluation ({"sid", "result", ...}) of a role source on one system (module docstring)."""
    if store is None:
        return None
    if source == "method":
        return store.method_eval(sid)
    kind, _, name = source.partition(":")
    if kind == "baseline":
        return store.baseline_eval(sid, name)
    if kind == "ref":
        return store.ref_eval(sid, name)
    if kind == "fixed":
        return resolve_eval(store, fixed_choice(fx if fx is not None else fixed(), name, sid), sid, fx)
    raise ValueError(f"unknown role source {source!r}")
