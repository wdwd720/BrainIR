"""Run the frozen Level B tournament driver with its fits and evaluations executed on Modal (goal4 section 58: use compute when it
saves wall-clock time). The protocol is unchanged: scripts/p3/tournament.py runs as is, and only its three execution functions
(run_fits, evaluate_models, reproducibility_jobs) are replaced by Modal-backed equivalents that run the SAME frozen workers
(brainir_state.suite_eval.fit_sandboxed / evaluate_model_job / reproducibility_job) in fresh subprocesses in Linux containers.
Reference controls are prefetched on Modal with the frozen reference_results into the same local cache.

    uv run --project phase3 --no-sync python scripts/p3/modal_tournament.py upload --tier dev|heldout|final
    uv run --project phase3 --no-sync python scripts/p3/modal_tournament.py run <tournament.py arguments> [--containers 100]
    uv run --project phase3 --no-sync python scripts/p3/modal_tournament.py refs --tier heldout [--k 1] [--systems s1,s2]
Level C (real suite; benchmark version 3):
    ... modal_tournament.py upload-real --what view,bundle,internal      # public fit view + bundle (fit volume), definitions (eval)
    ... modal_tournament.py upload-real --what hidden                    # after the lock: the hidden real data (eval volume only)
    ... modal_tournament.py equiv-real --method-dir <snapshot> --method <name> [--systems s1,s2]   # local vs Modal on PUBLIC data
    ... modal_tournament.py level-c <level_c.py arguments> [--containers 100]

Isolation on Modal (p3modal.remote, p3modal.guard):
- a fit container mounts only the FIT volume: public fit views (train / val rows) and method snapshots. Held-out data and truth live
  on a separate EVAL volume that fit containers never mount;
- every method subprocess installs the Linux guard before any method code runs: fits may read only their job directory, the method
  snapshot, the fit view and the Python environment; evaluation refuses file / process / network events while method frames are on
  the stack; realpath resolution; other processes' /proc entries refused;
- each job runs in a fresh interpreter, so method packages of different rounds never share one.
Costs: every call's container wall time is returned and summed into <round>/modal_costs.json.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import tarfile
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase3" / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "p3"))

APP_NAME = "brainir-p3-tournament"
FIT_VOLUME = "brainir-p3-fit"
EVAL_VOLUME = "brainir-p3-eval"
GEN_DIR = ROOT / "benchmarks" / "state_discovery_v1" / "generator"
PKG_DIR = ROOT / "phase3" / "src" / "brainir_state"
P3M_DIR = ROOT / "scripts" / "p3" / "p3modal"
PRICE_PER_CORE_S = 0.192 / 3600       # Modal CPU list price (2026), per physical core-second; approximate cost notes only
PRICE_PER_GIB_S = 0.024 / 3600
CPU, MEM_MB = 2.0, 6144           # Modal cpu = physical cores (2 hyperthreads each): room for the 3 fit / evaluation threads

_STATE: dict = {"costs": [], "methods_keys": {}}


# ------------------------------------------------------------------------------------------------ image, app, volumes
def image():
    import modal
    ign = ["**/__pycache__/**", "**/*.pyc"]
    # the frozen Phase 1-2 library `brainir` is on the path because the simulation service's import chain reaches the real engine
    # (brainir_state.simservice -> realgen -> realsim -> brainir.sim); synthetic simulation never calls it. Versions from phase3/uv.lock
    return (modal.Image.debian_slim(python_version="3.12")
            .pip_install("numpy==2.5.3", "scipy==1.18.1", "pandas==3.0.6", "pyarrow==25.0.1", "pydantic==2.13.5", "scikit-learn==1.9.1",
                         "threadpoolctl==3.7.0", "duckdb==1.5.5", "networkx==3.7", "requests==2.34.2", "cloudpickle==3.1.2",
                         "python-dateutil==2.9.0.post0")
            .pip_install("torch==2.14.0", index_url="https://download.pytorch.org/whl/cpu")
            .env({"PYTHONPATH": "/repo/phase3/src:/repo/p3modal:/repo/src", "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
            # numerical environment pinned to the AVX2 code paths of the development machine (benchmark version 3): Modal hosts are
            # heterogeneous, and on AVX-512 hosts numpy's X86_V4 dispatch, OpenBLAS's SkylakeX kernels and torch's AVX-512 kernels
            # change floating-point results (the real engine's trajectories then differ by up to ~0.1 Hz after 2 s; research/phase3/
            # level_c/modal_sim_hardware_check.json). With these settings every host runs the same kernels as the local machine.
            # OPENBLAS_CORETYPE is NOT forced: with the Haswell kernels forced, worker processes died by SIGSEGV on some hosts (every
            # retry in the same container crashed again; research/phase3/level_c/modal_pinning_crash_experiment.json). OpenBLAS picks
            # its kernels per host; dense linear algebra may then differ from the development machine at the floating-point level (the
            # real engine does not use it: its Modal trajectories stay bit-identical to the stored public records, checked by
            # generate_real_hidden.py smoke-public)
            .env({"NPY_DISABLE_CPU_FEATURES": "X86_V4 AVX512_ICL AVX512_SPR", "ATEN_CPU_CAPABILITY": "avx2"})
            .add_local_dir(str(ROOT / "src" / "brainir"), "/repo/src/brainir", ignore=ign)
            .add_local_dir(str(PKG_DIR), "/repo/phase3/src/brainir_state", ignore=ign)
            .add_local_dir(str(GEN_DIR), "/repo/benchmarks/state_discovery_v1/generator", ignore=ign)
            .add_local_dir(str(P3M_DIR), "/repo/p3modal/p3modal", ignore=ign + ["site/**"])
            .add_local_dir(str(P3M_DIR / "site"), "/repo/p3modal_site", ignore=ign)
            .add_local_dir(str(ROOT / "scripts" / "p3"), "/repo/scripts/p3", ignore=ign + ["p3modal/**"]))


def _remote_callables():
    """The functions Modal runs, created as closures so that they are serialised BY VALUE (a module-level function would be pickled by
    reference to this module, which does not exist in the container). They import the container-side package p3modal."""
    def p3_fit_call(payload):
        import p3modal.remote as R
        if payload.get("kind") == "fit_real":          # Level C (real suite, version 3): subviews, bundle-backed simulator
            return R.run_fit_real(payload)
        return R.run_fit(payload)

    def p3_eval_call(payload):
        import p3modal.remote as R
        if payload["kind"] in ("eval", "repro"):
            return R.run_eval(payload)
        if payload["kind"] in ("eval_real", "repro_real"):
            return R.run_eval_real(payload)
        if payload["kind"] == "refs_real":
            return R.run_refs_real(payload)
        if payload["kind"] == "extract_any":
            return R.run_extract_any(payload)
        if payload["kind"] == "extract":
            return R.run_extract(payload)
        if payload["kind"] == "call_commit":           # orchestrator functions that write to the eval volume (hidden real data)
            return R.run_call_commit(payload)
        return R.run_call(payload) if payload["kind"] == "call" else R.run_refs(payload)

    return p3_fit_call, p3_eval_call


def make_app(containers: int):
    import modal
    app = modal.App(APP_NAME, image=image())
    fitvol = modal.Volume.from_name(FIT_VOLUME, create_if_missing=True)
    evalvol = modal.Volume.from_name(EVAL_VOLUME, create_if_missing=True)
    # a job whose worker keeps crashing on one host (p3modal.remote.WorkerCrashed) is moved to another container up to 3 times
    retries = modal.Retries(max_retries=3, initial_delay=2.0, backoff_coefficient=1.0)
    fit_call, eval_call = _remote_callables()
    fit_fn = app.function(cpu=CPU, memory=MEM_MB, timeout=3 * 3600, max_containers=containers, retries=retries,
                          volumes={"/fitvol": fitvol}, serialized=True, name="p3_fit")(fit_call)
    eval_fn = app.function(cpu=CPU, memory=MEM_MB, timeout=2 * 3600, max_containers=containers, retries=retries,
                           volumes={"/fitvol": fitvol, "/evalvol": evalvol}, serialized=True, name="p3_eval")(eval_call)
    return app, fit_fn, eval_fn, fitvol


# ------------------------------------------------------------------------------------------------ uploads
def _suite_dirs(tier: str) -> tuple[Path, Path]:
    from tournament import suite_spec
    spec = suite_spec(tier)
    return Path(spec["public_dir"]), Path(spec["truth_dir"])


def upload(tier: str) -> None:
    import modal
    from brainir_state.suite_eval import SuiteData
    pub, truth = _suite_dirs(tier)
    fitvol = modal.Volume.from_name(FIT_VOLUME, create_if_missing=True)
    evalvol = modal.Volume.from_name(EVAL_VOLUME, create_if_missing=True)
    t0 = time.time()
    with tempfile.TemporaryDirectory(dir=str(ROOT / "data" / "phase3")) as td:
        view = SuiteData(pub, kind="synthetic").fit_view(Path(td) / "view")
        with fitvol.batch_upload(force=True) as b:
            b.put_directory(str(view), f"/views/{tier}")
    print(f"fit view of {tier} uploaded ({time.time() - t0:.0f} s)", flush=True)
    with evalvol.batch_upload(force=True) as b:
        b.put_directory(str(pub), f"/suites/{tier}/public")
        b.put_directory(str(truth), f"/suites/{tier}/truth")
    print(f"suite {tier} uploaded ({time.time() - t0:.0f} s)", flush=True)


def _truth_subset(pub: Path, truth: Path) -> list[Path]:
    """The truth files the evaluator reads: truth.json, the truth index, the per-system records, the pool latents and the latents of
    TEST-split trajectories (latent recovery K); training latents are only used by the dev calibration."""
    test_keys = set()
    for line in (pub / "index.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["split"] == "test":
            test_keys.add(r["key"])
    out = [p for p in (truth / "truth.json", truth / "truth_index.jsonl") if p.exists()]
    out += sorted(q for q in (truth / "systems").rglob("*") if q.is_file()) if (truth / "systems").exists() else []
    out += sorted(q for q in (truth / "pools").rglob("*") if q.is_file()) if (truth / "pools").exists() else []
    out += sorted(q for q in (truth / "latents").glob("*.npz") if q.stem in test_keys)
    return out


def upload_tar(tier: str, work: Path) -> None:
    """Upload a suite as two tars (public, truth subset) and unpack them in Modal (slow uplinks: per-file uploads are dominated by
    round trips). The fit view goes the same way to the fit volume if it is missing."""
    import modal
    pub, truth = _suite_dirs(tier)
    evalvol = modal.Volume.from_name(EVAL_VOLUME, create_if_missing=True)
    work.mkdir(parents=True, exist_ok=True)
    parts = {"public": (pub, sorted(q for q in pub.rglob("*") if q.is_file())), "truth": (truth, _truth_subset(pub, truth))}
    t0 = time.time()
    for part, (base, files) in parts.items():
        tar = work / f"{tier}_{part}.tar"
        with tarfile.open(tar, "w") as tf:
            for q in files:
                tf.add(str(q), arcname=q.relative_to(base).as_posix())
        size = tar.stat().st_size
        with evalvol.batch_upload(force=True) as b:
            b.put_file(str(tar), f"/_incoming/{tar.name}")
        print(f"uploaded {tar.name}: {len(files)} files, {size / 1e6:.0f} MB ({time.time() - t0:.0f} s)", flush=True)
        tar.unlink()
    app = _open_app(4)
    with _output(), app.run():
        res = _eval_map([{"job_id": uuid.uuid4().hex, "kind": "extract", "name": f"{tier}_{p}.tar", "dest": f"suites/{tier}/{p}"}
                         for p in parts], "extract")
    print(json.dumps([r if isinstance(r, dict) else repr(r) for r in res]), flush=True)


def _methods_key(mdir: Path, fitvol) -> str:
    """Deterministic tar of a methods snapshot, uploaded once to the fit volume; key = its sha256 (first 16 hex)."""
    mdir = Path(mdir)
    if str(mdir) in _STATE["methods_keys"]:
        return _STATE["methods_keys"][str(mdir)]
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for p in sorted(q for q in mdir.rglob("*") if q.is_file() and "__pycache__" not in q.parts and q.suffix != ".pyc"):
            data = p.read_bytes()
            ti = tarfile.TarInfo("methods/" + p.relative_to(mdir).as_posix())
            ti.size, ti.mtime, ti.mode = len(data), 0, 0o644
            tf.addfile(ti, io.BytesIO(data))
    blob = buf.getvalue()
    key = hashlib.sha256(blob).hexdigest()[:16]
    try:
        present = {Path(e.path).name for e in fitvol.listdir("/methods")}
    except Exception:  # noqa: BLE001
        present = set()
    if f"{key}.tar" not in present:
        with fitvol.batch_upload(force=True) as b:
            b.put_file(io.BytesIO(blob), f"/methods/{key}.tar")
    _STATE["methods_keys"][str(mdir)] = key
    return key


def _tar_dir(d: Path) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for p in sorted(q for q in Path(d).rglob("*") if q.is_file()):
            data = p.read_bytes()
            ti = tarfile.TarInfo(p.relative_to(d).as_posix())
            ti.size, ti.mtime, ti.mode = len(data), 0, 0o644
            tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def _model_files(p: Path) -> dict:
    p = Path(p)
    return {"pkl": p.read_bytes(), "json": p.with_suffix(".json").read_bytes() if p.with_suffix(".json").exists() else None}


def _cost(recs: list[dict], label: str) -> None:
    s = sum(float(r.get("container_wall_s") or 0.0) for r in recs if isinstance(r, dict))
    _STATE["costs"].append({"label": label, "calls": len(recs), "container_s": round(s, 1),
                            "usd_approx": round(s * (CPU * PRICE_PER_CORE_S + MEM_MB / 1024 * PRICE_PER_GIB_S), 3)})


# ------------------------------------------------------------------------------------------------ Modal-backed execution functions
def modal_run_fits(jobs: list[dict], parallel: int = 5) -> list[dict]:
    import tournament as T
    fit_fn, fitvol = _STATE["fit_fn"], _STATE["fitvol"]
    sysdefs_cache: dict = {}
    recs: list = [None] * len(jobs)
    payloads, where = [], []
    for i, j in enumerate(jobs):
        out = Path(j["out"])
        if out.exists() and out.with_suffix(".json").exists():
            recs[i] = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
            continue
        dsets, tier = [], None
        for d in j["datasets"]:
            d = Path(d)
            if d.name.startswith("fitview_"):
                tier = d.name[len("fitview_"):]
                dsets.append({"kind": "view", "tier": tier})
            else:
                dsets.append({"kind": "tar", "tar": _tar_dir(d)})
                tier = tier or _STATE.get("tier")
        sim = None
        if j.get("sim_queue"):
            t = tier or _STATE["tier"]
            if t not in sysdefs_cache:
                sysdefs_cache[t] = json.loads((T.BENCH / "hidden" / f"simservice_systems_{t}.json").read_text(encoding="utf-8"))
            sim = {"budget": int(_STATE["sim_budget"]), "systems": {s: sysdefs_cache[t][s] for s in j["systems"] if s in sysdefs_cache[t]}}
        payloads.append({"job_id": uuid.uuid4().hex, "methods_key": _methods_key(Path(j["method_dir"]), fitvol), "method": j["method"],
                         "systems": list(j["systems"]), "seed": int(j.get("seed", 0)), "config": j.get("config"),
                         "timeout_s": float(j.get("timeout_s", 3600.0)), "stem": out.stem, "datasets": dsets,
                         "adapt_from": _model_files(Path(j["adapt_from"])) if j.get("adapt_from") else None, "sim": sim})
        where.append(i)
    if payloads:
        t0 = time.time()
        results = list(fit_fn.map(payloads, order_outputs=True, return_exceptions=True))
        print(f"  modal fits: {len(payloads)} in {time.time() - t0:.0f} s", flush=True)
        for i, r in zip(where, results):
            out = Path(jobs[i]["out"])
            out.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(r, BaseException):
                rec = {"error": f"modal call failed: {r!r}"[:2000]}
                out.with_suffix(".error.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")
                recs[i] = rec
                continue
            if r.get("pkl") is not None:
                out.write_bytes(r["pkl"])
            if r.get("json") is not None:
                out.with_suffix(".json").write_bytes(r["json"])
            if r.get("error_json") is not None:
                out.with_suffix(".error.json").write_bytes(r["error_json"])
            recs[i] = r["rec"]
        _cost([r for r in results if isinstance(r, dict)], "fits")
    return recs


def _eval_map(payloads: list[dict], label: str) -> list:
    eval_fn = _STATE["eval_fn"]
    if not payloads:
        return []
    t0 = time.time()
    results = list(eval_fn.map(payloads, order_outputs=True, return_exceptions=True))
    print(f"  modal {label}: {len(payloads)} in {time.time() - t0:.0f} s", flush=True)
    _cost([r for r in results if isinstance(r, dict)], label)
    return results


def modal_evaluate_models(jobs: list[dict], workers: int = 6, threads: int = 2) -> list[dict]:
    fitvol = _STATE["fitvol"]
    payloads = [{"job_id": uuid.uuid4().hex, "kind": "eval", "methods_key": _methods_key(Path(j["method_dir"]), fitvol),
                 "job": {k: v for k, v in j.items() if k not in ("method_dir", "model_path")}, "models": [_model_files(Path(j["model_path"]))],
                 "timeout_s": 5400, "threads": 3} for j in jobs]
    out = []
    for j, r in zip(jobs, _eval_map(payloads, "evaluations")):
        if isinstance(r, BaseException):
            r = {"sid": j["sid"], "error": f"modal call failed: {r!r}"[:2000]}
        r["model"] = str(j["model_path"])
        out.append(r)
    prefetch_refs([(j["suite"], r["sid"], r.get("k")) for j, r in zip(jobs, out) if "error" not in r])
    return out


def modal_reproducibility_jobs(jobs: list[dict], workers: int = 6, threads: int = 2) -> list[dict]:
    fitvol = _STATE["fitvol"]
    payloads = [{"job_id": uuid.uuid4().hex, "kind": "repro", "methods_key": _methods_key(Path(j["method_dir"]), fitvol),
                 "job": {k: v for k, v in j.items() if k not in ("method_dir", "model_paths")},
                 "models": [_model_files(Path(p)) for p in j["model_paths"]], "timeout_s": 5400, "threads": 3} for j in jobs]
    out = []
    for j, r in zip(jobs, _eval_map(payloads, "reproducibility")):
        if isinstance(r, BaseException):
            r = {"sid": j["sid"], "error": f"modal call failed: {r!r}"[:2000]}
        out.append(r)
    return out


def call_remote(module: str, func: str, arg_lists: list[list], tier: str = "dev", containers: int = 100) -> list:
    """module.func(*args) for every args in arg_lists, each in its own Modal call (orchestrator functions only, no method code), with the
    suite of `tier` linked where the scripts expect it. Returns the results in order ({"error": ...} for a failed call)."""
    links = ({"/repo/data/phase3/synthetic_dev": "/evalvol/suites/dev/public", "/repo/data/phase3/synthetic_truth/dev": "/evalvol/suites/dev/truth"}
             if tier == "dev" else {f"/repo/data/phase3/synthetic/{tier}/public": f"/evalvol/suites/{tier}/public",
                                    f"/repo/data/phase3/synthetic/{tier}/truth": f"/evalvol/suites/{tier}/truth"})
    payloads = [{"job_id": uuid.uuid4().hex, "kind": "call", "module": module, "func": func, "args": list(a), "links": links, "timeout_s": 7200}
                for a in arg_lists]
    app = _open_app(containers)
    with _output(), app.run():
        res = _eval_map(payloads, f"call:{func}")
    out = []
    for r in res:
        if isinstance(r, BaseException):
            out.append({"error": f"modal call failed: {r!r}"[:2000]})
        elif "result" in r and r["result"] is not None:
            out.append(r["result"])
        else:
            out.append({"error": r.get("error"), "stderr": (r.get("stderr") or "")[-3000:]})
    print(json.dumps(_STATE["costs"]), flush=True)
    return out


def prefetch_refs(items: list[tuple[dict, str, object]], seed: int = 0) -> None:
    """Compute missing reference-control cache files (frozen reference_results) on Modal, in parallel, into the local cache."""
    import tournament as T
    from brainir_state.suite_eval import evaluator_code_tag
    ct = evaluator_code_tag()
    todo, seen = [], set()
    for spec, sid, k in items:
        kk = int(k) if k else 1
        cache = T.OUT / "_refcache" / spec["tier"]
        tag = sid.replace(":", "_")
        if (cache / f"refs_{tag}_s{seed}_{ct}.json").exists() and (cache / f"refs_{tag}_k{kk}_s{seed}_{ct}.json").exists():
            continue
        if (spec["tier"], sid, kk) in seen:
            continue
        seen.add((spec["tier"], sid, kk))
        todo.append((spec, sid, kk, cache))
    if not todo:
        return
    def _seed_files(cache: Path, sid: str) -> dict:
        f = cache / f"refs_{sid.replace(':', '_')}_s{seed}_{ct}.json"          # the k-independent controls, when already computed
        return {f.name: f.read_bytes()} if f.exists() else {}

    payloads = [{"job_id": uuid.uuid4().hex, "kind": "refs", "suite": spec, "sid": sid, "k": kk, "seed": seed, "timeout_s": 5400,
                 "seed_files": _seed_files(cache, sid)} for spec, sid, kk, cache in todo]
    for (spec, sid, kk, cache), r in zip(todo, _eval_map(payloads, "references")):
        if isinstance(r, BaseException) or r.get("error"):
            print(f"  reference prefetch failed for {sid} k={kk}: {r if isinstance(r, BaseException) else r.get('error')}", flush=True)
            continue
        cache.mkdir(parents=True, exist_ok=True)
        for name, data in r["files"].items():
            if not (cache / name).exists():
                (cache / name).write_bytes(data)


# ------------------------------------------------------------------------------------------------ Level C on Modal (real suite, version 3)
# The frozen Level C driver (scripts/p3/level_c.py) runs as is with its execution functions replaced, like the tournament above.
# Data staging (once): the PUBLIC real fit view -> /fitvol/views/real, the public blind bundle -> /fitvol/bundles/dng100_public_blind
# (fits may read both); the internal system definitions -> /evalvol/suites/real_internal/, and after the method lock the HIDDEN real
# data -> /evalvol/suites/real/hidden (the eval volume only: fit containers never mount it).
REAL_PUBLIC = ROOT / "data" / "phase3" / "real_public"
REAL_HIDDEN_DIR = ROOT / "data" / "phase3" / "real_hidden"
BUNDLE_SRC = ROOT / "benchmarks" / "dng100" / "public_blind"
INTERNAL_SRC = ROOT / "benchmarks" / "state_discovery_v1" / "hidden" / "systems_internal.json"
UPLOAD_WORK = ROOT / "data" / "phase3" / "_modal_upload"


def _upload_extract(items: list[tuple[str, Path, list[Path], str]], work: Path = UPLOAD_WORK) -> list:
    """items: (volume 'fit' | 'eval', base directory, files, destination under the volume). Each item is packed as ONE tar, uploaded to
    /<volume>/_incoming and unpacked there by a Modal call (per-file uploads are dominated by round trips on slow uplinks). The sha256
    of every file is returned for the record."""
    import modal
    fitvol = modal.Volume.from_name(FIT_VOLUME, create_if_missing=True)
    evalvol = modal.Volume.from_name(EVAL_VOLUME, create_if_missing=True)
    work.mkdir(parents=True, exist_ok=True)
    payloads, manifest = [], {}
    t0 = time.time()
    for vol, base, files, dest in items:
        name = dest.replace("/", "_") + ".tar"
        tar = work / name
        with tarfile.open(tar, "w") as tf:
            for q in files:
                tf.add(str(q), arcname=q.relative_to(base).as_posix())
        manifest[dest] = {"volume": vol, "n_files": len(files), "tar_bytes": tar.stat().st_size,
                          "sha256": {q.relative_to(base).as_posix(): hashlib.sha256(q.read_bytes()).hexdigest() for q in files}}
        with (fitvol if vol == "fit" else evalvol).batch_upload(force=True) as b:
            b.put_file(str(tar), f"/_incoming/{name}")
        print(f"uploaded {name}: {len(files)} files, {tar.stat().st_size / 1e6:.0f} MB ({time.time() - t0:.0f} s)", flush=True)
        tar.unlink()
        payloads.append({"job_id": uuid.uuid4().hex, "kind": "extract_any", "volume": vol, "name": name, "dest": dest})
    app = _open_app(4)
    with _output(), app.run():
        res = _eval_map(payloads, "extract")
    for p, r in zip(payloads, res):
        n = manifest[p["dest"]]["n_files"]
        got = r.get("extracted_files") if isinstance(r, dict) else None
        if got != n:
            raise SystemExit(f"extraction of {p['dest']} failed or incomplete: {r!r} (expected {n} files)")
    print(json.dumps(_STATE["costs"]), flush=True)
    return [manifest]


def upload_real(what: list[str]) -> None:
    """Stage the real-suite material on the Modal volumes (see the section comment). 'hidden' refuses before the method lock."""
    from brainir_state.suite_eval import SuiteData
    items = []
    with tempfile.TemporaryDirectory(dir=str(ROOT / "data" / "phase3")) as td:
        if "view" in what:
            view = SuiteData(REAL_PUBLIC, kind="real").fit_view(Path(td) / "view")
            items.append(("fit", view, sorted(q for q in view.rglob("*") if q.is_file()), "views/real"))
        if "bundle" in what:
            items.append(("fit", BUNDLE_SRC, sorted(q for q in BUNDLE_SRC.rglob("*") if q.is_file()), "bundles/dng100_public_blind"))
        if "internal" in what:
            items.append(("eval", INTERNAL_SRC.parent, [INTERNAL_SRC], "suites/real_internal"))
        if "hidden" in what:
            if not (ROOT / "research" / "phase3" / "METHOD_LOCK.json").exists() or not (REAL_HIDDEN_DIR / "manifest.json").exists():
                raise SystemExit("refusing: the hidden real data are staged only after the method lock and their generation")
            items.append(("eval", REAL_HIDDEN_DIR, sorted(q for q in REAL_HIDDEN_DIR.rglob("*") if q.is_file()), "suites/real/hidden"))
        man = _upload_extract(items)
    rec = ROOT / "research" / "phase3" / "level_c" / "modal_staging.json"
    rec.parent.mkdir(parents=True, exist_ok=True)
    old = json.loads(rec.read_text(encoding="utf-8")) if rec.exists() else {}
    for dest, m in man[0].items():
        old[dest] = {"volume": m["volume"], "n_files": m["n_files"], "tar_bytes": m["tar_bytes"],
                     "files_sha256": hashlib.sha256(json.dumps(m["sha256"], sort_keys=True).encode()).hexdigest(),
                     "staged_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    rec.write_text(json.dumps(old, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _real_dataset(d: Path) -> dict:
    """A fit dataset for a real fit call: the staged view (a directory named fitview_<name>), a SUBVIEW (rows of a staged view, marked by
    SUBVIEW.json; see level_c.limited_view / half_view) or, otherwise, a tar of the directory."""
    d = Path(d)
    if d.name.startswith("fitview_"):
        return {"kind": "view", "tier": d.name[len("fitview_"):]}
    if (d / "SUBVIEW.json").exists():
        meta = json.loads((d / "SUBVIEW.json").read_text(encoding="utf-8"))
        return {"kind": "subview", "base": meta["base"], "keys": list(meta["keys"]), "index": (d / "index.jsonl").read_text(encoding="utf-8"),
                "manifest": (d / "manifest.json").read_text(encoding="utf-8")}
    return {"kind": "tar", "tar": _tar_dir(d)}


def modal_run_fits_real(jobs: list[dict], parallel: int = 5) -> list[dict]:
    """run_fits for the real suite (Level C): payload kind fit_real; the simulation service's system definitions (held-out target lists
    removed) come from _STATE['sim_systems'], set by the level-c command."""
    fit_fn, fitvol = _STATE["fit_fn"], _STATE["fitvol"]
    recs: list = [None] * len(jobs)
    payloads, where = [], []
    for i, j in enumerate(jobs):
        out = Path(j["out"])
        if out.exists() and out.with_suffix(".json").exists():
            recs[i] = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
            continue
        sim = None
        if j.get("sim_queue") and _STATE.get("sim_systems"):
            sim = {"budget": int(_STATE["sim_budget"]), "systems": {s: _STATE["sim_systems"][s] for s in j["systems"] if s in _STATE["sim_systems"]}}
        payloads.append({"job_id": uuid.uuid4().hex, "kind": "fit_real", "methods_key": _methods_key(Path(j["method_dir"]), fitvol),
                         "method": j["method"], "systems": list(j["systems"]), "seed": int(j.get("seed", 0)), "config": j.get("config"),
                         "timeout_s": float(j.get("timeout_s", 3600.0)), "stem": out.stem, "datasets": [_real_dataset(d) for d in j["datasets"]],
                         "adapt_from": _model_files(Path(j["adapt_from"])) if j.get("adapt_from") else None, "sim": sim})
        where.append(i)
    if payloads:
        t0 = time.time()
        results = list(fit_fn.map(payloads, order_outputs=True, return_exceptions=True))
        print(f"  modal real fits: {len(payloads)} in {time.time() - t0:.0f} s", flush=True)
        for i, r in zip(where, results):
            out = Path(jobs[i]["out"])
            out.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(r, BaseException):
                rec = {"error": f"modal call failed: {r!r}"[:2000]}
                out.with_suffix(".error.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")
                recs[i] = rec
                continue
            if r.get("pkl") is not None:
                out.write_bytes(r["pkl"])
            if r.get("json") is not None:
                out.with_suffix(".json").write_bytes(r["json"])
            if r.get("error_json") is not None:
                out.with_suffix(".error.json").write_bytes(r["error_json"])
            recs[i] = r["rec"]
        _cost([r for r in results if isinstance(r, dict)], "real fits")
    return recs


def _real_spec(spec: dict) -> dict:
    return dict(spec, modal_view=spec.get("modal_view", "real"), modal_hidden=spec.get("modal_hidden", _STATE.get("real_hidden_name", "real")))


def modal_evaluate_models_real(jobs: list[dict], workers: int = 6, threads: int = 2) -> list[dict]:
    fitvol = _STATE["fitvol"]
    payloads = [{"job_id": uuid.uuid4().hex, "kind": "eval_real", "methods_key": _methods_key(Path(j["method_dir"]), fitvol),
                 "job": {k: (v if k != "suite" else _real_spec(v)) for k, v in j.items() if k not in ("method_dir", "model_path")},
                 "models": [_model_files(Path(j["model_path"]))], "timeout_s": 5400, "threads": 3} for j in jobs]
    out = []
    for j, r in zip(jobs, _eval_map(payloads, "real evaluations")):
        if isinstance(r, BaseException):
            r = {"sid": j["sid"], "error": f"modal call failed: {r!r}"[:2000]}
        r["model"] = str(j["model_path"])
        _STATE.setdefault("remote_code_tags", set()).add(r.get("evaluator_code_tag"))
        out.append(r)
    if _STATE.get("real_refcache"):
        # level_c.py reads the reference controls of the independent seed-0 fits only (tags "<model>/indep/<system>_s0")
        want = [(j, r) for j, r in zip(jobs, out) if "error" not in r and ("tag" not in j or ("/indep/" in j["tag"] and j["tag"].endswith("_s0")))]
        prefetch_refs_real([(j["suite"], r["sid"], r.get("k")) for j, r in want], Path(_STATE["real_refcache"]))
    return out


def modal_reproducibility_jobs_real(jobs: list[dict], workers: int = 6, threads: int = 2) -> list[dict]:
    fitvol = _STATE["fitvol"]
    payloads = [{"job_id": uuid.uuid4().hex, "kind": "repro_real", "methods_key": _methods_key(Path(j["method_dir"]), fitvol),
                 "job": {k: (v if k != "suite" else _real_spec(v)) for k, v in j.items() if k not in ("method_dir", "model_paths")},
                 "models": [_model_files(Path(p)) for p in j["model_paths"]], "timeout_s": 5400, "threads": 3} for j in jobs]
    out = []
    for j, r in zip(jobs, _eval_map(payloads, "real reproducibility")):
        if isinstance(r, BaseException):
            r = {"sid": j["sid"], "error": f"modal call failed: {r!r}"[:2000]}
        out.append(r)
    return out


def prefetch_refs_real(items: list[tuple[dict, str, object]], cache: Path, seed: int = 0) -> None:
    """Missing reference-control cache files of the real suite, computed on Modal (frozen reference_results) into the local cache."""
    from brainir_state.suite_eval import evaluator_code_tag
    ct = evaluator_code_tag()
    todo, seen = [], set()
    for spec, sid, k in items:
        kk = int(k) if k else 1
        tag = sid.replace(":", "_")
        if (cache / f"refs_{tag}_s{seed}_{ct}.json").exists() and (cache / f"refs_{tag}_k{kk}_s{seed}_{ct}.json").exists():
            continue
        if (sid, kk) in seen:
            continue
        seen.add((sid, kk))
        todo.append((spec, sid, kk))
    if not todo:
        return
    payloads = [{"job_id": uuid.uuid4().hex, "kind": "refs_real", "suite": _real_spec(spec), "sid": sid, "k": kk, "seed": seed, "timeout_s": 5400}
                for spec, sid, kk in todo]
    cache.mkdir(parents=True, exist_ok=True)
    for (spec, sid, kk), r in zip(todo, _eval_map(payloads, "real references")):
        if isinstance(r, BaseException) or r.get("error"):
            print(f"  real reference prefetch failed for {sid} k={kk}: {r if isinstance(r, BaseException) else (r.get('error'), (r.get('stderr') or '')[-800:])}",
                  flush=True)
            continue
        tag_remote = ((r.get("result") or {}).get("result") or {}).get("evaluator_code_tag")
        if tag_remote is not None and tag_remote != ct:
            print(f"  real reference prefetch for {sid}: remote evaluator tag {tag_remote} != local {ct}; not cached", flush=True)
            continue
        for name, data in r["files"].items():
            if not (cache / name).exists():
                (cache / name).write_bytes(data)


def cmd_level_c(rest: list[str], containers: int) -> int:
    """The frozen Level C driver with fits, evaluations, reference controls and G on Modal. The hidden data must be staged first
    (upload-real --what hidden, after the lock); level_c.py itself refuses to run without the lock and the local hidden data."""
    import level_c as L
    real_defs = json.loads(INTERNAL_SRC.read_text(encoding="utf-8"))
    _STATE.update(sim_budget=L.SIM_BUDGET, real_refcache=str(L.OUT / "_refcache"),
                  sim_systems={s: {k: v for k, v in dict(d, cost=10 if d["mode"] == "full" else 3).items() if k not in ("targets_heldout", "meta")}
                               for s, d in real_defs.items()})
    L.run_fits, L.evaluate_models, L.reproducibility_jobs = modal_run_fits_real, modal_evaluate_models_real, modal_reproducibility_jobs_real
    L.start_simservice = lambda *a, **k: (Path("modal-per-fit-simulator"), None)
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--attempt", default="01")
    known, _ = pre.parse_known_args(rest)
    app = _open_app(containers)
    t0 = time.time()
    with _output(), app.run():
        rc = L.main(rest)
    from brainir_state.suite_eval import evaluator_code_tag
    rec = {"attempt": known.attempt, "wall_s": round(time.time() - t0, 1), "cpu": CPU, "memory_mb": MEM_MB, "calls": _STATE["costs"],
           "usd_approx_total": round(sum(c["usd_approx"] for c in _STATE["costs"]), 2), "local_evaluator_code_tag": evaluator_code_tag(),
           "remote_evaluator_code_tags": sorted(t for t in _STATE.get("remote_code_tags", set()) if t)}
    out = L.OUT / known.attempt / "modal_costs.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in rec.items() if k != "calls"}), flush=True)
    return rc


# ------------------------------------------------------------------------------------------------ local vs Modal equivalence (public data)
EQUIV_FAMILY_MAP = {"nominal": "H_nominal", "init_state": "H_init_state", "kick_A": "H_kick_B", "pulse_A": "H_pulse_A",
                    "silence1_A": "H_silence1_A"}


def build_equiv_hidden(systems: list[str], dest: Path) -> Path:
    """A stand-in 'hidden' directory from PUBLIC real validation data (never hidden data): the val rows of the given systems under
    hidden family names (EQUIV_FAMILY_MAP) as split 'test', and their public twins. Used only to check that Modal and local execution
    give the same results before Level C."""
    import os
    import shutil
    rows = [json.loads(line) for line in (REAL_PUBLIC / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "traj").mkdir(parents=True)
    out = []
    for r in rows:
        if r["system_id"] not in systems or r["split"] not in ("val", "twin") or r["family"] not in EQUIV_FAMILY_MAP:
            continue
        r2 = dict(r, family=EQUIV_FAMILY_MAP[r["family"]], split="test" if r["split"] == "val" else "twin")
        src, dst = REAL_PUBLIC / "traj" / f"{r['key']}.npz", dest / "traj" / f"{r['key']}.npz"
        try:
            os.link(src, dst)
        except OSError:
            shutil.copy2(src, dst)
        out.append(r2)
    man = json.loads((REAL_PUBLIC / "manifest.json").read_text(encoding="utf-8"))
    man = dict(man, systems={s: man["systems"][s] for s in systems}, splits=["test", "twin"], notes="public validation stand-in (equivalence check)")
    (dest / "index.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in out), encoding="utf-8", newline="\n")
    (dest / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return dest


def _flat_numbers(obj, prefix: str = "") -> dict:
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("_units", "eval_wall_s", "model", "traceback", "container_wall_s", "evaluator_code_tag"):
                continue
            out.update(_flat_numbers(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            out.update(_flat_numbers(v, f"{prefix}[{i}]"))
    elif isinstance(obj, bool) or obj is None or isinstance(obj, str):
        out[prefix] = obj
    else:
        try:
            out[prefix] = float(obj)
        except (TypeError, ValueError):
            out[prefix] = str(obj)
    return out


def compare_results(a: dict, b: dict, rtol: float = 1e-6, atol: float = 1e-9) -> dict:
    """Leaf-by-leaf comparison of two evaluation results (numbers within rtol / atol, everything else equal)."""
    import math
    fa, fb = _flat_numbers(a), _flat_numbers(b)
    keys = sorted(set(fa) | set(fb))
    bad, worst = [], 0.0
    for k in keys:
        x, y = fa.get(k, "<missing>"), fb.get(k, "<missing>")
        if isinstance(x, float) and isinstance(y, float):
            if math.isnan(x) and math.isnan(y):
                continue
            d = abs(x - y)
            rel = d / max(abs(x), abs(y), 1e-300)
            if not (d <= atol or rel <= rtol):
                bad.append((k, x, y))
            if d > atol:
                worst = max(worst, rel)
        elif x != y:
            bad.append((k, x, y))
    return {"n_leaves": len(keys), "n_mismatch": len(bad), "max_rel_diff": worst, "mismatches": bad[:20]}


def cmd_equiv_real(method_dir: Path, method: str, systems: list[str], containers: int, out_json: Path) -> int:
    """Fit `method` on the given real systems locally and on Modal (public fit view), evaluate every fit locally and on Modal on the
    public-validation stand-in (lifting through the real engine included), and compare fits (k, predictions through the evaluation) and
    evaluation results leaf by leaf. Also checks the bundle-backed simulation service of a Modal fit container against the local
    engine on one public protocol."""
    import level_c as L
    from brainir_state.suite_eval import SuiteData, evaluate_models, fit_sandboxed
    work = Path(r"C:\Dev\BrainIR_p3run") / "equiv_real"
    work.mkdir(parents=True, exist_ok=True)
    hid = build_equiv_hidden(systems, ROOT / "data" / "phase3" / "_equiv_real_hidden")
    sd = SuiteData(REAL_PUBLIC, kind="real")
    view = sd.fit_view(work / "fitview_real")
    local_spec = dict(L.spec(), hidden_dir=str(hid), micro_dir=str(hid))

    def fresh_tag() -> str:
        import brainir_state.suite_eval as SE
        SE._CODE_TAG = None
        return SE.evaluator_code_tag()
    # ---- local
    local_fits = {s: fit_sandboxed(Path(method_dir), method, [view], [s], work / "local" / f"{s.replace(':', '_')}.pkl", seed=0, timeout_s=3600)
                  for s in systems}
    loc_jobs = [{"suite": local_spec, "sid": s, "method_dir": str(method_dir), "model_path": str(work / "local" / f"{s.replace(':', '_')}.pkl"),
                 "lift": True, "lift_cases": 2} for s in systems]
    ct0 = fresh_tag()
    loc_ev = evaluate_models(loc_jobs, workers=min(2, len(loc_jobs)))
    ct1 = fresh_tag()
    # ---- Modal: stage the stand-in on the eval volume, then the same fits and evaluations remotely
    _upload_extract([("eval", hid, sorted(q for q in hid.rglob("*") if q.is_file()), "suites/real_equiv/hidden")])
    _STATE.update(real_hidden_name="real_equiv", sim_budget=0, sim_systems={})
    app = _open_app(containers)
    with _output(), app.run():
        mfits = modal_run_fits_real([dict(method_dir=method_dir, method=method, datasets=[view], systems=[s],
                                          out=work / "modal" / f"{s.replace(':', '_')}.pkl", seed=0, timeout_s=3600) for s in systems])
        rem_jobs = [dict(j, model_path=str(work / "modal" / f"{j['sid'].replace(':', '_')}.pkl")) for j in loc_jobs]
        rem_ev = modal_evaluate_models_real(rem_jobs)
        # cross-check: the LOCAL fit evaluated on Modal (isolates evaluation equivalence from fit equivalence)
        cross_ev = modal_evaluate_models_real(loc_jobs)
        sim_check = _eval_map([{"job_id": uuid.uuid4().hex, "kind": "call", "module": "equiv_sim", "func": "simulate_public",
                                "args": [systems[0]], "links": {"/repo/data/phase3/real_public": "/fitvol/views/real"}, "timeout_s": 1800}],
                              "sim check")
    remote_tags = sorted(t for t in _STATE.get("remote_code_tags", set()) if t)
    report = {"method": method, "systems": systems, "local_evaluator_code_tag_before": ct0, "local_evaluator_code_tag_after": ct1,
              "remote_evaluator_code_tags": remote_tags, "same_evaluator_code": bool(ct0 == ct1 and remote_tags == [ct0]),
              "checked_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "per_system": {}}
    for s, lf, mf, le, re_, xe in zip(systems, [local_fits[s] for s in systems], mfits, loc_ev, rem_ev, cross_ev):
        report["per_system"][s] = {
            "fit_local_error": lf.get("error"), "fit_modal_error": (mf or {}).get("error"),
            "k_local": le.get("k"), "k_modal": re_.get("k"),
            "eval_local_error": le.get("error"), "eval_modal_error": re_.get("error"), "eval_cross_error": xe.get("error"),
            "local_fit__local_eval_vs_modal_eval": compare_results({"res": le.get("res"), "lift": le.get("lift")}, {"res": xe.get("res"), "lift": xe.get("lift")}),
            "local_fit_vs_modal_fit__evaluated": compare_results({"res": le.get("res"), "lift": le.get("lift")}, {"res": re_.get("res"), "lift": re_.get("lift")}),
        }
    try:
        from equiv_sim import simulate_public
        local_sim = simulate_public(systems[0])
        rs = (sim_check[0] or {}).get("result") if isinstance(sim_check[0], dict) else None
        report["simulator"] = {"local": local_sim, "modal": rs, "equal_within_1e-9": bool(rs and all(
            abs(float(a) - float(b)) <= 1e-9 * max(1.0, abs(float(a))) for a, b in zip(local_sim["summary"], rs["summary"])))}
    except Exception as e:  # noqa: BLE001
        report["simulator"] = {"error": repr(e), "modal": sim_check[0] if sim_check else None}
    report["modal_costs"] = _STATE["costs"]
    report["usd_approx_total"] = round(sum(c["usd_approx"] for c in _STATE["costs"]), 3)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({s: {k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != "mismatches"})
                          for k, v in r.items()} for s, r in report["per_system"].items()}, indent=1, default=str))
    print(json.dumps({"simulator": {k: v for k, v in report["simulator"].items() if k in ("equal_within_1e-9", "error")},
                      "usd": report["usd_approx_total"]}), flush=True)
    return 0


# ------------------------------------------------------------------------------------------------ CLI
def _output():
    """Modal's build / progress output on the console (image builds and container errors are visible in the run log)."""
    import modal
    return modal.enable_output()


def _open_app(containers: int):
    app, fit_fn, eval_fn, fitvol = make_app(containers)
    _STATE.update(fit_fn=fit_fn, eval_fn=eval_fn, fitvol=fitvol)
    return app


def cmd_run(rest: list[str], containers: int) -> int:
    import tournament as T
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--suite", default="heldout")
    pre.add_argument("--sim-budget", type=int, default=250)
    pre.add_argument("--round", required=True)
    known, _ = pre.parse_known_args(rest)
    _STATE.update(tier=known.suite, sim_budget=known.sim_budget)
    T.run_fits, T.evaluate_models, T.reproducibility_jobs = modal_run_fits, modal_evaluate_models, modal_reproducibility_jobs
    app = _open_app(containers)
    t0 = time.time()
    with _output(), app.run():
        rc = T.main(rest)
    rec = {"round": known.round, "suite": known.suite, "wall_s": round(time.time() - t0, 1), "cpu": CPU, "memory_mb": MEM_MB,
           "calls": _STATE["costs"], "usd_approx_total": round(sum(c["usd_approx"] for c in _STATE["costs"]), 2)}
    out = T.OUT / known.round / "modal_costs.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in rec.items() if k != "calls"}), flush=True)
    return rc


def cmd_refs(tier: str, ks: list[int], systems: list[str], containers: int) -> int:
    from tournament import suite_spec
    spec = suite_spec(tier)
    truth = json.loads((Path(spec["truth_dir"]) / "truth.json").read_text(encoding="utf-8"))
    sids = systems or sorted(truth["systems"])
    app = _open_app(containers)
    with _output(), app.run():
        prefetch_refs([(spec, s, k) for s in sids for k in ks])
    print(json.dumps(_STATE["costs"]), flush=True)
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        raise SystemExit(__doc__)
    cmd, rest = argv[0], argv[1:]
    containers = 100
    if "--containers" in rest:
        i = rest.index("--containers")
        containers = int(rest[i + 1])
        rest = rest[:i] + rest[i + 2:]
    if cmd == "upload":
        ap = argparse.ArgumentParser()
        ap.add_argument("--tier", required=True)
        ap.add_argument("--tar", action="store_true", help="upload the suite as tars and unpack in Modal (slow uplinks)")
        ap.add_argument("--work", default=str(ROOT / "data" / "phase3" / "_modal_upload"))
        a = ap.parse_args(rest)
        if a.tar:
            upload_tar(a.tier, Path(a.work))
        else:
            upload(a.tier)
        return 0
    if cmd == "run":
        return cmd_run(rest, containers)
    if cmd == "refs":
        ap = argparse.ArgumentParser()
        ap.add_argument("--tier", required=True)
        ap.add_argument("--k", default="1")
        ap.add_argument("--systems", default="")
        a = ap.parse_args(rest)
        return cmd_refs(a.tier, [int(x) for x in a.k.split(",")], [s for s in a.systems.split(",") if s], containers)
    if cmd == "upload-real":
        ap = argparse.ArgumentParser()
        ap.add_argument("--what", default="view,bundle,internal", help="comma list of view, bundle, internal, hidden (after the lock)")
        a = ap.parse_args(rest)
        upload_real([w for w in a.what.split(",") if w])
        return 0
    if cmd == "level-c":
        return cmd_level_c(rest, containers)
    if cmd == "equiv-real":
        ap = argparse.ArgumentParser()
        ap.add_argument("--method-dir", required=True)
        ap.add_argument("--method", required=True)
        ap.add_argument("--systems", default="real:net1:mech:02fa13b8,real:net2:mech:6883ab7b")
        ap.add_argument("--out", default=str(ROOT / "research" / "phase3" / "level_c" / "modal_equivalence.json"))
        a = ap.parse_args(rest)
        return cmd_equiv_real(Path(a.method_dir), a.method, [s for s in a.systems.split(",") if s], containers, Path(a.out))
    raise SystemExit(f"unknown command {cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
