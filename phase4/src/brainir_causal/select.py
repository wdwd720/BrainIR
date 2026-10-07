"""Method selection at Level B (benchmarks/causal_state_v1/PROTOCOL.md section 10; goal5 sections 66-68). Implements THE RULE of
section 10 (review E, B5 and M7):

PER-SYSTEM VALUES. `per_system_values(verdict, result, ...)` extracts the selection inputs of one fitted model on one system (the
verdict criteria A-H, the gate metrics, the ranking criteria); `failed_system_values(kind)` stands for a failed fit or evaluation.
FAILURES are charged the worst admissible value, never dropped: class-balanced EE 10, SMS +1, ICG +1, observational NMSE 10,
experiment efficiency (an EE) 10, fit failure = not compact; simplicity and compute of a failed fit are charged the worst value any
candidate of the round attained on that system (in `rank`); a criterion pass value that failed, was untested (e.g. an untestable MEV)
or was not computed counts as NOT passing. Every charged value is counted and reported. `seed_average` averages the values of the
round's fit seeds per system (pass values -> the fraction of seeds that pass; numeric values -> the mean after charging; a seed without
a result for a system counts as a failure there).

1. GATES (`gates`): a candidate is ELIGIBLE when, on the round's synthetic systems, its pass rates of A, D and E are each at least half
   of the TRUE-STATE reference's pass rates on the SAME systems (recomputed per round), and on the round's real systems its pass rate
   of A is at least half of the full-state bound's. Pass rate = the mean over systems of the seed-averaged pass fraction. The gate
   systems of a kind are the round's systems of that kind on which the reference has a result; systems without one (e.g. a synthetic
   type without a true causal state) are excluded from both rates and counted. A kind absent from the round imposes no gate; a kind
   present without ANY reference result is an error (the gate cannot be evaluated, never silently passed or failed).
2. If NO candidate is eligible, all candidates are ordered by the gate metrics: median over the round's systems of the class-balanced
   EE, then median SMS, then median linear ICG_y (the verdict quantities `verdict["metrics"]` "EE", "SMS", "ICG_y" of PROTOCOL
   section 9; lower is better; exact ties pass to the next metric, then the name) and the note "no candidate meets the gates" is set;
   halving keeps the better half by this order.
3. Among ELIGIBLE candidates: lexicographic with tie bands over (4) compression (per system 1 if compact and, synthetic, k consistent
   with k_true (k_true <= k <= k_true + d_draw, LOG P4-D43), or
   a correct "no compact causal state" on a non-compressible type; mechanism systems are not judged on compactness and count 1;
   higher is better), (5) observational prediction (passive NMSE at the primary horizon), (6) experiment efficiency (the EE after 50
   loop experiments with the candidate's own designer, random if it has none; a tie for every pair while no loop has run in the round),
   (7) simplicity (total parameters), (8) compute (fit CPU + GPU seconds) (lower is better). a and b are TIED on a criterion when the
   two-sided 95 % percentile CI of the mean over systems of their paired difference includes 0. The CI comes from the RESCALED
   kind-stratified system bootstrap (`rescaled_boot_mean`: strata synthetic / real; each stratum's resampled deviations multiplied by
   sqrt(n_h / (n_h - 1)); a stratum of size 1 is never used: the bootstrap then runs unstratified over all systems, also rescaled).
   Ties pass to the next criterion. Pairwise outcomes need not be transitive: the order repeatedly takes the candidate that beats
   every remaining one, else the one with the most pairwise wins (Copeland count), then the deterministic fallback (the point estimates
   of (4)-(8) in order, the gate-metric medians, the name).
Eligible candidates always rank above ineligible ones, which follow in the gate-metric order.

SUCCESSIVE HALVING (`halve`): the better half (ceil) of the FULL order (eligible first), or the top `finalists`, plus the carried
baseline: the one given, else the best-ranked eligible baseline, else the best-ranked baseline (P3-D16).
"""

from __future__ import annotations

import collections
import json
import math
from pathlib import Path

import numpy as np

from .stats import Estimate, percentile_ci

ROOT = Path(__file__).resolve().parents[3]
BENCH = ROOT / "benchmarks" / "causal_state_v1"
PILOT_SEED = 20260926
N_BOOT = 2000
CI_LEVEL = 0.95
GATE_FRACTION = 0.5
GATE_CRITERIA = {"synthetic": ("A", "D", "E"), "real": ("A",)}
PASS_CRITERIA = ("A", "B", "C", "D", "E", "F", "G", "H")
#: gate metrics: (name here, key in verdict["metrics"], worst admissible value); lower is better
GATE_METRICS = (("EE", "EE", 10.0), ("SMS", "SMS", 1.0), ("ICG", "ICG_y", 1.0))
#: ranking criteria (4)-(8): (name, sign) with sign +1 = higher is better, -1 = lower is better
CRITERIA = (("compression", +1), ("observational", -1), ("efficiency", -1), ("simplicity", -1), ("compute", -1))
WORST = {"EE": 10.0, "SMS": 1.0, "ICG": 1.0, "compression": 0.0, "observational": 10.0, "efficiency": 10.0}
#: criteria whose worst admissible value is the worst value any candidate of the round attained on the system
EXTREMAL = ("simplicity", "compute")
NO_GATE_NOTE = "no candidate meets the gates"


# ================================================================================================================ pilot subset
def pilot_rule() -> dict:
    """The pre-registered pilot rule (fixed before any candidate exists)."""
    return {"seed": PILOT_SEED,
            "synthetic": "for each synthetic type of the val tier (sorted by the generator's type label), the system at position "
                         "rng.integers(n) of that type's systems sorted by opaque id, with rng = numpy default_rng(sha256('pilot|"
                         "<seed>|<type>'))",
            "real": "for each real network letter (sorted), the mechanism system at position rng.integers(n) of that network's "
                    "mechanism systems sorted by id, with rng = numpy default_rng(sha256('pilot-real|<seed>|<letter>'))"}


def _rng(*parts) -> np.random.Generator:
    import hashlib
    return np.random.default_rng(int(hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:16], 16))


def pilot_real(real_ids: list[str]) -> list[str]:
    """One mechanism system per real network (the rule of `pilot_rule`)."""
    by_net: dict[str, list[str]] = {}
    for sid in sorted(real_ids):
        parts = sid.split(":")
        if len(parts) == 3 and parts[2].startswith("m"):
            by_net.setdefault(parts[1], []).append(sid)
    return [mech[int(_rng("pilot-real", PILOT_SEED, net).integers(len(mech)))] for net, mech in sorted(by_net.items())]


def pilot_synthetic(types: dict[str, str]) -> list[str]:
    """One validation system per synthetic type ({system id: type label} of the val tier; the rule of `pilot_rule`)."""
    by_type: dict[str, list[str]] = {}
    for sid, t in types.items():
        by_type.setdefault(str(t), []).append(sid)
    return sorted(sids[int(_rng("pilot", PILOT_SEED, t).integers(len(sids)))] for t, sids in
                  ((t, sorted(v)) for t, v in sorted(by_type.items())))


def write_pilot_subset(real_ids: list[str], synthetic_types: dict[str, str] | None = None, *, public_path: Path | None = None,
                       hidden_path: Path | None = None) -> dict:
    """public/pilot_subset.json: the rule, its seed and the resolved REAL systems (opaque ids); once the val tier exists, the
    resolved synthetic systems go to hidden/pilot_subset_resolved.json (with their types) and the public file lists the opaque ids
    only."""
    public_path = public_path or BENCH / "public" / "pilot_subset.json"
    hidden_path = hidden_path or BENCH / "hidden" / "pilot_subset_resolved.json"
    rec = {"rule": pilot_rule(), "real": pilot_real(real_ids), "synthetic": None,
           "note": "PROTOCOL section 10: the Level B pilot = one validation system per synthetic type + one real mechanism per network"}
    if synthetic_types:
        syn = pilot_synthetic(synthetic_types)
        rec["synthetic"] = syn
        hidden_path.parent.mkdir(parents=True, exist_ok=True)
        hidden_path.write_text(json.dumps({"synthetic": {s: synthetic_types[s] for s in syn}, "real": rec["real"]}, indent=1) + "\n",
                               encoding="utf-8", newline="\n")
    public_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    return rec


# ================================================================================================================ bootstrap
def rescaled_boot_mean(values: dict[str, float], strata: dict[str, str] | None = None, n_boot: int = N_BOOT, seed: int = 0,
                       level: float = CI_LEVEL) -> Estimate:
    """Mean over systems with the RESCALED (stratified) bootstrap: within each stratum h (n_h systems) the resampled stratum mean's
    deviation from the observed one is multiplied by sqrt(n_h / (n_h - 1)), which removes the (n_h - 1) / n_h variance shrinkage of
    the naive bootstrap (review E, B6); the replicate is the n_h-weighted combination of the stratum means (= the mean over systems).
    A stratum of size 1 is never used: if any stratum has a single system, the bootstrap runs unstratified over all systems (also
    rescaled). Fewer than 2 systems: no CI (NaN bounds). Values must be finite (charge failures first)."""
    sids = sorted(values)
    v = np.array([float(values[s]) for s in sids], dtype=np.float64)
    n = len(v)
    if n == 0:
        return Estimate(float("nan"), [float("nan"), float("nan")], 0, None)
    if not np.isfinite(v).all():
        raise ValueError("rescaled_boot_mean got non-finite values; charge failures first")
    point = float(v.mean())
    if n < 2:
        return Estimate(point, [float("nan"), float("nan")], n, None)
    labels = np.array([str((strata or {}).get(s, "all")) for s in sids])
    groups = [np.flatnonzero(labels == lab) for lab in sorted(set(labels))]
    if len(groups) > 1 and min(len(g) for g in groups) < 2:
        groups = [np.arange(n)]
    rng = np.random.default_rng(seed)
    reps = np.zeros(n_boot)
    for idx in groups:
        nh = len(idx)
        vh = v[idx]
        mh = float(vh.mean())
        draws = vh[rng.integers(0, nh, size=(n_boot, nh))].mean(axis=1)
        reps += (nh / n) * (mh + math.sqrt(nh / (nh - 1)) * (draws - mh))
    return Estimate(point, percentile_ci(reps, level), n, reps)


# ================================================================================================================ per-system values
def _point(x) -> float | None:
    """The finite point value of a metric entry ({"point": ...} or a number), else None."""
    if isinstance(x, dict):
        x = x.get("point")
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _as_pass(p) -> bool | None:
    return True if p is True else (False if p is False else None)


def failed_system_values(kind: str = "synthetic", reason: str = "failed") -> dict:
    """The values charged for a failed fit or evaluation on one system (every pass value False, worst admissible metrics)."""
    return {"kind": kind, "failed": True, "reason": reason, **dict.fromkeys(PASS_CRITERIA, False), "EE": WORST["EE"], "SMS": WORST["SMS"],
            "ICG": WORST["ICG"], "compression": WORST["compression"], "observational": WORST["observational"], "efficiency": None,
            "simplicity": None, "compute": None, "category": "failed", "charged": ["EE", "SMS", "ICG", "compression", "observational"]}


def per_system_values(verdict: dict | None, result: dict | None, *, truth_k=None, efficiency: float | None = None,
                      kind: str = "synthetic", fit_compute: dict | None = None, truth_d_draw: int | None = None) -> dict:
    """The selection inputs of one (candidate or reference, system) from its verdict (`harness.system_verdict_for`: {"metrics",
    "verdict": {"criteria", "category"}}), its result (`harness.evaluate_model`), the loop efficiency (the EE after 50 experiments;
    None while no loop has run) and the fit's measured compute (the runner's side record 'compute': cpu_s, gpu_s). A missing or
    failed verdict / result gives `failed_system_values`. Keys: kind, failed, A-H (True / False / None), EE, SMS, ICG (gate metrics,
    the verdict quantities; charged when missing), compression, observational, efficiency, simplicity, compute, category, charged."""
    ver = verdict or {}
    res = result or {}
    v = ver.get("verdict") or {}
    if not v or ver.get("error") or res.get("error") or not isinstance(v.get("criteria"), dict):
        return failed_system_values(kind, reason=str(ver.get("error") or res.get("error") or "no verdict")[:200])
    crit = v["criteria"]
    out: dict = {"kind": kind, "failed": False}
    charged: list[str] = []
    for c in PASS_CRITERIA:
        out[c] = _as_pass((crit.get(c) or {}).get("pass"))
    metrics = ver.get("metrics") or {}
    for name, key, worst in GATE_METRICS:
        x = _point(metrics.get(key))
        if x is None:
            out[name] = worst
            charged.append(name)
        else:
            out[name] = x
    k = res.get("k")
    judged = bool(res.get("compact_judged", True))
    compact = ((metrics.get("dimension") or {}).get("compact"))
    comp = 1.0 if (not judged or compact is True) else 0.0
    if kind == "synthetic" and truth_k is not None:
        declared = bool((res.get("abstain") or {}).get("no_compact_state"))
        if str(truth_k) == "none":
            comp = 1.0 if declared else 0.0
        else:
            try:
                # k CONSISTENT with the truth: k_true <= k <= k_true + d_draw (LOG P4-D43; d_draw 0 when the generator reports none)
                k_ok = k is not None and int(truth_k) <= int(k) <= int(truth_k) + int(truth_d_draw or 0)
            except (TypeError, ValueError):
                k_ok = False
            comp = comp if (k_ok and not declared) else 0.0
    out["compression"] = comp
    obs = _point(((res.get("items") or {}).get("observational") or {}).get("obs_nmse_medium"))
    if obs is None:
        out["observational"] = WORST["observational"]
        charged.append("observational")
    else:
        out["observational"] = min(obs, WORST["observational"])
    if efficiency is None:
        out["efficiency"] = None
    else:
        e = _point(efficiency)
        out["efficiency"] = WORST["efficiency"] if e is None else min(e, WORST["efficiency"])
        if e is None:
            charged.append("efficiency")
    cap = res.get("capacity") or {}
    params = cap.get("params") or {}
    npar = params.get("total") if params.get("reported") else None
    if npar is None:
        cnt = cap.get("params_counted") or {}
        npar = cnt.get("total") if isinstance(cnt, dict) else None
    out["simplicity"] = _point(npar)
    comp_s = fit_compute or {}
    cs = [_point(comp_s.get(k_)) for k_ in ("cpu_s", "gpu_s")]
    cs = [c for c in cs if c is not None]
    out["compute"] = float(sum(cs)) if cs else None
    out["category"] = v.get("category")
    out["charged"] = charged
    return out


def seed_average(per_seed: dict) -> dict[str, dict]:
    """{seed: {system: per-system values}} -> {system: values averaged over the round's fit seeds}. A seed without a result for a
    system counts as a failure there. Pass values become the fraction of seeds passing (None / False = not passing); EE, SMS, ICG,
    compression and observational the mean over seeds (charged values included); efficiency, simplicity and compute the mean over the
    seeds that have them (None when none has). 'charged' counts the charged values over seeds; 'n_failed_seeds' the failed seeds."""
    seeds = sorted(per_seed)
    sids = sorted({s for sd in seeds for s in (per_seed[sd] or {})})
    out: dict[str, dict] = {}
    for sid in sids:
        kind = next((per_seed[sd][sid].get("kind") for sd in seeds if sid in (per_seed[sd] or {})), "synthetic")
        rows = [(per_seed[sd] or {}).get(sid) or failed_system_values(kind, reason="no result for this seed") for sd in seeds]
        avg: dict = {"kind": kind, "n_seeds": len(rows), "n_failed_seeds": sum(1 for r in rows if r.get("failed")),
                     "failed": all(r.get("failed") for r in rows)}
        for c in PASS_CRITERIA:
            avg[c] = float(np.mean([1.0 if r.get(c) is True else (float(r[c]) if isinstance(r.get(c), float) else 0.0) for r in rows]))
        for name in ("EE", "SMS", "ICG", "compression", "observational"):
            avg[name] = float(np.mean([float(r[name]) for r in rows]))
        for name in ("efficiency", "simplicity", "compute"):
            vals = [float(r[name]) for r in rows if r.get(name) is not None and math.isfinite(float(r[name]))]
            avg[name] = float(np.mean(vals)) if vals else None
        cnt = collections.Counter(c for r in rows for c in (r.get("charged") or []))
        avg["charged"] = dict(cnt)
        avg["categories"] = [r.get("category") for r in rows]
        out[sid] = avg
    return out


# ================================================================================================================ gates
def _frac(v) -> float:
    if v is True:
        return 1.0
    if v is None or v is False:
        return 0.0
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.0
    return x if math.isfinite(x) else 0.0


def gates(candidate: dict[str, dict], true_state: dict[str, dict] | None, full_bound: dict[str, dict] | None,
          systems: dict[str, str] | None = None) -> dict:
    """The gates of section 10 rule 1 for one candidate ({system: seed-averaged values}); references {system: values} (the
    TRUE-STATE reference on synthetic systems, the full-state bound on real systems); systems = the round's {system: kind} (default:
    the candidate's systems). Returns {"eligible", "kinds": {kind: {...rates, reference rates, thresholds, passes...}}}."""
    systems = systems or {s: v.get("kind", "synthetic") for s, v in candidate.items()}
    out = {"eligible": True, "kinds": {}}
    for kind, crits in GATE_CRITERIA.items():
        ref = true_state if kind == "synthetic" else full_bound
        ref_name = "true-state reference" if kind == "synthetic" else "full-state bound"
        sids = sorted(s for s, k in systems.items() if k == kind)
        if not sids:
            out["kinds"][kind] = {"applies": False, "n_systems": 0}
            continue
        gate_sids = [s for s in sids if (ref or {}).get(s) is not None]
        if not gate_sids:
            raise ValueError(f"no {ref_name} result on any of the round's {len(sids)} {kind} systems: the gate cannot be evaluated")
        cand = {s: candidate.get(s) or failed_system_values(kind, reason="no result") for s in gate_sids}
        rates = {c: float(np.mean([_frac(cand[s].get(c)) for s in gate_sids])) for c in crits}
        ref_rates = {c: float(np.mean([_frac(ref[s].get(c)) for s in gate_sids])) for c in crits}
        thr = {c: GATE_FRACTION * ref_rates[c] for c in crits}
        passes = {c: bool(rates[c] >= thr[c] - 1e-12) for c in crits}
        out["kinds"][kind] = {"applies": True, "n_systems": len(sids), "n_gate_systems": len(gate_sids),
                              "n_reference_missing": len(sids) - len(gate_sids), "reference": ref_name, "rates": rates,
                              "reference_rates": ref_rates, "thresholds": thr, "passes": passes,
                              "vacuous": [c for c in crits if ref_rates[c] == 0.0]}
        out["eligible"] = out["eligible"] and all(passes.values())
    return out


# ================================================================================================================ ranking
def _median(values: list[float]) -> float:
    return float(np.median(values)) if values else float("inf")


def gate_metric_key(values: dict[str, dict], systems: list[str]) -> tuple:
    """(median EE, median SMS, median ICG) over the systems (charged values included); lower is better."""
    return tuple(_median([float(values[s][name]) for s in systems]) for name, _, _ in GATE_METRICS)


def _criterion_table(filled: dict[str, dict[str, dict]], systems: dict[str, str], loops_ran: bool) -> tuple[dict, dict]:
    """({criterion: {candidate: {system: value}}} with failures charged, {candidate: {criterion: charged count}})."""
    table: dict[str, dict[str, dict[str, float]]] = {}
    charged: dict[str, collections.Counter] = {m: collections.Counter() for m in filled}
    for crit, _ in CRITERIA:
        table[crit] = {m: {} for m in filled}
        if crit == "efficiency" and not loops_ran:
            continue
        if crit in EXTREMAL:
            worst_by_sys = {}
            for s in systems:
                vals = [filled[m][s].get(crit) for m in filled if filled[m][s].get(crit) is not None]
                if vals:
                    worst_by_sys[s] = max(float(x) for x in vals)
            for m in filled:
                for s in systems:
                    x = filled[m][s].get(crit)
                    if s not in worst_by_sys:
                        continue                       # nobody has a value on this system: excluded for everyone
                    if x is None or not math.isfinite(float(x)):
                        table[crit][m][s] = worst_by_sys[s]
                        charged[m][crit] += 1
                    else:
                        table[crit][m][s] = float(x)
            continue
        for m in filled:
            for s in systems:
                x = filled[m][s].get(crit)
                if x is None or not math.isfinite(float(x)):
                    table[crit][m][s] = WORST[crit]
                    charged[m][crit] += 1
                else:
                    table[crit][m][s] = float(x)
    return table, {m: dict(c) for m, c in charged.items()}


def compare(a: str, b: str, table: dict, systems: dict[str, str], *, loops_ran: bool, n_boot: int = N_BOOT, seed: int = 0) -> dict:
    """a vs b on criteria (4)-(8) in order: {"winner": "a" | "b" | None, "criterion": name | None, "details": [...]}."""
    details = []
    for crit, sign in CRITERIA:
        if crit == "efficiency" and not loops_ran:
            details.append({"criterion": crit, "tie": True, "reason": "no loop has run in this round"})
            continue
        va, vb = table[crit][a], table[crit][b]
        common = sorted(set(va) & set(vb))
        if len(common) < 2:
            details.append({"criterion": crit, "tie": True, "reason": f"{len(common)} system(s) with values"})
            continue
        est = rescaled_boot_mean({s: va[s] - vb[s] for s in common}, {s: systems[s] for s in common}, n_boot, seed)
        lo, hi = est.ci95
        if not (math.isfinite(lo) and math.isfinite(hi)):
            details.append({"criterion": crit, "tie": True, "diff": est.point, "reason": "no CI"})
            continue
        a_wins = (lo > 0) if sign > 0 else (hi < 0)
        b_wins = (hi < 0) if sign > 0 else (lo > 0)
        details.append({"criterion": crit, "diff": est.point, "ci95": est.ci95, "n": len(common), "tie": not (a_wins or b_wins)})
        if a_wins or b_wins:
            return {"winner": "a" if a_wins else "b", "criterion": crit, "details": details}
    return {"winner": None, "criterion": None, "details": details}


def rank(candidates: dict[str, dict[str, dict]], *, true_state: dict[str, dict] | None = None, full_bound: dict[str, dict] | None = None,
         systems: dict[str, str] | None = None, n_boot: int = N_BOOT, seed: int = 0) -> dict:
    """THE RULE of PROTOCOL section 10. candidates: {name: {system: seed-averaged values (`seed_average`)}}; true_state /
    full_bound: {system: values} of the references (per_system_values of their verdicts); systems: the round's {system: kind}
    (default: the union of the candidates' systems; a candidate without a result on a round system is charged as failed there)."""
    if systems is None:
        systems = {}
        for ps in candidates.values():
            for s, v in ps.items():
                systems.setdefault(s, v.get("kind", "synthetic"))
    sids = sorted(systems)
    filled: dict[str, dict[str, dict]] = {}
    missing: dict[str, int] = {}
    for m, ps in candidates.items():
        filled[m] = {}
        missing[m] = 0
        for s in sids:
            if ps.get(s) is None:
                filled[m][s] = failed_system_values(systems[s], reason="no result for this system")
                missing[m] += 1
            else:
                filled[m][s] = ps[s]
    gate = {m: gates(filled[m], true_state, full_bound, systems) for m in sorted(filled)}
    gkey = {m: gate_metric_key(filled[m], sids) for m in filled}
    eligible = sorted(m for m in filled if gate[m]["eligible"])
    ineligible = sorted((m for m in filled if not gate[m]["eligible"]), key=lambda m: (*gkey[m], m))
    loops_ran = any(filled[m][s].get("efficiency") is not None for m in filled for s in sids)
    table, charged = _criterion_table(filled, systems, loops_ran)
    pairwise: dict[str, dict[str, dict]] = {}
    for i, a in enumerate(eligible):
        for b in eligible[i + 1:]:
            r = compare(a, b, table, systems, loops_ran=loops_ran, n_boot=n_boot, seed=seed)
            pairwise.setdefault(a, {})[b] = r
            pairwise.setdefault(b, {})[a] = {**r, "winner": {"a": "b", "b": "a", None: None}[r["winner"]]}

    def fallback(m: str) -> tuple:
        pts = []
        for crit, sign in CRITERIA:
            vals = list(table[crit][m].values())
            pts.append(-sign * float(np.mean(vals)) if vals else 0.0)
        return (*pts, *gkey[m], m)

    def beats(x: str, y: str) -> bool:
        return pairwise.get(x, {}).get(y, {}).get("winner") == "a"

    order_elig: list[str] = []
    remaining = list(eligible)
    while remaining:
        dominant = [x for x in remaining if all(beats(x, y) for y in remaining if y != x)]
        if dominant:
            pick = min(dominant, key=fallback)
        else:
            wins = {x: sum(beats(x, y) for y in remaining if y != x) for x in remaining}
            best = max(wins.values())
            pick = min((x for x in remaining if wins[x] == best), key=fallback)
        order_elig.append(pick)
        remaining.remove(pick)
    charged_total = {}
    for m in filled:
        cnt: collections.Counter = collections.Counter()
        for s in sids:
            ch = filled[m][s].get("charged") or {}
            cnt.update(ch if isinstance(ch, dict) else collections.Counter(ch))
        cnt.update(charged.get(m) or {})
        charged_total[m] = {"values": dict(cnt), "systems_without_result": missing[m],
                            "failed_systems": sum(1 for s in sids if filled[m][s].get("failed"))}
    return {"order": order_elig + ineligible, "eligible_order": order_elig, "ineligible_order": ineligible,
            "any_eligible": bool(eligible), "note": None if eligible else NO_GATE_NOTE, "gates": gate,
            "eligibility": {m: {"eligible": gate[m]["eligible"], **gate[m]} for m in gate},
            "gate_metric_medians": {m: dict(zip([n for n, _, _ in GATE_METRICS], gkey[m], strict=True)) for m in gkey},
            "loops_ran": loops_ran, "pairwise": pairwise, "charged": charged_total, "systems": dict(systems)}


def halve(order: list[str], baselines, *, eligible=None, carried_baseline: str | None = None, finalists: int | None = None) -> dict:
    """The candidates kept for the next round: the better half (ceil) of the FULL order (eligible candidates first; when none is
    eligible, by the gate metrics), or the top `finalists`, plus the carried baseline (the one given, else the best-ranked eligible
    baseline, else the best-ranked baseline)."""
    bl = set(baselines or [])
    elig = set(eligible or [])
    n_keep = finalists if finalists is not None else math.ceil(len(order) / 2)
    keep = list(order[:n_keep])
    best = carried_baseline or next((m for m in order if m in bl and m in elig), None) or next((m for m in order if m in bl), None)
    if best is not None and best in order and best not in keep:
        keep.append(best)
    return {"keep": keep, "dropped": [m for m in order if m not in keep], "carried_baseline": best,
            "carried_eligible": (best in elig) if best is not None else None}
