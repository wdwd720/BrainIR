"""Entry points of the post-lock drivers' TRUSTED iso "call" jobs (CONTAINER SIDE; hashed by the method lock).

`brainir_causal.isolation.resolve_iso_target` loads a plain module FILE of /repo/scripts/p4 (this file; the drivers bake scripts/p4 into
the iso image, root-only after the lockdown) and `run_iso_payload` calls `fn(job, transport=<the job's LinuxUidTransport>,
models={name: bytes})` in the container's driver. The functions run the benchmark's own code (`isolation.fit_job`, `harness.evaluate_job`)
or the custom roles of `p4post.isojob`; method code runs only in model workers and the model bytes go to them unopened.

SIZE LIMITS (Modal): a function input or output larger than 2 MiB travels as a blob that the container up- / downloads over the network,
which the isolated classes block (block_network=True): such a job fails AFTER its work, at output time. So:
- MODELS larger than `INLINE_MAX` never travel inline. An evaluation reads them from the fit volume (`job["model_path"]`, staged by the
  driver before the wave; packed containers reload the volume once, at their start). A fit whose model is larger returns
  {"too_large": ...} from a packed container (packed jobs never write volumes); the driver re-runs it on an UNPACKED class with
  `job["model_dir"]`, where the fit writes the model to the fit volume (committed by the payload) and returns its reference. Unpacked
  fits carry `model_dir` from the start (one tier); a model within the limit still returns inline.
- OUTPUTS larger than `INLINE_MAX` are returned as an lzma-compressed pickle ({"lzma_pickle": bytes}; trusted driver output, decoded by
  `p4post.common.decode_output`); if still too large, bulky private per-unit payloads the post-lock studies never read (microstate /
  bisimulation / lift `_units`) are dropped and listed; beyond that the job returns an error (never a silent truncation).
"""

from __future__ import annotations

import hashlib
import lzma
import os
import pickle
import sys
import uuid
from pathlib import Path

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from p4post import isojob as _J  # noqa: E402

INLINE_MAX = 1_500_000            # bytes: the largest model / pickled output sent inline (Modal's inline limit is 2 MiB)
OUT_MAX = 1_900_000               # bytes: the largest compressed output (isolation.MAX_INLINE_OUTPUT is 1,966,080)
DROPPABLE = (("micro", "_units"), ("bisimulation", "_units"), ("lift", "_units"))


def _model(models: dict | None, job: dict) -> bytes:
    if models and models.get("model") is not None:
        return bytes(models["model"])
    p = job.get("model_path")
    if p:
        blob = Path(p).read_bytes()
        want = job.get("model_sha256")
        if want and hashlib.sha256(blob).hexdigest() != want:
            raise ValueError(f"model at {p} does not match its sha256")
        return blob
    raise ValueError("this role needs the model bytes (models['model'] or job['model_path'])")


def pack_output(out):
    """The output as is when its pickle fits inline, else an lzma-compressed pickle (dropping DROPPABLE payloads if needed)."""
    pk = pickle.dumps(out, protocol=pickle.HIGHEST_PROTOCOL)
    if len(pk) <= INLINE_MAX:
        return out
    z = lzma.compress(pk, preset=6)
    dropped = []
    if len(z) > OUT_MAX and isinstance(out, dict):
        res = out.get("result") if isinstance(out.get("result"), dict) else out
        for fam, key in DROPPABLE:
            if isinstance(res.get(fam), dict) and key in res[fam]:
                res[fam].pop(key)
                dropped.append(f"{fam}.{key}")
        pk = pickle.dumps(out, protocol=pickle.HIGHEST_PROTOCOL)
        z = lzma.compress(pk, preset=6)
    if len(z) > OUT_MAX:
        return {"error": f"output too large for an isolated container: {len(pk)} bytes pickled, {len(z)} compressed", "dropped": dropped}
    return {"lzma_pickle": z, "n_bytes": len(pk), "dropped": dropped}


def _fit_out(res: dict, job: dict) -> dict:
    blob = res["model"]
    sha = hashlib.sha256(blob).hexdigest()
    side = dict(res.get("side") or {})
    side["model_sha256"], side["model_bytes"] = sha, len(blob)
    if job.get("model_dir") and len(blob) > INLINE_MAX:
        # only a model above the inline limit goes through the fit volume (an unpacked fit; the job commits the volume)
        d = Path(job["model_dir"])
        d.mkdir(parents=True, exist_ok=True)
        tgt = d / f"{sha}.bin"
        if not tgt.exists():
            tmp = d / f".{sha}.{uuid.uuid4().hex[:8]}.tmp"
            tmp.write_bytes(blob)
            os.replace(tmp, tgt)
        return {"model_ref": str(tgt), "sha256": sha, "n_bytes": len(blob), "side": side}
    if len(blob) > INLINE_MAX:
        return {"too_large": len(blob), "sha256": sha, "side": side}
    return {"model": blob, "side": side}


# ---------------------------------------------------------------------------------------------------------------- fits
def fit_c(job: dict, transport=None, models: dict | None = None) -> dict:
    """`isolation.fit_job` (or the critical ablation's passive-only data rule, job["passive"]) with the size rule above."""
    from brainir_causal import isolation as I
    res = _J.fit_passive(job, transport) if job.get("passive") else I.fit_job(job, transport)
    return _fit_out(res, job)


def fit_passive(job: dict, transport=None, models: dict | None = None) -> dict:
    return _fit_out(_J.fit_passive(job, transport), job)


# ---------------------------------------------------------------------------------------------------------------- evaluations
def eval_c(job: dict, transport=None, models: dict | None = None):
    """The benchmark's unchanged `harness.evaluate_job` (every metric family) on the model (inline or from the fit volume)."""
    from brainir_causal import harness as H
    return pack_output(H.evaluate_job(job, transport=transport, model_bytes=_model(models, job)))


def predict_detail(job: dict, transport=None, models: dict | None = None):
    return pack_output(_J.predict_detail(job, transport, _model(models, job)))


def encodings(job: dict, transport=None, models: dict | None = None):
    return pack_output(_J.encodings(job, transport, _model(models, job)))


def readin_probe(job: dict, transport=None, models: dict | None = None):
    return pack_output(_J.readin_probe(job, transport, _model(models, job)))


def memo_probe(job: dict, transport=None, models: dict | None = None):
    return pack_output(_J.memo_probe(job, transport, _model(models, job)))


def lift_jitter(job: dict, transport=None, models: dict | None = None):
    return pack_output(_J.lift_jitter(job, transport, _model(models, job)))


ROLES = ("fit_c", "fit_passive", "eval_c", "predict_detail", "encodings", "readin_probe", "memo_probe", "lift_jitter")
