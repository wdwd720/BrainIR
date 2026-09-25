"""Paired comparison of two methods on the same synthetic tournament runs (SELECTION_PROTOCOL.md sections 3 and 5).

    uv run python scripts/compare_tournament_methods.py research/phase2/tournament/sel_v1_b1000.json \
        research/phase2/tournament/sel_mech_b1000_part{1,2,3}.json.gz --a brainir_v1 --b greedy_reference \
        --out research/phase2/tournament/cmp_v1_vs_greedy_reference_sel

Runs are paired on (instance, network, seed). A failed run counts as unsuccessful, with the full budget as its calls and 0 as its
robust pass. Reliability is identity consistency per instance (mean pairwise Jaccard of the canonical cores over all runs of
the instance, and whether they are all identical), computed for each method on the SAME runs. Every difference is A - B (calls:
calls saved = B - A), with a 95 % bootstrap CI that resamples instances. The pre-registered decision rule (section 5) is
evaluated: (a) A's success is not lower than B's (the CI of the structural-success difference does not lie entirely below 0);
(b) A is better on at least one of reliability, efficiency or robustness (a CI entirely above 0).
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np

from brainir.discovery.tournament import run_calls


def load_records(paths: list[Path]) -> tuple[list[dict], dict]:
    recs, budgets = [], {}
    for p in paths:
        p = Path(p)
        raw = gzip.open(p, "rt", encoding="utf-8").read() if p.suffix == ".gz" else p.read_text(encoding="utf-8")
        d = json.loads(raw)
        for r in d["records"]:
            r = dict(r)
            r.setdefault("budget", d.get("budget"))
            recs.append(r)
            budgets[r.get("method")] = d.get("budget")
    return recs, budgets


PER_RUN = {
    "structural_success": lambda r: float(r["structure"]["success"]),
    "causal_functional_success": lambda r: float(bool((r.get("function") or {}).get("functional_success_causal"))),
    "functional_success_preregistered": lambda r: float(bool((r.get("function") or {}).get("functional_success"))),
    "planted_success": lambda r: float(bool(r["structure"].get("success_planted"))),
    "robust_sd_x2": lambda r: (r.get("function") or {}).get("robust_sd_x2"),
    "robust_weight_noise": lambda r: (r.get("function") or {}).get("weight_noise_0.2"),
    "nominal_pass": lambda r: (r.get("function") or {}).get("nominal"),
    "core_size": lambda r: float(len(r["result"]["core"])),
    # reviews A / G: the mechanism the intact network uses
    "success_intact": lambda r: None if "success_intact" not in r["structure"] else float(bool(r["structure"]["success_intact"])),
    "essential_recall": lambda r: r["structure"].get("essential_recall"),
    "latent_backup_returned": lambda r: None if "latent_backup_returned" not in r["structure"] else float(bool(r["structure"]["latent_backup_returned"])),
    # adversarial trap suites only (third-party scorer, review G); reported, not part of the decision rule
    "adversarial_correct": lambda r: None if "adversarial" not in r else float(bool(r["adversarial"]["correct"])),
    "adversarial_confident_wrong": lambda r: None if "adversarial" not in r else float(bool(r["adversarial"]["confident_wrong"])),
}
FAILED = {"structural_success": 0.0, "causal_functional_success": 0.0, "functional_success_preregistered": 0.0, "planted_success": 0.0,
          "robust_sd_x2": 0.0, "robust_weight_noise": 0.0, "nominal_pass": 0.0, "core_size": None, "success_intact": 0.0, "essential_recall": 0.0,
          "latent_backup_returned": None, "adversarial_correct": 0.0, "adversarial_confident_wrong": None}


def _value(r: dict, metric: str):
    if "structure" not in r:
        return FAILED[metric]
    v = PER_RUN[metric](r)
    return None if v is None else float(v)


def _calls(r: dict, budget) -> float:
    if "structure" not in r:
        return float(budget or 0)
    return float(run_calls(r) or 0)


def _consistency(cores: list[frozenset]) -> tuple[float, float]:
    pairs = [(a, b) for i, a in enumerate(cores) for b in cores[i + 1:]]
    jac = float(np.mean([len(a & b) / len(a | b) if (a | b) else 0.0 for a, b in pairs]))
    return jac, float(len(set(cores)) == 1 and bool(cores[0]))


def compare(recs: list[dict], budgets: dict, a: str, b: str, *, n_boot: int = 4000, seed: int = 0) -> dict:
    by = {}
    for r in recs:
        if r.get("method") in (a, b):
            by[(r["method"], r["instance"], r.get("network"), r.get("seed"))] = r
    keys = sorted({k[1:] for k in by if (a, *k[1:]) in by and (b, *k[1:]) in by})
    insts = sorted({k[0] for k in keys})
    # the adversarial metrics exist only on trap suites; elsewhere a pair of failed runs must not create them
    per_run = [m for m in PER_RUN if not m.startswith("adversarial_") or any("adversarial" in by[(x, *k)] for k in keys for x in (a, b))]
    per_inst: dict[str, dict] = {i: {"rows": [], "cores_a": [], "cores_b": []} for i in insts}
    for k in keys:
        ra, rb = by[(a, *k)], by[(b, *k)]
        row = {}
        for m in per_run:
            va, vb = _value(ra, m), _value(rb, m)
            row[m] = (va, vb)
        row["calls"] = (_calls(ra, budgets.get(a)), _calls(rb, budgets.get(b)))
        per_inst[k[0]]["rows"].append(row)
        per_inst[k[0]]["cores_a"].append(frozenset(ra.get("core_canonical") or []))
        per_inst[k[0]]["cores_b"].append(frozenset(rb.get("core_canonical") or []))
    metrics = per_run + ["calls"]
    rng = np.random.default_rng(seed)
    # per instance, once: sums and counts of every paired metric, and each method's identity consistency
    sums = {m: np.zeros((len(insts), 3)) for m in metrics}  # columns: sum a, sum b, count
    cons_arr = np.full((len(insts), 4), np.nan)  # jaccard a, jaccard b, identical a, identical b
    for j, i in enumerate(insts):
        for row in per_inst[i]["rows"]:
            for m in metrics:
                x, y = row[m]
                if x is not None and y is not None:
                    sums[m][j] += (x, y, 1.0)
        if len(per_inst[i]["cores_a"]) >= 2:
            ca, cb = _consistency(per_inst[i]["cores_a"]), _consistency(per_inst[i]["cores_b"])
            cons_arr[j] = (ca[0], cb[0], ca[1], cb[1])

    def stat(idx: np.ndarray, metric: str):
        s = sums[metric][idx].sum(axis=0)
        return (float(s[0] / s[2]), float(s[1] / s[2])) if s[2] > 0 else (None, None)

    def cons(idx: np.ndarray):
        c = cons_arr[idx]
        c = c[~np.isnan(c[:, 0])]
        return tuple(float(x) for x in c.mean(axis=0)) if len(c) else (None,) * 4

    out: dict = {"a": a, "b": b, "n_runs": len(keys), "n_instances": len(insts), "metrics": {}}
    boots = {m: [] for m in metrics + ["jaccard", "identical"]}
    everything = np.arange(len(insts))
    for _ in range(n_boot):
        sel = rng.integers(0, len(insts), len(insts))
        for m in metrics:
            x, y = stat(sel, m)
            if x is not None:
                boots[m].append((y - x) if m == "calls" else (x - y))
        c = cons(sel)
        if c[0] is not None:
            boots["jaccard"].append(c[0] - c[1])
            boots["identical"].append(c[2] - c[3])
    for m in metrics:
        x, y = stat(everything, m)
        if x is None:
            continue
        diff = (y - x) if m == "calls" else (x - y)
        out["metrics"][m] = {"a": x, "b": y, "diff": diff, "ci95": [float(np.percentile(boots[m], 2.5)), float(np.percentile(boots[m], 97.5))],
                             "note": "calls saved by A (B - A)" if m == "calls" else "A - B"}
    c = cons(everything)
    if c[0] is not None:
        out["metrics"]["identity_jaccard"] = {"a": c[0], "b": c[1], "diff": c[0] - c[1],
                                              "ci95": [float(np.percentile(boots["jaccard"], 2.5)), float(np.percentile(boots["jaccard"], 97.5))]}
        out["metrics"]["identical_cores"] = {"a": c[2], "b": c[3], "diff": c[2] - c[3],
                                             "ci95": [float(np.percentile(boots["identical"], 2.5)), float(np.percentile(boots["identical"], 97.5))]}
    M = out["metrics"]
    above = lambda k: k in M and M[k]["ci95"][0] > 0  # noqa: E731
    not_lower = lambda k: k not in M or M[k]["ci95"][1] >= 0  # noqa: E731
    out["decision_rule"] = {
        # structural success and, when scored, success_intact (SELECTION_PROTOCOL section 8)
        "a_success_not_lower": bool("structural_success" in M and not_lower("structural_success") and not_lower("success_intact")),
        "b_better_reliability": bool(above("identity_jaccard") or above("identical_cores")),
        "b_better_efficiency": bool(above("calls")),
        "b_better_robustness": bool(above("robust_sd_x2") or above("robust_weight_noise")),
    }
    dr = out["decision_rule"]
    dr["pass"] = bool(dr["a_success_not_lower"] and (dr["b_better_reliability"] or dr["b_better_efficiency"] or dr["b_better_robustness"]))
    return out


def to_markdown(res: dict, sources: list[str]) -> str:
    lines = [f"# {res['a']} vs {res['b']} — paired comparison", "", "Sources: " + ", ".join(f"`{s}`" for s in sources), "",
             f"{res['n_runs']} paired runs on {res['n_instances']} instances (same instance, node order and seed). Differences are "
             f"{res['a']} - {res['b']} (calls: calls saved by {res['a']}); 95 % CIs resample instances. Failed runs count as unsuccessful "
             "at the full budget.", "", f"| metric | {res['a']} | {res['b']} | difference [95% CI] |", "|---|---|---|---|"]
    for m, v in res["metrics"].items():
        lines.append(f"| {m} | {v['a']:.3f} | {v['b']:.3f} | {v['diff']:+.3f} [{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}] |")
    dr = res["decision_rule"]
    lines += ["", "Pre-registered decision rule (SELECTION_PROTOCOL.md section 5):", "",
              f"- (a) success not lower than {res['b']}: **{'yes' if dr['a_success_not_lower'] else 'no'}**",
              f"- (b) better on reliability / efficiency / robustness (CI entirely above 0): {'yes' if dr['b_better_reliability'] else 'no'} / "
              f"{'yes' if dr['b_better_efficiency'] else 'no'} / {'yes' if dr['b_better_robustness'] else 'no'}",
              f"- rule {'PASSES' if dr['pass'] else 'FAILS'}"]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", nargs="+", type=Path)
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True, nargs="+")
    ap.add_argument("--out", type=Path, required=True, help="output stem; one <stem>_<b>.{json,md} per method b")
    args = ap.parse_args(argv)
    recs, budgets = load_records(args.results)
    for b in args.b:
        res = compare(recs, budgets, args.a, b)
        stem = args.out.parent / f"{args.out.name}_{b}"
        stem.parent.mkdir(parents=True, exist_ok=True)
        stem.with_suffix(".json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8", newline="\n")
        md = to_markdown(res, [p.name for p in args.results])
        stem.with_suffix(".md").write_text(md, encoding="utf-8", newline="\n")
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
