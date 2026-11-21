"""Job entry point for run 3 (PREREG v3 Part P). Kinds:

``group_v3``  the L14 group screen with run 3's read-out additions (`typescreen_v3.screen_group_v3`): arms H-M, H-C, sensitivity
              groups, the P7 pipeline test and its DNg100 regression;
``fixed_v3``  one simulation at fixed currents (run 1's frozen `typescreen.fixed_run`) with run 3's read-out: arm H-D.
Every other kind is delegated unchanged to run 2's `jobs_v2.run_job` (and from there to run 1's).

Read-out addition ``mn`` (job ``extras["mn"]`` = positions of motor neurons, e.g. all 732): for the read-out run, the peak rate of
each listed neuron after the analysis start (float64, the screen's own window and activity rule, `active_rate_hz`), the indices
(into the list) of those above `active_rate_hz`, and their full traces (float16 + zlib). The result keeps run 1's `digest`
(unchanged fields, so a DNg100 job reproduces run 2's digests) and adds `digest_v3`, which also covers `final_current`,
`final_verdict`, `final_run_extras` and the ``mn`` read-out (determinism gate P9.3).
"""

from __future__ import annotations

import hashlib
import json
import time
import traceback
import zlib

import numpy as np
from brainir.sim.model import sample_neuron_params

from . import jobs as J
from . import jobs_v2 as V2
from .env import fingerprint
from .typescreen import fixed_run
from .typescreen_v3 import screen_group_v3

KINDS_V3 = ("group_v3", "fixed_v3")


def pack16(arr: np.ndarray) -> dict:
    a = np.ascontiguousarray(arr, dtype=np.float16)
    return {"shape": list(a.shape), "dtype": "float16", "zlib": zlib.compress(a.tobytes(), 6)}


def unpack16(d: dict) -> np.ndarray:
    return np.frombuffer(zlib.decompress(d["zlib"]), dtype=np.float16).reshape(d["shape"]).astype(np.float64)


def extras_fn_v3(spec: dict, readout: np.ndarray, model_cfg, screen_cfg):
    base = J._extras_fn({k: v for k, v in spec.items() if k != "mn"}, readout, model_cfg, screen_cfg)
    mn = spec.get("mn")
    pos = None if mn is None else np.asarray(mn, dtype=np.int64)

    def fn(traj) -> dict:
        out = base(traj)
        if pos is not None:
            win = traj.window(screen_cfg.analysis_start_s)
            peak = np.asarray(win[:, pos], dtype=np.float64).max(axis=0)
            act = np.flatnonzero(peak > screen_cfg.active_rate_hz)
            out["mn_peak"] = [float(x) for x in peak]
            out["mn_active"] = act.tolist()
            out["mn_traces"] = pack16(traj.r[:, pos[act]])
        return out

    return fn


def _ex_digest(ex: dict | None) -> str | None:
    if not ex:
        return None
    keep = {k: ex.get(k) for k in ("n_active_notebook", "active_readout_positions", "legs", "offsets_v1", "offsets_v2", "mn_peak",
                                   "mn_active")}
    for k in ("readout_traces", "leg_signals", "watch_traces", "mn_traces"):
        if k in ex:
            keep[k] = hashlib.sha256(ex[k]["zlib"]).hexdigest()
    return hashlib.sha256(json.dumps(keep, sort_keys=True, default=str).encode()).hexdigest()


def digest_v3(res: dict) -> str:
    keep = {"digest": res.get("digest"), "final_current": res.get("final_current"), "final_verdict": res.get("final_verdict"),
            "extras": _ex_digest(res.get("extras")), "final_run_extras": _ex_digest(res.get("final_run_extras"))}
    return hashlib.sha256(json.dumps(keep, sort_keys=True, default=str).encode()).hexdigest()


def run_job(job: dict) -> dict:
    if job.get("kind") not in KINDS_V3:
        return V2.run_job(job)
    t0 = time.time()
    key = job.get("key")
    try:
        W = job["W"]
        model_cfg = J._model_cfg(job["model"])
        screen_cfg = J._screen_cfg(job["screen"])
        readout = np.asarray(job["readout"], bool)
        params = sample_neuron_params(model_cfg, W.shape[0], int(job["seed"]), job.get("sizes"))
        extras = extras_fn_v3(job.get("extras") or {}, readout, model_cfg, screen_cfg)
        if job["kind"] == "group_v3":
            rep = screen_group_v3(W, params, model_cfg, job["members"], readout, seed=int(job["seed"]), cfg=screen_cfg, extras=extras)
            res = rep.to_dict()
        else:
            res = fixed_run(W, params, model_cfg, job["stim_indices"], job["currents"], readout, cfg=screen_cfg, extras=extras)
            res["seed"] = int(job["seed"])
        res["key"] = key
        res["digest"] = J._digest(res)
        res["digest_v3"] = digest_v3(res)
        res["host"] = fingerprint()
        res["job_wall_s"] = round(time.time() - t0, 2)
        return res
    except Exception as e:  # noqa: BLE001 - a job never raises
        return {"key": key, "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()[-4000:], "host": fingerprint(),
                "job_wall_s": round(time.time() - t0, 2)}
