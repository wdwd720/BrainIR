"""Job entry point for run 4 (PREREG v4): two new kinds; every other kind is delegated unchanged to run 3's `jobs_v3.run_job`
(which delegates to run 2's and run 1's entry points), so Part A's `group_v2` jobs run exactly as R4's did.

``group_v4``  tuner v2 (`typescreen_v2.screen_group_v2`, unchanged) with **paired parameter draws** (G8) on an extended network
              (G4), optionally a hybrid built on the runner (B2.1: `mirror.columns_from(base, other, cols)`) and optionally a pure
              relabelling of every slot (B2.4). Fields of run 1's result plus `digest_v4`.
``sweep_v4``  run 1's `typescreen.fixed_run` (unchanged) at each current of a list, same parameters for every current (B1.1, B1.3,
              fix 1); `params` either ``standard`` (`sample_neuron_params` on the network, as the tuner replicate of that seed) or
              paired. Returns one record per current.
"""

from __future__ import annotations

import hashlib
import json
import time
import traceback

import numpy as np
import scipy.sparse as sp
from brainir.sim.model import sample_neuron_params

from . import jobs as J
from . import jobs_v3 as V3
from . import mirror as MR
from .env import fingerprint
from .typescreen import fixed_run
from .typescreen_v2 import screen_group_v2

KINDS_V4 = ("group_v4", "sweep_v4")


def _ext(d: dict) -> MR.Ext:
    return MR.Ext(sp.csr_matrix(d["C"]), np.asarray(d["sign"], np.float64), np.asarray(d["sizes"], np.float64),
                  np.asarray(d["present"], bool))


def _network(job: dict):
    """(W, slot sizes, stimulated slots, read-out mask) of a v4 job, before any relabelling; W times the job's `gain` (C4) if given."""
    hy = job.get("hybrid")
    if hy is not None:
        e = MR.columns_from(_ext(hy["base"]), _ext(hy["other"]), hy["cols"])
        W, sizes, members = e.W(), e.sizes, MR.stimulated(hy["slots"], e.present)
    else:
        W, sizes, members = sp.csr_matrix(job["W"]), np.asarray(job["sizes"], np.float64), [int(i) for i in job["members"]]
    g = job.get("gain")
    if g is not None and float(g) != 1.0:
        W = (W * float(g)).tocsr()
    return W, sizes, members, np.asarray(job["readout"], bool)


def _params(job: dict, model_cfg, n: int, sizes):
    p = job.get("params") or {"mode": "standard"}
    if p.get("mode", "paired") == "standard":
        return sample_neuron_params(model_cfg, n, int(job["seed"]), job.get("sizes"))
    return MR.paired_params(model_cfg, int(job["seed"]), int(p["n_real"]), p["sizes_real"], np.asarray(p["src"]), sizes)


def _relabel(W, sizes, members, readout, params, perm):
    perm = np.asarray(perm, dtype=np.int64)
    inv = np.argsort(perm)
    W = W[inv][:, inv].tocsr()
    W.sort_indices()
    from brainir.sim.model import NeuronParams  # noqa: PLC0415

    q = NeuronParams(tau=params.tau[inv], a=params.a[inv], theta=params.theta[inv], r_max=params.r_max[inv], seed=params.seed,
                     size_scale=params.size_scale[inv])
    return W, sizes[inv], [int(perm[i]) for i in members], readout[inv], q


def digest_v4(res: dict) -> str:
    keep = {k: res.get(k) for k in ("digest", "runs_digest", "params_mode", "n_slots", "gain")}
    return hashlib.sha256(json.dumps(keep, sort_keys=True, default=str).encode()).hexdigest()


def _runs_digest(runs: list[dict]) -> str:
    keep = [{k: r.get(k) for k in ("current", "verdict", "n_active_all", "n_high_fr", "score", "frequency_hz", "n_active_readout")}
            for r in runs]
    return hashlib.sha256(json.dumps(keep, sort_keys=True, default=str).encode()).hexdigest()


def run_job(job: dict) -> dict:
    if job.get("kind") not in KINDS_V4:
        return V3.run_job(job)
    t0 = time.time()
    key = job.get("key")
    try:
        model_cfg = J._model_cfg(job["model"])
        screen_cfg = J._screen_cfg(job["screen"])
        W, sizes, members, readout = _network(job)
        params = _params(job, model_cfg, W.shape[0], sizes)
        if job.get("perm") is not None:
            W, sizes, members, readout, params = _relabel(W, sizes, members, readout, params, job["perm"])
        mode = (job.get("params") or {"mode": "standard"}).get("mode", "paired")
        if job["kind"] == "group_v4":
            extras = J._extras_fn(job.get("extras") or {}, readout, model_cfg, screen_cfg)
            rep = screen_group_v2(W, params, model_cfg, members, readout, seed=int(job["seed"]), k_min=int(job["k_min"]),
                                  cfg=screen_cfg, extras=extras)
            res = rep.to_dict()
            res["k_min"] = int(job["k_min"])
            res["digest"] = J._digest(res)
        else:
            runs = []
            for c in job["currents"]:
                r = fixed_run(W, params, model_cfg, members, [float(c)] * len(members), readout, cfg=screen_cfg)
                r["current"] = float(c)
                r["in_bounds"] = bool(r["verdict"] == "ok" and r["n_active_readout"] >= int(job.get("k_min", 1)))
                runs.append(r)
            res = {"members": [int(m) for m in members], "seed": int(job["seed"]), "runs": runs, "runs_digest": _runs_digest(runs)}
        res["key"] = key
        res["params_mode"] = mode
        res["gain"] = float(job.get("gain") or 1.0)
        res["n_slots"] = int(W.shape[0])
        res["n_stimulated"] = len(members)
        res["digest_v4"] = digest_v4(res)
        res["host"] = fingerprint()
        res["job_wall_s"] = round(time.time() - t0, 2)
        return res
    except Exception as e:  # noqa: BLE001 - a job never raises
        return {"key": key, "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()[-4000:], "host": fingerprint(),
                "job_wall_s": round(time.time() - t0, 2)}
