"""Suite evaluation driver (ORCHESTRATOR SIDE; reads hidden data and synthetic truth; never enters a clean room).

A *suite* is a dataset directory with public train / val trajectories and the held-out evaluation material of the same systems:
- synthetic suites (data/phase3/synthetic/<tier>/): test + twin + pool rows in the same directory, truth in a separate directory;
- the real suite: data/phase3/real_public/ (train / val) and data/phase3/real_hidden/ (test / twin / pool; generated after the
  method lock).

Method fits run in sandboxed subprocesses (brainir_state.runner) that can read only a FIT VIEW of the suite (train / val rows,
hard-linked into a separate directory), the method's code copy and their output directory. Evaluation loads the pickled model in a
worker process that installs the EVAL guard after the held-out data are in memory (method code on the call stack cannot open files,
start processes or connect anywhere).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from . import evaluate as E
from .data import Dataset, Trajectory
from .harness import REAL_CFG, REAL_ROLES, SYNTH_CFG, SYNTH_ROLES, evaluate_system, fit_references, hidden_sets, pca_basis

FIT_SPLITS = ("train", "val")


# ------------------------------------------------------------------------------------------------------------ data access
class SuiteData:
    def __init__(self, public_dir: Path | str, *, kind: str, truth_dir: Path | str | None = None, hidden_dir: Path | str | None = None,
                 micro_dir: Path | str | None = None):
        self.public_dir = Path(public_dir)
        self.pub = Dataset(self.public_dir)
        self.hid = Dataset(hidden_dir) if hidden_dir else self.pub
        self.micro_dir = Path(micro_dir) if micro_dir else Path(hidden_dir or public_dir)
        self.kind = kind
        self.cfg = SYNTH_CFG if kind == "synthetic" else REAL_CFG
        self.roles = SYNTH_ROLES if kind == "synthetic" else REAL_ROLES
        self.truth_dir = Path(truth_dir) if truth_dir else None
        self.truth = json.loads((self.truth_dir / "truth.json").read_text(encoding="utf-8")) if self.truth_dir else None
        self._train: dict[str, list[Trajectory]] = {}
        self._hidden: dict[str, dict] = {}

    @property
    def systems(self) -> list[str]:
        return sorted(self.pub.systems)

    def sysinfo(self, sid: str) -> dict:
        return self.pub.systems[sid]

    def train(self, sid: str) -> list[Trajectory]:
        if sid not in self._train:
            self._train[sid] = [self.pub.load(r) for r in self.pub.select(system_id=sid) if r["split"] in FIT_SPLITS]
        return self._train[sid]

    def train_only(self, sid: str) -> list[Trajectory]:
        return [t for t in self.train(sid) if t.split == "train"]

    def hidden(self, sid: str) -> dict:
        if sid not in self._hidden:
            self._hidden[sid] = hidden_sets(self.hid, sid, self.micro_dir)
        return self._hidden[sid]

    def truth_system(self, sid: str) -> dict | None:
        return None if self.truth is None else self.truth["systems"].get(sid)

    def z_true(self, keys: list[str]) -> dict[str, np.ndarray]:
        """True latent trajectories (synthetic truth): per-trajectory files, and the pool trajectories' latents."""
        out = {}
        pool = None
        for k in keys:
            f = self.truth_dir / "latents" / f"{k}.npz"
            if f.exists():
                with np.load(f) as z:
                    out[k] = z["z"].astype(np.float64)
            else:
                if pool is None:
                    pf = self.truth_dir / "pools" / "pool_latents.npz"
                    pool = np.load(pf) if pf.exists() else {}
                if k in getattr(pool, "files", pool):
                    out[k] = np.asarray(pool[k], np.float64)
        if pool is not None and hasattr(pool, "close"):
            pool.close()
        return out

    def fit_view(self, root: Path | str) -> Path:
        """A directory with only the train / val rows (hard links to the trajectory files): what a sandboxed fit may read."""
        root = Path(root)
        if (root / "manifest.json").exists():
            return root
        (root / "traj").mkdir(parents=True, exist_ok=True)
        rows = [r for r in self.pub.index if r["split"] in FIT_SPLITS]
        for r in rows:
            src = self.public_dir / "traj" / f"{r['key']}.npz"
            dst = root / "traj" / f"{r['key']}.npz"
            if not dst.exists():
                try:
                    os.link(src, dst)
                except OSError:
                    shutil.copy2(src, dst)
        man = dict(self.pub.manifest)
        man["splits"] = list(FIT_SPLITS)
        (root / "index.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8", newline="\n")
        (root / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        return root


# ------------------------------------------------------------------------------------------------------------ sandboxed fits
def fit_sandboxed(method_dir: Path, method: str, datasets: list[Path], systems: list[str], out: Path, *, config: dict | None = None,
                  seed: int = 0, sim_queue: Path | None = None, adapt_from: Path | None = None, threads: int = 3,
                  timeout_s: float = 3600.0, python: str | None = None) -> dict:
    """Run one fit in a subprocess with the FIT guard; returns the side-file record (or an error record)."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and out.with_suffix(".json").exists():
        return json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    tmp = out.parent / f".tmp_{out.stem}"
    tmp.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("P3_CLEAN", "MODAL"))}
    env.update({"TEMP": str(tmp), "TMP": str(tmp), "P3_FIT_THREADS": str(threads), "OMP_NUM_THREADS": str(threads),
                "MKL_NUM_THREADS": str(threads), "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
    cmd = [python or sys.executable, "-m", "brainir_state.runner", "fit", "--method-dir", str(method_dir), "--method", method,
           "--systems", ",".join(systems), "--out", str(out), "--seed", str(seed)]
    for d in datasets:
        cmd += ["--dataset", str(d)]
    if config:
        cmd += ["--config", json.dumps(config)]
    if sim_queue:
        cmd += ["--sim-queue", str(sim_queue), "--agent", f"{method}:{'+'.join(systems)[:80]}:{seed}"]
    if adapt_from:
        cmd += ["--adapt-from", str(adapt_from)]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout_s)
        ok = p.returncode == 0 and out.exists()
        rec = json.loads(out.with_suffix(".json").read_text(encoding="utf-8")) if ok else {
            "error": f"exit {p.returncode}", "stderr": p.stderr[-4000:], "stdout": p.stdout[-2000:]}
    except subprocess.TimeoutExpired:
        rec = {"error": f"timeout after {timeout_s:.0f} s"}
    rec["wall_s_total"] = round(time.time() - t0, 1)
    if "error" in rec:
        out.with_suffix(".error.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    return rec


def run_fits(jobs: list[dict], parallel: int = 5) -> list[dict]:
    """jobs: kwargs of fit_sandboxed; runs `parallel` subprocesses at a time."""
    with ThreadPoolExecutor(max_workers=parallel) as ex:
        return list(ex.map(lambda j: fit_sandboxed(**j), jobs))


# ------------------------------------------------------------------------------------------------------------ references
_CODE_TAG: str | None = None


def evaluator_code_tag() -> str:
    """First 10 hex of the sha256 over the evaluation modules (reference caches are keyed by it: a changed evaluator never reuses
    stale references; review E minor)."""
    global _CODE_TAG
    if _CODE_TAG is None:
        import hashlib
        h = hashlib.sha256()
        here = Path(__file__).resolve().parent
        for name in ("evaluate.py", "evaluate_cross.py", "harness.py", "refmodels.py", "suite_eval.py", "data.py"):
            h.update((here / name).read_bytes().replace(b"\r\n", b"\n"))
        _CODE_TAG = h.hexdigest()[:10]
    return _CODE_TAG


def reference_results(sd: SuiteData, sid: str, k: int, cache_dir: Path, seed: int = 0, names: tuple[str, ...] | None = None) -> dict:
    """Evaluate the reference controls of PROTOCOL.md section 5 on one system. The controls are fitted on the public train + val
    trajectories (like a method; finite blow-ups left out), the normalisers (readout scale, PCA basis) come from train only. Cached on
    disk, keyed by the evaluator's code tag: the k-independent controls (full-state ceiling, input-only, readout-history,
    persistence) per system, the PCA-k / random-k controls per (system, k)."""
    from .refmodels import DirectHorizonModel, FullStateModel, ProjectionLinearModel
    cache_dir.mkdir(parents=True, exist_ok=True)
    tag = sid.replace(":", "_")
    ct = evaluator_code_tag()
    f_fixed = cache_dir / f"refs_{tag}_s{seed}_{ct}.json"
    f_k = cache_dir / f"refs_{tag}_k{k}_s{seed}_{ct}.json"
    fit = train = hs = scale = pca = None

    def prep():
        nonlocal fit, train, hs, scale, pca
        if train is None:
            train = sd.train_only(sid)
            full = sd.train(sid)
            fit = [t for t, b in zip(full, E.blowup_mask(full)) if not b] or list(full)
            hs = sd.hidden(sid)
            scale = E.readout_scale(train)
            pca = pca_basis(train)

    if f_fixed.exists():
        fixed = json.loads(f_fixed.read_text(encoding="utf-8"))
    else:
        prep()
        n_y = train[0].y.shape[1]
        observed = sd.sysinfo(sid)["observed"]
        fixed = {"full_state": evaluate_system(FullStateModel(observed, n_y, seed=seed).fit(sid, fit), sid, hs, scale, pca, sd.cfg, k=k,
                                               families=("A", "C", "D", "R", "E"), roles=sd.roles, train=train),
                 "input_only": evaluate_system(DirectHorizonModel("input_only").fit(sid, fit), sid, hs, scale, pca, sd.cfg,
                                               families=("A",), roles=sd.roles),
                 "readout_hist": evaluate_system(DirectHorizonModel("readout_hist").fit(sid, fit), sid, hs, scale, pca, sd.cfg,
                                                 families=("A",), roles=sd.roles)}
        nonint = [t for fam in sd.roles["non_intervention"] for t in hs["by_family"].get(fam, [])]
        fixed["persistence"] = E.eval_persistence(sid, nonint, scale, sd.cfg) if nonint else {}
        f_fixed.write_text(json.dumps(fixed, default=_json_default) + "\n", encoding="utf-8")
    if f_k.exists():
        kdep = json.loads(f_k.read_text(encoding="utf-8"))
    else:
        prep()
        observed = sd.sysinfo(sid)["observed"]
        kdep = {"pca_k": evaluate_system(ProjectionLinearModel(k, "pca").fit(sid, fit, observed), sid, hs, scale, pca, sd.cfg, k=k,
                                         families=("A", "C", "D", "R", "E"), roles=sd.roles, train=train),
                "random_k": evaluate_system(ProjectionLinearModel(k, "random", seed=seed).fit(sid, fit, observed), sid, hs, scale, pca,
                                            sd.cfg, k=k, families=("A", "C", "D", "R", "E"), roles=sd.roles, train=train)}
        f_k.write_text(json.dumps(kdep, default=_json_default) + "\n", encoding="utf-8")
    out = {**fixed, **kdep}
    return {n: v for n, v in out.items() if not names or n in names or n == "persistence"}


def _json_default(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, tuple):
        return list(o)
    return str(o)


def dump(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=_json_default) + "\n", encoding="utf-8", newline="\n")


# ------------------------------------------------------------------------------------------------------------ model evaluation
_SUITES: dict[str, SuiteData] = {}
_GUARDED: set[str] = set()


def suite_from_spec(spec: dict) -> SuiteData:
    key = json.dumps(spec, sort_keys=True)
    if key not in _SUITES:
        _SUITES[key] = SuiteData(spec["public_dir"], kind=spec["kind"], truth_dir=spec.get("truth_dir"), hidden_dir=spec.get("hidden_dir"),
                                 micro_dir=spec.get("micro_dir"))
    return _SUITES[key]


def _simulator(spec: dict, sid: str):
    """simulate(protocol) -> {t, x, u, y[, z]} for lifting checks (orchestrator code; never called from method frames)."""
    if spec["kind"] == "synthetic":
        from .synthsim import simulate
        return lambda proto: simulate(spec["tier"], int(spec["suite_seed"]), sid, proto)
    from .realsim import RealEngine, RealSystem, dense
    sysdef = json.loads(Path(spec["systems_internal"]).read_text(encoding="utf-8"))[sid]
    eng = RealEngine(spec["bundle"], sysdef["network"])
    system = RealSystem(system_id=sid, network=sysdef["network"], mode=sysdef["mode"], keep=tuple(sysdef["keep"]),
                        observed=tuple(sysdef["observed"]), readout=tuple(sysdef["readout"]), stimulus=tuple(sysdef["stimulus"]))

    def run(proto):
        rec = eng.run(system, proto)
        return {"t": rec["t"], "x": dense(rec, list(system.observed)), "u": rec["u"], "y": dense(rec, list(system.readout))}
    return run


def evaluate_model_job(job: dict) -> dict:
    """Worker: evaluate one fitted model on one system of a suite. job: {suite: spec, sid, method_dir, model_path, lift: bool,
    lift_cases: int}."""
    from .runguard import install_eval_guard
    from .runner import load_model
    t0 = time.time()
    sd = suite_from_spec(job["suite"])
    sid = job["sid"]
    hs = sd.hidden(sid)
    train = sd.train_only(sid)
    scale = E.readout_scale(train)
    pca = pca_basis(train)
    test_trajs = [t for fam in sd.roles["non_intervention"] for t in hs["by_family"].get(fam, [])]
    z_true = sd.z_true([t.key for t in test_trajs]) if sd.truth is not None else {}
    mdir = str(Path(job["method_dir"]).resolve())
    if mdir not in _GUARDED:
        install_eval_guard([mdir], allowed=[str(Path(job["model_path"]).resolve().parent)])
        _GUARDED.add(mdir)
    out: dict = {"sid": sid, "model": str(job["model_path"])}
    try:
        model = load_model(job["method_dir"], job["model_path"])
        info = model.info() or {}
        k = (info.get("k") or {}).get(sid)
        if k is None:                                     # k = 0 is a value, not a missing entry (review E minor)
            k = (getattr(model, "k", {}) or {}).get(sid)
        out["info"] = info
        out["k"] = k
        out["res"] = evaluate_system(model, sid, hs, scale, pca, sd.cfg, k=k, roles=sd.roles, train=train)
        if sd.truth is not None:
            from .evaluate_synth import dimension_recovery, eval_latent_recovery
            tr = sd.truth_system(sid) or {}
            out["K"] = eval_latent_recovery(model, sid, test_trajs, z_true, sd.cfg) if tr.get("k") != "none" else {"note": "non-compressible"}
            out["K_dim"] = dimension_recovery(k, (info.get("k_range") or {}).get(sid), tr.get("k"))
        if job.get("lift") and hasattr(model, "lift"):
            from .evaluate_lift import eval_lifting
            cases = []
            for t in test_trajs[: int(job.get("lift_cases", 6))]:
                for ts in sd.cfg.start_times_s[1:3]:
                    cases.append({"protocol": dict(t.protocol, events=[]), "t": ts})
            out["lift"] = eval_lifting(model, sid, cases, _simulator(job["suite"], sid), scale, sd.cfg, future_s=sd.cfg.micro_future_s)
    except Exception as e:  # noqa: BLE001
        import traceback
        out["error"] = repr(e)
        out["traceback"] = traceback.format_exc()[-4000:]
    out["eval_wall_s"] = round(time.time() - t0, 1)
    return out


def limit_threads(n: int = 2) -> None:
    """Worker initialiser: the evaluator runs several processes in parallel, so each uses few BLAS / torch threads."""
    try:
        from threadpoolctl import threadpool_limits
        threadpool_limits(n)
    except Exception:  # noqa: BLE001
        pass
    try:
        import torch
        torch.set_num_threads(n)
    except Exception:  # noqa: BLE001
        pass


def evaluate_models(jobs: list[dict], workers: int = 6, threads: int = 2) -> list[dict]:
    from concurrent.futures import ProcessPoolExecutor
    if workers <= 1:
        limit_threads(threads)
        return [evaluate_model_job(j) for j in jobs]
    with ProcessPoolExecutor(max_workers=workers, initializer=limit_threads, initargs=(threads,)) as ex:
        return list(ex.map(evaluate_model_job, jobs))


def reproducibility_job(job: dict) -> dict:
    """Worker: G for one system - models of one method fitted with different seeds (job['model_paths']); alignment fitted on the
    PUBLIC validation trajectories, measured on the held-out non-intervention trajectories."""
    from .evaluate_cross import eval_reproducibility
    from .runguard import install_eval_guard
    from .runner import load_model
    sd = suite_from_spec(job["suite"])
    sid = job["sid"]
    hs = sd.hidden(sid)
    val = [t for t in sd.train(sid) if t.split == "val"]
    test = [t for fam in sd.roles["non_intervention"] for t in hs["by_family"].get(fam, [])]
    scale = E.readout_scale(sd.train_only(sid))
    mdir = str(Path(job["method_dir"]).resolve())
    if mdir not in _GUARDED:
        install_eval_guard([mdir], allowed=[str(Path(p).resolve().parent) for p in job["model_paths"]])
        _GUARDED.add(mdir)
    try:
        models = [load_model(job["method_dir"], p) for p in job["model_paths"]]
        return {"sid": sid, "G": eval_reproducibility(models, sid, val, test, scale, sd.cfg)}
    except Exception as e:  # noqa: BLE001
        return {"sid": sid, "error": repr(e)}


def reproducibility_jobs(jobs: list[dict], workers: int = 6, threads: int = 2) -> list[dict]:
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=max(1, workers), initializer=limit_threads, initargs=(threads,)) as ex:
        return list(ex.map(reproducibility_job, jobs))
