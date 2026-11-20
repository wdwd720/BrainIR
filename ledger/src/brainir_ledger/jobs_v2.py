"""Job entry point for run 2 (PREREG v2 Part P): kind ``group_v2`` runs tuner v2 (`typescreen_v2.screen_group_v2`, with the
job's ``k_min``); every other kind is delegated unchanged to run 1's `jobs.run_job`. The result fields, the digest and the
host fingerprint are run 1's, so v2 results are comparable with v1 digests (tuner-regression gate). New module.
"""

from __future__ import annotations

import time
import traceback

import numpy as np
from brainir.sim.model import sample_neuron_params

from . import jobs as J
from .env import fingerprint
from .typescreen_v2 import screen_group_v2


def run_job(job: dict) -> dict:
    if job.get("kind") != "group_v2":
        return J.run_job(job)
    t0 = time.time()
    key = job.get("key")
    try:
        W = job["W"]
        model_cfg = J._model_cfg(job["model"])
        screen_cfg = J._screen_cfg(job["screen"])
        readout = np.asarray(job["readout"], bool)
        params = sample_neuron_params(model_cfg, W.shape[0], int(job["seed"]), job.get("sizes"))
        extras = J._extras_fn(job.get("extras") or {}, readout, model_cfg, screen_cfg)
        rep = screen_group_v2(W, params, model_cfg, job["members"], readout, seed=int(job["seed"]), k_min=int(job["k_min"]),
                              cfg=screen_cfg, extras=extras)
        res = rep.to_dict()
        res["key"] = key
        res["k_min"] = int(job["k_min"])
        res["digest"] = J._digest(res)
        res["host"] = fingerprint()
        res["job_wall_s"] = round(time.time() - t0, 2)
        return res
    except Exception as e:  # noqa: BLE001 - a job never raises
        return {"key": key, "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()[-4000:], "host": fingerprint(),
                "job_wall_s": round(time.time() - t0, 2)}
