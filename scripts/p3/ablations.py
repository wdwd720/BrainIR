"""Ablations of the LOCKED method (goal4 sections 84, 85 criterion 40). ORCHESTRATOR SIDE; runs after the method lock.

    uv run --project phase3 --no-sync python scripts/p3/ablations.py --suite final|heldout|dev [--switches all|a,b]
        [--systems all|s1,s2] [--seed 0] [--shared-variants full,sharing,sharing_test | none] [--full-from ROUND]
        [--backend modal|local] [--containers 200] [--parallel 5] [--eval-workers 6] [--round NAME] [--reason TEXT] [--dry-run]
    (development smoke runs before the lock: --allow-unlocked --method NAME --methods-dir DIR, dev suite only)

A variant is the locked method with ONE ablation switch removed, via the method's own mechanism: config {"ablate": [switch]},
switch names from the module's ABLATIONS table. The table is read with ast, never executed here. Each variant is fitted and
evaluated exactly like a Level B candidate:
- the frozen sandboxed fit and evaluation workers (brainir_state.suite_eval) or their Modal equivalents (scripts/p3/modal_tournament.py);
- the public simulation service with the lock's per-fit budget;
- the cached reference controls, the calibrated tolerances and harness.verdict;
- the profile S1-S8 of evaluate_cross over the FIXED list of the suite's compressible systems, with failures imputed as the worst
  value.
Outputs per variant:
- the profile, the verdict counts and the abstention summary (family L, over all systems, non-compressible controls included);
- PAIRED differences against the full locked method over the compressible systems: variant minus full per system, the median and
  mean difference with a system-bootstrap 95 % CI, and the fraction of systems where the variant is worse; failures are counted apart;
- the S6 exact-k rate difference and the verdict transitions (full -> variant).
S8 (sharing) needs shared and leave-one-implementation-out fits. They run only for --shared-variants (default: the full method and the
sharing switches), and S8 differences are reported only there.

Suite choice (pre-registered in PROTOCOL.md version 3 by the orchestrator; see research/phase3/POSTLOCK_RUNBOOK.md):
- 'final' gives unbiased component effects; it runs after the Level B confirmation, is logged as a hidden evaluation, and its
  outputs are ANSWER-BEARING;
- 'heldout' was used for selection, so its component effects are selection-biased;
- 'dev' is the developer's own data.
Every run on heldout / final is appended to research/phase3/HIDDEN_EVALUATIONS.md.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase3" / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "p3"))

DATA = ROOT / "data" / "phase3"
BENCH = ROOT / "benchmarks" / "state_discovery_v1"
LOCK = ROOT / "research" / "phase3" / "METHOD_LOCK.json"
LOCKED_DIR = ROOT / "phase3" / "src" / "brainir_state" / "methods"
RUN = Path(r"C:\Dev\BrainIR_p3run")
OUT = ROOT / "research" / "phase3" / "ablations"
TOURN_OUT = ROOT / "research" / "phase3" / "tournament"
S_KEYS = ("S1_A_over_full", "S2_C_heldout", "S3_D_micro_gain", "S4_E_ratio", "S5_K_r2_rff")


# ------------------------------------------------------------------------------------------------ inputs
def suite_spec(tier: str) -> dict:
    rec = json.loads((BENCH / "hidden" / "synthetic_suites.json").read_text(encoding="utf-8"))[tier]
    pub = DATA / "synthetic_dev" if tier == "dev" else DATA / "synthetic" / tier / "public"
    truth = DATA / "synthetic_truth" / "dev" if tier == "dev" else DATA / "synthetic" / tier / "truth"
    return {"public_dir": str(pub), "truth_dir": str(truth), "kind": "synthetic", "tier": tier, "suite_seed": int(rec["seed"])}


def read_ablations(methods_dir: Path, method: str) -> dict[str, str]:
    """The ABLATIONS table ({switch: what it removes}) of the module that registers `method`, read with ast (no code execution)."""
    files = [methods_dir / f"{method}.py"] + sorted(p for p in methods_dir.glob("*.py") if p.stem != method)
    for f in files:
        if not f.exists():
            continue
        tree = ast.parse(f.read_text(encoding="utf-8"))
        names = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        if method not in names and f.stem != method:
            continue
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(t, ast.Name) and t.id == "ABLATIONS" for t in targets) and node.value is not None:
                    return dict(ast.literal_eval(node.value))
    raise SystemExit(f"no ABLATIONS table found for {method} in {methods_dir}")


def lock_state(allow_unlocked: bool) -> dict | None:
    if not LOCK.exists():
        if not allow_unlocked:
            raise SystemExit("refusing: ablations of the locked method run only after research/phase3/METHOD_LOCK.json exists "
                             "(development smoke runs: --allow-unlocked --method NAME --methods-dir DIR on the dev suite)")
        return None
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    bad = [k for k, v in lock["source_sha256"].items() if not (ROOT / k).exists() or _sha(ROOT / k) != v]
    if bad:
        raise SystemExit(f"refusing: the locked method's sources changed since the lock: {bad[:5]}")
    return lock


def _sha(p: Path) -> str:
    b = p.read_bytes()
    if p.suffix in {".py", ".md", ".txt", ".json", ".jsonl", ".toml", ".lock"}:
        b = b.replace(b"\r\n", b"\n")
    return hashlib.sha256(b).hexdigest()


def set_tag(members) -> str:
    return hashlib.sha256("+".join(sorted(members)).encode()).hexdigest()[:8]


def fresh_code_tag() -> str:
    """The evaluator code tag recomputed from the files (suite_eval caches the first value per process)."""
    import brainir_state.suite_eval as SE
    SE._CODE_TAG = None
    return SE.evaluator_code_tag()


def limited_view(sd, sid: str, root: Path, every: int = 4) -> Path:
    """Fit view with 25 % of one system's training trajectories (leave-one-implementation-out adaptation data; the same rule as
    scripts/p3/tournament.py)."""
    import os
    import shutil
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


# ------------------------------------------------------------------------------------------------ statistics
def paired_vs_full(per_full: dict, per_var: dict, compressible: list[str], n_boot: int = 2000, seed: int = 0) -> dict:
    """Variant minus full per compressible system for S1-S5 (lower is better for S1-S4, higher for S5) and the S6 exact-k indicator;
    system-bootstrap 95 % CIs of the median and mean differences. Failures (non-finite on either side) are counted, not imputed."""
    from brainir_state.evaluate_cross import LOWER_IS_BETTER, system_values
    rng = np.random.default_rng(seed)
    vf = {s: system_values(per_full, s) for s in compressible}
    vv = {s: system_values(per_var, s) for s in compressible}
    out = {}
    for key in S_KEYS:
        pairs = [(vf[s][key], vv[s][key]) for s in compressible if vf[s][key] is not None and vv[s][key] is not None]
        fin = [(a, b) for a, b in pairs if np.isfinite(a) and np.isfinite(b)]
        d = np.array([b - a for a, b in fin], float)
        lower = key in LOWER_IS_BETTER
        rec = {"n": int(len(d)), "n_failed_either": int(len(pairs) - len(fin)),
               "n_failed_variant_only": int(sum(1 for a, b in pairs if np.isfinite(a) and not np.isfinite(b))),
               "direction": "lower is better" if lower else "higher is better"}
        if len(d):
            idx = rng.integers(0, len(d), (n_boot, len(d)))
            bm, bmean = np.median(d[idx], axis=1), d[idx].mean(axis=1)
            rec.update(median_diff=float(np.median(d)), median_ci95=[float(np.percentile(bm, 2.5)), float(np.percentile(bm, 97.5))],
                       mean_diff=float(d.mean()), mean_ci95=[float(np.percentile(bmean, 2.5)), float(np.percentile(bmean, 97.5))],
                       frac_variant_worse=float(np.mean(d > 0) if lower else np.mean(d < 0)),
                       frac_variant_better=float(np.mean(d < 0) if lower else np.mean(d > 0)))
        out[key] = rec
    ef = np.array([bool(vf[s]["S6_dim_ok"]) for s in compressible], float)
    ev = np.array([bool(vv[s]["S6_dim_ok"]) for s in compressible], float)
    if len(ef):
        d = ev - ef
        idx = rng.integers(0, len(d), (n_boot, len(d)))
        bm = d[idx].mean(axis=1)
        out["S6_exact_k_rate"] = {"full": float(ef.mean()), "variant": float(ev.mean()), "diff": float(d.mean()),
                                  "diff_ci95": [float(np.percentile(bm, 2.5)), float(np.percentile(bm, 97.5))], "n": int(len(d))}
    return out


def verdict_transitions(per_full: dict, per_var: dict, compressible: list[str]) -> dict:
    t: dict[str, int] = {}
    for s in compressible:
        a = ((per_full.get(s) or {}).get("verdict") or {}).get("verdict", "failed")
        b = ((per_var.get(s) or {}).get("verdict") or {}).get("verdict", "failed")
        t[f"{a} -> {b}"] = t.get(f"{a} -> {b}", 0) + 1
    return dict(sorted(t.items()))


# ------------------------------------------------------------------------------------------------ per-system records (mirrors tournament.py)
def system_record(e: dict | None, sd, s: str, taus: dict, tier: str) -> tuple[dict, dict]:
    """The per-system record and the abstention row of one evaluated model, computed exactly as scripts/p3/tournament.py computes
    them (keep the two in step when the evaluator changes)."""
    from brainir_state.evaluate_synth import abstention_row
    from brainir_state.harness import verdict
    from brainir_state.suite_eval import reference_results
    tr = sd.truth["systems"][s]
    if e is None or "error" in e:
        return {"error": (e or {}).get("error", "fit failed"), "trap": tr.get("trap")}, abstention_row(tr, None, None)
    k = e.get("k")
    refs = reference_results(sd, s, int(k) if k else 1, TOURN_OUT / "_refcache" / tier)
    ab = ((e.get("info") or {}).get("abstain") or {}).get(s)
    v = verdict(e["res"], refs, taus, len(sd.sysinfo(s)["observed"]), k, "synthetic", sd.cfg, abstain=ab)
    rec = {"k": k, "k_true": tr["k"], "trap": tr.get("trap"), "verdict": v, "K": e.get("K"), "K_dim": e.get("K_dim"),
           "A_over_full": (v["A"] / v["A_full"]) if v["A_full"] else None, "eval_wall_s": e.get("eval_wall_s"),
           "transition_params": ((e.get("info") or {}).get("n_params") or {}).get("transition")}
    return rec, abstention_row(tr, ab, v)


def sharing_rows(by: dict, variant: str, shared_sets: list, a_key: str, c_key: str) -> list[dict]:
    """I rows (groups and unrelated pairs) of one variant, as the tournament computes them."""
    from brainir_state.evaluate_cross import loio_comparison, sharing_comparison, sharing_verdict
    rows = []
    for kind, members in shared_sets:
        tag = set_tag(members)
        sh = {s: by.get((variant, s, f"shared:{kind}_{tag}")) for s in members}
        ind = {s: by.get((variant, s, "indep_s0")) for s in members}
        expected = "supported" if kind == "group" else "rejected"
        if any(v_ is None or "error" in v_ for v_ in list(sh.values()) + list(ind.values())):
            rows.append({"kind": kind, "members": members, "verdict": "untestable", "expected": expected, "correct": False,
                         "reason": "missing fit or evaluation"})
            continue
        shared_res = {s: {"A": sh[s]["res"]["A_B"], "C": sh[s]["res"].get("C_heldout") or {}} for s in members}
        indep_res = {s: {"A": ind[s]["res"]["A_B"], "C": ind[s]["res"].get("C_heldout") or {}} for s in members}
        npar = (sh[members[0]].get("info") or {}).get("n_params") or {}
        p_sh = {"encoder": 0, "readout": 0, "transition": 0, "total": 0, "reported": False}
        if npar:
            enc = sum(int((npar.get("encoder") or {}).get(s, 0)) for s in members)
            ro = sum(int((npar.get("readout") or {}).get(s, 0)) for s in members)
            trn = int(npar.get("transition", 0) or 0)
            p_sh = {"encoder": enc, "readout": ro, "transition": trn, "total": enc + ro + trn, "reported": True}
        p_in = {"encoder": 0, "readout": 0, "transition": 0, "total": 0, "reported": True}
        for s in members:
            np_s = (ind[s].get("info") or {}).get("n_params") or {}
            if not np_s:
                p_in["reported"] = False
                continue
            for kk in ("encoder", "readout"):
                p_in[kk] += int((np_s.get(kk) or {}).get(s, 0))
            p_in["transition"] += int(np_s.get("transition", 0) or 0)
        p_in["total"] = p_in["encoder"] + p_in["readout"] + p_in["transition"]
        comp = sharing_comparison(shared_res, indep_res, p_sh, p_in, a_key=a_key, c_key=c_key)
        loio = []
        for held in members:
            ad, sc = by.get((variant, held, f"loio:{tag}_adapt_{held}")), by.get((variant, held, f"loio:{tag}_scratch_{held}"))
            if ad and sc and "error" not in ad and "error" not in sc:
                loio.append(loio_comparison({"A": ad["res"]["A_B"], "C": ad["res"].get("C_heldout") or {}},
                                            {"A": sc["res"]["A_B"], "C": sc["res"].get("C_heldout") or {}}, a_key=a_key, c_key=c_key))
        vd = sharing_verdict(comp, loio)
        rows.append({"kind": kind, "members": members, "verdict": vd, "expected": expected, "correct": vd == expected,
                     "comparison": {k_: v_ for k_, v_ in comp.items() if k_ != "per_system"}, "loio": loio})
    return rows


# ------------------------------------------------------------------------------------------------ main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", choices=("final", "heldout", "dev"), required=True)
    ap.add_argument("--method", default="")
    ap.add_argument("--methods-dir", default="")
    ap.add_argument("--switches", default="all")
    ap.add_argument("--systems", default="all")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--shared-variants", default="full,sharing,sharing_test", help="variants that also get shared / LOIO fits (S8); 'none'")
    ap.add_argument("--full-from", default="", help="a Level B round (RUN/<round>/<method>/indep) whose seed-0 fits of the locked method are reused")
    ap.add_argument("--backend", choices=("modal", "local"), default="modal")
    ap.add_argument("--containers", type=int, default=200)
    ap.add_argument("--parallel", type=int, default=5)
    ap.add_argument("--eval-workers", type=int, default=6)
    ap.add_argument("--sim-budget", type=int, default=-1, help="simulation units per fit (-1: the lock's budget; 0 without a lock)")
    ap.add_argument("--timeout", type=float, default=-1)
    ap.add_argument("--round", default="")
    ap.add_argument("--reason", default="post-lock ablations of the locked method (goal4 sections 84-85)")
    ap.add_argument("--allow-unlocked", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    from brainir_state.evaluate_cross import profile_from_systems, rank_profiles
    from brainir_state.evaluate_synth import abstention_summary
    from brainir_state.harness import key_a
    from brainir_state.suite_eval import SuiteData, dump
    lock = lock_state(args.allow_unlocked)
    if lock is None and args.suite != "dev":
        raise SystemExit("refusing: without a method lock only the dev suite may be used")
    method = args.method or (lock or {}).get("method") or ""
    mdir = Path(args.methods_dir) if args.methods_dir else LOCKED_DIR
    if not method or not mdir.exists():
        raise SystemExit("need --method and --methods-dir (or a method lock)")
    table = read_ablations(mdir, method)
    switches = sorted(table) if args.switches == "all" else [s for s in args.switches.split(",") if s]
    unknown = [s for s in switches if s not in table]
    if unknown:
        raise SystemExit(f"unknown switches {unknown}; the method's table: {sorted(table)}")
    budgets = (lock or {}).get("budgets") or {}
    sim_budget = args.sim_budget if args.sim_budget >= 0 else int(budgets.get("sim_budget_units_per_fit", 0))
    timeout = args.timeout if args.timeout > 0 else float((budgets.get("fit_timeout_s") or {}).get("synthetic", 1800))
    spec = suite_spec(args.suite)
    sd = SuiteData(spec["public_dir"], kind="synthetic", truth_dir=spec["truth_dir"])
    truth = sd.truth
    sids = sd.systems if args.systems == "all" else [s for s in args.systems.split(",") if s]
    compressible = [s for s in sids if truth["systems"][s]["k"] != "none"]
    groups = [g for g in truth["suite"]["implementation_groups"].values() if set(g) <= set(sids)]
    pairs = [p for p in truth["suite"]["unrelated_pairs"] if set(p) <= set(sids)]
    shared_sets = [("group", g) for g in groups] + [("pair", p) for p in pairs]
    shared_variants = set() if args.shared_variants == "none" else {v for v in args.shared_variants.split(",") if v}
    variants = ["full"] + switches
    round_name = args.round or f"ablations_{args.suite}"
    run_dir = RUN / round_name
    out_dir = OUT / round_name
    hidden_material = args.suite in ("final", "heldout")
    plan = {"round": round_name, "suite": args.suite, "method": method, "methods_dir": str(mdir), "switches": switches,
            "table": {s: table[s] for s in switches}, "systems": sids, "n_compressible": len(compressible), "seed": args.seed,
            "shared_variants": sorted(shared_variants), "n_shared_sets": len(shared_sets), "sim_budget": sim_budget, "timeout_s": timeout,
            "backend": args.backend, "locked": lock is not None, "lock_commit": (lock or {}).get("commit_at_lock"),
            "hidden_material": hidden_material}
    n_fit = len(variants) * len(sids) + sum(len(shared_sets) * 1 + sum(2 * len(m) for _, m in shared_sets) for v in variants
                                            if v in shared_variants)
    plan["n_fits_planned"] = n_fit
    if args.dry_run:
        print(json.dumps(plan, indent=1))
        return 0
    run_dir.mkdir(parents=True, exist_ok=True)
    tag0 = fresh_code_tag()          # the evaluator the Modal containers mount; checked again before the verdicts
    view = sd.fit_view(run_dir / f"fitview_{args.suite}")
    if hidden_material:
        from counterexamples import log_hidden
        log_hidden(round_name, f"ablations START ({args.suite} suite; {len(variants)} variants x {len(sids)} systems)", method, args.reason,
                   f"research/phase3/ablations/{round_name}/")
    t0 = time.time()
    # ---- fit jobs
    sim_q = run_dir / "sim" / "simq" if sim_budget > 0 else None
    jobs, sim_proc = [], None
    for v in variants:
        cfg = None if v == "full" else {"ablate": [v]}
        vroot = run_dir / v
        for s in sids:
            out = vroot / "indep" / f"{s}_s{args.seed}.pkl"
            if v == "full" and args.full_from:
                src = RUN / args.full_from / method / "indep" / f"{s}_s{args.seed}.pkl"
                if src.exists() and src.with_suffix(".json").exists() and not out.exists():
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_bytes(src.read_bytes())
                    out.with_suffix(".json").write_bytes(src.with_suffix(".json").read_bytes())
            jobs.append(dict(method_dir=mdir, method=method, datasets=[view], systems=[s], out=out, seed=args.seed, config=cfg,
                             timeout_s=timeout, sim_queue=sim_q))
        if v in shared_variants:
            for kind, members in shared_sets:
                tag = set_tag(members)
                scfg = {"sharing": "shared", **({"ablate": [v]} if v != "full" else {})}
                jobs.append(dict(method_dir=mdir, method=method, datasets=[view], systems=list(members), out=vroot / "shared" / f"{kind}_{tag}.pkl",
                                 config=scfg, seed=args.seed, timeout_s=timeout * 2, sim_queue=sim_q))
                for held in members:
                    others = [x for x in members if x != held]
                    jobs.append(dict(method_dir=mdir, method=method, datasets=[view], systems=others,
                                     out=vroot / "loio" / f"{tag}_without_{held}.pkl", config=scfg, seed=args.seed, timeout_s=timeout * 2,
                                     sim_queue=sim_q))
    evaluate_models = run_fits = None
    app_ctx = None
    if args.backend == "modal":
        import modal_tournament as MT
        app = MT._open_app(args.containers)
        MT._STATE.update(tier=args.suite, sim_budget=sim_budget)
        run_fits, evaluate_models = MT.modal_run_fits, MT.modal_evaluate_models
        app_ctx = (MT._output(), app.run())
        for c in app_ctx:
            c.__enter__()
    else:
        from brainir_state.suite_eval import evaluate_models as _ev
        from brainir_state.suite_eval import run_fits as _rf
        run_fits, evaluate_models = (lambda j: _rf(j, parallel=args.parallel)), (lambda j: _ev(j, workers=args.eval_workers))
        if sim_budget > 0:
            import subprocess
            sysfile = BENCH / "hidden" / f"simservice_systems_{args.suite}.json"
            if not sysfile.exists():
                subprocess.run([sys.executable, str(ROOT / "scripts" / "p3" / "simservice_systems.py"), "--suite", args.suite], check=True)
            sim_proc = subprocess.Popen([sys.executable, "-m", "brainir_state.simservice", "--clean", str(run_dir / "sim"), "--systems",
                                         str(sysfile), "--bundle", str(ROOT / "benchmarks" / "dng100" / "public_blind"), "--store",
                                         str(DATA / "store"), "--budget", str(sim_budget), "--workers", "4"],
                                        stdout=open(run_dir / "simservice.log", "a"), stderr=subprocess.STDOUT)
    try:
        fit_recs = run_fits(jobs)
        loio_jobs = []
        for v in variants:
            if v not in shared_variants:
                continue
            scfg = {"ablate": [v]} if v != "full" else None
            vroot = run_dir / v
            for _kind, members in shared_sets:
                tag = set_tag(members)
                for held in members:
                    base = vroot / "loio" / f"{tag}_without_{held}.pkl"
                    lv = limited_view(sd, held, run_dir / f"limited_{args.suite}_{held}")
                    if base.exists():
                        loio_jobs.append(dict(method_dir=mdir, method=method, datasets=[lv], systems=[held],
                                              out=vroot / "loio" / f"{tag}_adapt_{held}.pkl", adapt_from=base, config=scfg, seed=args.seed,
                                              timeout_s=timeout, sim_queue=sim_q))
                    loio_jobs.append(dict(method_dir=mdir, method=method, datasets=[lv], systems=[held],
                                          out=vroot / "loio" / f"{tag}_scratch_{held}.pkl", config=scfg, seed=args.seed, timeout_s=timeout,
                                          sim_queue=sim_q))
        if loio_jobs:
            fit_recs += run_fits(loio_jobs)
        jobs += loio_jobs
        # ---- evaluations
        ev_jobs, ev_keys = [], []
        for v in variants:
            vroot = run_dir / v
            for s in sids:
                p = vroot / "indep" / f"{s}_s{args.seed}.pkl"
                if p.exists():
                    ev_jobs.append({"suite": spec, "sid": s, "method_dir": str(mdir), "model_path": str(p), "lift": False})
                    ev_keys.append((v, s, "indep_s0"))
            if v in shared_variants:
                for p in sorted((vroot / "shared").glob("*.pkl")) + sorted((vroot / "loio").glob("*_adapt_*.pkl")) + \
                        sorted((vroot / "loio").glob("*_scratch_*.pkl")):
                    side = json.loads(p.with_suffix(".json").read_text(encoding="utf-8"))
                    for s in side["systems"]:
                        ev_jobs.append({"suite": spec, "sid": s, "method_dir": str(mdir), "model_path": str(p), "lift": False})
                        ev_keys.append((v, s, p.parent.name + ":" + p.stem))
        evs = evaluate_models(ev_jobs)
    finally:
        if app_ctx is not None:
            for c in reversed(app_ctx):
                c.__exit__(None, None, None)
        if sim_proc is not None:
            sim_proc.terminate()
    by = {key: e for key, e in zip(ev_keys, evs)}
    if fresh_code_tag() != tag0:
        raise SystemExit("refusing: the evaluator changed while the run was in flight (evaluator code tag differs); the evaluations and "
                         "the verdicts would mix versions. Freeze the evaluator and rerun (fits are reused from the run directory).")
    taus = json.loads((BENCH / "public" / "tolerances.json").read_text(encoding="utf-8"))
    ca, cc = key_a(sd.cfg), f"C_w{int(round(sd.cfg.primary_c_window_s * 1000))}ms"
    results = {}
    for v in variants:
        per_sys, l_rows = {}, []
        for s in sids:
            rec, lrow = system_record(by.get((v, s, "indep_s0")), sd, s, taus, args.suite)
            per_sys[s], _ = rec, l_rows.append(lrow)
        i_rows = sharing_rows(by, v, shared_sets, ca, cc) if v in shared_variants else []
        lsum = abstention_summary(l_rows)
        prof = profile_from_systems(per_sys, compressible, lsum, i_rows)
        counts: dict[str, int] = {}
        for s in compressible:
            vv = (per_sys[s].get("verdict") or {}).get("verdict", "failed")
            counts[vv] = counts.get(vv, 0) + 1
        n_fit_fail = sum(1 for j, r in zip(jobs, fit_recs) if "error" in r and Path(j["out"]).parts[-3] == v)
        n_eval_fail = sum(1 for key, e in by.items() if key[0] == v and "error" in e)
        results[v] = {"variant": v, "removes": table.get(v, "(the full locked method)"), "profile": prof, "verdict_counts_compressible": counts,
                      "abstention": lsum, "n_fit_failures": n_fit_fail, "n_evaluation_failures": n_eval_fail, "per_system": per_sys,
                      "abstention_rows": l_rows, "I": i_rows}
        dump(results[v], out_dir / f"{v}.json")
    full = results["full"]
    summary = {"plan": plan, "wall_s": round(time.time() - t0, 1), "variants": {}}
    for v in variants:
        r = results[v]
        row = {"removes": r["removes"], "profile": r["profile"], "verdict_counts_compressible": r["verdict_counts_compressible"],
               "abstention": r["abstention"], "failures": {"fits": r["n_fit_failures"], "evaluations": r["n_evaluation_failures"]}}
        if v != "full":
            row["paired_vs_full"] = paired_vs_full(full["per_system"], r["per_system"], compressible)
            row["verdict_transitions"] = verdict_transitions(full["per_system"], r["per_system"], compressible)
            if v in shared_variants and "full" in shared_variants:
                row["S8_diff"] = (r["profile"].get("S8_sharing_correct", float("nan")) - full["profile"].get("S8_sharing_correct", float("nan")))
        summary["variants"][v] = row
    rk = rank_profiles({v: results[v]["profile"] for v in variants})
    summary["mean_rank_descriptive"] = rk["mean_rank"]
    if args.backend == "modal":
        import modal_tournament as MT
        summary["modal"] = {"calls": MT._STATE["costs"], "usd_approx_total": round(sum(c["usd_approx"] for c in MT._STATE["costs"]), 2)}
        dump(summary["modal"], out_dir / "modal_costs.json")
    dump(summary, out_dir / "SUMMARY.json")
    (out_dir / "SUMMARY.md").write_text(summary_md(summary), encoding="utf-8", newline="\n")
    print(json.dumps({"round": round_name, "wall_s": summary["wall_s"], "variants": len(variants),
                      "usd": (summary.get("modal") or {}).get("usd_approx_total")}))
    return 0


def summary_md(summary: dict) -> str:
    def f(x, nd=3):
        try:
            return f"{float(x):.{nd}g}"
        except (TypeError, ValueError):
            return "-"
    p = summary["plan"]
    lines = [f"# Ablations of {p['method']} ({p['suite']} suite, round {p['round']})", "",
             f"- {len(p['switches'])} switches x {len(p['systems'])} systems ({p['n_compressible']} compressible), seed {p['seed']}; "
             f"locked: {p['locked']}; hidden material: {p['hidden_material']}; backend {p['backend']}",
             "- Paired differences = variant minus full per compressible system (median [system-bootstrap 95 % CI]); S1-S4 lower is better, "
             "S5 higher is better; S6 = exact-k rate difference.", "",
             "| variant | removes | S1 | S2 | S3 | S4 | S5 | S6 | verdicts (compressible) | failures |", "|---|---|---|---|---|---|---|---|---|---|"]
    for v, row in summary["variants"].items():
        if v == "full":
            pr = row["profile"]
            cells = [f(pr.get(k)) for k in S_KEYS] + [f(pr.get("S6_dim_rate"))]
        else:
            pv = row["paired_vs_full"]
            cells = [(f"{f(pv[k].get('median_diff'))} [{f((pv[k].get('median_ci95') or [None])[0])}, {f((pv[k].get('median_ci95') or [None, None])[1])}]"
                      if "median_diff" in pv[k] else "-") for k in S_KEYS]
            s6 = pv.get("S6_exact_k_rate") or {}
            cells.append(f"{f(s6.get('diff'))} [{f((s6.get('diff_ci95') or [None])[0])}, {f((s6.get('diff_ci95') or [None, None])[1])}]" if s6 else "-")
        vc = ", ".join(f"{k}: {n}" for k, n in sorted(row["verdict_counts_compressible"].items()))
        lines.append(f"| {v} | {row['removes'][:60]} | " + " | ".join(cells) + f" | {vc} | {row['failures']['fits']}+{row['failures']['evaluations']} |")
    lines += ["", "The full method's row shows its profile values; the other rows show paired differences against it.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
