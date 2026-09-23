"""Structural-only null distributions for the DNg100 baselines, and empirical p-values of every baseline against its null.

EVALUATOR-SIDE SCRIPT. It imports the frozen evaluator's scoring functions (``evaluator/evaluate.py``), which read the
oracle; it is therefore answer-bearing and is never run by, imported from, or shown to a discovery method (the clean-room
runner refuses any method file that imports ``evaluate``). It lives here only because its outputs belong with the baselines.

For each network of the blind bundle and each k in {3, 4, 5}, ``--n`` (500) random interneuron sets are drawn under
  (a) ``uniform``:              uniformly among all interneurons (role_class vnc_intrinsic, stimulus/readout excluded);
  (b) ``two_hop``:              uniformly among the interneurons within two directed hops downstream of the stimulus;
  (c) ``sign_matched_two_hop``: as (b) with the sign composition fixed to round(k/3) inhibitory + the rest excitatory
                                (the rule of the random_matched baseline: 2 E + 1 I for k = 3),
and scored with the structural and type_role metric families only (no simulation; the same code path as
``evaluate.py --no-simulation``). Reported per (network, k, sampler): mean and 2.5-97.5 percentile interval of excitatory-core
recall, inhibitory-slot rate, precision and Jaccard, plus hit probabilities. For every baseline with an evaluation file
(``results/eval/<method>.json``) the one-sided empirical p-value against its matched null at the same k is
``(1 + #{null >= observed}) / (1 + n)`` for each metric.

    uv run python benchmarks/dng100/baselines/null_distributions.py [--n 500] [--seed 0] [--bundle benchmarks/dng100/public_blind]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from brainir.benchmark.prediction import BrainIRMechanismPrediction, MethodInfo, NeuronClaim

HERE = Path(__file__).resolve().parent
DNG = HERE.parent
sys.path.insert(0, str(DNG / "evaluator"))
import evaluate as ev  # noqa: E402  (evaluator-side; sets up the oracle import path itself)

RESULTS = HERE / "results"
KS = (3, 4, 5)
SAMPLERS = ("uniform", "two_hop", "sign_matched_two_hop")
METRICS = ("excitatory_core_recall", "inhibitory_slot_filled", "precision", "jaccard", "type_level_excitatory_recall")
MATCHED_NULL = {"random_matched": "sign_matched_two_hop", "degree_topk": "two_hop", "pagerank": "two_hop", "betweenness_stim_to_readout": "two_hop",
                "recurrence_loop": "two_hop", "greedy_prune_sim": "two_hop", "kcore_scc": "uniform", "community": "uniform",
                "statistical_motif": "uniform"}
"""Which sampler a baseline is compared with: methods that search the 2-hop downstream set vs. methods ranging over all interneurons."""


def sign_composition(k: int) -> tuple[int, int]:
    n_inh = max(1, round(k / 3)) if k >= 2 else 0
    return k - n_inh, n_inh


def role_of(sign: int) -> str:
    return "excitatory" if sign > 0 else "inhibitory" if sign < 0 else "unknown"


def downstream_within(edges: pd.DataFrame, sources: list[int], hops: int) -> set[int]:
    src = {int(s) for s in sources}
    frontier, seen = set(src), set()
    for _ in range(hops):
        nxt = {int(i) for i in edges.loc[edges["pre_id"].isin(frontier), "post_id"]} - seen - src
        seen |= nxt
        frontier = nxt
    return seen


def candidate_sets(bnet: ev.BundleNetwork) -> dict[str, dict[str, list[int]]]:
    nrn = bnet.neurons
    stim = {int(s) for s in bnet.stimulus["source_ids"]}
    ro = {int(r) for r in bnet.readout["source_ids"]}
    inter = sorted(int(i) for i in nrn.loc[(nrn["role_class"] == "vnc_intrinsic") & ~nrn["is_stimulus"] & ~nrn["is_readout"], "source_id"]
                   if int(i) not in stim | ro)
    two_hop = sorted(downstream_within(bnet.edges, sorted(stim), 2) & set(inter))
    sign = nrn.set_index("source_id")["sign"]
    split = lambda ids: {"all": ids, "exc": [i for i in ids if int(sign.loc[i]) > 0], "inh": [i for i in ids if int(sign.loc[i]) < 0]}  # noqa: E731
    return {"uniform": split(inter), "two_hop": split(two_hop), "sign_matched_two_hop": split(two_hop)}


def draw(rng: np.random.Generator, sampler: str, cand: dict[str, list[int]], k: int) -> list[int]:
    if sampler == "sign_matched_two_hop":
        n_exc, n_inh = sign_composition(k)
        core = list(rng.choice(cand["exc"], size=min(n_exc, len(cand["exc"])), replace=False)) if cand["exc"] else []
        core += list(rng.choice(cand["inh"], size=min(n_inh, len(cand["inh"])), replace=False)) if cand["inh"] else []
        rest = [i for i in cand["all"] if i not in core]
        if len(core) < k and rest:
            core += list(rng.choice(rest, size=min(k - len(core), len(rest)), replace=False))
        return [int(i) for i in core]
    pool = cand["all"]
    return [int(i) for i in rng.choice(pool, size=min(k, len(pool)), replace=False)]


def score_set(core: list[int], bnet: ev.BundleNetwork, onet, oracle_raw: dict, manifest: dict) -> dict:
    sign = {int(i): int(s) for i, s in zip(bnet.neurons["source_id"], bnet.neurons["sign"]) if int(i) in set(core)}
    pred = BrainIRMechanismPrediction(benchmark_id=manifest["benchmark_id"], dataset=bnet.info["dataset"], dataset_version=bnet.info["version"],
                                      stimulus_source_ids=[int(i) for i in bnet.stimulus["source_ids"]],
                                      core_neurons=[NeuronClaim(source_id=i, role=role_of(sign[i])) for i in core], method=MethodInfo(name="null"))
    s = ev.structural(pred, onet)
    t = ev.type_role(pred, onet, bnet, oracle_raw)
    return {"excitatory_core_recall": float(s["excitatory_core_recall"] or 0.0), "inhibitory_slot_filled": float(bool(s["inhibitory_slot_filled"])),
            "precision": float(s["precision_vs_all_published_labels"] or 0.0), "jaccard": float(s["jaccard_vs_reference_core"] or 0.0),
            "type_level_excitatory_recall": float(t["type_level_excitatory_recall"] or 0.0)}


def summarise_null(values: dict[str, np.ndarray]) -> dict:
    out = {}
    for m, v in values.items():
        out[m] = {"mean": float(v.mean()), "sd": float(v.std()), "p2.5": float(np.percentile(v, 2.5)), "p97.5": float(np.percentile(v, 97.5)),
                  "p_positive": float((v > 0).mean())}
    e = values["excitatory_core_recall"]
    out["p_excitatory_recall_ge_half"] = float((e >= 0.5).mean())
    out["p_excitatory_recall_full"] = float((e >= 1.0).mean())
    out["p_any_published_label"] = float((values["precision"] > 0).mean())
    return out


def build_nulls(bundle: Path, n: int, seed: int) -> tuple[dict, dict]:
    oracle_raw, onets = ev.load_oracle()
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    summary, raw = {}, {}
    for ni, spec in enumerate(manifest["networks"]):
        name = spec["name"]
        bnet = ev.BundleNetwork(bundle, name)
        cands = candidate_sets(bnet)
        summary[name] = {"n_interneurons": len(cands["uniform"]["all"]), "n_two_hop_interneurons": len(cands["two_hop"]["all"]),
                         "two_hop_sign_split": {"excitatory": len(cands["two_hop"]["exc"]), "inhibitory": len(cands["two_hop"]["inh"])}, "k": {}}
        raw[name] = {}
        for k in KS:
            summary[name]["k"][str(k)] = {}
            raw[name][k] = {}
            for si, sampler in enumerate(SAMPLERS):
                rng = np.random.default_rng([seed, ni, k, si])
                vals = {m: np.zeros(n) for m in METRICS}
                for r in range(n):
                    sc = score_set(draw(rng, sampler, cands[sampler], k), bnet, onets[name], oracle_raw, manifest)
                    for m in METRICS:
                        vals[m][r] = sc[m]
                raw[name][k][sampler] = vals
                summary[name]["k"][str(k)][sampler] = summarise_null(vals)
    return summary, raw


def baseline_pvalues(raw: dict) -> list[dict]:
    rows = []
    for method, sampler in MATCHED_NULL.items():
        ef = RESULTS / "eval" / f"{method}.json"
        if not ef.exists():
            continue
        evj = json.loads(ef.read_text(encoding="utf-8"))
        for net, r in evj["networks"].items():
            s, t = r["structural"], r["type_role"]
            k = int(s["n_predicted"])
            k_used = min(KS, key=lambda kk: abs(kk - k))
            obs = {"excitatory_core_recall": float(s["excitatory_core_recall"] or 0.0), "inhibitory_slot_filled": float(bool(s["inhibitory_slot_filled"])),
                   "precision": float(s["precision_vs_all_published_labels"] or 0.0), "jaccard": float(s["jaccard_vs_reference_core"] or 0.0),
                   "type_level_excitatory_recall": float(t["type_level_excitatory_recall"] or 0.0)}
            null = raw[net][k_used][sampler]
            n = len(next(iter(null.values())))
            row = {"method": method, "network": net, "k": k, "k_null": k_used, "matched_null": sampler}
            for m in METRICS:
                row[f"observed_{m}"] = obs[m]
                row[f"p_{m}"] = float((1 + np.sum(null[m] >= obs[m] - 1e-12)) / (1 + n))
            row["beats_null_jaccard_p05"] = bool(row["p_jaccard"] < 0.05)
            row["beats_null_excitatory_recall_p05"] = bool(row["p_excitatory_core_recall"] < 0.05)
            rows.append(row)
    return rows


def _f(v) -> str:
    return "–" if v is None else (f"{v:.3f}" if isinstance(v, float) else str(v))


def to_markdown(out: dict) -> str:
    b = out["bundle"]
    lines = [f"# DNg100 structural null distributions (bundle `{b['root']}`, tier {b['tier']}, sha `{b['bundle_sha256'][:12]}`)", "",
             f"Generated {out['created_utc']} by `benchmarks/dng100/baselines/null_distributions.py` (evaluator-side; answer-bearing output).",
             f"{out['n_draws']} random interneuron sets per (network, k, sampler), seed {out['seed']}; structural + type-level families only, no",
             "simulation. Samplers: uniform = all interneurons; two_hop = interneurons within two directed hops downstream of the stimulus;",
             "sign_matched_two_hop = two_hop with round(k/3) inhibitory + the rest excitatory. Intervals are 2.5-97.5 percentiles.", ""]
    for net, s in out["null"].items():
        lines += [f"## {net} — {s['n_interneurons']} interneurons, {s['n_two_hop_interneurons']} within 2 hops "
                  f"(E {s['two_hop_sign_split']['excitatory']} / I {s['two_hop_sign_split']['inhibitory']})", "",
                  "| k | sampler | E-core recall mean [95 %] | P(E recall >= 0.5) | I-slot rate | precision mean [95 %] | Jaccard mean [95 %] | "
                  "P(any label) |", "|---|---|---|---|---|---|---|---|"]
        for k, per in s["k"].items():
            for sampler, v in per.items():
                e, p, j = v["excitatory_core_recall"], v["precision"], v["jaccard"]
                lines.append(f"| {k} | {sampler} | {e['mean']:.3f} [{e['p2.5']:.2f}, {e['p97.5']:.2f}] | {v['p_excitatory_recall_ge_half']:.3f} | "
                             f"{v['inhibitory_slot_filled']['mean']:.3f} | {p['mean']:.3f} [{p['p2.5']:.2f}, {p['p97.5']:.2f}] | "
                             f"{j['mean']:.3f} [{j['p2.5']:.2f}, {j['p97.5']:.2f}] | {v['p_any_published_label']:.3f} |")
        lines.append("")
    if out["baseline_pvalues"]:
        lines += ["## Baselines against their matched null (one-sided empirical p = (1 + #null >= observed) / (1 + n))", "",
                  "| method | network | k | null | E-core recall (p) | I-slot (p) | precision (p) | Jaccard (p) | type-level E recall (p) | "
                  "beats null (Jaccard, p<0.05) |", "|---|---|---|---|---|---|---|---|---|---|"]
        for r in out["baseline_pvalues"]:
            cells = [f"{_f(r['observed_' + m])} ({r['p_' + m]:.3f})" for m in METRICS]
            lines.append(f"| {r['method']} | {r['network']} | {r['k']} | {r['matched_null']} | " + " | ".join(cells) +
                         f" | {'yes' if r['beats_null_jaccard_p05'] else 'no'} |")
        lines.append("")
    return "\n".join(lines)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bundle", type=Path, default=DNG / "public_blind")
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)
    t0 = time.time()
    manifest = json.loads((args.bundle / "manifest.json").read_text(encoding="utf-8"))
    summary, raw = build_nulls(args.bundle, args.n, args.seed)
    bundle_rec = {"root": args.bundle.name, "tier": manifest["tier"], "bundle_sha256": manifest["bundle_sha256"], "benchmark_id": manifest["benchmark_id"]}
    out = {"created_utc": _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"), "bundle": bundle_rec,
           "evaluator_version": ev.EVALUATOR_VERSION, "oracle_sha256": ev.oracle_sha256(), "n_draws": args.n, "seed": args.seed, "ks": list(KS),
           "samplers": list(SAMPLERS), "matched_null_by_method": MATCHED_NULL, "null": summary, "baseline_pvalues": baseline_pvalues(raw),
           "wall_time_s": round(time.time() - t0, 1)}
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "null_distributions.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    (RESULTS / "null_distributions.md").write_text(to_markdown(out) + "\n", encoding="utf-8", newline="\n")
    print(to_markdown(out))


if __name__ == "__main__":
    main()
