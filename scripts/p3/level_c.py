"""state_discovery_v1 Level C: the real hidden evaluation of the LOCKED method (orchestrator; PROTOCOL.md sections 1, 7, 8, 10).

    uv run --project phase3 python scripts/p3/level_c.py --method-dir <locked methods copy> --method <name> --baseline <name>
                                                       [--parallel 4] [--eval-workers 4] [--attempt 01]

Refuses to run without research/phase3/METHOD_LOCK.json and without the hidden real data (scripts/p3/generate_real_hidden.py, run
after the lock). Every run is appended to research/phase3/HIDDEN_EVALUATIONS.md. Steps:
1. fits in the sandbox on the PUBLIC real data (train + val): the locked method on every system with seeds 0-4 (G), the strongest
   baseline with seed 0; shared fits per network (I) with leave-one-implementation-out adaptation; cross-connectome models on the
   full systems (J): (1) independent, (2) common k with independent dynamics, (3) shared dynamics, (4) partially shared where
   supported, for net1+net2 (independent reconstructions) and, reported apart, net1+net3 (same reconstruction);
2. evaluates every model on the hidden sets (families A-E, R, P, H; lifting through the real engine), the references per system;
3. verdicts (PROTOCOL section 7), sharing verdicts, and the primary paired comparisons of the locked method with the strongest
   baseline (families A, C, D, E per full system; Holm across them);
4. writes research/phase3/level_c/<attempt>/ (ANSWER-BEARING).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase3" / "src"))
from brainir_state.evaluate_cross import holm, loio_comparison, paired_diff, paired_ratio_diff, sharing_comparison, sharing_verdict  # noqa: E402
from brainir_state.harness import key_a, key_c, key_d, verdict  # noqa: E402
from brainir_state.suite_eval import (SuiteData, dump, evaluate_models, limit_threads, reference_results, reproducibility_jobs,  # noqa: E402
                                      run_fits)

DATA = ROOT / "data" / "phase3"
BENCH = ROOT / "benchmarks" / "state_discovery_v1"
RUN = Path(r"C:\Dev\BrainIR_p3run")
OUT = ROOT / "research" / "phase3" / "level_c"


def spec() -> dict:
    return {"public_dir": str(DATA / "real_public"), "hidden_dir": str(DATA / "real_hidden"), "micro_dir": str(DATA / "real_hidden"),
            "kind": "real", "systems_internal": str(BENCH / "hidden" / "systems_internal.json"),
            "bundle": str(ROOT / "benchmarks" / "dng100" / "public_blind")}


def limited_view(sd: SuiteData, sid: str, root: Path, every: int = 4) -> Path:
    import os
    if (root / "manifest.json").exists():
        return root
    (root / "traj").mkdir(parents=True, exist_ok=True)
    rows = [r for r in sd.pub.select(system_id=sid) if r["split"] == "train"][::every]
    for r in rows:
        src, dst = sd.public_dir / "traj" / f"{r['key']}.npz", root / "traj" / f"{r['key']}.npz"
        if not dst.exists():
            try:
                os.link(src, dst)
            except OSError:
                shutil.copy2(src, dst)
    man = dict(sd.pub.manifest)
    man["systems"] = {sid: sd.pub.systems[sid]}
    man["splits"] = ["train"]
    (root / "index.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8", newline="\n")
    (root / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return root


def _tag(members) -> str:
    return hashlib.sha256("+".join(sorted(members)).encode()).hexdigest()[:8]


def _params(info: dict, members: list[str]) -> dict:
    npar = (info or {}).get("n_params") or {}
    if not npar:
        return {"encoder": 0, "readout": 0, "transition": 0, "total": 0, "reported": False}
    enc = sum(int((npar.get("encoder") or {}).get(s, 0)) for s in members)
    ro = sum(int((npar.get("readout") or {}).get(s, 0)) for s in members)
    tr = int(npar.get("transition", 0) or 0)
    return {"encoder": enc, "readout": ro, "transition": tr, "total": enc + ro + tr, "reported": True}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--method-dir", required=True)
    ap.add_argument("--method", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--attempt", default="01")
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--eval-workers", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=3600.0)
    ap.add_argument("--reason", default="first and only planned Level C evaluation")
    args = ap.parse_args(argv)
    if not (ROOT / "research" / "phase3" / "METHOD_LOCK.json").exists():
        raise SystemExit("refusing: Level C runs only after research/phase3/METHOD_LOCK.json exists")
    if not (DATA / "real_hidden" / "manifest.json").exists():
        raise SystemExit("refusing: generate the hidden real data first (scripts/p3/generate_real_hidden.py)")
    limit_threads(4)
    t0 = time.time()
    sp = spec()
    sd = SuiteData(sp["public_dir"], kind="real", hidden_dir=sp["hidden_dir"], micro_dir=sp["micro_dir"])
    run_dir = RUN / f"level_c_{args.attempt}"
    run_dir.mkdir(parents=True, exist_ok=True)
    mdir = Path(args.method_dir).resolve()
    view = sd.fit_view(run_dir / "fitview_real")
    # the fits get the same public simulation access as during development (public policy; 250 budget units per fit)
    import subprocess
    real_defs = json.loads((BENCH / "hidden" / "systems_internal.json").read_text(encoding="utf-8"))
    sysfile = run_dir / "simservice_systems_real.json"
    sysfile.write_text(json.dumps({s_: dict(d, cost=10 if d["mode"] == "full" else 3) for s_, d in real_defs.items()}), encoding="utf-8")
    simq = run_dir / "sim" / "simq"
    sim_proc = subprocess.Popen([sys.executable, "-m", "brainir_state.simservice", "--clean", str(run_dir / "sim"), "--systems", str(sysfile),
                                 "--bundle", sp["bundle"], "--store", str(DATA / "store"), "--budget", "250", "--workers", "4"],
                                stdout=open(run_dir / "simservice.log", "a"), stderr=subprocess.STDOUT)
    taus = json.loads((BENCH / "public" / "tolerances.json").read_text(encoding="utf-8"))
    sids = sd.systems
    nets = sorted({sd.sysinfo(s)["network"] for s in sids})
    by_net = {n: [s for s in sids if sd.sysinfo(s)["network"] == n] for n in nets}
    full = {n: next(s for s in by_net[n] if sd.sysinfo(s)["mode"] == "full") for n in nets}
    out_dir = OUT / args.attempt
    log = ROOT / "research" / "phase3" / "HIDDEN_EVALUATIONS.md"
    if not log.exists():
        log.write_text("# Phase 3 hidden evaluation log (Level C and Level B confirmation; PROTOCOL.md section 10)\n\n| time (UTC) | "
                       "attempt | what | method / baseline | reason | outputs |\n|---|---|---|---|---|---|\n", encoding="utf-8", newline="\n")
    with open(log, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(f"| {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} | {args.attempt} | Level C START (real hidden) | {args.method} / "
                 f"{args.baseline} | {args.reason} | research/phase3/level_c/{args.attempt}/ |\n")
    # ---------------------------------------------------------------- fits
    jobs = []
    for m, seeds in ((args.method, range(5)), (args.baseline, range(1))):
        for s in sids:
            for seed in seeds:
                jobs.append(dict(method_dir=mdir, method=m, datasets=[view], systems=[s], out=run_dir / m / "indep" / f"{s.replace(':', '_')}_s{seed}.pkl",
                                 seed=seed, timeout_s=args.timeout, sim_queue=simq))
    m = args.method
    for n, members in by_net.items():
        if len(members) > 1:
            t = _tag(members)
            jobs.append(dict(method_dir=mdir, method=m, datasets=[view], systems=members, out=run_dir / m / "shared" / f"net_{n}_{t}.pkl",
                             config={"sharing": "shared"}, seed=0, timeout_s=args.timeout * 2, sim_queue=simq))
            for held in members:
                others = [s for s in members if s != held]
                jobs.append(dict(method_dir=mdir, method=m, datasets=[view], systems=others,
                                 out=run_dir / m / "loio" / f"{t}_without_{held.replace(':', '_')}.pkl", config={"sharing": "shared"}, seed=0,
                                 timeout_s=args.timeout * 2, sim_queue=simq))
    cc_pairs = [(nets[0], nets[1])] + ([(nets[0], nets[2])] if len(nets) > 2 else [])
    for a, b in cc_pairs:
        members = [full[a], full[b]]
        t = _tag(members)
        jobs.append(dict(method_dir=mdir, method=m, datasets=[view], systems=members, out=run_dir / m / "cross" / f"shared_{t}.pkl",
                         config={"sharing": "shared"}, seed=0, timeout_s=args.timeout * 2, sim_queue=simq))
        jobs.append(dict(method_dir=mdir, method=m, datasets=[view], systems=members, out=run_dir / m / "cross" / f"partial_{t}.pkl",
                         config={"sharing": "partial"}, seed=0, timeout_s=args.timeout * 2, sim_queue=simq))
        for held in members:       # cross-connectome transfer: dynamics fitted on the other network only
            other = [x for x in members if x != held]
            jobs.append(dict(method_dir=mdir, method=m, datasets=[view], systems=other,
                             out=run_dir / m / "cross" / f"{t}_without_{held.replace(':', '_')}.pkl", config={"sharing": "shared"}, seed=0,
                             timeout_s=args.timeout * 2, sim_queue=simq))
    print(f"{len(jobs)} fits", flush=True)
    recs = run_fits(jobs, parallel=args.parallel)
    # model 2 (common k, independent dynamics) needs the shared model's k; LOIO adaptation needs the shared-on-others models
    jobs2 = []
    for a, b in cc_pairs:
        members = [full[a], full[b]]
        t = _tag(members)
        p = run_dir / m / "cross" / f"shared_{t}.pkl"
        if p.exists():
            k_sh = json.loads(p.with_suffix(".json").read_text(encoding="utf-8"))["info"].get("k", {})
            kc = max(int(v) for v in k_sh.values()) if k_sh else None
            if kc:
                for s in members:
                    jobs2.append(dict(method_dir=mdir, method=m, datasets=[view], systems=[s], out=run_dir / m / "cross" / f"commonk_{t}_{s.replace(':', '_')}.pkl",
                                      config={"k": kc, "sharing": "independent"}, seed=0, timeout_s=args.timeout, sim_queue=simq))
    for a, b in cc_pairs:
        members = [full[a], full[b]]
        t = _tag(members)
        for held in members:
            base = run_dir / m / "cross" / f"{t}_without_{held.replace(':', '_')}.pkl"
            lv = limited_view(sd, held, run_dir / f"limited_{held.replace(':', '_')}")
            if base.exists():
                jobs2.append(dict(method_dir=mdir, method=m, datasets=[lv], systems=[held], out=run_dir / m / "cross" / f"{t}_adapt_{held.replace(':', '_')}.pkl",
                                  adapt_from=base, seed=0, timeout_s=args.timeout, sim_queue=simq))
            scratch = run_dir / m / "loio" / f"{t}_scratch_{held.replace(':', '_')}.pkl"
            jobs2.append(dict(method_dir=mdir, method=m, datasets=[lv], systems=[held], out=scratch, seed=0, timeout_s=args.timeout, sim_queue=simq))
    for n, members in by_net.items():
        if len(members) > 1:
            t = _tag(members)
            for held in members:
                base = run_dir / m / "loio" / f"{t}_without_{held.replace(':', '_')}.pkl"
                lv = limited_view(sd, held, run_dir / f"limited_{held.replace(':', '_')}")
                if base.exists():
                    jobs2.append(dict(method_dir=mdir, method=m, datasets=[lv], systems=[held], out=run_dir / m / "loio" / f"{t}_adapt_{held.replace(':', '_')}.pkl",
                                      adapt_from=base, seed=0, timeout_s=args.timeout, sim_queue=simq))
                jobs2.append(dict(method_dir=mdir, method=m, datasets=[lv], systems=[held], out=run_dir / m / "loio" / f"{t}_scratch_{held.replace(':', '_')}.pkl",
                                  seed=0, timeout_s=args.timeout, sim_queue=simq))
    recs += run_fits(jobs2, parallel=args.parallel)
    sim_proc.terminate()
    # ---------------------------------------------------------------- evaluation
    ev_jobs = []
    for mm in (args.method, args.baseline):
        for p in sorted((run_dir / mm).rglob("*.pkl")):
            side = json.loads(p.with_suffix(".json").read_text(encoding="utf-8"))
            for s in side["systems"]:
                lift = mm == args.method and p.parent.name == "indep" and p.stem.endswith("_s0")
                ev_jobs.append({"suite": sp, "sid": s, "method_dir": str(mdir), "model_path": str(p), "lift": lift, "lift_cases": 4,
                                "tag": f"{mm}/{p.parent.name}/{p.stem}"})
    print(f"{len(ev_jobs)} evaluations", flush=True)
    evs = evaluate_models(ev_jobs, workers=args.eval_workers)
    by = {(e["sid"], j["tag"]): e for e, j in zip(evs, ev_jobs)}

    def ev(mm, sub, stem, s):
        return by.get((s, f"{mm}/{sub}/{stem}"))
    cfg = sd.cfg
    result = {"attempt": args.attempt, "method": args.method, "baseline": args.baseline, "tolerances": taus, "systems": {}, "fit_failures":
              [r for r in recs if "error" in r][:50]}
    pvals, comps = {}, {}
    for s in sids:
        info = sd.sysinfo(s)
        row = {"mode": info["mode"], "network": info["network"], "n_observed": len(info["observed"])}
        for mm in (args.method, args.baseline):
            e = ev(mm, "indep", f"{s.replace(':', '_')}_s0", s)
            if e is None or "error" in e:
                row[mm] = {"error": (e or {}).get("error", "fit or evaluation failed")}
                continue
            k = e.get("k")
            refs = reference_results(sd, s, int(k) if k else 1, OUT / "_refcache")
            ab = ((e.get("info") or {}).get("abstain") or {}).get(s)
            v = verdict(e["res"], refs, taus, len(info["observed"]), k, "mech" if info["mode"] == "mech" else "full", cfg, abstain=ab)
            row[mm] = {"k": k, "k_range": ((e.get("info") or {}).get("k_range") or {}).get(s), "verdict": v, "lift": e.get("lift"),
                       "res": e["res"], "references": {n: {kk: vv for kk, vv in r.items() if kk != "C_per_family"} for n, r in refs.items()}}
        # primary paired comparisons (full systems): locked method vs strongest baseline
        em, eb = ev(args.method, "indep", f"{s.replace(':', '_')}_s0", s), ev(args.baseline, "indep", f"{s.replace(':', '_')}_s0", s)
        if info["mode"] == "full" and em and eb and "error" not in em and "error" not in eb:
            ra, rb = em["res"], eb["res"]
            ka = key_a(cfg)
            c_key = f"C_w{int(round(cfg.primary_c_window_s * 1000))}ms"
            comps[s] = {"A": paired_diff((ra["A_B"].get("_units") or {}).get(ka, {}), (rb["A_B"].get("_units") or {}).get(ka, {})),
                        "C": paired_ratio_diff(((ra.get("C_heldout") or {}).get("_units") or {}).get(c_key, {}),
                                               ((rb.get("C_heldout") or {}).get("_units") or {}).get(c_key, {})),
                        "D": {"method": ((ra.get("D") or {}).get(key_d(cfg)) or {}).get("micro_gain"),
                              "baseline": ((rb.get("D") or {}).get(key_d(cfg)) or {}).get("micro_gain")},
                        "E": {"method": (ra.get("E") or {}).get("E_ratio_latent_to_random"),
                              "baseline": (rb.get("E") or {}).get("E_ratio_latent_to_random")}}
            for fam in ("A", "C"):
                pvals[f"{s}:{fam}"] = comps[s][fam]["p"]
        result["systems"][s] = row
    result["primary_comparisons"] = comps
    result["primary_holm"] = holm(pvals)
    # ---------------------------------------------------------------- G (5 seeds of the locked method)
    g_jobs = []
    for s in sids:
        paths = [run_dir / args.method / "indep" / f"{s.replace(':', '_')}_s{seed}.pkl" for seed in range(5)]
        if all(p.exists() for p in paths):
            g_jobs.append({"suite": sp, "sid": s, "method_dir": str(mdir), "model_paths": [str(p) for p in paths]})
    result["G"] = {r["sid"]: r for r in reproducibility_jobs(g_jobs, workers=args.eval_workers)} if g_jobs else {}
    # ---------------------------------------------------------------- I (per network) and J (cross-connectome)
    c_key = f"C_w{int(round(cfg.primary_c_window_s * 1000))}ms"
    i_rows = {}
    for n, members in by_net.items():
        if len(members) < 2:
            continue
        t = _tag(members)
        sh = {s: ev(m, "shared", f"net_{n}_{t}", s) for s in members}
        ind = {s: ev(m, "indep", f"{s.replace(':', '_')}_s0", s) for s in members}
        if any(v is None or "error" in v for v in list(sh.values()) + list(ind.values())):
            i_rows[n] = {"verdict": "untestable", "reason": "missing fit or evaluation"}
            continue
        comp = sharing_comparison({s: {"A": sh[s]["res"]["A_B"], "C": sh[s]["res"].get("C_heldout") or {}} for s in members},
                                  {s: {"A": ind[s]["res"]["A_B"], "C": ind[s]["res"].get("C_heldout") or {}} for s in members},
                                  _params(sh[members[0]].get("info"), members),
                                  {"encoder": sum(_params(ind[s].get("info"), [s])["encoder"] for s in members),
                                   "readout": sum(_params(ind[s].get("info"), [s])["readout"] for s in members),
                                   "transition": sum(_params(ind[s].get("info"), [s])["transition"] for s in members),
                                   "total": sum(_params(ind[s].get("info"), [s])["total"] for s in members),
                                   "reported": all(_params(ind[s].get("info"), [s])["reported"] for s in members)},
                                  taus["tau_A"], a_key=key_a(cfg), c_key=c_key)
        loio = []
        for held in members:
            ad = ev(m, "loio", f"{t}_adapt_{held.replace(':', '_')}", held)
            sc = ev(m, "loio", f"{t}_scratch_{held.replace(':', '_')}", held)
            if ad and sc and "error" not in ad and "error" not in sc:
                loio.append(loio_comparison({"A": ad["res"]["A_B"], "C": ad["res"].get("C_heldout") or {}},
                                            {"A": sc["res"]["A_B"], "C": sc["res"].get("C_heldout") or {}}, a_key=key_a(cfg), c_key=c_key) | {"held": held})
        i_rows[n] = {"members": members, "verdict": sharing_verdict(comp, loio), "comparison": comp, "loio": loio,
                     "method_own_verdict": ((sh[members[0]].get("info") or {}).get("sharing") or {})}
    result["I"] = i_rows
    j_rows = {}
    for a, b in cc_pairs:
        members = [full[a], full[b]]
        t = _tag(members)
        sh = {s: ev(m, "cross", f"shared_{t}", s) for s in members}
        ind = {s: ev(m, "indep", f"{s.replace(':', '_')}_s0", s) for s in members}
        ck = {s: ev(m, "cross", f"commonk_{t}_{s.replace(':', '_')}", s) for s in members}
        pa = {s: ev(m, "cross", f"partial_{t}", s) for s in members}
        row = {"members": members, "note": "independent reconstructions" if {a, b} == {nets[0], nets[1]} else "same reconstruction (descriptive)"}
        for name, mod in (("model1_independent", ind), ("model2_common_k", ck), ("model3_shared", sh), ("model4_partial", pa)):
            row[name] = {s: (None if (mod.get(s) is None or "error" in mod.get(s)) else
                             {"A": mod[s]["res"]["A_B"].get(key_a(cfg)), "C": (mod[s]["res"].get("C_heldout") or {}).get(key_c(cfg)),
                              "k": mod[s].get("k")}) for s in members}
        if all(v is not None and "error" not in v for v in list(sh.values()) + list(ind.values())):
            comp = sharing_comparison({s: {"A": sh[s]["res"]["A_B"], "C": sh[s]["res"].get("C_heldout") or {}} for s in members},
                                      {s: {"A": ind[s]["res"]["A_B"], "C": ind[s]["res"].get("C_heldout") or {}} for s in members},
                                      _params(sh[members[0]].get("info"), members),
                                      {"encoder": sum(_params(ind[s].get("info"), [s])["encoder"] for s in members),
                                       "readout": sum(_params(ind[s].get("info"), [s])["readout"] for s in members),
                                       "transition": sum(_params(ind[s].get("info"), [s])["transition"] for s in members),
                                       "total": sum(_params(ind[s].get("info"), [s])["total"] for s in members),
                                       "reported": all(_params(ind[s].get("info"), [s])["reported"] for s in members)},
                                      taus["tau_A"], a_key=key_a(cfg), c_key=c_key)
            loio = []
            for held in members:        # transfer to the other network: encoder-only adaptation vs from scratch on 25 % of its data
                ad = ev(m, "cross", f"{t}_adapt_{held.replace(':', '_')}", held)
                sc = ev(m, "loio", f"{t}_scratch_{held.replace(':', '_')}", held)
                if ad and sc and "error" not in ad and "error" not in sc:
                    loio.append(loio_comparison({"A": ad["res"]["A_B"], "C": ad["res"].get("C_heldout") or {}},
                                                {"A": sc["res"]["A_B"], "C": sc["res"].get("C_heldout") or {}}, a_key=key_a(cfg), c_key=c_key) | {"held": held})
            row["verdict"] = sharing_verdict(comp, loio)
            row["comparison"] = comp
            row["transfer"] = loio
        else:
            row["verdict"] = "untestable"
        j_rows[f"{a}+{b}"] = row
    result["J"] = j_rows
    result["wall_s"] = round(time.time() - t0, 1)
    dump(result, out_dir / "level_c_results.json")
    with open(log, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(f"| {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} | {args.attempt} | Level C DONE ({result['wall_s']:.0f} s) | {args.method} / "
                 f"{args.baseline} | results written | research/phase3/level_c/{args.attempt}/level_c_results.json |\n")
    print(json.dumps({s: {mm: (r.get(mm) or {}).get("verdict", {}).get("verdict") for mm in (args.method, args.baseline)} for s, r in result["systems"].items()},
                     indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
