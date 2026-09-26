"""Method selection at Level B (benchmarks/causal_state_v1/PROTOCOL.md section 10; goal5 sections 66-68).

ELIGIBILITY (goal5 section 68 gates 1-3): a candidate is eligible when, over the round's systems, criterion A passes on >= 50 %, D on
>= 40 % and E on >= 40 % (a criterion that is untested or fails counts as not passing; a non-binding D / E criterion counts as its
own pass value). A method that predicts passive dynamics well but fails the gates cannot win.

RANKING among eligible candidates (no single scalar): lexicographic over
    (4) compression        per system 1 if the model is compact (full / synthetic systems) and, synthetic, k = k_true; else 0 (higher)
    (5) observational      passive readout NMSE at the primary horizon (lower)
    (6) experiment eff.    the candidate's EE after 50 loop experiments with its own designer (random if it has none) (lower)
    (7) simplicity         total parameters (encoder + transition + read-in + readout) (lower)
    (8) compute            fit CPU + GPU seconds (lower)
with TIE BANDS: candidate a beats b on a criterion only when the paired, type-stratified system-bootstrap CI of the per-system
difference excludes 0 in a's favour; otherwise they are tied there and the next criterion decides. A criterion with missing values for
either candidate on a system is compared on the systems both have; with fewer than 3 common systems it is a tie. When every criterion
ties, the point estimate of (4), then (5), then the name decide (deterministic). Pairwise comparisons need not be transitive; the order
is built by repeatedly picking the candidate that beats every other remaining candidate on the first deciding criterion, falling back
to the most pairwise wins (Copeland count), then the deterministic tie-break.

SUCCESSIVE HALVING (PROTOCOL section 10): pilot (the pre-registered subset: one validation system per synthetic type plus one real
mechanism per network, `pilot_subset`) -> keep the better half (ceil) of the eligible ranked candidates -> medium (all validation
systems + all real mechanisms) -> finalists (top 3 + the best baseline) -> full public confirmation. The best-ranked ELIGIBLE baseline
of the pilot is carried into every later round as the comparator even when halving would drop it (the Phase 3 rule P3-D16);
ineligible candidates never advance.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from .stats import paired_system_boot

ROOT = Path(__file__).resolve().parents[3]
BENCH = ROOT / "benchmarks" / "causal_state_v1"
PILOT_SEED = 20260926
GATES = {"A": 0.5, "D": 0.4, "E": 0.4}
CRITERIA = (("compression", +1), ("observational", -1), ("efficiency", -1), ("simplicity", -1), ("compute", -1))
MIN_COMMON = 3


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


# ================================================================================================================ gates and ranking
def _pass(v) -> bool:
    return bool(v is True)


def eligibility(per_system: dict[str, dict]) -> dict:
    """per_system: {system id: {"A": pass, "D": pass, "E": pass, ...}} (criterion pass values: True / False / None) -> the gate
    fractions and the eligibility."""
    n = len(per_system)
    frac = {c: (sum(_pass(v.get(c)) for v in per_system.values()) / n if n else 0.0) for c in GATES}
    return {"n_systems": n, "fractions": frac, "eligible": bool(n > 0 and all(frac[c] >= GATES[c] for c in GATES))}


def _criterion_values(per_system: dict[str, dict], crit: str) -> dict[str, float]:
    out = {}
    for sid, v in per_system.items():
        x = v.get(crit)
        if x is None:
            continue
        x = float(x)
        if np.isfinite(x):
            out[sid] = x
    return out


def compare(a: dict[str, dict], b: dict[str, dict], strata: dict | None = None, n_boot: int = 2000, seed: int = 0) -> dict:
    """a vs b on the ranking criteria in order: {"winner": "a" | "b" | None, "criterion": name | None, "details": [...]}."""
    details = []
    for crit, sign in CRITERIA:
        va, vb = _criterion_values(a, crit), _criterion_values(b, crit)
        common = sorted(set(va) & set(vb))
        if len(common) < MIN_COMMON:
            details.append({"criterion": crit, "tie": True, "reason": f"{len(common)} common systems"})
            continue
        est = paired_system_boot({s: va[s] for s in common}, {s: vb[s] for s in common}, strata, n_boot, seed)
        lo, hi = est.ci95
        # sign +1: higher is better (a wins when the CI of a - b is above 0); -1: lower is better
        a_wins = (lo > 0) if sign > 0 else (hi < 0)
        b_wins = (hi < 0) if sign > 0 else (lo > 0)
        details.append({"criterion": crit, "diff": est.point, "ci95": est.ci95, "n": len(common), "tie": not (a_wins or b_wins)})
        if a_wins or b_wins:
            return {"winner": "a" if a_wins else "b", "criterion": crit, "details": details}
    return {"winner": None, "criterion": None, "details": details}


def _fallback_key(name: str, per_system: dict[str, dict]) -> tuple:
    comp = _criterion_values(per_system, "compression")
    obs = _criterion_values(per_system, "observational")
    return (-(np.mean(list(comp.values())) if comp else -np.inf), np.mean(list(obs.values())) if obs else np.inf, name)


def rank(candidates: dict[str, dict[str, dict]], strata: dict | None = None, n_boot: int = 2000, seed: int = 0) -> dict:
    """candidates: {name: per_system dict (criterion pass values and ranking values)}. Returns the eligibility of every candidate,
    the order of the eligible ones and the pairwise comparison table."""
    elig = {m: eligibility(ps) for m, ps in candidates.items()}
    ok = sorted(m for m, e in elig.items() if e["eligible"])
    table: dict[str, dict[str, dict]] = {}
    for i, a in enumerate(ok):
        for b in ok[i + 1:]:
            r = compare(candidates[a], candidates[b], strata, n_boot, seed)
            table.setdefault(a, {})[b] = r
            table.setdefault(b, {})[a] = {**r, "winner": {"a": "b", "b": "a", None: None}[r["winner"]]}
    order: list[str] = []
    remaining = list(ok)
    while remaining:
        def beats(x, y):
            return table.get(x, {}).get(y, {}).get("winner") == "a"
        dominant = [x for x in remaining if all(beats(x, y) or x == y for y in remaining)]
        if dominant:
            pick = dominant[0]
        else:
            wins = {x: sum(beats(x, y) for y in remaining if y != x) for x in remaining}
            best = max(wins.values())
            tied = [x for x in remaining if wins[x] == best]
            pick = min(tied, key=lambda x: _fallback_key(x, candidates[x]))
        order.append(pick)
        remaining.remove(pick)
    return {"eligibility": elig, "order": order, "pairwise": table}


def halve(order: list[str], baselines: set[str] | list[str], *, carried_baseline: str | None = None, finalists: int | None = None) -> dict:
    """The candidates kept for the next round: the better half (ceil) of the eligible order (or the top `finalists`), plus the
    carried best baseline (the best-ranked eligible baseline of the pilot)."""
    bl = set(baselines)
    n_keep = finalists if finalists is not None else math.ceil(len(order) / 2)
    keep = list(order[:n_keep])
    best_bl = carried_baseline or next((m for m in order if m in bl), None)
    if best_bl is not None and best_bl not in keep and best_bl in order:
        keep.append(best_bl)
    return {"keep": keep, "dropped": [m for m in order if m not in keep], "carried_baseline": best_bl}


# ================================================================================================================ per-system values
def per_system_values(verdict: dict, result: dict, *, truth_k=None, efficiency: float | None = None, kind: str = "synthetic",
                      fit_compute: dict | None = None) -> dict:
    """The selection inputs of one (candidate, system) from its verdict (harness.system_verdict_for), result
    (harness.evaluate_model) and the fit's measured compute (the runner's side record 'compute': cpu_s, gpu_s)."""
    v = (verdict or {}).get("verdict") or {}
    crit = v.get("criteria") or {}
    out = {c: (crit.get(c) or {}).get("pass") for c in ("A", "B", "C", "D", "E", "F", "G", "H")}
    for c in ("D", "E"):
        cc = crit.get(c) or {}
        if cc.get("binding") is False:
            out[c] = cc.get("pass")
    k = result.get("k")
    compact = (((verdict or {}).get("metrics") or {}).get("dimension") or {}).get("compact")
    judged = result.get("compact_judged", True)
    comp = 1.0 if (not judged or compact) else 0.0
    if kind == "synthetic" and truth_k is not None:
        comp = comp if (str(truth_k) == "none" and (result.get("abstain") or {}).get("no_compact_state")) or k == truth_k else 0.0
    out["compression"] = comp
    obs = (((result.get("items") or {}).get("observational") or {}).get("obs_nmse_medium") or {}).get("point")
    out["observational"] = obs
    out["efficiency"] = efficiency
    params = (result.get("capacity") or {}).get("params") or {}
    npar = params.get("total") if params.get("reported") else None
    if npar is None:
        cnt = (result.get("capacity") or {}).get("params_counted") or {}
        npar = cnt.get("total") if isinstance(cnt, dict) else None
    out["simplicity"] = float(npar) if npar is not None else None
    comp_s = fit_compute or {}
    cs = [float(comp_s[k_]) for k_ in ("cpu_s", "gpu_s") if comp_s.get(k_) is not None]
    out["compute"] = float(sum(cs)) if cs else None
    out["category"] = v.get("category")
    return out
