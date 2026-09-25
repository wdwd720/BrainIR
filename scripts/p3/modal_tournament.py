"""Run the frozen Level B tournament driver with its fits and evaluations executed on Modal (goal4 section 58: use compute when it
saves wall-clock time). The protocol is unchanged: scripts/p3/tournament.py runs as is, and only its three execution functions
(run_fits, evaluate_models, reproducibility_jobs) are replaced by Modal-backed equivalents that run the SAME frozen workers
(brainir_state.suite_eval.fit_sandboxed / evaluate_model_job / reproducibility_job) in fresh subprocesses in Linux containers.
Reference controls are prefetched on Modal with the frozen reference_results into the same local cache.

    uv run --project phase3 --no-sync python scripts/p3/modal_tournament.py upload --tier dev|heldout|final
    uv run --project phase3 --no-sync python scripts/p3/modal_tournament.py run <tournament.py arguments> [--containers 100]
    uv run --project phase3 --no-sync python scripts/p3/modal_tournament.py refs --tier heldout [--k 1] [--systems s1,s2]

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
    return (modal.Image.debian_slim(python_version="3.12")
            .pip_install("numpy==2.5.3", "scipy==1.18.1", "pandas==3.0.6", "pyarrow==25.0.1", "pydantic==2.13.5", "scikit-learn==1.9.1",
                         "threadpoolctl==3.7.0")
            .pip_install("torch==2.14.0", index_url="https://download.pytorch.org/whl/cpu")
            .env({"PYTHONPATH": "/repo/phase3/src:/repo/p3modal", "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
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
        return R.run_fit(payload)

    def p3_eval_call(payload):
        import p3modal.remote as R
        if payload["kind"] in ("eval", "repro"):
            return R.run_eval(payload)
        if payload["kind"] == "extract":
            return R.run_extract(payload)
        return R.run_call(payload) if payload["kind"] == "call" else R.run_refs(payload)

    return p3_fit_call, p3_eval_call


def make_app(containers: int):
    import modal
    app = modal.App(APP_NAME, image=image())
    fitvol = modal.Volume.from_name(FIT_VOLUME, create_if_missing=True)
    evalvol = modal.Volume.from_name(EVAL_VOLUME, create_if_missing=True)
    retries = modal.Retries(max_retries=1, initial_delay=5.0, backoff_coefficient=1.0)
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
    payloads = [{"job_id": uuid.uuid4().hex, "kind": "refs", "suite": spec, "sid": sid, "k": kk, "seed": seed, "timeout_s": 5400}
                for spec, sid, kk, _ in todo]
    for (spec, sid, kk, cache), r in zip(todo, _eval_map(payloads, "references")):
        if isinstance(r, BaseException) or r.get("error"):
            print(f"  reference prefetch failed for {sid} k={kk}: {r if isinstance(r, BaseException) else r.get('error')}", flush=True)
            continue
        cache.mkdir(parents=True, exist_ok=True)
        for name, data in r["files"].items():
            if not (cache / name).exists():
                (cache / name).write_bytes(data)


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
    raise SystemExit(f"unknown command {cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
