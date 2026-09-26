"""Phase 4 Modal backend CLI (ORCHESTRATOR SIDE; goal5 sections 62-65, 97). The backend itself: brainir_causal.p4modal.

    uv run --no-sync --project phase4 python scripts/p4/modal_p4.py volumes                  # create / list the Phase 4 volumes (v2)
    uv run --no-sync --project phase4 python scripts/p4/modal_p4.py smoke-sim [--full 1] [--mech 2] [--t-end 0.5]
          host-gated real-engine simulations on Modal vs the local engine, bit for bit (every array, sha256), plus the volume
          store's cache (second pass all cached, identical) and restarts (provided source / volume source) ->
          research/phase4/modal_smoke_sim.json
    uv run --no-sync --project phase4 python scripts/p4/modal_p4.py equiv-gpu [--gpus L4,A100-80GB,H100] [--steps 50]
          CPU / GPU equivalence of seeded training (brainir_causal.equiv) -> research/phase4/GPU_BENCHMARK.json ("equivalence")
    uv run --no-sync --project phase4 python scripts/p4/modal_p4.py deploy                   # a deployed app for long-lived services

Every run is recorded in research/phase4/MODAL_RUNS.md (by hand, with the app id this prints).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))
OUT = ROOT / "research" / "phase4"


# ------------------------------------------------------------------------------------------------ smoke test of the simulation workers
def _smoke_protocols(d: dict, t_end: float, full: bool) -> list[dict]:
    """Protocols exercising every event kind of protocol v2 that the real engine supports (no policy applies: orchestrator-side)."""
    tg = list(d["targets_public"])
    a, c = tg[0], tg[-1]
    b = {"system": d["system_id"], "params_seed": 23, "t_end": t_end, "dt": 0.001, "stimulus": [[0.0, 0.0], [0.02, 1.0]]}
    edges = [(int(p), int(q)) for p, q, _ in d["public_graph"]["edges_post_pre_signed_count"] if int(p) != int(q)]
    out = [dict(b),
           {**b, "events": [{"kind": "kick", "t": 0.1, "delta": {str(a): 30.0}}]},
           {**b, "events": [{"kind": "current", "t0": 0.1, "t1": 0.2, "targets": {str(a): 40.0}}]},
           {**b, "events": [{"kind": "silence", "t0": 0.1, "t1": 0.3, "targets": [c]}]},
           {**b, "events": [{"kind": "param", "t0": 0.1, "t1": None, "targets": {str(a): {"gain": 1.3, "threshold": -1.0}}}]}]
    if not full:
        out += [{**b, "events": [{"kind": "current_seq", "t0": 0.1, "seg": 0.01, "targets": {str(a): [20.0, 0.0] * 5}}]},
                {**b, "weight_noise": {"sd": 0.05, "seed": 3}, "stimulus": [[0.0, 0.0], [0.02, 1.3], [0.15, 0.7]]}]
        if edges:
            out.append({**b, "events": [{"kind": "edge_scale", "t0": 0.1, "t1": 0.4, "edges": [list(edges[0])], "factor": 0.5}]})
    return out


def _digest(rec: dict) -> dict:
    import numpy as np
    return {k: hashlib.sha256(np.ascontiguousarray(v).tobytes()).hexdigest() for k, v in rec.items() if k != "info"}


def cmd_smoke_sim(n_full: int, n_mech: int, t_end: float) -> int:
    from brainir_causal import protocol as P
    from brainir_causal.p4modal import remote
    from brainir_causal.p4modal.app import Backend
    from brainir_causal.realsim import RealEngine, RealSystem
    from brainir_causal.store import TrajectoryStore
    from brainir_causal.systems import BUNDLE, load_real_internal
    internal = load_real_internal()
    fulls = sorted(s for s, d in internal.items() if d["mode"] == "full")[:n_full]
    mechs = sorted((s for s, d in internal.items() if d["mode"] == "mech"), key=lambda s: -len(internal[s]["keep"]))[:n_mech]
    items = []
    for sid in fulls + mechs:
        d = internal[sid]
        for p in _smoke_protocols(d, t_end, d["mode"] == "full"):
            items.append({"sysdef": d, "protocol": P.validate(p), "meta": {"source": "smoke"}})
    # ---- local reference (the development machine's engine; a local store for the restart sources)
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="p4smoke_", dir=str(ROOT / "data")))
    local = TrajectoryStore(tmp / "store")
    engines: dict = {}
    loc = []
    t0 = time.time()
    for it in items:
        d = it["sysdef"]
        if d["network"] not in engines:
            engines[d["network"]] = RealEngine(BUNDLE, d["network"])
        ts = time.time()
        key, rec, _ = local.get_or_run(engines[d["network"]], RealSystem.from_record(d), it["protocol"], d["system_hash"])
        loc.append({"key": key, "sha": _digest(rec), "wall_s": round(time.time() - ts, 3), "system": d["system_id"], "mode": d["mode"]})
    local_wall = time.time() - t0
    # restart protocols: from the first (nominal) trajectory of each system at t = t_end / 2
    restarts, src_keys = [], {}
    for it, lr in zip(items, loc):
        if not it["protocol"]["events"] and it["protocol"]["weight_noise"] is None and it["protocol"]["r0"]["kind"] == "rest" \
                and it["sysdef"]["system_id"] not in src_keys:
            src_keys[it["sysdef"]["system_id"]] = lr["key"]
            q = P.validate({**it["protocol"], "r0": {"kind": "restart", "key": lr["key"], "t": round(t_end / 2, 3)},
                            "events": [{"kind": "kick", "t": 0.05, "delta": {str(it["sysdef"]["targets_public"][0]): 25.0}}]})
            restarts.append({"sysdef": it["sysdef"], "protocol": q, "meta": {"source": "smoke"}})
    loc_rs = []
    for it in restarts:
        d = it["sysdef"]
        key, rec, _ = local.get_or_run(engines[d["network"]], RealSystem.from_record(d), it["protocol"], d["system_hash"])
        loc_rs.append({"key": key, "sha": _digest(rec)})
    sub = f"smoke_{time.strftime('%Y%m%dT%H%M%S')}"
    report = {"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "systems": fulls + mechs, "t_end": t_end,
              "n_protocols": len(items), "n_restarts": len(restarts), "local_wall_s": round(local_wall, 1), "store_sub": sub}
    with Backend(classes=["sim", "util"]) as be:
        report["app_id"] = be.app_id
        # pass 1: every protocol computed on gated hosts, written to the volume store (a smoke sub-store)
        r1 = be.simulate(items, mode="digest", store="store", store_sub=sub, batch=4, label="smoke pass 1")
        # pass 2: the same protocols again -> must all be served from the volume store, identical
        r2 = be.simulate(items, mode="digest", store="store", store_sub=sub, batch=4, label="smoke pass 2 (cache)")
        # restarts: (a) source record provided in the payload, (b) source taken from the volume store (computed in pass 1)
        prov = [dict(it, restart_src={it["protocol"]["r0"]["key"]: local.path(it["protocol"]["r0"]["key"]).read_bytes()}) for it in restarts]
        r3 = be.simulate(prov, mode="digest", store=None, batch=4, label="smoke restarts (provided source)")
        r4 = be.simulate(restarts, mode="digest", store="store", store_sub=sub, batch=4, label="smoke restarts (volume source)")
        # the full-record path the local simulation service uses (one mechanism protocol), bytes decoded and compared
        r5 = be.simulate(items[-1:], mode="full", store=None, batch=1, label="smoke full record")
        report["costs"] = be.cost_summary()

    def cmp(rem, ref):
        rows = []
        for r, lr in zip(rem, ref):
            if isinstance(r, BaseException):
                rows.append({"error": repr(r)[:500]})
                continue
            rows.append({"key_equal": r["key"] == lr["key"], "bit_identical": r["sha"] == lr["sha"], "computed": r.get("computed"),
                         "differing_arrays": [k for k in lr["sha"] if r["sha"].get(k) != lr["sha"][k]], "sim_wall_s": r.get("sim_wall_s"),
                         "host_ok": True})
        return rows

    p1, p2, p3_, p4_ = cmp(r1, loc), cmp(r2, loc), cmp(r3, loc_rs), cmp(r4, loc_rs)
    full_ok = None
    if not isinstance(r5[0], BaseException):
        rec5 = remote.record_from_bytes(r5[0]["record"])
        full_ok = _digest(rec5) == loc[-1]["sha"]
    per_sys = {}
    for lr, r in zip(loc, r1):
        s = per_sys.setdefault(lr["system"], {"mode": lr["mode"], "n": 0, "local_s": 0.0, "modal_sim_s": 0.0})
        s["n"] += 1
        s["local_s"] += lr["wall_s"]
        s["modal_sim_s"] += float(r.get("sim_wall_s") or 0.0) if isinstance(r, dict) else 0.0
    for s in per_sys.values():
        s["local_s_per_traj"] = round(s["local_s"] / s["n"], 3)
        s["modal_sim_s_per_traj"] = round(s["modal_sim_s"] / s["n"], 3)
    report.update({
        "pass1_all_bit_identical": all(r.get("bit_identical") for r in p1), "pass1_all_computed": all(r.get("computed") for r in p1),
        "pass2_all_cached": all(r.get("computed") is False for r in p2), "pass2_all_bit_identical": all(r.get("bit_identical") for r in p2),
        "restart_provided_bit_identical": all(r.get("bit_identical") for r in p3_),
        "restart_volume_bit_identical": all(r.get("bit_identical") for r in p4_),
        "full_record_bytes_identical": full_ok, "per_system": per_sys,
        "rows": {"pass1": p1, "pass2": p2, "restart_provided": p3_, "restart_volume": p4_},
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    c = report["costs"]
    n_traj = len(items) * 2 + len(restarts) * 2 + 1
    report["usd_approx_per_trajectory_all_passes"] = round(c["usd_approx_total"] / n_traj, 5)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "modal_smoke_sim.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    summary = {k: v for k, v in report.items() if k not in ("rows", "costs")}
    print(json.dumps(summary, indent=1), flush=True)
    print(json.dumps({"usd_approx_total": c["usd_approx_total"], "refusals": c["refusals"], "hosts": c["hosts"]}), flush=True)
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    ok = all(report[k] for k in ("pass1_all_bit_identical", "pass2_all_cached", "pass2_all_bit_identical", "restart_provided_bit_identical",
                                 "restart_volume_bit_identical")) and full_ok
    return 0 if ok else 1


# ------------------------------------------------------------------------------------------------ CPU / GPU equivalence
PLATFORM_NOTE = (
    "Platform note (2026-09-26, diagnostic apps ap-23qX72eDLkEHEC5nQkhdQ7 and ap-Xd8Ki87qinobSHsOj4c8DC). The Linux CPU runs of every "
    "container kind (gated with the AVX2 pins, ungated with the pins, the CUDA image's CPU path) agree with each other exactly. A first "
    "version of the reference trainer initialised its parameters in float32 and cast them to float64: the development machine (Windows) "
    "then differed from Linux by about 1e-7 relative from the first loss on, because the initialisers' float32 uniform transform rounds "
    "differently on the two platforms (compiled with / without fused multiply-add: one float32 rounding, ~6e-8). With the parameters "
    "initialised in float64 (the committed trainer), local Windows and Linux runs agree to ~1e-16 in float64 after 50 steps (rollout "
    "4e-16, GRU 2e-15) and to ~1e-7 in float32. Consequences for methods: (1) GPU and CPU training agree within the stated tolerances; "
    "(2) float32 initialisation or float32 arithmetic makes local and Modal results differ at the float32 level, which is harmless for "
    "comparisons but not bit-reproducible across platforms, so locked fits run on ONE platform (as in Phase 3); (3) elementary float64 "
    "kernels differ at the last digits across platforms (exp up to 8 ulp; matmul summation order), which recurrent rollouts do not "
    "amplify noticeably over 50 steps here.")


def cmd_equiv_gpu(gpus: list[str], dtypes: list[str], steps: int) -> int:
    import modal
    from brainir_causal import equiv as E
    from brainir_causal.p4modal import images
    app = modal.App("brainir-p4-equiv")

    def equiv_call(spec):
        from brainir_causal import equiv as EE
        return EE.container_pair(spec)

    img = images.full_image(gpu=True)
    fns = {g: app.function(gpu=g, cpu=4.0, memory=32768, timeout=3600, serialized=True, image=img,
                           name=f"equiv_{g.replace('-', '_').lower()}")(equiv_call) for g in gpus}
    spec = {"builder": E.REFERENCE, "configs": E.REFERENCE_CONFIGS, "dtypes": dtypes, "seed": 0, "steps": steps}
    # the development machine's CPU runs of the same builders (platform difference, informational)
    local = {}
    for cfg in spec["configs"]:
        for dt in dtypes:
            local[(cfg["kind"], dt)] = E.run_training(spec["builder"], cfg, "cpu", dt, 0, steps)
    t0 = time.time()
    res = {}
    with modal.enable_output(), app.run() as run:
        app_id = getattr(run, "app_id", None)
        calls = {g: fns[g].spawn(spec) for g in gpus}
        for g, c in calls.items():
            try:
                res[g] = c.get(timeout=3600)
            except Exception as e:  # noqa: BLE001
                res[g] = {"error": repr(e)[:800]}
    rows = []
    for g, r in res.items():
        if "error" in r:
            rows.append({"gpu_class": g, "error": r["error"]})
            continue
        for pair in r["runs"]:
            s = E.summarize_pair(pair, local.get((pair["config"]["kind"], pair["dtype"])))
            s["gpu_class"] = g
            s["gpu_train_s"] = pair["gpu1"]["train_wall_s"]
            s["container_cpu_train_s"] = pair["cpu"]["train_wall_s"]
            s["torch_cuda"] = pair["gpu1"]["info"].get("cuda")
            rows.append(s)
    doc_path = OUT / "GPU_BENCHMARK.json"
    doc = json.loads(doc_path.read_text(encoding="utf-8")) if doc_path.exists() else {}
    eq = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "app_id": app_id, "wall_s": round(time.time() - t0, 1),
          "builder": spec["builder"], "configs": spec["configs"], "steps": steps, "tolerances": E.TOLERANCES, "settings": E.SETTINGS,
          "rows": rows, "platform_note": PLATFORM_NOTE,
          "all_pass": bool(rows) and all(r.get("criterion_39_pass") for r in rows if "error" not in r) and not any("error" in r for r in rows)}
    doc["equivalence"] = eq
    (OUT / "GPU_BENCHMARK.equiv.json").write_text(json.dumps(eq, indent=1) + "\n", encoding="utf-8", newline="\n")
    doc_path.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
    try:
        sys.path.insert(0, str(ROOT / "scripts" / "p4"))
        from gpu_benchmark import render_md
        if "rows" in doc:
            (OUT / "GPU_BENCHMARK.md").write_text(render_md(doc), encoding="utf-8", newline="\n")
    except Exception as e:  # noqa: BLE001
        print(f"markdown not re-rendered: {e!r}", flush=True)
    brief = [{k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk in ("loss_rel_max", "param_rel", "pred_rel",
                                                                                                "bitwise_identical", "pass")})
              for k, v in r.items() if k in ("gpu_class", "gpu", "dtype", "config", "gpu_vs_cpu", "gpu_run_to_run", "container_cpu_vs_local_cpu",
                                             "criterion_39_pass", "error")} for r in rows]
    print(json.dumps(brief, indent=1), flush=True)
    return 0 if doc["equivalence"]["all_pass"] else 1


# ------------------------------------------------------------------------------------------------ smoke test of guarded method jobs
SMOKE_METHOD = '''"""Smoke-test method for the Phase 4 Modal backend (fork E4): probes the guard and uses the per-job simulation service."""
import json, os, socket, subprocess
from pathlib import Path


def _try(fn):
    try:
        fn()
        return "ALLOWED"
    except PermissionError:
        return "blocked"
    except FileNotFoundError:
        return "absent"
    except Exception as e:  # noqa: BLE001
        return type(e).__name__


def probe(job_dir, simq, system_id, target):
    out = {"read_own_input": _try(lambda: Path(job_dir, "input.json").read_text())}
    for name, path in [("list_storevol", "/storevol"), ("list_fitvol", "/fitvol"), ("read_repo_bundle", "/repo/benchmarks/dng100/public_blind/manifest.json"),
                       ("list_other_jobs", "/tmp/p4m/jobs"), ("list_root_home", "/root"), ("read_proc_1_environ", "/proc/1/environ"),
                       ("read_proc_self_status", "/proc/self/status")]:
        out[name] = _try((lambda p=path: os.listdir(p)) if not path.endswith(("manifest.json", "environ", "status")) else (lambda p=path: open(p, "rb").read()))
    def via_chdir():
        cwd = os.getcwd()
        try:
            os.chdir("/proc")
            open("1/environ", "rb").read()
        finally:
            os.chdir(cwd)
    out["read_proc_1_via_chdir"] = _try(via_chdir)
    out["read_proc_1_via_self_root"] = _try(lambda: open("/proc/self/root/proc/1/environ", "rb").read())
    out["list_storevol_via_self_root"] = _try(lambda: os.listdir("/proc/self/root/storevol"))
    out["subprocess"] = _try(lambda: subprocess.run(["true"], check=False))
    out["socket"] = _try(lambda: socket.create_connection(("1.1.1.1", 80), timeout=3))
    from brainir_causal.simclient import SimClient
    p = {"system": system_id, "params_seed": 5, "t_end": 0.3, "dt": 0.001, "stimulus": [[0.0, 0.0], [0.02, 1.0]],
         "events": [{"kind": "kick", "t": 0.1, "delta": {str(target): 10.0}}]}
    r = SimClient(queue=simq, agent="smoke").run([p, dict(p, params_seed=10**9 + 5)])
    out["sim_public_ok"] = bool(r[0]["ok"])
    out["sim_x_shape"] = list(r[0]["x"].shape) if r[0]["ok"] else r[0]["error"]
    out["sim_hidden_seed_refused"] = (not r[1]["ok"]) and r[1]["error"]
    Path(job_dir, "out").mkdir(exist_ok=True)
    Path(job_dir, "out", "result.json").write_text(json.dumps(out))
    return out
'''


def cmd_smoke_method() -> int:
    import tempfile

    from brainir_causal.p4modal.app import Backend
    from brainir_causal.systems import load_real_internal
    internal = load_real_internal()
    sid = sorted(s for s, d in internal.items() if d["mode"] == "mech")[0]
    fid = sorted(s for s, d in internal.items() if d["mode"] == "full")[0]
    public_defs = {s: {k: v for k, v in internal[s].items() if k not in ("targets_heldout", "meta")} for s in (sid, fid)}
    tmp = Path(tempfile.mkdtemp(prefix="p4smoke_method_", dir=str(ROOT / "data")))
    (tmp / "p4smoke_method.py").write_text(SMOKE_METHOD, encoding="utf-8")
    rep = {"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "system": sid, "full_system": fid}

    def payload(s: str, guard: str) -> dict:
        return {"target": "p4smoke_method:probe", "args": ["$JOB", "$SIMQ", s, int(public_defs[s]["targets_public"][0])], "methods_key": key,
                "inputs": {"input.json": b'{"hello": 1}'}, "outputs": ["out/*.json"], "threads": 2, "timeout_s": 900, "guard": guard,
                "sim": {"systems": {s: public_defs[s]}, "budget": 20, "workers": 2, "store": "store"}}

    with Backend(classes=["fit_s", "eval_s"]) as be:
        key = be.methods_key(tmp)
        rf = be.run_methods([payload(sid, "fit")], cls="fit_s", label="smoke method (fit guard)")[0]
        re_ = be.run_methods([payload(sid, "eval")], cls="eval_s", label="smoke method (eval guard)")[0]
        # a full network: the per-job service serves it through VolumeStoreBackend (volume cache, else computed in the container);
        # the second identical job must be served from the volume store
        rfull1 = be.run_methods([payload(fid, "fit")], cls="fit_s", label="smoke method (full network, 1st)")[0]
        rfull2 = be.run_methods([payload(fid, "fit")], cls="fit_s", label="smoke method (full network, 2nd)")[0]
        rep["app_id"] = be.app_id
        rep["costs"] = be.cost_summary()
    for name, r in (("full_first", rfull1), ("full_second", rfull2)):
        ok = isinstance(r, dict) and "result" in r
        rep[name] = {"sim_public_ok": ok and bool(r["result"].get("sim_public_ok")), "x_shape": ok and r["result"].get("sim_x_shape"),
                     "remote_computed": (r.get("sim") or {}).get("remote_computed") if ok else None, "error": None if ok else str(r)[:2000]}
    rep["full_cache_ok"] = (rep["full_first"]["remote_computed"] == 1 and rep["full_second"]["remote_computed"] == 0
                            and rep["full_first"]["sim_public_ok"] and rep["full_second"]["sim_public_ok"])
    for name, r in (("fit", rf), ("eval", re_)):
        if isinstance(r, BaseException) or "result" not in r:
            rep[name] = {"error": str(r)[:3000]}
            continue
        rep[name] = {"probe": r["result"], "files": sorted(r.get("files") or {}), "sim": {k: v for k, v in (r.get("sim") or {}).items() if k != "ledger"},
                     "ledger_agents": sorted((r.get("sim") or {}).get("ledger", {}))}
    expect_blocked = ["list_storevol", "list_fitvol", "read_repo_bundle", "list_other_jobs", "list_root_home", "read_proc_1_environ",
                      "read_proc_1_via_chdir", "read_proc_1_via_self_root", "list_storevol_via_self_root", "subprocess", "socket"]
    for name in ("fit", "eval"):
        pr = (rep.get(name) or {}).get("probe") or {}
        rep[f"{name}_guard_ok"] = bool(pr) and all(pr.get(k) in ("blocked", "absent") for k in expect_blocked) and pr.get("read_own_input") == "ALLOWED"
        rep[f"{name}_sim_ok"] = bool(pr.get("sim_public_ok")) and bool(pr.get("sim_hidden_seed_refused"))
    rep["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (OUT / "modal_smoke_method.json").write_text(json.dumps(rep, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in rep.items() if k != "costs"}, indent=1, default=str), flush=True)
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if all(rep.get(k) for k in ("fit_guard_ok", "eval_guard_ok", "fit_sim_ok", "eval_sim_ok", "full_cache_ok")) else 1


# ------------------------------------------------------------------------------------------------ volumes / deploy
def cmd_volumes() -> int:
    from brainir_causal.p4modal.app import VOLUMES, volume
    for k in VOLUMES:
        v = volume(k)
        try:
            n = len(list(v.listdir("/")))
        except Exception as e:  # noqa: BLE001
            n = f"error {e!r}"
        print(k, VOLUMES[k], "top-level entries:", n, flush=True)
    return 0


def cmd_deploy(classes: list[str] | None) -> int:
    from brainir_causal.p4modal.app import make_app
    app, _fns, _vols = make_app(classes)
    import modal
    with modal.enable_output():
        app.deploy()
    print("deployed", app.name, flush=True)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("smoke-sim")
    s.add_argument("--full", type=int, default=1)
    s.add_argument("--mech", type=int, default=2)
    s.add_argument("--t-end", type=float, default=0.5)
    e = sub.add_parser("equiv-gpu")
    e.add_argument("--gpus", default="L4,A100-80GB,H100")
    e.add_argument("--dtypes", default="float64,float32")
    e.add_argument("--steps", type=int, default=50)
    sub.add_parser("volumes")
    sub.add_parser("smoke-method")
    d = sub.add_parser("deploy")
    d.add_argument("--classes", default="")
    a = ap.parse_args(argv)
    if a.cmd == "smoke-sim":
        return cmd_smoke_sim(a.full, a.mech, a.t_end)
    if a.cmd == "smoke-method":
        return cmd_smoke_method()
    if a.cmd == "equiv-gpu":
        return cmd_equiv_gpu([g for g in a.gpus.split(",") if g], [x for x in a.dtypes.split(",") if x], a.steps)
    if a.cmd == "volumes":
        return cmd_volumes()
    return cmd_deploy([c for c in a.classes.split(",") if c] or None)


if __name__ == "__main__":
    raise SystemExit(main())
