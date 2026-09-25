"""state_discovery_v1 Level C: the real hidden evaluation of the LOCKED method (orchestrator; PROTOCOL.md sections 1, 7, 8, 10).

    uv run --project phase3 python scripts/p3/level_c.py --method-dir <locked methods copy> --method <name> --baseline <name>
                                                       [--parallel 4] [--eval-workers 4] [--attempt 01] [--resample-arm 5]
                                                       [--decision-round r3]
    (on Modal: scripts/p3/modal_tournament.py level-c <the same arguments>)

Refuses to run without research/phase3/METHOD_LOCK.json and without the hidden real data (scripts/p3/generate_real_hidden.py, run
after the lock). Every run is appended to research/phase3/HIDDEN_EVALUATIONS.md. Steps:
1. fits in the sandbox on the PUBLIC real data (train + val): the locked method on every system with seeds 0-4 (G), the strongest
   baseline with seed 0; shared fits per network (I) with leave-one-implementation-out adaptation; cross-connectome models on the
   full systems (J): (1) independent, (2) common k with independent dynamics, (3) shared dynamics, (4) partially shared where
   supported, for net1+net2 (independent reconstructions) and, reported apart, net1+net3 (same reconstruction); with
   --resample-arm N, N more fits of the locked method (seed 0) on seeded half-samples of each system's training trajectories
   (validation kept): a data-resampling arm of G (review A M3; descriptive);
2. evaluates every model on the hidden sets (families A-E, R, P, H; lifting through the real engine), the references per system;
3. verdicts (PROTOCOL section 7), sharing verdicts, and the primary paired comparisons of the locked method with the strongest
   baseline (families A, C, D, E per full system and K on the synthetic final suite; Holm across them);
4. writes research/phase3/level_c/<attempt>/ (ANSWER-BEARING).

Version 3 (pre-lock reviews A-D):
- K (the 13th primary test) compares min(R^2 true <- model, R^2 model <- true) (random features), clipped to [-1, 1], a failure = -1;
- every C row carries the method's own held-out C and its upper CI against the no-effect value 1; a non-inferiority pass on C may be
  worded "interventional" only when that upper CI is below 1 (c_below_no_effect; review C M4);
- every row carries its lineage: the RECONSTRUCTION of its network (derived from the internal network ids: net1 and net3 come from
  one reconstruction) and, for mechanism systems, the MECHANISM FAMILY (keep-only mechanisms of one network that share neurons are one
  family). No claim may count systems of one reconstruction as independent confirmations, or overlapping mechanisms as separate
  mechanisms (review D M4);
- the real I-sharing rows (full system + mechanisms of one network) are DESCRIPTIVE: they are in neither Holm family;
- with --decision-round, the baseline must be the comparator fixed by that round's decision (merge_rounds.py --decide).
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
SIM_BUDGET = 250          # simulation budget units per fit: the same public access as during development
REAL_VIEW_NAME = "real"   # the staged public fit view (run_dir / "fitview_real"; on Modal /fitvol/views/real)


def spec() -> dict:
    return {"public_dir": str(DATA / "real_public"), "hidden_dir": str(DATA / "real_hidden"), "micro_dir": str(DATA / "real_hidden"),
            "kind": "real", "systems_internal": str(BENCH / "hidden" / "systems_internal.json"),
            "bundle": str(ROOT / "benchmarks" / "dng100" / "public_blind")}


def _write_view(sd: SuiteData, sid: str, rows: list[dict], root: Path, splits: list[str]) -> Path:
    """A fit view with the given rows of one system (hard links), marked as a SUBVIEW of the staged public fit view (SUBVIEW.json: the
    Modal backend links the same rows from /fitvol/views/real instead of shipping trajectory data)."""
    import os
    (root / "traj").mkdir(parents=True, exist_ok=True)
    for r in rows:
        src, dst = sd.public_dir / "traj" / f"{r['key']}.npz", root / "traj" / f"{r['key']}.npz"
        if not dst.exists():
            try:
                os.link(src, dst)
            except OSError:
                shutil.copy2(src, dst)
    man = dict(sd.pub.manifest)
    man["systems"] = {sid: sd.pub.systems[sid]}
    man["splits"] = list(splits)
    (root / "index.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8", newline="\n")
    (root / "SUBVIEW.json").write_text(json.dumps({"base": REAL_VIEW_NAME, "keys": [r["key"] for r in rows]}) + "\n", encoding="utf-8",
                                       newline="\n")
    (root / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return root


def limited_view(sd: SuiteData, sid: str, root: Path, every: int = 4) -> Path:
    """25 % of one system's training trajectories (leave-one-implementation-out and transfer adaptation data)."""
    if (root / "manifest.json").exists():
        return root
    rows = [r for r in sd.pub.select(system_id=sid) if r["split"] == "train"][::every]
    return _write_view(sd, sid, rows, root, ["train"])


def half_view(sd: SuiteData, sid: str, root: Path, h: int) -> Path:
    """Data-resampling arm of G (review A M3): a seeded half of one system's training trajectories plus all its validation trajectories.
    The half-sample depends only on (system, h), never on results."""
    if (root / "manifest.json").exists():
        return root
    train = sorted((r for r in sd.pub.select(system_id=sid) if r["split"] == "train"), key=lambda r: r["key"])
    val = sorted((r for r in sd.pub.select(system_id=sid) if r["split"] == "val"), key=lambda r: r["key"])
    seed = int(hashlib.sha256(f"half:{sid}:{h}".encode()).hexdigest()[:8], 16)
    pick = np.sort(np.random.default_rng(seed).permutation(len(train))[: len(train) // 2])
    return _write_view(sd, sid, [train[i] for i in pick] + val, root, ["train", "val"])


def start_simservice(run_dir: Path, sp: dict, real_defs: dict) -> tuple[Path, object]:
    """The public simulation service for the fits (the same policy as during development; SIM_BUDGET units per fit). The Modal backend
    replaces this with a per-fit simulator in the fit container."""
    import subprocess
    sysfile = run_dir / "simservice_systems_real.json"
    sysfile.write_text(json.dumps({s_: dict(d, cost=10 if d["mode"] == "full" else 3) for s_, d in real_defs.items()}), encoding="utf-8")
    simq = run_dir / "sim" / "simq"
    proc = subprocess.Popen([sys.executable, "-m", "brainir_state.simservice", "--clean", str(run_dir / "sim"), "--systems", str(sysfile),
                             "--bundle", sp["bundle"], "--store", str(DATA / "store"), "--budget", str(SIM_BUDGET), "--workers", "4"],
                            stdout=open(run_dir / "simservice.log", "a"), stderr=subprocess.STDOUT)
    return simq, proc


# ---------------------------------------------------------------- lineage (version 3; review D M4)
def reconstruction_of(network_id: str) -> str:
    """The connectome reconstruction behind an internal network id ('<dataset>_v<version>' -> '<dataset>'): networks built from different
    versions of one dataset share a reconstruction."""
    import re
    m = re.match(r"^(.*?)_v\d", str(network_id))
    return m.group(1) if m else str(network_id)


def lineage(public_systems: dict, internal: dict) -> dict:
    """{system_id: {"network", "reconstruction", "mechanism_family"}}. Mechanism systems of one network whose member sets overlap form
    one mechanism family (connected components of the overlap graph); full systems have none."""
    out = {}
    by_net: dict[str, list[str]] = {}
    for sid, info in public_systems.items():
        net_int = (internal.get(sid) or {}).get("network", info.get("network"))
        out[sid] = {"network": info.get("network"), "reconstruction": reconstruction_of(net_int), "mechanism_family": None}
        if info.get("mode") == "mech":
            by_net.setdefault(info.get("network"), []).append(sid)
    for net, mechs in by_net.items():
        members = {s: set(int(n) for n in (public_systems[s].get("members") or public_systems[s].get("observed") or [])) for s in mechs}
        parent = {s: s for s in mechs}

        def find(s):
            while parent[s] != s:
                parent[s] = parent[parent[s]]
                s = parent[s]
            return s
        for i, a in enumerate(sorted(mechs)):
            for b in sorted(mechs)[i + 1:]:
                if members[a] & members[b]:
                    parent[find(b)] = find(a)
        comps: dict[str, list[str]] = {}
        for s in mechs:
            comps.setdefault(find(s), []).append(s)
        for comp in comps.values():
            fam = f"{net}:mechfam:{hashlib.sha256('+'.join(sorted(comp)).encode()).hexdigest()[:8]}"
            for s in comp:
                out[s]["mechanism_family"] = fam
                out[s]["mechanism_family_size"] = len(comp)
    return out


LINEAGE_RULES = ("Systems of one reconstruction (the same connectome dataset, see each row's 'reconstruction') are not independent "
                 "confirmations; overlapping keep-only mechanisms of one network are one mechanism family, not separate mechanisms. "
                 "Counts of systems with a property are reported per reconstruction and per mechanism family.")


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


# ---------------------------------------------------------------- the pre-registered primary family (PROTOCOL.md section 8, version 2)
# one-sided NON-INFERIORITY of the locked method against the strongest baseline; diff = method - baseline on a lower-is-better scale
NI_MARGIN = {"A": ("relative", 0.2), "C": ("relative_min", 0.2, 0.05), "D": ("absolute", 0.05), "E": ("relative", 0.2), "K": ("absolute", 0.05)}
N_BOOT = 2000


def _margin(fam: str, base_value: float) -> float:
    m = NI_MARGIN[fam]
    if m[0] == "absolute":
        return m[1]
    if not np.isfinite(base_value):
        return float("nan")
    return max(m[2], m[1] * base_value) if m[0] == "relative_min" else m[1] * base_value


def _test_row(point: float, boot: np.ndarray, margin: float, extra: dict | None = None) -> dict:
    from brainir_state.evaluate_cross import _boot_p, _ci, ni_p
    ok = np.isfinite(point) and len(boot) > 0 and np.isfinite(margin)
    return {"diff": point, "ci95": _ci(boot) if len(boot) else [float("nan")] * 2, "margin": margin,
            "p_noninferiority": ni_p(boot, margin) if ok else 1.0, "p_two_sided": _boot_p(boot, point) if ok else 1.0,
            "computable": bool(ok), **(extra or {})}


C_CLAIM_YES = "interventional: held-out intervention effects predicted better than no effect (own C upper CI < 1)"
C_CLAIM_NO = ("not an interventional claim: the method's own held-out C does not have an upper CI below the no-effect value 1, so "
              "non-inferiority to the baseline on C carries no interventional content")


def c_flag(c_res: dict | None) -> dict:
    """The method's own held-out C (ratio, 95 % CI) against the no-effect value 1 (version 3; review C M4). A C test row may be worded
    "interventional" only when c_below_no_effect is True."""
    c_res = c_res or {}
    ci = c_res.get("ci95") or [float("nan"), float("nan")]
    try:
        up = float(ci[1])
    except (TypeError, ValueError, IndexError):
        up = float("nan")
    below = bool(np.isfinite(up) and up < 1.0)
    return {"method_C": c_res.get("ratio"), "method_C_ci95": ci, "method_C_upper": up, "c_below_no_effect": below,
            "claim": C_CLAIM_YES if below else C_CLAIM_NO}


def k_min_value(kres: dict | None) -> float:
    """K of one system (version 3; review C M3): min(R^2 true <- model, R^2 model <- true), random-feature regressors, clipped to
    [-1, 1]; a missing or non-finite direction counts as a failure (-1)."""
    kres = kres or {}
    vals = []
    for key in ("r2_true_from_model_rff", "r2_model_from_true_rff"):
        try:
            v = float(kres.get(key))
        except (TypeError, ValueError):
            return -1.0
        if not np.isfinite(v):
            return -1.0
        vals.append(float(np.clip(v, -1.0, 1.0)))
    return float(min(vals))


def primary_tests(ra: dict | None, rb: dict | None, cfg) -> dict:
    """A, C, D, E of one full system: the method (ra) against the baseline (rb). A comparison that cannot be computed (missing result,
    untestable E, no common units) has p = 1 and stays in the family."""
    from brainir_state.evaluate_cross import paired_diff_boot, paired_e_diff_boot, paired_gain_diff_boot, paired_ratio_diff_boot
    out = {}
    if ra is None or rb is None:
        return {f: _test_row(float("nan"), np.zeros(0), float("nan"), {"note": "missing fit or evaluation"}) for f in ("A", "C", "D", "E")}
    ka, kc = key_a(cfg), f"C_w{int(round(cfg.primary_c_window_s * 1000))}ms"
    pa, ba, _ = paired_diff_boot((ra["A_B"].get("_units") or {}).get(ka, {}), (rb["A_B"].get("_units") or {}).get(ka, {}), N_BOOT)
    out["A"] = _test_row(pa, ba, _margin("A", (rb["A_B"].get(ka) or {}).get("mean", float("nan"))))
    pc, bc, _, ex = paired_ratio_diff_boot(((ra.get("C_heldout") or {}).get("_units") or {}).get(kc, {}),
                                           ((rb.get("C_heldout") or {}).get("_units") or {}).get(kc, {}), N_BOOT)
    out["C"] = _test_row(pc, bc, _margin("C", ex.get("ratio_b", float("nan"))), {**ex, **c_flag((ra.get("C_heldout") or {}).get(key_c(cfg)))})
    ua = (((ra.get("D") or {}).get(key_d(cfg)) or {}).get("_units")) or {}
    ub = (((rb.get("D") or {}).get(key_d(cfg)) or {}).get("_units")) or {}
    pd_, bd = paired_gain_diff_boot(ua, ub, N_BOOT)
    out["D"] = _test_row(pd_, bd, _margin("D", float("nan")))
    ea, eb = ra.get("E") or {}, rb.get("E") or {}
    if ea.get("E_testable") is False or eb.get("E_testable") is False:
        out["E"] = _test_row(float("nan"), np.zeros(0), float("nan"), {"note": "E untestable for the method or the baseline"})
    else:
        pe, be = paired_e_diff_boot(ea.get("_units") or {}, eb.get("_units") or {}, cfg.micro_match_quantile, N_BOOT)
        out["E"] = _test_row(pe, be, _margin("E", eb.get("E_ratio_latent_to_random", float("nan"))))
    return out


def k_test_values(rm: dict, rb: dict, compressible: list[str] | None = None) -> np.ndarray:
    """Per-system K differences baseline - method (lower is better for the method); K = k_min_value (version 3). The systems are the
    round's FIXED list of compressible systems when given (a failed fit or evaluation of either model counts as -1 for that model), else
    the systems whose record states a compressible true k."""
    if compressible is None:
        compressible = [s for s in sorted(set(rm) | set(rb))
                        if (rm.get(s) or {}).get("k_true", (rb.get(s) or {}).get("k_true")) not in (None, "none")]
    return np.array([k_min_value((rb.get(s) or {}).get("K")) - k_min_value((rm.get(s) or {}).get("K")) for s in compressible], float)


def k_test_final(final_round: str, method: str, baseline: str) -> dict:
    """K (latent recovery; version 3: min of the two cross-fitted random-feature R^2 directions) on the synthetic FINAL suite, paired by
    system instance: diff = baseline - method (lower is better for the method), non-inferiority margin 0.05, bootstrap over systems."""
    base = ROOT / "research" / "phase3" / "tournament" / final_round
    try:
        jm = json.loads((base / f"{method}.json").read_text(encoding="utf-8"))
        jb = json.loads((base / f"{baseline}.json").read_text(encoding="utf-8"))
        rm, rb = jm["per_system"], jb["per_system"]
    except (OSError, KeyError, ValueError):
        return _test_row(float("nan"), np.zeros(0), float("nan"), {"note": f"final round {final_round!r} results missing"})
    comp = (jm.get("design") or {}).get("compressible") or (jb.get("design") or {}).get("compressible")
    d = k_test_values(rm, rb, list(comp) if comp else None)
    if len(d) == 0:
        return _test_row(float("nan"), np.zeros(0), float("nan"), {"note": "no common systems"})
    rng = np.random.default_rng(0)
    boot = np.array([d[rng.integers(0, len(d), len(d))].mean() for _ in range(N_BOOT)])
    return _test_row(float(d.mean()), boot, _margin("K", float("nan")),
                     {"n_systems": int(len(d)), "note": "K = min(R^2 true <- model, R^2 model <- true), random features, clipped to [-1, 1]; "
                                                        "a failure = -1", "system": "final_suite", "reconstruction": "synthetic",
                      "mechanism_family": None})


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
    ap.add_argument("--final-round", default="final", help="the Level B confirmation round (tournament --suite final) holding K")
    ap.add_argument("--resample-arm", type=int, default=0,
                    help="N fits of the locked method on seeded half-samples of each system's training data (G data arm; descriptive)")
    ap.add_argument("--decision-round", default=None,
                    help="a round with ROUND_DECISION.json (merge_rounds.py --decide): the baseline must be its comparator")
    args = ap.parse_args(argv)
    if not (ROOT / "research" / "phase3" / "METHOD_LOCK.json").exists():
        raise SystemExit("refusing: Level C runs only after research/phase3/METHOD_LOCK.json exists")
    if not (DATA / "real_hidden" / "manifest.json").exists():
        raise SystemExit("refusing: generate the hidden real data first (scripts/p3/generate_real_hidden.py)")
    if args.decision_round:
        dec = json.loads((ROOT / "research" / "phase3" / "tournament" / args.decision_round / "ROUND_DECISION.json").read_text(encoding="utf-8"))
        comp = (dec.get("comparator") or {}).get("chosen") or dec.get("comparator_baseline")
        if comp != args.baseline:
            raise SystemExit(f"refusing: the baseline {args.baseline!r} is not the comparator {comp!r} fixed by round {args.decision_round}")
    limit_threads(4)
    t0 = time.time()
    sp = spec()
    sd = SuiteData(sp["public_dir"], kind="real", hidden_dir=sp["hidden_dir"], micro_dir=sp["micro_dir"])
    run_dir = RUN / f"level_c_{args.attempt}"
    run_dir.mkdir(parents=True, exist_ok=True)
    mdir = Path(args.method_dir).resolve()
    view = sd.fit_view(run_dir / f"fitview_{REAL_VIEW_NAME}")
    # the fits get the same public simulation access as during development (public policy; SIM_BUDGET units per fit)
    real_defs = json.loads((BENCH / "hidden" / "systems_internal.json").read_text(encoding="utf-8"))
    simq, sim_proc = start_simservice(run_dir, sp, real_defs)
    taus = json.loads((BENCH / "public" / "tolerances.json").read_text(encoding="utf-8"))
    sids = sd.systems
    nets = sorted({sd.sysinfo(s)["network"] for s in sids})
    by_net = {n: [s for s in sids if sd.sysinfo(s)["network"] == n] for n in nets}
    full = {n: next(s for s in by_net[n] if sd.sysinfo(s)["mode"] == "full") for n in nets}
    lin = lineage({s: sd.sysinfo(s) for s in sids}, real_defs)
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
    # data-resampling arm of G (review A M3): the locked method, seed 0, on seeded half-samples of each system's training trajectories
    for s in sids:
        for h in range(max(0, args.resample_arm)):
            hv = half_view(sd, s, run_dir / f"half_{s.replace(':', '_')}_h{h}", h)
            jobs.append(dict(method_dir=mdir, method=m, datasets=[hv], systems=[s], out=run_dir / m / "half" / f"{s.replace(':', '_')}_h{h}.pkl",
                             seed=0, timeout_s=args.timeout, sim_queue=simq))
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
    if sim_proc is not None:
        sim_proc.terminate()
    # ---------------------------------------------------------------- evaluation
    ev_jobs = []
    for mm in (args.method, args.baseline):
        for p in sorted((run_dir / mm).rglob("*.pkl")):
            if p.parent.name == "half":          # the resampling arm enters G only (reproducibility_jobs below)
                continue
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
              [r for r in recs if "error" in r][:50], "benchmark_version": 3, "lineage": lin, "lineage_rules": LINEAGE_RULES,
              "decision_round": args.decision_round}
    pvals, comps, sup = {}, {}, {}
    for s in sids:
        info = sd.sysinfo(s)
        row = {"mode": info["mode"], "network": info["network"], "n_observed": len(info["observed"]), **lin[s]}
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
        # primary paired comparisons (full systems): locked method vs strongest baseline (PROTOCOL.md section 8, version 2)
        if info["mode"] == "full":
            em, eb = ev(args.method, "indep", f"{s.replace(':', '_')}_s0", s), ev(args.baseline, "indep", f"{s.replace(':', '_')}_s0", s)
            ok = bool(em and eb and "error" not in em and "error" not in eb)
            comps[s] = primary_tests(em["res"] if ok else None, eb["res"] if ok else None, cfg)
            for fam, r in comps[s].items():
                r.update({"system": s, "family": fam, **lin[s]})
                pvals[f"{s}:{fam}"] = r["p_noninferiority"]
                sup[f"{s}:{fam}"] = r["p_two_sided"]
        result["systems"][s] = row
    comps["final_suite:K"] = k_test_final(args.final_round, args.method, args.baseline)
    pvals["final_suite:K"] = comps["final_suite:K"]["p_noninferiority"]
    sup["final_suite:K"] = comps["final_suite:K"]["p_two_sided"]
    result["primary_comparisons"] = comps
    result["primary_family"] = sorted(pvals)
    result["primary_holm"] = holm(pvals)
    result["secondary_superiority_holm"] = holm(sup)
    # ---------------------------------------------------------------- G (5 seeds of the locked method)
    g_jobs = []
    for s in sids:
        paths = [run_dir / args.method / "indep" / f"{s.replace(':', '_')}_s{seed}.pkl" for seed in range(5)]
        if all(p.exists() for p in paths):
            g_jobs.append({"suite": sp, "sid": s, "method_dir": str(mdir), "model_paths": [str(p) for p in paths]})
    result["G"] = {r["sid"]: r for r in reproducibility_jobs(g_jobs, workers=args.eval_workers)} if g_jobs else {}
    # data-resampling arm (half-samples of the training data, seed 0): r2_min_mean, k agreement, prediction disagreement (descriptive)
    h_jobs = []
    for s in sids:
        paths = [run_dir / args.method / "half" / f"{s.replace(':', '_')}_h{h}.pkl" for h in range(max(0, args.resample_arm))]
        if len(paths) >= 2 and all(p.exists() for p in paths):
            h_jobs.append({"suite": sp, "sid": s, "method_dir": str(mdir), "model_paths": [str(p) for p in paths]})
    g_half = {r["sid"]: r for r in reproducibility_jobs(h_jobs, workers=args.eval_workers)} if h_jobs else {}
    result["G_resample"] = {"n_half_samples": int(args.resample_arm), "role": "descriptive (review A M3)",
                            "per_system": {s: {**lin[s], **({k_: (r.get("G") or {}).get(k_) for k_ in
                                                             ("k", "k_agree", "r2_min_mean", "prediction_disagreement_nmse", "cca_mean")}
                                                            if "G" in r else {"error": r.get("error")})}
                                           for s, r in g_half.items()},
                            "missing_systems": sorted(set(sids) - set(g_half)) if args.resample_arm else []}
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
    for n, r in i_rows.items():
        # version 3 (review D M4): the real groups are nested keep-only subsets of one circuit, not alternative implementations of one
        # computation; the sharing verdicts on them are DESCRIPTIVE and in no Holm family
        r.update({"role": "descriptive (not a pre-registered test; in neither Holm family)", "network": n,
                  "reconstruction": lin[full[n]]["reconstruction"] if n in full else None,
                  "mechanism_families": sorted({lin[s]["mechanism_family"] for s in by_net[n] if lin[s]["mechanism_family"]})})
    result["I"] = i_rows
    j_rows = {}
    for a, b in cc_pairs:
        members = [full[a], full[b]]
        t = _tag(members)
        sh = {s: ev(m, "cross", f"shared_{t}", s) for s in members}
        ind = {s: ev(m, "indep", f"{s.replace(':', '_')}_s0", s) for s in members}
        ck = {s: ev(m, "cross", f"commonk_{t}_{s.replace(':', '_')}", s) for s in members}
        pa = {s: ev(m, "cross", f"partial_{t}", s) for s in members}
        same = lin[full[a]]["reconstruction"] == lin[full[b]]["reconstruction"]
        row = {"members": members, "reconstructions": [lin[full[a]]["reconstruction"], lin[full[b]]["reconstruction"]],
               "note": "same reconstruction (descriptive only; never a second confirmation)" if same else "independent reconstructions"}
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
