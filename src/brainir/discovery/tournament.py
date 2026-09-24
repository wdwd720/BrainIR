"""Synthetic tournament: run discovery methods on synthetic instances and score them against the hidden truth.

The truth files (``<suite>/truth/<instance>.json``) are read ONLY here, by the scorer; methods see the public instance
directory. Scoring is per (method, instance, network variant, seed):

    structural   recall / precision / Jaccard of the predicted core vs the truth core, and vs the BEST-matching sufficient
                 alternative (a method that finds a different valid implementation is not penalised);
                 success = every member of some sufficient alternative recovered (recall 1 vs that alternative)
    roles        fraction of predicted core neurons whose generic role matches the truth role (unknown never counts)
    essential    accuracy of essentiality claims against the simulation-verified truth (claims only)
    functional   keep-only of the predicted core passes the criterion on the TRUE simulator: nominal ensemble (fresh seeds),
                 robust ensemble (widened parameter sds), weight-noise ensemble — pass fractions
    minimality   |predicted| / |smallest sufficient alternative|; predicted members whose removal keeps the function
    budget       simulator calls, simulated seconds, wall time (from the method's own report)
    uncertainty  Brier score of inclusion probabilities against membership in the best-matching alternative

Runs are registered in the experiment registry; the per-run JSON keeps the prediction, the method's diagnostics and the scores.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np

from ..compute.registry import ExperimentRecord, artifact_record, content_hash, register_run
from .interface import DiscoveryResult, MethodRegistry
from .interventions import keep_only, silence
from .problem import DiscoveryProblem, pack_bundle, path_basename, unpack_bundle
from .simulator import RESERVED_SEED_FLOOR, BudgetedSimulator, BudgetExhausted, SimQuery, count_real_simulations


# ---------------------------------------------------------------------------- scoring
def _set_metrics(pred: set[int], truth: set[int]) -> dict:
    inter = pred & truth
    return {"recall": len(inter) / len(truth) if truth else None, "precision": len(inter) / len(pred) if pred else 0.0,
            "jaccard": len(inter) / len(pred | truth) if (pred | truth) else None, "n_pred": len(pred), "n_truth": len(truth)}


def score_structure(result: DiscoveryResult, truth_net: dict) -> dict:
    """Structural scores against the truth's sufficient alternatives: the planted ones plus any unplanted sufficient sets found by
    the suite audit (:mod:`brainir.discovery.suite_audit`). ``success`` counts either; ``success_planted`` only the planted ones."""
    core = set(int(p) for p in result.core)
    alts = [set(int(p) for p in a) for a in truth_net["alternatives_positions"]]
    unplanted = {frozenset(int(p) for p in a) for a in truth_net.get("unplanted_alternatives_positions", [])}
    vs_core = _set_metrics(core, set(truth_net["core_positions"]))
    per_alt = [_set_metrics(core, a) for a in alts]
    best_i = int(np.argmax([m["jaccard"] or 0 for m in per_alt])) if per_alt else 0
    best = per_alt[best_i] if per_alt else vs_core
    success = any(m["recall"] == 1.0 for m in per_alt)
    success_planted = any(m["recall"] == 1.0 for m, a in zip(per_alt, alts) if frozenset(a) not in unplanted)
    # uncertainty: Brier score of inclusion probabilities vs membership of the best alternative (over all candidates assessed)
    probs = result.inclusion_probability
    brier = None
    if probs:
        target = alts[best_i] if alts else set(truth_net["core_positions"])
        brier = float(np.mean([(float(q) - (1.0 if int(p) in target else 0.0)) ** 2 for p, q in probs.items()]))
    roles = truth_net.get("roles_positions", {})
    role_hits, role_n = 0, 0
    for p, (r, _q) in result.roles.items():
        if int(p) in core and str(p) in {str(k) for k in roles}:
            role_n += 1
            role_hits += int(r == roles.get(str(p), roles.get(p)))
    ess = truth_net.get("essential_positions", {})
    ess_hits, ess_n = 0, 0
    for p, v in result.essential.items():
        key = str(p)
        if v is not None and key in ess:
            ess_n += 1
            ess_hits += int(bool(v) == bool(ess[key]))
    smallest = min((len(a) for a in alts), default=len(truth_net["core_positions"]))
    return {"vs_core": vs_core, "vs_best_alternative": best, "best_alternative_index": best_i, "success": bool(success),
            "success_planted": bool(success_planted), "n_unplanted_alternatives": len(unplanted),
            "role_accuracy": (role_hits / role_n) if role_n else None, "n_roles_scored": role_n,
            "essential_accuracy": (ess_hits / ess_n) if ess_n else None, "n_essential_claims": ess_n,
            "size_ratio_vs_smallest_sufficient": (len(core) / smallest) if smallest else None, "brier_inclusion": brier,
            "n_alternatives_claimed": len(result.alternatives)}


MINIMALITY_MAX_CORE = 40


def causal_minimality(problem: DiscoveryProblem, sim: BudgetedSimulator, removable: list[int], seeds: list[int], *, sufficient: bool) -> dict:
    """Clarified minimality: a member that keep-only does not need is still causally justified when silencing it alone in the
    INTACT network destroys the function (a context member such as a lateral inhibitor, whose partner keep-only removes anyway).

    ``functional_success_causal`` = sufficient AND every member is keep-only-necessary or full-network-essential. Reported next to
    the pre-registered ``functional_success`` (sufficient AND 1-minimal under keep-only), never instead of it."""
    unjustified = []
    for p in removable:
        if sim.pass_fraction(silence([int(p)]), seeds) >= 0.5:
            unjustified.append(int(p))
    return {"context_members": [int(p) for p in removable if int(p) not in unjustified], "unjustified_members": unjustified,
            "functional_success_causal": bool(sufficient and not unjustified)}


def score_function(problem: DiscoveryProblem, result: DiscoveryResult, *, seeds: list[int], workers: int = 1, robust: bool = True) -> dict:
    """Keep-only of the predicted core on fresh seeds on the TRUE simulator: nominal pass fraction, 1-minimality (which members
    can be removed without losing the function) and, with ``robust``, widened-parameter and weight-noise ensembles.

    ``functional_success`` = the core is sufficient (nominal pass >= 0.5) AND 1-minimal (no single member removable): a valid
    compact mechanism even when it is not one the generator planted (goal3 section 8 defines the target this way; unplanted
    sufficient sets exist, e.g. a strongly driven hub under an activity-band criterion)."""
    core = [int(p) for p in result.core]
    sim = BudgetedSimulator(problem, max_calls=10 ** 9, workers=workers)
    out = {"nominal": None, "robust_sd_x2": None, "weight_noise_0.2": None, "minimality": None, "functional_success": False}
    if not core:
        return {**out, "nominal": 0.0}
    iv = keep_only(problem, core)
    out["nominal"] = sim.pass_fraction(iv, seeds)
    if len(core) <= MINIMALITY_MAX_CORE:
        removable = []
        if out["nominal"] >= 0.5 and len(core) > 1:
            for p in core:
                if sim.pass_fraction(keep_only(problem, [q for q in core if q != p]), seeds) >= 0.5:
                    removable.append(p)
        out["minimality"] = {"removable_members": removable, "n_removable": len(removable), "checked": bool(out["nominal"] >= 0.5)}
        out["functional_success"] = bool(out["nominal"] >= 0.5 and not removable)
        out.update(causal_minimality(problem, sim, removable, seeds, sufficient=out["nominal"] >= 0.5))
    if robust:
        cfg = problem.model_cfg
        wide = {"tau_sd": cfg.tau_sd * 2, "a_sd": cfg.a_sd * 2, "theta_sd": cfg.theta_sd * 2, "r_max_sd": cfg.r_max_sd * 2}
        out["robust_sd_x2"] = float(np.mean([o.passed for o in sim.evaluate(iv, seeds, cfg_override=wide)]))
        noisy = [keep_only(problem, core, weight_noise_sd=0.2, weight_noise_seed=1000 + s) for s in seeds]
        out["weight_noise_0.2"] = float(np.mean([sim.run(SimQuery(n, s)).passed for n, s in zip(noisy, seeds)]))
    out["verification_calls"] = sim.calls
    return out


# ---------------------------------------------------------------------------- running
def run_one(method_name: str, instance_dir: Path, network: str, *, budget: int, seed: int, config: dict | None, truth_path: Path | None,
            score_seeds: list[int], workers: int = 1, robust: bool = True, truth_json: bytes | None = None) -> dict:
    """One discovery run, then scoring. The method runs under :func:`brainir.discovery.guard.truth_guard` (no truth directory can be
    opened or listed); the truth is read only after the result exists. ``truth_json`` (remote jobs) replaces ``truth_path``, so no
    truth file exists on a worker's disk while the method runs (review E finding 7)."""
    from .guard import truth_guard
    from .provenance import runtime_env

    problem = DiscoveryProblem.from_bundle(instance_dir, network)
    sim = BudgetedSimulator(problem, max_calls=budget, workers=workers)
    method = MethodRegistry.get(method_name)
    cfg = {**method.default_config, **(config or {})}
    exhausted = False
    with count_real_simulations() as counter, truth_guard(None if truth_path is None else Path(truth_path).parent):
        t0, c0 = time.time(), time.process_time()
        try:
            result = method.discover(problem, sim, seed=seed, config=cfg)
        except BudgetExhausted:
            exhausted = True
            result = DiscoveryResult(core=[], diagnostics={"error": "budget exhausted before a result"})
        wall, cpu = time.time() - t0, time.process_time() - c0
    result.budget = {**sim.report(), "wall_s": round(wall, 2)}
    rec = {"method": method_name, "version": method.version, "instance": path_basename(instance_dir), "network": network, "seed": seed, "budget": budget,
           "config": cfg, "result": result.to_dict(), "wall_s": round(wall, 2), "discover_cpu_s": round(cpu, 2), "budget_exhausted": exhausted,
           "problem": problem.public_summary(), "env": runtime_env()}
    # budget integrity (review F finding 2): every real simulation during discover must have been charged; calls within budget;
    # the parameter seeds a method queries must stay out of the namespace reserved for scoring (finding 13)
    integrity = {"real_simulations": counter["n"], "charged_computed": sim.total_computed_calls(), "charged_calls": sim.total_calls(),
                 "budget": budget, "param_seeds": sim.report()["param_seeds"]}
    rec["integrity"] = integrity
    seeds_used = sim.param_seeds()
    reserved = set(int(s) for s in score_seeds)
    if workers == 1 and counter["n"] != integrity["charged_computed"]:
        rec["error"] = f"budget integrity: {counter['n']} real simulations but {integrity['charged_computed']} charged"
    elif sim.total_calls() > budget:  # every network's calls count (spawned simulators share the pool; review E finding 6)
        rec["error"] = f"budget integrity: {sim.total_calls()} calls exceed the budget {budget}"
    elif any(s >= RESERVED_SEED_FLOOR or s in reserved for s in seeds_used):
        rec["error"] = f"seed namespace: method queried reserved parameter seeds (max {max(seeds_used)})"
    if "error" in rec:
        rec["result"] = compact_result(rec["result"])
        return rec
    if truth_json is not None or (truth_path is not None and truth_path.exists()):
        ts = time.time()
        truth = json.loads(truth_json.decode("utf-8") if truth_json is not None else truth_path.read_text(encoding="utf-8"))
        tnet = truth["networks"][network]
        rec["structure"] = score_structure(result, tnet)
        rec["function"] = score_function(problem, result, seeds=score_seeds, workers=workers, robust=robust)
        rec["truth_family"] = truth["spec"]["family"]
        rec["truth_complications"] = truth["spec"].get("complications")
        perm = truth["networks"][network]["perm"]
        rec["truth_n"] = len(perm)
        # the core in the generator's canonical node frame: comparable across node-order variants of the same instance
        rec["core_canonical"] = sorted(int(perm[int(p)]) for p in result.core if 0 <= int(p) < len(perm))
        if "correspondence_positions" in truth or "identity_positions" in truth:
            rec.update(score_cross_claims(truth, network, result))
        rec["scoring_wall_s"] = round(time.time() - ts, 2)
    rec["result"] = compact_result(rec["result"])
    return rec


def score_cross_claims(truth: dict, network: str, result: DiscoveryResult) -> dict:
    """A single-network method run on one network of a synthetic PAIR: score the identity claims it makes about the other network
    (``diagnostics["cross_connectome"]``) against the pair's identity truth (review E finding 1)."""
    from .pair_tournament import identity_truth, score_identity_claims

    ids, hom = identity_truth(truth)
    claims = []
    for c in (result.diagnostics or {}).get("cross_connectome", []) or []:
        x, y = int(c["source_position"]), int(c["other_source_id"])  # synthetic pairs are tier A: source ids are positions
        claims.append((x, y, c.get("confidence")) if network == "a" else (y, x, c.get("confidence")))
    spec = truth.get("spec") or {}
    return {"cross_claims": score_identity_claims(claims, ids, hom, core_a=result.core if network == "a" else None),
            "pair_flags": {"shift": bool(spec.get("implementation_shift")), "null_pair": bool(spec.get("null_family")),
                           "structural_decoy": bool(spec.get("structural_decoy")), "decoy": bool(spec.get("anchor_decoy"))}}


def summarize_cross_claims(records: list[dict]) -> dict:
    """Per method, pooled over runs on pair instances: identity claims, precision, false claims by pair type, Brier score and a
    reliability diagram of the claim confidence."""
    from .pair_tournament import reliability_bins

    out: dict = {}
    for m in sorted({r["method"] for r in records if "cross_claims" in r}):
        rs = [r for r in records if r.get("method") == m and "cross_claims" in r]

        def tot(key, pred=lambda r: True, rs=rs):
            return int(sum(int(r["cross_claims"].get(key) or 0) for r in rs if pred(r)))

        confs = [(c, ok) for r in rs for c, ok in (r["cross_claims"].get("items") or []) if c is not None]
        n = tot("n_claimed")
        out[m] = {"n_runs": len(rs), "claims_total": n, "claims_correct": tot("n_correct"), "precision_pooled": (tot("n_correct") / n) if n else None,
                  "false_shift": tot("n_false", lambda r: r["pair_flags"]["shift"]), "false_null": tot("n_false", lambda r: r["pair_flags"]["null_pair"]),
                  "false_structural_decoy": tot("n_false", lambda r: r["pair_flags"]["structural_decoy"]),
                  "claims_on_null_pairs": tot("n_claimed", lambda r: r["pair_flags"]["null_pair"]),
                  "runs_with_claims": int(sum(1 for r in rs if r["cross_claims"]["n_claimed"])),
                  "recall_core_mean": _mean(rs, lambda r: r["cross_claims"].get("recall_core")) if any(
                      r["cross_claims"].get("recall_core") is not None for r in rs) else None,
                  "brier_pooled": float(np.mean([(c - float(ok)) ** 2 for c, ok in confs])) if confs else None,
                  "reliability": reliability_bins(confs)}
    return out


def run_calls(rec: dict) -> int | None:
    """Calls a run charged to its budget on every network (``total_calls``; older records only have ``calls``)."""
    b = (rec.get("result") or {}).get("budget") or {}
    v = b.get("total_calls", b.get("calls"))
    return None if v is None else int(v)


def compact_result(res: dict, *, top_inclusion: int = 100, max_diag_bytes: int = 4000) -> dict:
    """Storage form of a result dict (scores are computed from the full result before this): the inclusion probabilities of the
    top-``top_inclusion`` candidates (plus their count) and only the small diagnostic entries (large ones are replaced by their size)."""
    out = dict(res)
    inc = res.get("inclusion_probability") or {}
    if len(inc) > top_inclusion:
        top = sorted(inc.items(), key=lambda kv: -kv[1])[:top_inclusion]
        out["inclusion_probability"] = {int(k): float(v) for k, v in top}
        out["n_inclusion_assessed"] = len(inc)
    diag = {}
    for k, v in (res.get("diagnostics") or {}).items():
        s = json.dumps(v, default=str)
        diag[k] = v if len(s) <= max_diag_bytes else {"omitted_bytes": len(s)}
    out["diagnostics"] = diag
    return out


def run_one_job(args) -> dict:
    """Module-level wrapper for backends (one discovery run = one job).

    ``args`` = (method, instance_dir, network, budget, seed, config, truth_path, score_seeds, robust[, packs]). On a remote worker
    the instance directory does not exist; ``packs`` (a dict {instance name: pack_bundle dict, "truth/<name>.json": bytes}, usually a
    :class:`brainir.compute.Shared` payload) is then unpacked into a temporary directory first."""
    method_name, instance_dir, network, budget, seed, config, truth_path, score_seeds, robust = args[:9]
    packs = args[9] if len(args) > 9 else None
    name = path_basename(instance_dir)
    try:
        instance_dir = Path(instance_dir)
        truth_path = None if truth_path is None else Path(truth_path)
        truth_json = None
        if not instance_dir.exists() and packs is not None:
            import tempfile
            # only the instance goes to disk; the truth stays in memory until the result exists (review E finding 7)
            tmp = Path(tempfile.mkdtemp(prefix="brainir_job_"))
            unpack_bundle(packs[name], tmp / "inst" / name)
            instance_dir = tmp / "inst" / name
            if truth_path is not None:
                truth_json = packs.get(f"truth/{path_basename(truth_path)}")
                truth_path = None
        return run_one(method_name, instance_dir, network, budget=budget, seed=seed, config=config, truth_path=truth_path,
                       score_seeds=list(score_seeds), workers=1, robust=robust, truth_json=truth_json)
    except Exception as e:  # noqa: BLE001 - a failed run is a scored failure, identical locally and remotely (review F finding 1)
        import traceback
        return {"method": method_name, "instance": name, "network": network, "seed": seed, "budget": budget,
                "error": f"{type(e).__name__}: {e}"[:500], "traceback": traceback.format_exc()[-2000:]}


def pack_suite(suite_root: Path, inst_dirs: list[Path], networks: tuple[str, ...]) -> dict:
    """Everything remote tournament workers need: each instance's public files and its truth file. The requested networks are
    packed, plus every network of ANOTHER dataset in the instance (the other connectome of a synthetic pair), so a method sees
    the same bundle remotely as locally."""
    packs: dict = {}
    for d in inst_dirs:
        pack: dict[str, bytes] = {}
        wanted = [net for net in networks if (d / "networks" / net).exists()]
        if wanted:
            first = DiscoveryProblem.from_bundle(d, wanted[0])
            wanted += [x for x in first.other_dataset_networks() if x not in wanted]
        for net in wanted:
            pack.update(pack_bundle(d, net))
        packs[d.name] = pack
        t = Path(suite_root) / "truth" / f"{d.name}.json"
        if t.exists():
            packs[f"truth/{t.name}"] = t.read_bytes()
    return packs


def summarize(records: list[dict]) -> dict:
    """Aggregate per method: success rate, recall/precision, functional pass, calls, with bootstrap CIs on the success rate.

    Every ATTEMPTED run is in the success denominators: a run that failed (exception, timeout, budget-integrity or seed-namespace
    violation) counts as unsuccessful (review F finding 1); ``n_failed`` reports how many. Cost/size statistics use scored runs."""
    out: dict[str, dict] = {}
    rng = np.random.default_rng(0)
    for m in sorted({r["method"] for r in records if "method" in r}):
        rs = [r for r in records if r.get("method") == m and "structure" in r]
        failed = [r for r in records if r.get("method") == m and "structure" not in r]
        if not rs and not failed:
            continue
        zeros = [0.0] * len(failed)
        succ = np.array([r["structure"]["success"] for r in rs] + zeros, dtype=float)
        fsucc = np.array([bool((r.get("function") or {}).get("functional_success")) for r in rs] + zeros, dtype=float)
        either = np.maximum(succ, fsucc)
        boot = [rng.choice(succ, len(succ)).mean() for _ in range(2000)] if len(succ) > 1 else [succ.mean()]
        fboot = [rng.choice(fsucc, len(fsucc)).mean() for _ in range(2000)] if len(fsucc) > 1 else [fsucc.mean()]
        causal = [float(r["function"]["functional_success_causal"]) for r in rs if "functional_success_causal" in (r.get("function") or {})]
        out[m] = {"n_runs": len(rs) + len(failed), "n_scored": len(rs), "n_failed": len(failed),
                  "failures": [{"instance": r.get("instance"), "network": r.get("network"), "seed": r.get("seed"), "error": str(r.get("error"))[:200]}
                               for r in failed[:20]],
                  "success_rate": float(succ.mean()),
                  "success_ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
                  "success_planted_rate": float(np.mean([float(r["structure"].get("success_planted", r["structure"]["success"])) for r in rs] + zeros)),
                  "functional_success_rate": float(fsucc.mean()),
                  "functional_success_ci95": [float(np.percentile(fboot, 2.5)), float(np.percentile(fboot, 97.5))],
                  "functional_success_causal_rate": float(np.mean(causal + zeros)) if (causal or zeros) else None,
                  "success_or_functional_rate": float(either.mean()),
                  "recall_best_alt_median": _median(rs, lambda r: r["structure"]["vs_best_alternative"]["recall"]),
                  "precision_best_alt_median": _median(rs, lambda r: r["structure"]["vs_best_alternative"]["precision"]),
                  "functional_nominal_mean": _mean(rs, lambda r: (r.get("function") or {}).get("nominal")),
                  "functional_robust_mean": _mean(rs, lambda r: (r.get("function") or {}).get("robust_sd_x2")),
                  "calls_median": _median(rs, lambda r: run_calls(r)),
                  "calls_mean": _mean(rs, lambda r: run_calls(r) or 0),
                  "size_median": _median(rs, lambda r: len(r["result"]["core"])),
                  "role_accuracy_mean": _mean(rs, lambda r: r["structure"]["role_accuracy"]),
                  "brier_mean": _mean(rs, lambda r: r["structure"]["brier_inclusion"]),
                  "essential_accuracy_mean": _mean(rs, lambda r: r["structure"].get("essential_accuracy")),
                  "removable_fraction": _mean(rs, lambda r: None if not (r.get("function") or {}).get("minimality") else
                                              float(r["function"]["minimality"]["n_removable"] > 0)),
                  "simulated_seconds_median": _median(rs, lambda r: r["result"]["budget"].get("simulated_seconds")),
                  "identity_consistency": identity_consistency(rs),
                  "by_family": _by_family(rs)}
    return out


def identity_consistency(rs: list[dict]) -> dict:
    """Reliability across node orders x parameter draws x internal randomness (a node-order variant re-assigns the per-neuron
    parameter draws, so order and draw are confounded; review F finding 6): for every instance with >= 2 runs, the mean pairwise
    Jaccard of the runs' cores in the canonical frame, and whether all runs returned the identical set; averaged over instances.
    An empty core agrees with nothing (two empty cores score 0, not 1; review F finding 16)."""
    by_inst: dict[str, list[frozenset[int]]] = {}
    for r in rs:
        if "core_canonical" in r:
            by_inst.setdefault(r["instance"], []).append(frozenset(r["core_canonical"]))
    jac, same = [], []
    n_empty = sum(1 for cores in by_inst.values() for c in cores if not c)
    for cores in by_inst.values():
        if len(cores) < 2:
            continue
        pairs = [(a, b) for i, a in enumerate(cores) for b in cores[i + 1:]]
        jac.append(float(np.mean([len(a & b) / len(a | b) if (a | b) else 0.0 for a, b in pairs])))
        same.append(float(len(set(cores)) == 1 and bool(cores[0])))
    return {"n_instances": len(jac), "pairwise_jaccard_mean": float(np.mean(jac)) if jac else None,
            "identical_fraction": float(np.mean(same)) if same else None, "n_empty_cores": n_empty}


def _median(rs: list[dict], key_fn) -> float | None:
    vals = [v for v in (key_fn(r) for r in rs) if v is not None]
    return float(np.median(vals)) if vals else None


def _mean(rs: list[dict], key_fn) -> float | None:
    vals = [v for v in (key_fn(r) for r in rs) if v is not None]
    return float(np.mean(vals)) if vals else None


def _by_family(rs: list[dict]) -> dict:
    fams = sorted({r.get("truth_family", "?") for r in rs})
    return {f: {"n": sum(1 for r in rs if r.get("truth_family") == f),
                "success_rate": float(np.mean([r["structure"]["success"] for r in rs if r.get("truth_family") == f])),
                "functional_success_rate": float(np.mean([bool((r.get("function") or {}).get("functional_success")) for r in rs
                                                          if r.get("truth_family") == f])),
                "calls_median": float(np.median([run_calls(r) or 0 for r in rs if r.get("truth_family") == f]))} for f in fams}


SCORE_SEEDS = (5000, 5001, 5002, 5003)


def instance_spec(suite_root: Path, name: str) -> dict:
    """Family and size of an instance, from its PRIVATE truth file (names may be anonymised); falls back to parsing a readable name."""
    t = Path(suite_root) / "truth" / f"{name}.json"
    if t.exists():
        spec = json.loads(t.read_text(encoding="utf-8")).get("spec", {})
        n = spec.get("n_total") or max(int(spec.get("n_total_a") or 0), int(spec.get("n_total_b") or 0))
        return {"family": spec.get("family"), "n": int(n) if n else None, "complications": spec.get("complications")}
    parts = name.split("__")
    fam = parts[1] if parts[0] == "pair" and len(parts) > 1 else parts[0]
    size = next((p for p in parts if p.startswith("n") and p[1:].replace("x", "").isdigit()), None)
    n = max(int(x) for x in size[1:].split("x")) if size else None
    return {"family": fam, "n": n, "complications": None}


def select_instances(suite_root: Path | str, *, max_n: int | None = None, min_n: int | None = None, families=None) -> list[str]:
    """Instance names of a suite filtered by size / family (read from truth, so anonymised suites work)."""
    suite_root = Path(suite_root)
    out = []
    for d in sorted(p for p in (suite_root / "instances").iterdir() if p.is_dir()):
        s = instance_spec(suite_root, d.name)
        if max_n is not None and (s["n"] is None or s["n"] > max_n):
            continue
        if min_n is not None and (s["n"] is None or s["n"] < min_n):
            continue
        if families and s["family"] not in set(families):
            continue
        out.append(d.name)
    return out


def suite_hash(suite_root: Path, inst_dirs: list[Path]) -> str:
    """Content hash of the instances used (their manifests' bundle hashes) and of their truth files."""
    h = hashlib.sha256()
    for d in inst_dirs:
        man = d / "manifest.json"
        h.update(d.name.encode())
        h.update(man.read_bytes() if man.exists() else b"-")
        t = Path(suite_root) / "truth" / f"{d.name}.json"
        h.update(t.read_bytes() if t.exists() else b"-")
    return h.hexdigest()


def run_tournament(methods: list[str], suite_root: Path, *, instances: list[str] | None = None, networks: tuple[str, ...] = ("main",),
                   seeds: tuple[int, ...] = (0,), budget: int = 1000, configs: dict[str, dict] | None = None,
                   score_seeds: tuple[int, ...] = SCORE_SEEDS, backend=None, workers: int = 1, robust: bool = True, out_dir: Path | None = None,
                   registry_dir: Path | None = None, label: str = "tournament", allow_dirty: bool = False) -> dict:
    from .provenance import launch_provenance

    code = launch_provenance()
    if backend is not None and code["dirty_src"] and not allow_dirty:
        raise RuntimeError("refusing a remote campaign with uncommitted changes in src/ (the image is built from the working tree); "
                           "commit first or pass allow_dirty=True")
    suite_root = Path(suite_root)
    inst_dirs = sorted(p for p in (suite_root / "instances").iterdir() if p.is_dir())
    if instances:
        inst_dirs = [p for p in inst_dirs if p.name in set(instances)]
    jobs = []
    for m in methods:
        for d in inst_dirs:
            for net in networks:
                if not (d / "networks" / net).exists():
                    continue
                truth = str(suite_root / "truth" / f"{d.name}.json")
                for s in seeds:
                    jobs.append((m, str(d), net, budget, int(s), (configs or {}).get(m, {}), truth, list(score_seeds), robust))
    t0 = time.time()
    if backend is not None:
        from ..compute.backend import Shared, split_failures
        packs = pack_suite(suite_root, inst_dirs, networks)
        remote_jobs = [(*j, Shared("packs")) for j in jobs]
        records, failed = split_failures(backend.map(run_one_job, remote_jobs, shared={"packs": packs}))
        for f in failed:  # remote infrastructure failures (timeout, OOM): scored as failed runs
            j = jobs[f["index"]]
            records.append({"method": j[0], "instance": path_basename(j[1]), "network": j[2], "seed": j[4], "budget": j[3], "error": f["error"]})
    elif workers > 1 and len(jobs) > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=workers) as ex:
            records = list(ex.map(run_one_job, jobs))
    else:
        records = [run_one_job(j) for j in jobs]
    wall = time.time() - t0
    summary = summarize(records)
    bstats = backend.last_stats.to_dict() if backend is not None and backend.last_stats else {"backend": "local", "n_workers": workers}
    envs = {json.dumps({k: v for k, v in (r.get("env") or {}).items() if k != "blas_env"}, sort_keys=True) for r in records if r.get("env")}
    s_hash = suite_hash(suite_root, inst_dirs)
    out = {"label": label, "suite": suite_root.name, "suite_sha256": s_hash, "methods": methods, "n_jobs": len(jobs), "budget": budget,
           "seeds": list(seeds), "networks": list(networks), "score_seeds": list(score_seeds), "robust": robust, "wall_s": round(wall, 1),
           "backend": bstats, "code": code, "environments": [json.loads(e) for e in sorted(envs)], "summary": summary, "records": records}
    if any("cross_claims" in r for r in records):  # a pair suite: the identity claims each method made about the other network
        out["cross_claims"] = summarize_cross_claims(records)
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        p = out_dir / f"{label}.json"
        p.write_text(json.dumps(out, indent=1, default=_json_default) + "\n", encoding="utf-8", newline="\n")
        (out_dir / f"{label}.md").write_text(to_markdown(out), encoding="utf-8", newline="\n")
        if registry_dir is not None:
            rec = ExperimentRecord(name=label, config={"methods": methods, "budget": budget, "seeds": list(seeds), "networks": list(networks),
                                                       "configs": configs or {}, "instances": [d.name for d in inst_dirs],
                                                       "score_seeds": list(score_seeds), "robust": robust},
                                   seeds=list(seeds), inputs={"suite": suite_root.name, "suite_sha256": s_hash, "n_instances": len(inst_dirs),
                                                              "jobs_hash": content_hash(jobs), "source_tree_sha256": code["source_tree_sha256"],
                                                              "launched_utc": code["launched_utc"]},
                                   backend=out["backend"], artifacts={"results": artifact_record(p)}, code=code,
                                   environment={"remote": out["environments"]} if out["environments"] else {},
                                   summary={m: {k: v for k, v in s.items() if k not in ("by_family", "failures")} for m, s in summary.items()})
            register_run(rec, registry_dir)
    return out


def to_markdown(t: dict) -> str:
    lines = [f"# Synthetic tournament — {t['label']}", "",
             f"suite `{t['suite']}`; {t['n_jobs']} runs; budget {t['budget']} calls; seeds {t['seeds']}; networks {t['networks']}; "
             f"wall {t['wall_s']} s on {t['backend'].get('backend')}", "",
             "| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | "
             "recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | "
             "Brier | identity Jaccard / identical |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m, s in t["summary"].items():
        ci = s["success_ci95"]
        fci = s.get("functional_success_ci95", [float("nan")] * 2)
        ic = s.get("identity_consistency") or {}
        fmt = lambda v: "–" if v is None else f"{v:.2f}"  # noqa: E731
        runs = f"{s['n_runs']}" + (f" ({s['n_failed']} failed)" if s.get("n_failed") else "")
        lines.append(f"| {m} | {runs} | {s['success_rate']:.2f} [{ci[0]:.2f}, {ci[1]:.2f}] | "
                     f"{fmt(s.get('functional_success_rate'))} [{fci[0]:.2f}, {fci[1]:.2f}] | {fmt(s.get('functional_success_causal_rate'))} | "
                     f"{fmt(s.get('success_or_functional_rate'))} | {fmt(s['recall_best_alt_median'])} | "
                     f"{fmt(s['precision_best_alt_median'])} | {fmt(s['functional_nominal_mean'])} | {fmt(s['functional_robust_mean'])} | "
                     f"{fmt(s['calls_median'])} | {fmt(s['size_median'])} | {fmt(s['role_accuracy_mean'])} | {fmt(s['brier_mean'])} | "
                     f"{fmt(ic.get('pairwise_jaccard_mean'))} / {fmt(ic.get('identical_fraction'))} |")
    lines += ["", "runs = attempted runs; failed runs (errors, timeouts, budget-integrity or seed-namespace violations) count as unsuccessful.",
              "structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite "
              "audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal "
              "functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network."]
    lines += ["", "## By family (success rate / median calls)", ""]
    fams = sorted({f for s in t["summary"].values() for f in s["by_family"]})
    lines += ["| family | " + " | ".join(t["summary"]) + " |", "|---|" + "---|" * len(t["summary"])]
    for f in fams:
        cells = []
        for s in t["summary"].values():
            b = s["by_family"].get(f)
            cells.append("–" if b is None else f"{b['success_rate']:.2f} / {b['calls_median']:.0f} (n={b['n']})")
        lines.append(f"| {f} | " + " | ".join(cells) + " |")
    if t.get("cross_claims"):
        fmt = lambda v: "–" if v is None else f"{v:.2f}"  # noqa: E731
        lines += ["", "## Identity claims about the other network of each pair (review E)", "",
                  "A claim is correct only if both neurons are the same planted member; under an implementation shift only the retained "
                  "alternative counts; on a null pair every claim is false.", "",
                  "| method | runs (with claims) | claims (correct) | precision | false: shift / null / structural decoy | claims on null pairs | "
                  "core recall | Brier | reliability (bin: confidence -> observed, n) |", "|---|---|---|---|---|---|---|---|---|"]
        for m, c in t["cross_claims"].items():
            rel = "; ".join(f"{b['mean_confidence']:.2f}->{b['observed']:.2f} ({b['n']})" for b in c["reliability"]) or "–"
            lines.append(f"| {m} | {c['n_runs']} ({c['runs_with_claims']}) | {c['claims_total']} ({c['claims_correct']}) | {fmt(c['precision_pooled'])} | "
                         f"{c['false_shift']} / {c['false_null']} / {c['false_structural_decoy']} | {c['claims_on_null_pairs']} | "
                         f"{fmt(c['recall_core_mean'])} | {fmt(c['brier_pooled'])} | {rel} |")
    return "\n".join(lines) + "\n"


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)
