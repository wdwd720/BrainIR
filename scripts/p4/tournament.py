"""causal_state_v1 Level B tournament driver (ORCHESTRATOR SIDE; benchmarks/causal_state_v1/PROTOCOL.md sections 9-11).

    uv run --no-sync --project phase4 python scripts/p4/tournament.py run --round r1 --stage pilot --methods m1,m2 [--baselines b1]
        [--room C:/Dev/BrainIR_p4clean] [--backend local|modal] [--parallel 4] [--seeds 0,1,2] [--systems s1,s2]
        [--loops --designers own,random,fixed --loop-seeds 0,1,2 --budget 200] [--no-lift] [--timeout 3600] [--tier val]
    uv run --no-sync --project phase4 python scripts/p4/tournament.py decide --round r1 [--finalists 3] [--carried BASELINE]
    uv run --no-sync --project phase4 python scripts/p4/tournament.py feedback --rounds r1,r2 --out <file.md>
    uv run --no-sync --project phase4 python scripts/p4/tournament.py simserver --round r1 --tier val [--budget 100000]

ISOLATION (research/phase4/EVAL_ARCHITECTURE.md; review F, F-B2 / F-B3). Method code runs ONLY in MODEL WORKERS: fresh unprivileged-uid
processes under a trusted root driver, in containers without network. The orchestrator never imports, fits or loads method code:
`isolation.describe_method` reads a method's declared device in a worker, `isolation.fit_job` fits in a worker (the model comes back as
BYTES), `harness.evaluate_job` evaluates the model bytes through `isolation.RemoteFresh` (the phase order A -> lift -> C), and
`isolation.loop_job` runs the loop in the driver with the learner / own designer in a worker. Local rounds use the Docker sandbox
transport; Modal rounds use the "iso" classes (block_network=True). Only the driver's safe-decoded results leave a worker.

A round:
1. snapshots the room's methods package (with the per-developer subpackages methods/<prefix>/) into <run>/<round>/methods with sha256
   hashes (the orchestrator never imports the room); a method's files in the round are named by `method_key`;
2. resolves the stage's systems ('pilot' / 'medium' / 'finalists' / 'full');
3. FITS every method x system x seed in a worker (the main-comparison data D0 + D1 of PROTOCOL 4); at Level C (conf tier) also the
   5 bootstrap refits of the training interventions per system (PROTOCOL 5.10, criterion F);
4. fits and evaluates the k-independent REFERENCES once per system (trusted, in-process) and stores BOUNDS.json: the full-state bound
   (the FULL-STATE reference or the best full-state baseline) and the ID-shortcut comparator (the ID-SHORTCUT reference or the best ID
   baseline), ONE choice per system kind (lowest median EE on the round's validation systems; `choose_bounds`, review E round 3,
   N-new-9), FIXED at Level B and applied unchanged to the confirmation systems (`bounds_for_systems`; PROTOCOL 9, 11);
5. EVALUATES every fitted model of EVERY fit seed in a worker (every metric family; the verdict items only for the verdict; OOD /
   robustness -> the 5.12 report), assembles the verdict per seed with the fixed bounds and the criterion-F k list of all seeds
   (`harness.assemble_verdict`), the per-seed selection values and their SEED AVERAGE (`select.seed_average`), and the per-system
   verdicts and selection values of the gate REFERENCES (the TRUE-STATE reference on synthetic systems, the full-state bound on real
   systems) (review E, N1);
6. optionally (finalists / full) runs the experiment loops of PROTOCOL 5.17 and evaluates the checkpoints;
7. writes research/phase4/tournament/<round>/ (ANSWER-BEARING for held-out data: never into a room).
decide (`decide_round`): eligibility (gates against the stored reference rows), ranking (`select.rank` on the seed-averaged values)
and the halving decision (`select.halve`), and the developer-facing aggregate (`feedback.aggregate`, F-M5 hardened). The Level C
driver additionally builds the primary family with `verdict.build_primary_family` (H1-H6, Holm at alpha 0.05; PROTOCOL 11).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import pickle
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))

from brainir_causal import feedback as FB  # noqa: E402
from brainir_causal import harness as H  # noqa: E402
from brainir_causal import isolation as ISO  # noqa: E402
from brainir_causal import refs as REFS  # noqa: E402
from brainir_causal import select as SEL  # noqa: E402
from brainir_causal import suites as SU  # noqa: E402
from brainir_causal import systems as SY  # noqa: E402

# the host defaults; the Linux driver container (scripts/p4/linux_driver.py, P8) sets both (the room comes in with --extra-mount)
ROOM = Path(os.environ.get("P4_ROOM_CLEAN") or "C:/Dev/BrainIR_p4clean")
RUN = Path(os.environ.get("P4_RUN_BASE") or "C:/Dev/BrainIR_p4run")
OUT = ROOT / "research" / "phase4" / "tournament"
BENCH = ROOT / "benchmarks" / "causal_state_v1"
LOG = ROOT / "research" / "phase4" / "LEVELB_LOG.md"
GENERATOR = ROOT / SU.GENERATOR_REL          # the hash-locked generator package directory (generator/src)
GENERATOR_PKG = "p4synth"
#: full-state baselines (candidates that learn the full observed state) and ID-shortcut baselines, for the fixed bounds of PROTOCOL 9
FULLSTATE_BASELINES = ("full_state_baseline", "linear_fullstate")
IDSHORTCUT_BASELINES = ("id_baseline", "intervention_id")
N_REFITS = 5                    # Level C dimension refits (PROTOCOL 5.10)
N_SEEDS_LEVEL_B = 3             # PROTOCOL 10 / 5.10: every Level B round fits and evaluates 3 seeds (review E, N1 / N7)


# ================================================================================================================ helpers
def method_key(m: str) -> str:
    """The file / directory name of method `m` in a round (method code lives in per-developer packages methods/<prefix>/, and a method
    is named "<prefix>.<module>:<name>" or by its registered name; ':' is not a path character on Windows): ':' -> '__', path
    separators -> '_'."""
    return m.replace(":", "__").replace("/", "_").replace("\\", "_")


def snapshot_methods(round_dir: Path, room: Path) -> tuple[Path, dict]:
    src = room / "src" / "brainir_causal" / "methods"
    dst = round_dir / "methods"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"))
    hashes = {p.relative_to(dst).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dst.rglob("*.py"))}
    return dst, hashes


def stage_systems(stage: str, tier: str, systems: list[str] | None, *, suites_root: Path = SU.SUITES,
                  real_root: Path = SU.REAL_SETS, include_real: bool = True) -> dict[str, dict]:
    """{system id: {"kind", "heldout_root", "heldout_tier", "public_root", "public_tier", "internal_path"}} of a stage."""
    syn_int = SU.tier_dirs(tier, suites_root)["base"] / "internal_records.json"
    syn_ids = sorted(json.loads(syn_int.read_text(encoding="utf-8"))) if syn_int.exists() else []
    real_int = BENCH / "hidden" / "real_systems_internal.json"
    real_ids = sorted(json.loads(real_int.read_text(encoding="utf-8"))) if (include_real and real_int.exists()) else []
    if stage == "pilot":
        pil = json.loads((BENCH / "public" / "pilot_subset.json").read_text(encoding="utf-8"))
        syn_sel, real_sel = pil.get("synthetic") or [], pil.get("real") or []
    elif stage == "medium":
        syn_sel, real_sel = syn_ids, [s for s in real_ids if ":m" in s]
    else:
        syn_sel, real_sel = syn_ids, real_ids
    out = {}
    for s in syn_sel:
        out[s] = {"kind": "synthetic", "heldout_root": str(suites_root), "heldout_tier": tier, "public_root": str(suites_root),
                  "public_tier": tier, "internal_path": str(syn_int)}
    for s in real_sel:
        out[s] = {"kind": "real", "heldout_root": str(real_root), "heldout_tier": SU.REAL_TIERS["B"], "public_root": str(real_root),
                  "public_tier": SU.REAL_TIERS["public"], "internal_path": str(real_int)}
    if systems:
        out = {s: v for s, v in out.items() if s in set(systems)}
    return out


def fit_data(sysd: dict, sid: str) -> str:
    return str(Path(sysd["public_root"]) / sysd["public_tier"] / "public" / SU._safe(sid))


def base_eval_job(sysd: dict, sid: str, *, store_root: str, ref_cache: str, gen, lift: bool, n_boot: int) -> dict:
    return {"sid": sid, "heldout_root": sysd["heldout_root"], "heldout_tier": sysd["heldout_tier"], "public_root": sysd["public_root"],
            "public_tier": sysd["public_tier"], "internal_path": sysd["internal_path"], "store_root": store_root, "ref_cache": ref_cache,
            "generator": gen if sysd["kind"] == "synthetic" else None, "lift": lift, "n_boot": n_boot}


def _ee_of(res) -> float:
    try:
        return float((((res or {}).get("items") or {}).get("effects") or {}).get("EE_cb_medium", {}).get("point", "nan"))
    except Exception:  # noqa: BLE001
        return float("nan")


def _seed_mean_ee(evs_by_seed: dict, sid: str) -> float:
    """The mean over the round's fit seeds of a model's verdict-suite EE on one system (a seed without a result counts as the worst
    admissible EE, 10: a baseline that fails on a seed cannot become the bound by it)."""
    vals = []
    for evs in (evs_by_seed or {}).values():
        v = _ee_of(((evs or {}).get(sid) or {}).get("result"))
        vals.append(10.0 if math.isnan(v) else v)
    return float(sum(vals) / len(vals)) if vals else float("nan")


BOUND_ROLES = {"full_state": FULLSTATE_BASELINES, "id_shortcut": IDSHORTCUT_BASELINES}


def _median(vals: list[float]) -> float:
    v = sorted(vals)
    n = len(v)
    return float("nan") if not n else (v[n // 2] if n % 2 else 0.5 * (v[n // 2 - 1] + v[n // 2]))


def bounds_for_systems(bounds: dict, systems: dict) -> dict:
    """The per-system choices of a Level B BOUNDS.json applied to (new) systems (review E round 3, N-new-9): every system gets the ONE
    choice of its kind; a kind without a choice gets the reference. The Level C driver maps the confirmation systems with this (and
    fits the chosen baseline there)."""
    cbk = bounds.get("choice_by_kind") or {}
    return {role: {sid: ((cbk.get(role) or {}).get(sysd["kind"]) or f"ref:{role}") for sid, sysd in systems.items()}
            for role in BOUND_ROLES}


def choose_bounds(refs_results: dict, method_evals: dict, systems: dict) -> dict:
    """BOUNDS.json (fixed at Level B; PROTOCOL 9, 11; review E round 3, N-new-9): ONE model choice per system KIND (synthetic, real)
    for the full-state bound (the FULL-STATE reference, an extra full-state reference candidate of `refs.BOUND_EXTRA_REFS` fitted in the
    round's reference stage, e.g. FULL-STATE with the joint one-step fit, or a full-state baseline) and for the ID-shortcut comparator
    (the ID-SHORTCUT reference or an ID baseline): the candidate with the lowest MEDIAN verdict-suite EE over the round's validation
    systems of that kind (a baseline's per-system EE is its mean over the round's fit seeds; a missing seed, system or reference result
    counts as the worst EE, 10; ties go to the role's own reference, "ref:full_state" / "ref:id_shortcut"). The choice is applied unchanged to every system of the kind, here and on the
    confirmation systems at Level C (`bounds_for_systems`): a per-system minimum over candidates on the same data was optimistic for
    the bound and had no counterpart on new systems. Where the chosen baseline has no result on a system (for its first fit seed,
    whose effects are the fixed comparator, `bound_effects`), that system falls back to the reference, recorded in "fallbacks".
    `refs_results` = {sid: {name: result}}; `method_evals` = {method: {seed: {sid: evaluation}}}."""
    def worst(v: float) -> float:
        return 10.0 if math.isnan(v) else v
    out: dict = {"choice_by_kind": {r: {} for r in BOUND_ROLES}, "median_ee_by_kind": {r: {} for r in BOUND_ROLES},
                 "fallbacks": {r: [] for r in BOUND_ROLES}, "full_state_baselines": list(FULLSTATE_BASELINES),
                 "id_shortcut_baselines": list(IDSHORTCUT_BASELINES), "full_state_extra_references": list(REFS.BOUND_EXTRA_REFS),
                 "baseline_seed_for_effects": "the first fit seed of the round",
                 "rule": "one choice per system kind: the lowest median verdict EE over the round's validation systems (review E, "
                         "N-new-9)"}
    for role, basel in BOUND_ROLES.items():
        for kind in sorted({sysd["kind"] for sysd in systems.values()}):
            sids = [s for s, sysd in systems.items() if sysd["kind"] == kind]
            cands = {f"ref:{role}": [worst(_ee_of((refs_results.get(s) or {}).get(role))) for s in sids]}
            if role == "full_state":
                for extra in REFS.BOUND_EXTRA_REFS:          # extra full-state reference candidates (never the calibration's)
                    cands[f"ref:{extra}"] = [worst(_ee_of((refs_results.get(s) or {}).get(extra))) for s in sids]
            for m, evs in method_evals.items():
                if m in basel:
                    cands[f"baseline:{m}"] = [worst(_seed_mean_ee(evs, s)) for s in sids]
            med = {c: _median(v) for c, v in cands.items()}
            out["median_ee_by_kind"][role][kind] = med
            out["choice_by_kind"][role][kind] = min(med, key=lambda c: (med[c], c != f"ref:{role}", not c.startswith("ref:"), c))
    per_sys = bounds_for_systems(out, systems)
    for role, choices in per_sys.items():
        for sid, choice in choices.items():
            if choice.startswith("baseline:"):
                evs = method_evals.get(choice.split(":", 1)[1]) or {}
                first = next(iter(evs.values()), {}) if evs else {}
                ev = (first or {}).get(sid) or {}
                if not ev.get("result") or ev.get("error"):
                    choices[sid] = f"ref:{role}"
                    out["fallbacks"][role].append(sid)
        out[role] = choices
    return out


def bound_effects(choice: str, sid: str, refs_results: dict, method_evals: dict, seed: int):
    """The effects (with private units) of the model a BOUNDS choice names (`ref:<name>` or `baseline:<method>`; a baseline's first
    fit seed `seed`)."""
    kind, name = choice.split(":", 1)
    if kind == "ref":
        return H.verdict_effects((refs_results.get(sid) or {}).get(name))
    return H.verdict_effects((((method_evals.get(name) or {}).get(seed) or {}).get(sid) or {}).get("result"))


def check_seeds(seeds: list[int], level: str, tier: str) -> None:
    """PROTOCOL 10 / 5.10 (review E, N1 / N7): a Level B round fits and evaluates at least N_SEEDS_LEVEL_B = 3 seeds (the toy tiers of
    the tests are exempt)."""
    if level == "B" and tier not in ("toy", "toyC") and len(set(seeds)) < N_SEEDS_LEVEL_B:
        raise SystemExit(f"a Level B round needs at least {N_SEEDS_LEVEL_B} fit seeds (got {sorted(set(seeds))}; PROTOCOL 10)")


# ================================================================================================================ transports
def local_transport(mdir: Path):
    """The Docker sandbox transport of the development machine (the only local transport a tournament uses)."""
    tr, pub = ISO.local_transport(mdir, kind="docker")
    return tr, pub


def modal_iso_payload(role: str, key: str, job: dict, *, model: bytes | None = None, reload=("fit",), commit=(), timeout_s: float = 3600) -> dict:
    p = {"role": role, "job": job, "methods_key": key, "reload": list(reload), "commit": list(commit), "timeout_s": timeout_s}
    if model is not None:
        p["model"] = model
    return p


# ================================================================================================================ run
def _fit_side(round_dir: Path, m: str, sid: str, seed: int) -> dict:
    p = round_dir / method_key(m) / "fits" / f"{SU._safe(sid)}_s{seed}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _refit_ks(round_dir: Path, m: str, sid: str, seeds: list[int], level: str) -> list:
    """Criterion F's k list: Level C the 5 bootstrap refits' k; Level B the round's fit seeds' k (PROTOCOL 5.10). One entry per
    required fit, None for a missing or failed fit (review E, N7: `verdict.dimension_status` counts it as disagreeing, never drops
    it)."""
    ks: list = []
    if level == "C":
        for b in range(N_REFITS):
            p = round_dir / method_key(m) / "refits" / f"{SU._safe(sid)}_b{b}.json"
            k = ((json.loads(p.read_text(encoding='utf-8')).get("info") or {}).get("k") or {}).get(sid) if p.exists() else None
            ks.append(None if k is None else int(k))
    else:
        for seed in seeds:
            k = ((_fit_side(round_dir, m, sid, seed).get("info") or {}).get("k") or {}).get(sid)
            ks.append(None if k is None else int(k))
    return ks


def cmd_run(args) -> int:
    t_start = time.time()
    methods = [m for m in args.methods.split(",") if m]
    baselines = [m for m in (args.baselines or "").split(",") if m]
    all_methods = methods + [b for b in baselines if b not in methods]
    level = SU.LEVEL_OF_TIER.get(args.tier, "B")
    round_dir = Path(args.run_root) / args.round
    round_dir.mkdir(parents=True, exist_ok=True)
    mdir, mhash = snapshot_methods(round_dir, Path(args.room))
    systems = stage_systems(args.stage, args.tier, [s for s in (args.systems or "").split(",") if s] or None,
                            suites_root=Path(args.suites_root), real_root=Path(args.real_root), include_real=not args.no_real)
    seeds = [int(s) for s in args.seeds.split(",") if s]
    check_seeds(seeds, level, args.tier)
    out_dir = Path(args.out_root) / args.round
    out_dir.mkdir(parents=True, exist_ok=True)
    gen = None if args.tier in ("toy", "toyC") else [str(GENERATOR), GENERATOR_PKG]
    report = {"round": args.round, "suite": args.tier, "level": level, "backend": args.backend,
              "design": {"stage": args.stage, "tier": args.tier, "systems": sorted(systems), "seeds": seeds, "lift": not args.no_lift,
                         "loops": bool(args.loops), "benchmark": "causal_state_v1"},
              "methods": methods, "baselines": baselines, "method_hashes": mhash, "results": {}}
    if args.backend == "modal":
        return cmd_run_modal(args)
    if args.tier not in ("toy", "toyC"):
        # the local transport's trusted driver simulates on the host; official rounds simulate on the reference platform only (P4-D32)
        raise SystemExit("official rounds (synthetic / real tiers) run with --backend modal (reference platform, LOG P4-D32)")

    tr, pub = local_transport(mdir)
    print(f"[{args.round}] docker transport ready ({pub})", flush=True)
    # devices (read in a worker; the orchestrator never imports method code)
    devices = {}
    for m in all_methods:
        try:
            devices[m] = ISO.describe_method(tr, m).get("device", "cpu")
        except Exception as e:  # noqa: BLE001 - a method that cannot even be described fails its fits later (recorded)
            devices[m] = f"error: {type(e).__name__}"

    # ---- 3. fits (+ Level C bootstrap refits)
    def do_fit(m: str, sid: str, seed: int, boot: int | None) -> dict:
        sysd = systems[sid]
        rel = f"{SU._safe(sid)}_b{boot}" if boot is not None else f"{SU._safe(sid)}_s{seed}"
        sub = "refits" if boot is not None else "fits"
        out = round_dir / method_key(m) / sub / f"{rel}.pkl"
        if out.exists() and not args.refit:
            return {"ok": True, "cached": True}
        out.parent.mkdir(parents=True, exist_ok=True)
        job = {"method": m, "systems": [sid], "data": [fit_data(sysd, sid)], "seed": seed, "config": {},
               "timeout_s": args.timeout, "threads": 3}
        if boot is not None:
            job["bootstrap"] = boot
        try:
            res = ISO.fit_job(job, tr)
            out.write_bytes(res["model"])
            out.with_suffix(".json").write_text(json.dumps(res["side"], indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
            return {"ok": True}
        except Exception as e:  # noqa: BLE001 - recorded per fit
            import traceback
            rec = {"ok": False, "error": f"{type(e).__name__}: {e}"[-3000:], "traceback": traceback.format_exc()[-2000:]}
            out.with_suffix(".fitlog.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")
            return rec
    fit_specs = [(m, sid, seed, None) for m in all_methods for sid in systems for seed in seeds]
    if level == "C":
        fit_specs += [(m, sid, seeds[0], b) for m in all_methods for sid in systems for b in range(N_REFITS)]
    print(f"[{args.round}] {len(fit_specs)} fits (incl. Level C refits) on {len(systems)} systems", flush=True)
    with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as ex:
        fit_recs = list(ex.map(lambda t: do_fit(*t), fit_specs))
    n_fit_fail = sum(1 for r in fit_recs if not r.get("ok"))

    # ---- 4. references (trusted, in-process) + BOUNDS. The in-process numerics run with the thread counts of the Modal path (references
    # 4, evaluation drivers 3: `isolation.pinned_threads`), never this machine's CPU count, which changes multi-threaded BLAS sums.
    ref_cache = str(Path(args.run_root) / "refcache")
    refs_results: dict = {}
    refs_meta: dict = {}
    with ISO.pinned_threads(4):
        for sid, sysd in systems.items():
            job = base_eval_job(sysd, sid, store_root=str(args.store_root), ref_cache=str(Path(ref_cache) / sysd["heldout_tier"]), gen=gen,
                                lift=False, n_boot=args.n_boot)
            job["ref_names"] = list(REF_JOB_NAMES)
            job["return_results"] = True
            try:
                rj = H.references_job(job) or {}
                refs_results[sid] = rj.get("results") or {}
                refs_meta[sid] = {k: rj.get(k) for k in ("truth_k", "truth_d_draw", "truth_noncompressible", "kind")}
            except Exception as e:  # noqa: BLE001
                refs_results[sid] = {}
                report.setdefault("reference_errors", {})[sid] = f"{type(e).__name__}: {e}"[:500]

    # ---- 5. evaluations (workers)
    def do_eval(m: str, sid: str, seed: int):
        sysd = systems[sid]
        mp = round_dir / method_key(m) / "fits" / f"{SU._safe(sid)}_s{seed}.pkl"
        if not mp.exists():
            return None
        job = base_eval_job(sysd, sid, store_root=str(args.store_root), ref_cache=str(Path(ref_cache) / sysd["heldout_tier"]), gen=gen,
                           lift=not args.no_lift, n_boot=args.n_boot)
        job["seed"] = seed
        try:
            return H.evaluate_job(job, transport=tr, model_bytes=mp.read_bytes())
        except Exception as e:  # noqa: BLE001
            import traceback
            return {"sid": sid, "error": f"{type(e).__name__}: {e}"[-2000:], "traceback": traceback.format_exc()[-2000:]}
    method_evals: dict = {m: {sd: {} for sd in seeds} for m in all_methods}          # {method: {seed: {sid: evaluation}}}
    ev_specs = [(m, sid, sd) for m in all_methods for sid in systems for sd in seeds]
    print(f"[{args.round}] {len(ev_specs)} evaluations ({len(seeds)} fit seeds)", flush=True)
    with ISO.pinned_threads(3), ThreadPoolExecutor(max_workers=max(1, args.eval_workers)) as ex:   # the eval jobs' "threads"
        for (m, sid, sd), ev in zip(ev_specs, ex.map(lambda t: do_eval(*t), ev_specs)):
            if ev is not None:
                method_evals[m][sd][sid] = ev
                ep = round_dir / method_key(m) / "evals" / f"{SU._safe(sid)}_s{sd}.pkl"
                ep.parent.mkdir(parents=True, exist_ok=True)
                with open(ep, "wb") as fh:
                    pickle.dump(ev, fh, protocol=pickle.HIGHEST_PROTOCOL)

    bounds = choose_bounds(refs_results, method_evals, systems)
    (out_dir / "BOUNDS.json").write_text(json.dumps({k: v for k, v in bounds.items()}, indent=1) + "\n", encoding="utf-8", newline="\n")

    assemble_round(args, report, all_methods, systems, method_evals, refs_results, bounds, round_dir, seeds, level, fit_specs,
                   fit_recs, out_dir, refs_meta=refs_meta)
    report["n_fit_failures"], report["devices"], report["bounds"] = n_fit_fail, devices, {k: bounds[k] for k in ("full_state", "id_shortcut")}
    if args.loops:
        report["loops"] = run_loops(args, methods, systems, mdir, round_dir, tr, gen)
    report["wall_s"] = round(time.time() - t_start, 1)
    H.dump({k: v for k, v in report.items() if k != "results"}, out_dir / "ROUND.json")
    _log_row(args, methods, systems)
    print(json.dumps({"round": args.round, "fit_failures": n_fit_fail, "wall_s": report["wall_s"]}), flush=True)
    return 0


def _reference_row(name: str, c: dict) -> dict | None:
    """The verdict row of reference `name` on one system (context c from `reference_rows`); None when it has no result."""
    res = c["rr"].get(name)
    if not res or res.get("error"):
        return None
    ev = {"sid": c["sid"], "kind": c["kind"], "result": res, "truth_k": c["meta"].get("truth_k"), "truth_d_draw": c["meta"].get("truth_d_draw"),
          "truth_noncompressible": c["meta"].get("truth_noncompressible")}
    k = res.get("k")
    av = H.assemble_verdict(ev, {"results": c["rr"]}, c["tol"], calibrated=c["calibrated"], fullbound_eff=c["fb"], idshortcut_eff=c["idsc"],
                            k_refits=[k] * len(c["seeds"]) if k is not None else None, level=c["level"], n_boot=c["n_boot"])
    return {"kind": c["kind"], "verdict": H.public_view(av["verdict"]), "selection": av["selection"], "source": f"ref:{name}"}


def reference_rows(systems: dict, refs_results: dict, refs_meta: dict | None, bounds: dict, method_rows: dict, tol, calibrated: bool,
                   seeds: list[int], level: str, n_boot: int, method_evals: dict) -> dict:
    """The per-system rows of the GATE REFERENCES (PROTOCOL 10 rule 1; review E, N1): {"true_state": {sid: row}, "full_state_bound":
    {sid: row}}, row = {"kind", "verdict", "selection", "source"}. TRUE-STATE: its verdict on the round's synthetic systems where the
    reference exists (the Level B-fixed full-state bound and ID comparator, as for candidates; its k is fixed, so its F k list is that
    k for every fit seed: stable by construction, PROTOCOL 5.10). FULL-STATE BOUND: on every system, the model BOUNDS.json names (the
    FULL-STATE reference's own verdict, or the chosen full-state baseline's SEED-AVERAGED candidate row)."""
    out: dict = {"true_state": {}, "full_state_bound": {}}
    for sid, sysd in systems.items():
        rr = refs_results.get(sid) or {}
        meta = (refs_meta or {}).get(sid) or {}
        ctx = {"sid": sid, "kind": sysd["kind"], "rr": rr, "meta": meta, "tol": tol, "calibrated": calibrated, "seeds": seeds,
               "level": level, "n_boot": n_boot,
               "fb": bound_effects(bounds["full_state"][sid], sid, refs_results, method_evals, seeds[0]),
               "idsc": bound_effects(bounds["id_shortcut"][sid], sid, refs_results, method_evals, seeds[0])}
        if sysd["kind"] == "synthetic":
            row = _reference_row("true_state", ctx)
            if row is not None:
                out["true_state"][sid] = row
        choice = bounds["full_state"][sid]
        if choice.startswith("ref:"):
            row = _reference_row(choice.split(":", 1)[1], ctx)
            if row is not None:
                out["full_state_bound"][sid] = row
        else:
            base = choice.split(":", 1)[1]
            sel = ((method_rows.get(base) or {}).get("seed_averaged") or {}).get(sid)
            if sel is not None:
                out["full_state_bound"][sid] = {"kind": sysd["kind"], "selection": sel, "source": choice}
    return out


def assemble_round(args, report: dict, all_methods: list[str], systems: dict, method_evals: dict, refs_results: dict, bounds: dict,
                   round_dir: Path, seeds: list[int], level: str, fit_specs: list, fit_recs: list, out_dir: Path,
                   refs_meta: dict | None = None) -> None:
    """Verdicts + selection values of every (method, system, fit seed) and their SEED AVERAGE (ORCHESTRATOR SIDE, shared by the local
    and the Modal paths; review E, N1): the Level B-fixed bounds of BOUNDS.json, the criterion-F k list of all fit seeds (Level B; Level
    C: the bootstrap refits), the calibrated tolerances (provisional ones flagged). method_evals = {method: {seed: {sid: evaluation}}}.
    Writes <method>.json (per system: the verdict of every seed, the per-seed selection values, and `seed_averaged` =
    `select.seed_average` over the round's seeds, a seed without a result counting as a failure) and true_state.json /
    full_state_bound.json (`reference_rows`), which `decide_round` reads."""
    tol, calibrated = H.tolerances_or_provisional(args.tolerances)
    method_rows: dict = {}
    for m in all_methods:
        per_sys: dict = {}
        per_seed_sel: dict = {sd: {} for sd in seeds}
        n_eval_fail = 0
        for sid in systems:
            fb = bound_effects(bounds["full_state"][sid], sid, refs_results, method_evals, seeds[0])
            idsc = bound_effects(bounds["id_shortcut"][sid], sid, refs_results, method_evals, seeds[0])
            ks = _refit_ks(round_dir, m, sid, seeds, level)
            by_seed = {}
            for sd in seeds:
                ev = ((method_evals.get(m) or {}).get(sd) or {}).get(sid)
                if ev is None or ev.get("error"):
                    n_eval_fail += 1
                    sel = SEL.failed_system_values(systems[sid]["kind"], reason=str((ev or {}).get("error", "no output"))[:200])
                    by_seed[sd] = {"error": (ev or {}).get("error", "no output"), "selection": sel}
                    per_seed_sel[sd][sid] = sel
                    continue
                av = H.assemble_verdict(ev, {"results": refs_results.get(sid) or {}}, tol, calibrated=calibrated, fullbound_eff=fb,
                                        idshortcut_eff=idsc, k_refits=ks, level=level,
                                        fit_compute=(_fit_side(round_dir, m, sid, sd).get("compute")), n_boot=args.n_boot)
                by_seed[sd] = {"verdict": H.public_view(av["verdict"]), "selection": av["selection"],
                               "result": H.public_view(ev.get("result"))}
                per_seed_sel[sd][sid] = av["selection"]
            per_sys[sid] = {"kind": systems[sid]["kind"], "seeds": by_seed, "k_values": ks}
        averaged = SEL.seed_average(per_seed_sel)
        for sid, row in per_sys.items():
            row["seed_averaged"] = averaged.get(sid)
        method_rows[m] = {"per_system": per_sys, "seed_averaged": averaged, "seeds": list(seeds),
                          "n_fits": sum(1 for s in fit_specs if s[0] == m and s[3] is None),
                          "n_fit_failures": sum(1 for s, r in zip(fit_specs, fit_recs) if s[0] == m and s[3] is None and not r.get("ok")),
                          "n_eval_failures": n_eval_fail}
        report["results"][m] = method_rows[m]
        H.dump(method_rows[m], out_dir / f"{method_key(m)}.json")
    refs = reference_rows(systems, refs_results, refs_meta, bounds, method_rows, tol, calibrated, seeds, level, args.n_boot, method_evals)
    for name, rows in refs.items():
        H.dump({"reference": name, "per_system": rows, "seeds": list(seeds)}, out_dir / f"{name}.json")
    report["references_assembled"] = {name: sorted(rows) for name, rows in refs.items()}


# ================================================================================================================ run on Modal
def modal_system_paths(sid: str, kind: str, tier: str) -> dict:
    """Container paths of one system's data in the remote-build layout (suites.REMOTE): the fit data (public part), the tier roots
    the harness reads (public on the fit volume, held-out / truth on the eval volume) and the internal records."""
    from pathlib import PurePosixPath
    if kind == "synthetic":
        pub_root, held_root = PurePosixPath(SU.REMOTE["fit"]) / "suites", PurePosixPath(SU.REMOTE["eval"]) / "suites"
        return {"fit_data": str(pub_root / tier / "public" / SU._safe(sid)), "public_root": str(pub_root), "public_tier": tier,
                "heldout_root": str(held_root), "heldout_tier": tier, "internal_path": str(held_root / tier / "internal_records.json")}
    pub_root, held_root = PurePosixPath(SU.REMOTE["fit"]) / "real", PurePosixPath(SU.REMOTE["eval"]) / "real"
    return {"fit_data": str(pub_root / SU.REAL_TIERS["public"] / "public" / SU._safe(sid)), "public_root": str(pub_root),
            "public_tier": SU.REAL_TIERS["public"], "heldout_root": str(held_root), "heldout_tier": SU.REAL_TIERS["B"],
            "internal_path": str(held_root / "real_systems_internal.json")}


#: the packed class of the per-(system, reference) reference jobs (trusted; see cmd_run_modal.run_references) and the relative cost of
#: one reference job (every job fits FULL-STATE first, then its own reference, then evaluates it)
REF_PACK_CLS = "pack_xl"
REF_WEIGHT = {"full_state": 1.3, "no_effect": 1.3, "true_state": 2.0, "obs_shortcut": 2.0, "random_k": 1.8, "pca_k": 1.8,
              "id_shortcut": 1.2, "full_state_joint": 2.3}
#: the references a Level B round fits and evaluates per system: the verdict references plus the extra CANDIDATES of the full-state bound
#: (`refs.BOUND_EXTRA_REFS`, e.g. FULL-STATE with the joint one-step fit; E13, LOG P4-D51). The calibration never fits the extras.
REF_JOB_NAMES = tuple(H.REF_EVAL_NAMES) + tuple(n for n in REFS.BOUND_EXTRA_REFS if n not in H.REF_EVAL_NAMES)
#: relative cost weight of a system for LONGEST-PROCESSING-TIME scheduling (research/phase4/LEVEL_B_EXECUTION.md): real full networks
#: dominate, then real medium, then real other, then synthetic; refined by a job's measured wall time when a previous run recorded it
SIZE_WEIGHT = {"real_full": 100.0, "real_medium": 40.0, "real_other": 20.0, "synthetic": 10.0}


def _size_class(sid: str, sysd: dict) -> str:
    if sysd["kind"] == "real":
        return "real_full" if ":full" in sid else ("real_medium" if ":m" in sid else "real_other")
    return "synthetic"


_SIZE_CACHE: dict = {}


def _n_units(sid: str, sysd: dict) -> float:
    """The system's unit count from its internal record (orchestrator side, read once per file; used only for scheduling)."""
    p = sysd.get("internal_path")
    if p not in _SIZE_CACHE:
        try:
            _SIZE_CACHE[p] = json.loads(Path(p).read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - a missing file only weakens the prior
            _SIZE_CACHE[p] = {}
    rec = (_SIZE_CACHE[p] or {}).get(sid) or {}
    n = rec.get("n_units") or (rec.get("system") or {}).get("n_units") if isinstance(rec, dict) else None
    try:
        return float(n) if n else 50.0
    except (TypeError, ValueError):
        return 50.0


def _expected_s(round_dir: Path, m: str, sid: str, sysd: dict, kind: str, seed: int = 0) -> float:
    """A job's expected wall time for LPT: for a FIT, the measured wall time of the same fit if one is on disk (a --refit or resumed
    round: its side record's fit_wall_s), else a size-weighted prior (the size class x the unit count / 50; evaluations and loops cost
    more than fits). Evaluations and loops always use the prior: a fit's wall time does not predict its evaluation's (P1 dry run:
    evaluations took 686-1008 s for fits of 307-995 s). kind in {"fit", "eval", "loop"}."""
    base = SIZE_WEIGHT[_size_class(sid, sysd)] * max(0.5, _n_units(sid, sysd) / 50.0)
    mult = {"fit": 1.0, "eval": 1.6, "loop": 6.0}.get(kind, 1.0)
    if kind == "fit":
        side = _fit_side(round_dir, m, sid, seed)
        w = side.get("job_wall_s") or side.get("fit_wall_s")
        if isinstance(w, (int, float)) and w > 0:
            return float(w)
    return base * mult


def ref_code_key() -> str:
    """A content key of the evaluator + reference-learner code (every brainir_causal module, line endings normalised). The reference
    cache on the eval volume is keyed by system / name / k only (harness.fit_system_references), so the Modal rounds put it under
    <root>/<tier>/<this key>: a pre-freeze change of refs.py or of the evaluator can never be answered from a stale cache (the refs run
    concurrently with the fits, so recomputing them once per code version costs no wall time)."""
    pkg = ROOT / "phase4" / "src" / "brainir_causal"
    h = hashlib.sha256()
    for p in sorted(pkg.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        h.update(p.relative_to(pkg).as_posix().encode("utf-8") + b"\0")
        h.update(p.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()[:16]


def modal_ref_cache(args, tier: str) -> str:
    root = str(args.ref_cache_root)
    if not root.startswith("/") or ":" in root:
        # Git Bash rewrites a POSIX argument such as /evalvol/refcache into C:/Program Files/Git/evalvol/refcache (MSYS path conversion);
        # the containers would then cache under a relative directory that no later round sees
        raise SystemExit(f"--ref-cache-root must be a container path (/evalvol/...), got {root!r}; from Git Bash set MSYS_NO_PATHCONV=1")
    return f"{root.rstrip('/')}/{tier}/{args.ref_code_key}"


def stage_fetch(be, ref: dict, staged_refs: list) -> bytes:
    """Download a staged artefact (isolation.stage_blob / Backend.stage_put ref; hash-verified) and record it for the round's cleanup."""
    staged_refs.append(dict(ref))
    return be.stage_get(ref)


def model_field(be, model: bytes, staged_refs: list) -> dict:
    """The model of an evaluation payload: inline when small, else staged on the STORE volume (a fitted model is derived from public
    training data only) and passed by ref, since a block_network container cannot receive more than 2 MiB inline."""
    from brainir_causal.isolation import STAGE_THRESHOLD
    if len(model) <= STAGE_THRESHOLD:
        return {"model": model}
    ref = be.stage_put(model, vol="store")
    staged_refs.append(dict(ref))
    return {"model_ref": ref}


#: the text of a final INFRASTRUCTURE failure (p4modal.app.Backend.run after its re-submissions; isolation.InfraFault; the host gate;
#: staging freshness): never a method's result
INFRA_MARKS = ("call failed repeatedly", "InfraFault", "no admissible host", "not completed after", "not visible after", "PackInfraError")


def infra_failure(r) -> str | None:
    """The reason when a Modal job's final result is an INFRASTRUCTURE failure (an exception from the Backend, an infrastructure marker,
    or an error text of INFRA_MARKS), else None. Such a result is never stored as the job's output (a rerun of the round recomputes it)
    and never charged to a method: the round is marked INCOMPLETE and is not assembled."""
    if isinstance(r, BaseException):
        return f"{type(r).__name__}: {r}"[:500]
    if isinstance(r, dict):
        if r.get("__infra__"):
            return str(r.get("error") or "InfraFault")[:500]
        err = str(r.get("error") or "")
        if err and any(m in err for m in INFRA_MARKS):
            return err[:500]
    return None


def eval_of(be, r, sid: str, staged_refs: list) -> dict:
    """An evaluation job's result: inline, or staged on the EVAL volume (a large record) and downloaded; the record is the trusted
    driver's own output (worker replies were safe-decoded in the driver). An error result is kept as {"sid", "error"}."""
    if isinstance(r, dict) and "result" in r:
        return r["result"]
    if isinstance(r, dict) and isinstance(r.get("result_ref"), dict):
        return pickle.loads(stage_fetch(be, r["result_ref"], staged_refs))
    return {"sid": sid, "error": str((r or {}).get("error") if isinstance(r, dict) else r)[-2000:]}


def _pack_class(base: str, gpu: bool, args) -> str:
    """The class for a job group: the packed class when --pack, else the unpacked one. base in {"fit", "eval", "loop"}."""
    from brainir_causal.p4modal.app import CLASSES
    if base == "fit" and gpu:
        gcls = f"iso_pack_gpu_{args.gpu_class.replace('gpu_', '')}" if args.pack else f"iso_{args.gpu_class}"
        return gcls if gcls in CLASSES else (f"iso_{args.gpu_class}")
    packed = {"fit": "iso_pack_fit", "eval": "iso_pack_eval", "loop": "iso_pack_loop"}[base]
    unpacked = {"fit": "iso_fit_s", "eval": "iso_eval_s", "loop": "iso_loop"}[base]
    return packed if (args.pack and packed in CLASSES) else unpacked


def cmd_run_modal(args) -> int:
    """A round on Modal through the ISOLATED classes only (block_network=True; kind "iso"): method descriptions, fits (and Level C
    refits) and evaluations run in unprivileged-uid model workers under a root driver; the references (trusted code) run once per
    system through `Backend.call`; verdicts are assembled here exactly as for local rounds. The model bytes travel from the fit results
    to the evaluation payloads and are never loaded by the orchestrator.

    With --pack (the default) fits, evaluations and loops run PACKED (several jobs per large container, `Backend.run_iso_packed`,
    longest expected first, idempotent per-job keys so a round resumes without recomputation), and the references run CONCURRENTLY with
    the fits in a thread of the same app. The packed and unpacked paths compute the same results (research/phase4/LEVEL_B_EXECUTION.md;
    a bit-identity check on a sample is part of the dry run)."""
    from brainir_causal.p4modal.app import Backend
    t_start = time.time()
    args.ref_code_key = ref_code_key()          # the reference cache is keyed by the code version (never a stale cache)
    modal_ref_cache(args, args.tier)            # refuses a mangled --ref-cache-root before anything runs
    methods = [m for m in args.methods.split(",") if m]
    baselines = [m for m in (args.baselines or "").split(",") if m]
    all_methods = methods + [b for b in baselines if b not in methods]
    level = SU.LEVEL_OF_TIER.get(args.tier, "B")
    round_dir = Path(args.run_root) / args.round
    round_dir.mkdir(parents=True, exist_ok=True)
    mdir, mhash = snapshot_methods(round_dir, Path(args.room))
    systems = stage_systems(args.stage, args.tier, [s for s in (args.systems or "").split(",") if s] or None,
                            suites_root=Path(args.suites_root), real_root=Path(args.real_root), include_real=not args.no_real)
    seeds = [int(s) for s in args.seeds.split(",") if s]
    check_seeds(seeds, level, args.tier)
    out_dir = Path(args.out_root) / args.round
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {sid: modal_system_paths(sid, sd["kind"], args.tier) for sid, sd in systems.items()}
    synthetic = any(sd["kind"] == "synthetic" for sd in systems.values()) and args.tier not in ("toy", "toyC")
    extra = {SU.GENERATOR_REL: SU.GENERATOR_CONTAINER} if synthetic else None
    gen = [SU.GENERATOR_CONTAINER, GENERATOR_PKG] if synthetic else None
    report = {"round": args.round, "suite": args.tier, "level": level, "backend": "modal-iso",
              "design": {"stage": args.stage, "tier": args.tier, "systems": sorted(systems), "seeds": seeds, "lift": not args.no_lift,
                         "loops": bool(args.loops), "benchmark": "causal_state_v1"},
              "methods": methods, "baselines": baselines, "method_hashes": mhash, "results": {},
              "modal": {"ref_cache": modal_ref_cache(args, "<tier>"), "ref_code_key": args.ref_code_key}}
    from brainir_causal.p4modal.app import CLASSES
    describe_cls = "iso_fit_s"
    fit_cls, eval_cls, loop_cls = _pack_class("fit", False, args), _pack_class("eval", False, args), _pack_class("loop", False, args)
    gpu_fit_cls = _pack_class("fit", True, args)
    # devices, read in a worker (a small app of its own, so the GPU class is created only when a method declares 'cuda')
    with Backend(classes=[describe_cls], app_name="brainir-p4-iso-describe") as be0:
        key = be0.methods_key(mdir)
        dres = be0.run_iso([{"role": "describe", "job": {"method": m}, "methods_key": key} for m in all_methods], describe_cls, "describe")
        report["modal"]["describe"] = be0.cost_summary()
    devices = {m: ((r or {}).get("describe") or {}).get("device", "cpu") if isinstance(r, dict) else "error"
               for m, r in zip(all_methods, dres)}
    need_gpu = any(d == "cuda" for d in devices.values())
    ref_cls = REF_PACK_CLS if args.pack else "eval_l"
    with_loops = bool(args.loops and args.stage in ("finalists", "full"))
    classes = sorted({fit_cls, eval_cls, ref_cls} | ({gpu_fit_cls} if need_gpu else set()) | ({loop_cls} if with_loops else set()))
    report["modal"]["classes"] = {"fit": fit_cls, "eval": eval_cls, "loop": loop_cls, "gpu_fit": gpu_fit_cls if need_gpu else None,
                                  "packed": bool(args.pack)}

    def run_iso_group(be, payloads, cls, expected, keys, label):
        """Packed (longest-first, resumable) or unpacked, by class."""
        if CLASSES[cls].get("slots"):
            # every result is stored under its job key AS IT ARRIVES (round_dir/_done/<label>): a crashed orchestrator resumes the wave
            # without recomputing what already finished (the per-file skips below cover jobs whose outputs were written)
            return be.run_iso_packed(payloads, cls, expected_s=expected, keys=keys, label=label,
                                     done_dir=round_dir / "_done" / label.replace(":", "_"))
        return be.run_iso(payloads, cls, label)

    with Backend(classes=classes, extra_dirs=extra, app_name="brainir-p4-iso") as be:
        key = be.methods_key(mdir)
        # ---- references (trusted, once per system): run CONCURRENTLY with the fits (they do not depend on them)
        def run_references():
            """The references (trusted; the ORCHESTRATOR alone consumes their results: bounds and verdict assembly; no evaluation job
            reads them). Packed: one job per (system, reference) on REF_PACK_CLS, longest first (each job fits FULL-STATE first, as
            harness.fit_system_references always does, so NO-EFFECT keeps its base; every reference's result is computed independently,
            so the per-reference jobs give the per-system job's results); packed jobs never commit. Unpacked: one job per system on
            eval_l, committing the cache (the earlier path). Each system's results are saved to <round>/refs/<sid>.pkl (resume)."""
            rdir = round_dir / "refs"
            rdir.mkdir(parents=True, exist_ok=True)
            rr, rm = {}, {}
            todo = []
            for sid in systems:
                f = rdir / f"{SU._safe(sid)}.pkl"
                if f.exists() and not args.refit:
                    with open(f, "rb") as fh:
                        saved = pickle.load(fh)
                    rr[sid], rm[sid] = saved["results"], saved["meta"]
                else:
                    todo.append(sid)

            def job_of(sid, names):
                p = paths[sid]
                j = base_eval_job({**systems[sid], **p}, sid, store_root="/tmp/p4m/evalstore",
                                  ref_cache=modal_ref_cache(args, p['heldout_tier']), gen=gen, lift=False, n_boot=args.n_boot)
                j.update({"store_read_roots": [SU.REMOTE["eval_store"], SU.REMOTE["store"]], "ref_names": list(names),
                          "return_results": True})
                return j
            meta_keys = ("truth_k", "truth_d_draw", "truth_noncompressible", "kind")
            if args.pack:
                specs = [(sid, name) for sid in todo for name in REF_JOB_NAMES]

                def ref_job(sid, name):
                    # a PRIVATE cache subdirectory per (system, reference): the harness locks a system's cache directory, so jobs sharing
                    # it would run one after another in a container; each job fits its own FULL-STATE base (deterministic: the same fit)
                    j = job_of(sid, [name])
                    j["ref_cache"] = f"{j['ref_cache']}/by_ref/{name}"
                    return j
                res = be.call_packed("brainir_causal.harness:references_job", [[ref_job(sid, name)] for sid, name in specs], cls=ref_cls,
                                     timeout_s=args.timeout, threads=4, reload=["fit", "eval", "store"],
                                     expected_s=[_expected_s(round_dir, "", sid, systems[sid], "fit") * REF_WEIGHT.get(name, 1.0)
                                                 for sid, name in specs], label="references",
                                     # resumable per (system, reference); keyed by the evaluator code too, so a resume after a code change
                                     # recomputes (a packed job's own reference cache writes are never committed)
                                     keys=[f"ref|{args.ref_code_key}|{sid}|{name}" for sid, name in specs],
                                     done_dir=round_dir / "_done" / "references")
                per = {sid: {"results": {}, "errors": {}, "meta": {}} for sid in todo}
                for (sid, name), r in zip(specs, res):
                    why = infra_failure(r)
                    if why:
                        infra.append({"stage": "references", "sid": sid, "name": name, "why": why})
                        per[sid]["infra"] = True
                        continue
                    out = (r or {}).get("result") if isinstance(r, dict) else None
                    if not isinstance(out, dict):
                        per[sid]["errors"][name] = str((r or {}).get("error") if isinstance(r, dict) else r)[-500:]
                        continue
                    per[sid]["results"].update(out.get("results") or {})
                    per[sid]["errors"].update(out.get("errors") or {})
                    per[sid]["meta"] = per[sid]["meta"] or {k: out.get(k) for k in meta_keys}
                for sid in todo:
                    rr[sid], rm[sid] = per[sid]["results"], per[sid]["meta"]
            else:
                res = be.call("brainir_causal.harness:references_job", [[job_of(sid, REF_JOB_NAMES)] for sid in todo], cls="eval_l",
                              timeout_s=args.timeout, threads=4, reload=["fit", "eval", "store"], commit=["eval"])
                for sid, r in zip(todo, res):
                    why = infra_failure(r)
                    if why:
                        infra.append({"stage": "references", "sid": sid, "why": why})
                        rr[sid], rm[sid] = {}, {}
                        continue
                    out = (r or {}).get("result") if isinstance(r, dict) else None
                    rr[sid] = (out or {}).get("results") or {}
                    rm[sid] = {k: (out or {}).get(k) for k in meta_keys} if isinstance(out, dict) else {}
            bad = {x["sid"] for x in infra if x["stage"] == "references"}
            for sid in todo:
                if sid in bad:                      # never store a partial reference set: a rerun recomputes this system's references
                    continue
                with open(rdir / f"{SU._safe(sid)}.pkl", "wb") as fh:
                    pickle.dump({"results": rr[sid], "meta": rm[sid]}, fh, protocol=pickle.HIGHEST_PROTOCOL)
            return rr, rm

        infra: list = report.setdefault("infrastructure_failures", [])     # appended by every stage (list.append is thread-safe)
        ref_ex = ThreadPoolExecutor(max_workers=1)
        ref_future = ref_ex.submit(run_references)

        # ---- fits (+ Level C refits): skip any already on disk (idempotent resume) unless --refit; packed, longest-first
        fit_specs = [(m, sid, seed, None) for m in all_methods for sid in systems for seed in seeds]
        if level == "C":
            fit_specs += [(m, sid, seeds[0], b) for m in all_methods for sid in systems for b in range(N_REFITS)]
        fit_recs = [None] * len(fit_specs)
        staged_refs: list = []                    # every staged artefact of the round (retention: cleared at the end)
        by_cls: dict = {}
        for i, (m, sid, seed, b) in enumerate(fit_specs):
            sub, rel = ("refits", f"{SU._safe(sid)}_b{b}") if b is not None else ("fits", f"{SU._safe(sid)}_s{seed}")
            out = round_dir / method_key(m) / sub / f"{rel}.pkl"
            if out.exists() and not args.refit:
                fit_recs[i] = {"ok": True, "cached": True}
                continue
            job = {"method": m, "systems": [sid], "data": [paths[sid]["fit_data"]], "seed": seed, "config": {}, "threads": 3,
                   "timeout_s": args.timeout}
            if b is not None:
                job["bootstrap"] = b
            cls = gpu_fit_cls if devices.get(m) == "cuda" else fit_cls
            by_cls.setdefault(cls, []).append((i, {"role": "fit", "job": job, "methods_key": key, "reload": ["fit"]}))
        for cls, items in sorted(by_cls.items()):
            idx = [i for i, _ in items]
            exp = [_expected_s(round_dir, *fit_specs[i][:2], systems[fit_specs[i][1]], "fit", fit_specs[i][2]) for i in idx]
            keys = [f"fit|{fit_specs[i][0]}|{fit_specs[i][1]}|s{fit_specs[i][2]}|b{fit_specs[i][3]}" for i in idx]
            for i, r in zip(idx, run_iso_group(be, [p for _, p in items], cls, exp, keys, f"fits:{cls}")):
                m, sid, seed, b = fit_specs[i]
                why = infra_failure(r)
                if why:                             # never the method's fit failure: not stored, the round is incomplete
                    infra.append({"stage": "fits", "method": m, "sid": sid, "seed": seed, "boot": b, "why": why})
                    fit_recs[i] = {"ok": False, "infrastructure": why}
                    continue
                sub, rel = ("refits", f"{SU._safe(sid)}_b{b}") if b is not None else ("fits", f"{SU._safe(sid)}_s{seed}")
                out = round_dir / method_key(m) / sub / f"{rel}.pkl"
                out.parent.mkdir(parents=True, exist_ok=True)
                model = None
                if isinstance(r, dict) and isinstance(r.get("model"), bytes):
                    model = r["model"]
                elif isinstance(r, dict) and isinstance(r.get("model_ref"), dict):
                    model = stage_fetch(be, r["model_ref"], staged_refs)      # staged: too large to return inline
                ok = model is not None
                if ok:
                    out.write_bytes(model)
                    out.with_suffix(".json").write_text(json.dumps(r.get("side") or {}, indent=1, default=str) + "\n", encoding="utf-8",
                                                        newline="\n")
                fit_recs[i] = {"ok": ok, **({} if ok else {"error": str((r or {}).get("error") if isinstance(r, dict) else r)[-2000:]})}
        # ---- evaluations (model workers; the model bytes go from the fit results to the payloads): skip cached, packed, longest-first.
        # They do not read the references (harness.evaluate_job never touches the reference cache), so they run while the references
        # are still running; the wait for the references comes after the evaluations and the loops.
        method_evals: dict = {m: {sd: {} for sd in seeds} for m in all_methods}
        ev_specs, ev_payloads = [], []
        for m in all_methods:
            for sid in systems:
                for sd in seeds:
                    mp = round_dir / method_key(m) / "fits" / f"{SU._safe(sid)}_s{sd}.pkl"
                    if not mp.exists():
                        continue
                    ep = round_dir / method_key(m) / "evals" / f"{SU._safe(sid)}_s{sd}.pkl"
                    if ep.exists() and not args.refit:
                        with open(ep, "rb") as fh:
                            method_evals[m][sd][sid] = pickle.load(fh)
                        continue
                    p = paths[sid]
                    j = base_eval_job({**systems[sid], **p}, sid, store_root="/tmp/p4m/evalstore",
                                      ref_cache=modal_ref_cache(args, p['heldout_tier']), gen=gen, lift=not args.no_lift, n_boot=args.n_boot)
                    j.update({"store_read_roots": [SU.REMOTE["eval_store"], SU.REMOTE["store"]], "seed": sd})
                    ev_specs.append((m, sid, sd))
                    ev_payloads.append({"role": "eval", "job": j, "methods_key": key, **model_field(be, mp.read_bytes(), staged_refs),
                                        "reload": ["fit", "eval", "store"]})
        if ev_payloads:
            exp = [_expected_s(round_dir, m, sid, systems[sid], "eval", sd) for (m, sid, sd) in ev_specs]
            keys = [f"eval|{args.ref_code_key}|{m}|{sid}|s{sd}" for (m, sid, sd) in ev_specs]     # + the evaluator code (resume)
            for (m, sid, sd), r in zip(ev_specs, run_iso_group(be, ev_payloads, eval_cls, exp, keys, "evaluations")):
                why = infra_failure(r)
                if why:                             # never the method's failed evaluation: not stored, the round is incomplete
                    infra.append({"stage": "evaluations", "method": m, "sid": sid, "seed": sd, "why": why})
                    continue
                ev = eval_of(be, r, sid, staged_refs)
                method_evals[m][sd][sid] = ev
                ep = round_dir / method_key(m) / "evals" / f"{SU._safe(sid)}_s{sd}.pkl"
                ep.parent.mkdir(parents=True, exist_ok=True)
                with open(ep, "wb") as fh:
                    pickle.dump(ev, fh, protocol=pickle.HIGHEST_PROTOCOL)
        # ---- loops (PROTOCOL 5.17): finalists / full, PACKED on Modal, then packed checkpoint evaluations
        if args.loops and args.stage in ("finalists", "full"):
            report["loops"] = run_loops_modal(be, args, methods, systems, key, paths, gen, loop_cls, round_dir, devices, gpu_fit_cls,
                                              staged_refs=staged_refs)
            infra.extend(report["loops"].pop("infrastructure_failures", []))
        refs_results, refs_meta = ref_future.result()
        ref_ex.shutdown(wait=True)
        report["modal"]["staged"] = {"n": len(staged_refs), "bytes": sum(int(x.get("size") or 0) for x in staged_refs),
                                     "removed": be.stage_clear(staged_refs) if staged_refs else 0}
        report["modal"]["cost"] = be.cost_summary()
    if report.get("infrastructure_failures"):
        # an INCOMPLETE round: infrastructure failures are never charged to a method, so the round is neither assembled nor decided; its
        # completed jobs are stored, and a rerun of the same command resumes the missing ones
        report["incomplete"] = True
        report["wall_s"] = round(time.time() - t_start, 1)
        H.dump({k: v for k, v in report.items() if k != "results"}, out_dir / "ROUND.json")
        print(json.dumps({"round": args.round, "INCOMPLETE": True, "infrastructure_failures": len(report["infrastructure_failures"]),
                          "first": report["infrastructure_failures"][:3], "action": "rerun the same command to resume"}, default=str),
              flush=True)
        return 3
    bounds = choose_bounds(refs_results, method_evals, systems)
    (out_dir / "BOUNDS.json").write_text(json.dumps(bounds, indent=1) + "\n", encoding="utf-8", newline="\n")
    assemble_round(args, report, all_methods, systems, method_evals, refs_results, bounds, round_dir, seeds, level, fit_specs, fit_recs,
                   out_dir, refs_meta=refs_meta)
    report["n_fit_failures"] = sum(1 for r in fit_recs if not (r or {}).get("ok"))
    report["devices"], report["bounds"] = devices, {k: bounds[k] for k in ("full_state", "id_shortcut")}
    report["wall_s"] = round(time.time() - t_start, 1)
    H.dump({k: v for k, v in report.items() if k != "results"}, out_dir / "ROUND.json")
    _log_row(args, methods, systems)
    print(json.dumps({"round": args.round, "fit_failures": report["n_fit_failures"], "wall_s": report["wall_s"]}), flush=True)
    return 0


def run_loops(args, methods: list[str], systems: dict, mdir: Path, round_dir: Path, tr, gen) -> dict:
    """PROTOCOL 5.17 loops run by the DRIVER (isolation.loop_job): the learner / own designer in a worker; reference designers and the
    magnitude-matched control (`random_matched`, from the method's own loop directory) trusted in the driver."""
    designers = [d for d in args.designers.split(",") if d]
    lseeds = [int(s) for s in args.loop_seeds.split(",") if s]
    n = 0
    fails = 0
    for m in methods:
        for sid, sysd in systems.items():
            budget = args.budget if not (sysd["kind"] == "real" and ":full" in sid) else min(args.budget, 100)
            # 'own' first (it provides the magnitude profile for random_matched)
            order = ([d for d in designers if d == "own"] + [d for d in designers if d not in ("own", "random_matched")]
                     + [d for d in designers if d == "random_matched"])
            for d in order:
                for s in lseeds:
                    out = round_dir / method_key(m) / "loops" / f"{SU._safe(sid)}_{d}_s{s}"
                    out.mkdir(parents=True, exist_ok=True)
                    job = {"method": m, "designer": d, "sid": sid, "data": [fit_data(sysd, sid)], "budget": budget,
                           "seed": s, "config": {}, "store_root": str(args.store_root), "internal_path": sysd["internal_path"],
                           "heldout_root": sysd["heldout_root"], "heldout_tier": sysd["heldout_tier"], "public_root": sysd["public_root"],
                           "public_tier": sysd["public_tier"], "generator": gen if sysd["kind"] == "synthetic" else None,
                           "timeout_s": args.timeout * 4}
                    if d == "random_matched":
                        job["profile_dir"] = str(round_dir / method_key(m) / "loops" / f"{SU._safe(sid)}_own_s{s}")
                    n += 1
                    try:
                        ISO.loop_job(job, tr, out_dir=out)
                    except Exception as e:  # noqa: BLE001
                        fails += 1
                        (out / "loop_error.json").write_text(json.dumps({"error": f"{type(e).__name__}: {e}"[:2000]}) + "\n", encoding="utf-8")
    return {"n_loops": n, "n_failed": fails, "designers": designers, "loop_seeds": lseeds}


def run_loops_modal(be, args, methods: list[str], systems: dict, key: str, paths: dict, gen, loop_cls: str, round_dir: Path,
                    devices: dict, gpu_fit_cls: str, staged_refs: list | None = None) -> dict:
    """PROTOCOL 5.17 loops on Modal, PACKED (isolation.loop_job in a slot's child driver; the learner / own designer in a model worker,
    the driver runs run_loop with DirectSim from the system context). 'own' and the reference designers run first; then 'random_matched'
    runs with the own loop's experiment profile. Checkpoint models (ckpt_*.pkl) are downloaded and evaluated PACKED (the frozen
    evaluator on each checkpoint: EE / SMS / k / lift of 5.17). Longest-first by system size; idempotent by the files already on disk."""
    from brainir_causal.p4modal.app import CLASSES
    staged_refs = staged_refs if staged_refs is not None else []
    designers = [d for d in args.designers.split(",") if d]
    lseeds = [int(s) for s in args.loop_seeds.split(",") if s]
    non_matched = [d for d in designers if d != "random_matched"]
    non_matched = [d for d in non_matched if d == "own"] + [d for d in non_matched if d != "own"]

    def loop_payload(m, sid, d, s, profile_files=None):
        sysd = systems[sid]
        p = paths[sid]
        budget = args.budget if not (sysd["kind"] == "real" and ":full" in sid) else min(args.budget, 100)
        job = {"method": m, "designer": d, "sid": sid, "data": [p["fit_data"]], "budget": budget, "seed": s, "config": {},
               "store_root": "/tmp/p4m/evalstore", "internal_path": p["internal_path"], "heldout_root": p["heldout_root"],
               "heldout_tier": p["heldout_tier"], "public_root": p["public_root"], "public_tier": p["public_tier"],
               "generator": gen if sysd["kind"] == "synthetic" else None, "timeout_s": args.timeout * 4,
               "store_read_roots": [SU.REMOTE["eval_store"], SU.REMOTE["store"]]}
        # a packed loop never commits (it reads eval / store and returns its files to the driver); the unpacked path commits eval
        commit = [] if CLASSES[loop_cls].get("slots") else ["eval"]
        pl = {"role": "loop", "job": job, "methods_key": key, "reload": ["fit", "eval", "store"], "commit": commit}
        if profile_files:
            pl["profile_files"] = profile_files
        return pl

    def run_group(specs, get_profile):
        payloads = [loop_payload(m, sid, d, s, get_profile(m, sid, s)) for (m, sid, d, s) in specs]
        exp = [_expected_s(round_dir, m, sid, systems[sid], "loop", s) for (m, sid, d, s) in specs]
        keys = [f"loop|{args.ref_code_key}|{m}|{sid}|{d}|s{s}" for (m, sid, d, s) in specs]
        res = (be.run_iso_packed(payloads, loop_cls, expected_s=exp, keys=keys, label="loops", done_dir=round_dir / "_done" / "loops")
               if CLASSES[loop_cls].get("slots") else be.run_iso(payloads, loop_cls, "loops"))
        n_fail = 0
        for (m, sid, d, s), r in zip(specs, res):
            out = round_dir / method_key(m) / "loops" / f"{SU._safe(sid)}_{d}_s{s}"
            out.mkdir(parents=True, exist_ok=True)
            why = infra_failure(r)
            if why:                                 # never the method's failed loop: no loop_error.json, the round is incomplete
                loop_infra.append({"stage": "loops", "method": m, "sid": sid, "designer": d, "seed": s, "why": why})
                continue
            if isinstance(r, dict) and (r.get("files") or r.get("file_refs")):
                for name, blob in (r.get("files") or {}).items():
                    (out / Path(name).name).write_bytes(blob)
                for name, ref in (r.get("file_refs") or {}).items():   # a large checkpoint model staged on the eval volume
                    (out / Path(name).name).write_bytes(stage_fetch(be, ref, staged_refs))
            else:
                n_fail += 1
                (out / "loop_error.json").write_text(json.dumps({"error": str((r or {}).get("error") if isinstance(r, dict) else r)[:2000]})
                                                     + "\n", encoding="utf-8")
        return n_fail

    loop_infra: list = []
    specs0 = [(m, sid, d, s) for m in methods for sid in systems for d in non_matched for s in lseeds]
    n_fail = run_group(specs0, lambda m, sid, s: None)
    # random_matched: profile from the method's OWN loop directory (its experiments.jsonl), if present
    matched_specs = []
    profiles = {}
    if "random_matched" in designers:
        for m in methods:
            for sid in systems:
                for s in lseeds:
                    exp_f = round_dir / method_key(m) / "loops" / f"{SU._safe(sid)}_own_s{s}" / "experiments.jsonl"
                    if exp_f.exists():
                        profiles[(m, sid, s)] = {"experiments.jsonl": exp_f.read_bytes()}
                        matched_specs.append((m, sid, "random_matched", s))
        n_fail += run_group(matched_specs, lambda m, sid, s: profiles.get((m, sid, s)))
    # checkpoint evaluations (frozen evaluator on each downloaded checkpoint), PACKED
    ck_specs, ck_payloads = [], []
    for m in methods:
        for sid in systems:
            for d in designers:
                for s in lseeds:
                    ld = round_dir / method_key(m) / "loops" / f"{SU._safe(sid)}_{d}_s{s}"
                    for ckpt in sorted(ld.glob("ckpt_*.pkl")):
                        p = paths[sid]
                        j = base_eval_job({**systems[sid], **p}, sid, store_root="/tmp/p4m/evalstore",
                                          ref_cache=modal_ref_cache(args, p['heldout_tier']), gen=gen, lift=not args.no_lift, n_boot=args.n_boot)
                        j.update({"store_read_roots": [SU.REMOTE["eval_store"], SU.REMOTE["store"]], "seed": s,
                                  "families": ["items", "micro", "stability", "lift"]})
                        ck_specs.append((m, sid, d, s, ckpt.name))
                        ck_payloads.append({"role": "eval", "job": j, "methods_key": key, **model_field(be, ckpt.read_bytes(), staged_refs),
                                            "reload": ["fit", "eval", "store"]})
    rows = []
    if ck_payloads:
        eval_cls = _pack_class("eval", False, args)
        exp = [_expected_s(round_dir, m, sid, systems[sid], "eval", s) for (m, sid, d, s, _) in ck_specs]
        keys = [f"ckeval|{args.ref_code_key}|{m}|{sid}|{d}|s{s}|{cn}" for (m, sid, d, s, cn) in ck_specs]
        res = (be.run_iso_packed(ck_payloads, eval_cls, expected_s=exp, keys=keys, label="checkpoint-evals",
                                 done_dir=round_dir / "_done" / "checkpoint-evals")
               if CLASSES[eval_cls].get("slots") else be.run_iso(ck_payloads, eval_cls, "checkpoint-evals"))
        for (m, sid, d, s, cn), r in zip(ck_specs, res):
            why = infra_failure(r)
            if why:                                 # never the method's failed checkpoint: no row, the round is incomplete
                loop_infra.append({"stage": "checkpoint-evals", "method": m, "sid": sid, "designer": d, "seed": s, "checkpoint": cn,
                                   "why": why})
                continue
            budget = int(cn.split("_")[1].split(".")[0])
            ev = eval_of(be, r, sid, staged_refs)          # the evaluate_job record {"sid", "kind", "result", ...} (or {"sid", "error"})
            ee = _ee_of(ev.get("result") if isinstance(ev, dict) and isinstance(ev.get("result"), dict) else None)
            row = {"system": sid, "method": m, "designer": d, "loop_seed": s, "budget": budget, "EE": ee}
            if isinstance(ev, dict) and ev.get("error"):
                row["error"] = str(ev["error"])[:500]
            rows.append(row)
            outp = round_dir / method_key(m) / "loops" / f"{SU._safe(sid)}_{d}_s{s}" / f"{cn}.eval.json"
            outp.write_text(json.dumps(row, default=str) + "\n", encoding="utf-8", newline="\n")
            with open(outp.with_suffix(".pkl"), "wb") as fh:           # the whole checkpoint evaluation (EE, SMS, k, lift of 5.17)
                pickle.dump(ev, fh, protocol=pickle.HIGHEST_PROTOCOL)
    (round_dir / "loops_rows.json").write_text(json.dumps(rows, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    return {"n_loops": len(specs0) + len(matched_specs), "n_failed": n_fail, "designers": designers, "loop_seeds": lseeds,
            "n_checkpoint_evals": len(rows), "packed": bool(CLASSES[loop_cls].get("slots")), "infrastructure_failures": loop_infra}


def _log_row(args, methods, systems) -> None:
    if args.tier in ("dev", "toy", "toyC") or args.no_log:
        return
    if not LOG.exists():
        LOG.write_text("# Level B evaluation log (causal_state_v1; PROTOCOL.md section 10)\n\n| time (UTC) | round | stage | tier | methods "
                       "| systems | result dir |\n|---|---|---|---|---|---|---|\n", encoding="utf-8", newline="\n")
    with open(LOG, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(f"| {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} | {args.round} | {args.stage} | {args.tier} | {', '.join(methods)} | "
                 f"{len(systems)} | research/phase4/tournament/{args.round}/ |\n")


# ================================================================================================================ decide / feedback
def _ref_values(out_dir: Path, ref_name: str) -> dict:
    """{sid: selection values} of a gate reference row file written by `assemble_round` (true_state.json / full_state_bound.json)."""
    p = out_dir / f"{ref_name}.json"
    if not p.exists():
        return {}
    r = json.loads(p.read_text(encoding="utf-8"))
    return {sid: (v.get("selection") or {}) for sid, v in (r.get("per_system") or {}).items() if v.get("selection")}


def _aggregate_view(r: dict) -> dict:
    """A method row in the shape `feedback.aggregate` reads: per system the SEED-AVERAGED selection values (pass fractions over the
    seeds; category = the modal category of the seeds, 'failed' when none) and the first seed's public result (for the medians)."""
    import collections
    ps = {}
    for sid, v in (r.get("per_system") or {}).items():
        sel = dict(v.get("seed_averaged") or {})
        cats = [c for c in (sel.get("categories") or []) if c]
        sel["category"] = collections.Counter(cats).most_common(1)[0][0] if cats else "failed"
        first = next(iter((v.get("seeds") or {}).values()), {}) or {}
        ps[sid] = {"kind": v.get("kind"), "selection": sel, "result": first.get("result")}
    return {**{k: r[k] for k in ("n_fit_failures", "n_eval_failures") if k in r}, "per_system": ps}


def decide_round(out_dir: Path, *, carried: str | None = None, finalists: int | None = None, n_boot: int = SEL.N_BOOT) -> dict:
    """PROTOCOL 10 on a finished round (review E, N1): the candidates' SEED-AVERAGED values (`seed_averaged` of <method>.json; the
    round's full fit-seed set), the gate references of true_state.json / full_state_bound.json, `select.rank` and `select.halve`;
    writes DECISION.json and the developer-facing aggregate. A round whose synthetic systems have no true-state reference row fails
    loudly (select.gates), never silently."""
    rnd = json.loads((out_dir / "ROUND.json").read_text(encoding="utf-8"))
    methods = list(rnd["methods"]) + [b for b in (rnd.get("baselines") or []) if b not in rnd["methods"]]
    cands, strata, n_seeds = {}, {}, {}
    for m in methods:
        p = out_dir / f"{method_key(m)}.json"
        if not p.exists():
            continue
        r = json.loads(p.read_text(encoding="utf-8"))
        avg = r.get("seed_averaged")
        if avg is None:
            raise SystemExit(f"{p.name} has no seed-averaged values (a round assembled before review E, N1): re-assemble the round")
        cands[m] = {sid: v for sid, v in avg.items() if v is not None}
        n_seeds[m] = len(r.get("seeds") or [])
        for sid, v in (r.get("per_system") or {}).items():
            strata[sid] = v.get("kind", "synthetic")
    true_state = _ref_values(out_dir, "true_state") or None
    full_bound = _ref_values(out_dir, "full_state_bound") or None
    rk = SEL.rank(cands, true_state=true_state, full_bound=full_bound, systems=strata, n_boot=n_boot)
    eligible = {m for m in rk["eligibility"] if rk["eligibility"][m].get("eligible")}
    decision = SEL.halve(rk["order"], set(rnd.get("baselines") or []), eligible=eligible, carried_baseline=carried, finalists=finalists)
    rep = {"round": rnd.get("round"), "suite": rnd.get("suite"), "order": rk["order"], "eligible_order": rk["eligible_order"],
           "any_eligible": rk["any_eligible"], "note": rk["note"], "gate_metric_medians": rk["gate_metric_medians"],
           "gates": rk["gates"], "decision": decision, "charged": rk["charged"], "n_fit_seeds": n_seeds,
           "references": {"true_state_systems": sorted(true_state or {}), "full_state_bound_systems": sorted(full_bound or {})},
           "pairwise": {a: {b: {k: v for k, v in c.items() if k != "details"} for b, c in row.items()} for a, row in rk["pairwise"].items()}}
    (out_dir / "DECISION.json").write_text(json.dumps(rep, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    full = {"round": rnd.get("round"), "suite": rnd.get("suite"), "eligibility": rk["eligibility"], "order": rk["order"],
            "results": {m: _aggregate_view(json.loads((out_dir / f"{method_key(m)}.json").read_text(encoding="utf-8"))) for m in methods
                        if (out_dir / f"{method_key(m)}.json").exists()}}
    FB.dump_json(FB.aggregate(full), out_dir / "AGGREGATE_developer_facing.json")
    return rep


def cmd_decide(args) -> int:
    rep = decide_round(Path(args.out_root) / args.round, carried=args.carried, finalists=args.finalists)
    print(json.dumps({"order": rep["order"], "keep": rep["decision"]["keep"], "note": rep["note"]}, indent=1))
    return 0


def cmd_feedback(args) -> int:
    rounds = [r for r in args.rounds.split(",") if r]
    tiers = {json.loads((Path(args.out_root) / r / "ROUND.json").read_text(encoding="utf-8")).get("suite") for r in rounds}
    aggs = [json.loads((Path(args.out_root) / r / "AGGREGATE_developer_facing.json").read_text(encoding="utf-8")) for r in rounds]
    try:
        ev = FB.release(aggs, args.out, tiers=tiers)
    except ValueError as e:
        raise SystemExit(f"feedback refused (F-M5): {e}") from None
    print(f"wrote {args.out} ({len(aggs)} rounds; system-set fingerprints {[a.get('system_ids_hash') for a in aggs]}; "
          f"release logged at {ev['released_utc']}, sha256 {ev['file_sha256'][:16]})")
    return 0


# ================================================================================================================ simulation service
def cmd_simserver(args) -> int:
    """An orchestrator-internal simulation service for a round (not used by the official loops, which the trusted driver runs):
    every simulation on the REFERENCE PLATFORM (`simdocker.DockerPool`, LOG P4-D32 / P4-D33), public restart sources from the
    tier's local public rows (`build_public_keys`; recomputed on demand)."""
    from brainir_causal.simdocker import DockerPool
    from brainir_causal.simservice import SimServer, build_public_keys
    systems = {}
    dirs = SU.tier_dirs(args.tier, Path(args.suites_root))
    syn_int = dirs["base"] / "internal_records.json"
    if syn_int.exists():
        systems.update(json.loads(syn_int.read_text(encoding="utf-8")))
    real_int = BENCH / "hidden" / "real_systems_internal.json"
    if real_int.exists():
        systems.update(json.loads(real_int.read_text(encoding="utf-8")))
    pub_dirs = [d for base in (dirs["public"], SU.REAL_SETS / "real_public" / "public") if base.exists()
                for d in sorted(base.iterdir()) if (d / "index.jsonl").exists()]
    pk = build_public_keys(pub_dirs, systems=set(systems))
    # salted tiers are not warmed: their seed is secret and the container's command line is recorded (docker_run.json)
    warm = [] if args.tier in SU.SALTED_TIERS else [(args.tier, SU.tier_seed(args.tier))]
    pool = DockerPool(store_root=SU.STORE, bridge_dir=RUN / args.round / "sim_bridge", bundle=SY.BUNDLE, workers=args.workers,
                      cpus=float(args.workers), warm=warm).start()
    try:
        SimServer(RUN / args.round / "sim", systems, SU.STORE, bundle=SY.BUNDLE, default_budget=args.budget, workers=args.workers,
                  ledger_dir=RUN / args.round / "sim_ledger", pool=pool, public_keys=pk).serve_forever()
    finally:
        pool.shutdown()
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--round", required=True)
    r.add_argument("--stage", choices=("pilot", "medium", "finalists", "full"), default="pilot")
    r.add_argument("--methods", required=True)
    r.add_argument("--baselines", default="")
    r.add_argument("--room", default=str(ROOM))
    r.add_argument("--tier", default="val")
    r.add_argument("--suites-root", default=str(SU.SUITES))
    r.add_argument("--real-root", default=str(SU.REAL_SETS))
    r.add_argument("--systems", default="")
    r.add_argument("--seeds", default="0,1,2", help="fit seeds (Level B: at least 3, PROTOCOL 10)")
    r.add_argument("--parallel", type=int, default=4)
    r.add_argument("--eval-workers", type=int, default=4)
    r.add_argument("--timeout", type=float, default=3600.0)
    r.add_argument("--n-boot", type=int, default=2000)
    r.add_argument("--no-lift", action="store_true")
    r.add_argument("--no-real", action="store_true")
    r.add_argument("--refit", action="store_true")
    r.add_argument("--store-root", default=str(SU.STORE))
    r.add_argument("--tolerances", default=None)
    r.add_argument("--no-log", action="store_true", help="smoke runs: no LEVELB_LOG row")
    r.add_argument("--out-root", default=str(OUT))
    r.add_argument("--run-root", default=str(RUN))
    r.add_argument("--backend", choices=("local", "modal"), default="modal")
    r.add_argument("--gpu-class", default="gpu_rtx6000", help="the round's ONE GPU class (iso_<class>) for methods declaring device 'cuda'")
    r.add_argument("--pack", dest="pack", action="store_true", default=True,
                   help="Modal: several isolated jobs per large container (default; research/phase4/LEVEL_B_EXECUTION.md)")
    r.add_argument("--no-pack", dest="pack", action="store_false", help="Modal: one job per container (the earlier unpacked path)")
    r.add_argument("--ref-cache-root", default="/evalvol/refcache",
                   help="Modal: the reference cache root on the eval volume (<root>/<tier>/<code key>; dry runs use their own root)")
    r.add_argument("--loops", action="store_true")
    r.add_argument("--designers", default="own,random,uniform,magnitude_sweep,greedy_error,structural,passive,fixed,random_matched")
    r.add_argument("--loop-seeds", default="0,1,2")
    r.add_argument("--budget", type=int, default=200)
    d = sub.add_parser("decide")
    d.add_argument("--round", required=True)
    d.add_argument("--finalists", type=int, default=None)
    d.add_argument("--carried", default=None)
    d.add_argument("--out-root", default=str(OUT))
    f = sub.add_parser("feedback")
    f.add_argument("--rounds", required=True)
    f.add_argument("--out", required=True)
    f.add_argument("--out-root", default=str(OUT))
    s = sub.add_parser("simserver")
    s.add_argument("--round", required=True)
    s.add_argument("--tier", default="val")
    s.add_argument("--suites-root", default=str(SU.SUITES))
    s.add_argument("--budget", type=int, default=10**7)
    s.add_argument("--workers", type=int, default=4)
    args = ap.parse_args(argv)
    return {"run": cmd_run, "decide": cmd_decide, "feedback": cmd_feedback, "simserver": cmd_simserver}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
