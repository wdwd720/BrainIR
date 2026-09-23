"""Run every baseline through the clean-room runner on the blind bundle, evaluate each with the frozen evaluator, summarise.

EVALUATOR-SIDE driver. It calls ``cleanroom/run_method.py`` (one subprocess per method; the method sees only a copy of the
bundle) and then ``evaluator/evaluate.py`` (a separate subprocess) — it imports neither, and a method never sees its outputs.
Evaluation output under ``results/eval/`` names published labels and is therefore answer-bearing: never hand it to a
discovery method. The summary tables contain scalar metrics only.

    uv run python benchmarks/dng100/baselines/run_all_baselines.py [--methods NAME ...] [--skip-run] [--skip-eval] [--summary-only]
        [--bundle benchmarks/dng100/public_blind] [--n-replicates 8] [--workers 4] [--t-end 1.0] [--seed 0]

Outputs (small JSON/MD only)
    results/runs/<method>/prediction_<network>.json, run_record.json   method outputs, bundle/method/prediction hashes, wall time
    results/eval/<method>.json, .md                                     frozen-evaluator output (answer-bearing)
    results/baselines_summary.json, .md                                 one table per network: structural, type-level and functional
                                                                        metrics of every baseline, plus wall times
The simulation-based baseline (greedy_prune_sim) is run and evaluated last.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DNG = HERE.parent
REPO = DNG.parents[1]
RUNNER = DNG / "cleanroom" / "run_method.py"
EVALUATOR = DNG / "evaluator" / "evaluate.py"
RESULTS = HERE / "results"
METHODS = ["random_matched", "degree_topk", "pagerank", "betweenness_stim_to_readout", "kcore_scc", "recurrence_loop", "community",
           "statistical_motif", "greedy_prune_sim"]  # greedy_prune_sim (simulation-based) deliberately last


def _rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return p.name


def prediction_files(method: str) -> list[Path]:
    d = RESULTS / "runs" / method
    return sorted(p for p in d.glob("prediction_*.json") if not p.name.endswith("greedy_trace.json")) if d.exists() else []


def run_method(method: str, bundle: Path, seed: int, timeout_s: int) -> dict:
    out = RESULTS / "runs" / method
    cmd = [sys.executable, str(RUNNER), "--method", str(HERE / f"{method}.py"), "--bundle", str(bundle), "--out", str(out), "--seed", str(seed),
           "--timeout", str(timeout_s)]
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, timeout=timeout_s + 60)
    rec = {"method": method, "returncode": proc.returncode, "wall_time_s": round(time.time() - t0, 1), "stdout_tail": proc.stdout[-1500:],
           "stderr_tail": proc.stderr[-1500:]}
    rr = out / "run_record.json"
    if rr.exists():
        rec["run_record"] = json.loads(rr.read_text(encoding="utf-8"))
    return rec


def evaluate_method(method: str, bundle: Path, n_replicates: int, workers: int, t_end: float, timeout_s: int) -> dict:
    preds = prediction_files(method)
    out = RESULTS / "eval" / f"{method}.json"
    if not preds:
        return {"method": method, "returncode": None, "error": "no prediction files"}
    cmd = [sys.executable, str(EVALUATOR), *map(str, preds), "--bundle", str(bundle), "--out", str(out), "--n-replicates", str(n_replicates),
           "--workers", str(workers), "--t-end", str(t_end)]
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, timeout=timeout_s)
    return {"method": method, "returncode": proc.returncode, "wall_time_s": round(time.time() - t0, 1), "stderr_tail": proc.stderr[-1500:],
            "eval_file": _rel(out) if out.exists() else None}


# ----------------------------------------------------------------------------- summary (scalar metrics only)
def _row(method: str, net: str, r: dict, method_wall: float | None, eval_wall: float | None) -> dict:
    s, t, f = r["structural"], r["type_role"], r.get("functional")
    row = {"method": method, "network": net, "k": s["n_predicted"], "excitatory_core_recall": s["excitatory_core_recall"],
           "inhibitory_slot_filled": bool(s["inhibitory_slot_filled"]), "precision": s["precision_vs_all_published_labels"],
           "jaccard": s["jaccard_vs_reference_core"], "modal_circuit_recovered": bool(s["modal_circuit_recovered"]),
           "type_level_excitatory_recall": t["type_level_excitatory_recall"],
           "type_level_inhibitory_slot_filled": bool(t["type_level_inhibitory_slot_filled"]),
           "role_consistent_with_network_sign": t["role_consistent_with_network_sign"]["fraction"],
           "internal_edges": r["mechanism"]["internal_edges"], "loop_is_strongly_connected": r["mechanism"]["loop_is_strongly_connected"],
           "sufficiency_pass": None, "sufficiency_fraction_rhythmic": None, "necessity_accuracy": None, "n_necessity_claims": 0,
           "intact_fraction_rhythmic": None, "robustness_noise_0.3_fraction_rhythmic": None,
           "method_wall_time_s": method_wall, "eval_wall_time_s_all_networks": eval_wall}
    if f is not None:
        suff = f["sufficiency_keep_only_core"]
        row.update(sufficiency_pass=bool(f["sufficiency_pass"]), sufficiency_fraction_rhythmic=None if suff is None else suff["fraction_rhythmic"],
                   necessity_accuracy=f["necessity_accuracy"], n_necessity_claims=len(f["necessity"]),
                   intact_fraction_rhythmic=f["intact_network"]["fraction_rhythmic"])
        rob = r.get("robustness", {}).get("keep_only_core_weight_noise_0.3")
        if isinstance(rob, dict):
            row["robustness_noise_0.3_fraction_rhythmic"] = rob["fraction_rhythmic"]
    return row


def summarise(methods: list[str], bundle: Path) -> dict:
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    rows, evals = [], {}
    for m in methods:
        ef = RESULTS / "eval" / f"{m}.json"
        rr = RESULTS / "runs" / m / "run_record.json"
        if not ef.exists():
            continue
        ev = json.loads(ef.read_text(encoding="utf-8"))
        rec = json.loads(rr.read_text(encoding="utf-8")) if rr.exists() else {}
        walls = {r["network"]: r["wall_time_s"] for r in rec.get("runs", [])}
        evals[m] = {"evaluator_sha256": ev["evaluator_sha256"], "oracle_sha256": ev["oracle_sha256"], "bundle_sha256": ev["bundle"]["bundle_sha256"],
                    "run_bundle_sha256": rec.get("bundle", {}).get("bundle_sha256"), "method_sha256": rec.get("method_sha256"),
                    "simulation": ev["simulation"], "eval_wall_time_s": ev["wall_time_s"],
                    "cross_connectome_excitatory_core_in_all": (ev.get("cross_connectome") or {}).get("excitatory_core_in_all")}
        for net, r in ev["networks"].items():
            rows.append(_row(m, net, r, walls.get(net), ev["wall_time_s"]))
    bundle_rec = {"root": bundle.name, "tier": manifest["tier"], "bundle_sha256": manifest["bundle_sha256"], "benchmark_id": manifest["benchmark_id"]}
    return {"created_utc": _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"), "bundle": bundle_rec,
            "networks": [n["name"] for n in manifest["networks"]], "methods": list(evals), "per_method": evals, "rows": rows,
            "note": "scalar metrics copied from results/eval/<method>.json (frozen evaluator); no aggregate score by design"}


def _fmt(v) -> str:
    if v is None:
        return "–"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:.2f}" if abs(v) < 100 else f"{v:.0f}"
    return str(v)


def to_markdown(summary: dict) -> str:
    b = summary["bundle"]
    lines = [f"# DNg100 baselines — {b['benchmark_id']} (bundle `{b['root']}`, tier {b['tier']}, sha `{b['bundle_sha256'][:12]}`)", "",
             f"Generated {summary['created_utc']} by `benchmarks/dng100/baselines/run_all_baselines.py`. Metrics are copied from the frozen",
             "evaluator's output (`results/eval/<method>.json`, answer-bearing: never expose to a method). There is deliberately no aggregate",
             "score. E-core recall = fraction of the two published excitatory core neurons recovered by exact id; I-slot = a published",
             "inhibitory-slot neuron is in the core; precision = fraction of predicted neurons that carry any published label; Jaccard is",
             "against the reference core; type-level recall credits same-type neurons; sufficiency = keep-only-core simulation still",
             "rhythmic in >= 50 % of replicates; necessity accuracy = fraction of essential/non-essential claims confirmed by silencing.", ""]
    for m, info in summary["per_method"].items():
        sim = info["simulation"]
        lines.append(f"- `{m}`: method sha `{(info['method_sha256'] or '')[:12]}`, evaluator `{info['evaluator_sha256'][:12]}`, "
                     f"simulation replicates {sim['n_replicates']} (seeds {sim['seeds'][0]}..{sim['seeds'][-1]}), t_end {sim['t_end']} s, "
                     f"evaluation wall {info['eval_wall_time_s']} s (all networks)")
    lines.append("")
    cols = [("method", "method"), ("k", "k"), ("excitatory_core_recall", "E-core recall"), ("inhibitory_slot_filled", "I-slot"),
            ("precision", "precision"), ("jaccard", "Jaccard"), ("type_level_excitatory_recall", "type-level E recall"),
            ("sufficiency_fraction_rhythmic", "sufficiency frac"), ("sufficiency_pass", "sufficiency pass"), ("necessity_accuracy", "necessity acc"),
            ("n_necessity_claims", "claims"), ("method_wall_time_s", "method wall s")]
    for net in summary["networks"]:
        rows = [r for r in summary["rows"] if r["network"] == net]
        if not rows:
            continue
        lines += [f"## {net}", "", "| " + " | ".join(c[1] for c in cols) + " |", "|" + "---|" * len(cols)]
        for r in rows:
            lines.append("| " + " | ".join(_fmt(r[c[0]]) for c in cols) + " |")
        lines.append("")
    return "\n".join(lines)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--methods", nargs="*", default=None, help="subset of baseline names (default: all, simulation-based last)")
    ap.add_argument("--bundle", type=Path, default=DNG / "public_blind")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n-replicates", type=int, default=8)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--t-end", type=float, default=1.0)
    ap.add_argument("--skip-run", action="store_true", help="reuse existing predictions")
    ap.add_argument("--skip-eval", action="store_true", help="only run the methods")
    ap.add_argument("--summary-only", action="store_true", help="rebuild the summary from existing evaluation files")
    ap.add_argument("--method-timeout", type=int, default=1800)
    ap.add_argument("--eval-timeout", type=int, default=2400)
    args = ap.parse_args(argv)
    methods = [m for m in METHODS if args.methods is None or m in args.methods]
    unknown = set(args.methods or []) - set(METHODS)
    if unknown:
        raise SystemExit(f"unknown baselines: {sorted(unknown)}; known: {METHODS}")
    RESULTS.mkdir(exist_ok=True)
    log = {"started_utc": _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"), "bundle": _rel(args.bundle),
           "settings": {"seed": args.seed, "n_replicates": args.n_replicates, "workers": args.workers, "t_end": args.t_end}, "runs": [], "evals": []}
    t0 = time.time()
    if not args.summary_only:
        for m in methods:
            if not args.skip_run:
                rec = run_method(m, args.bundle, args.seed, args.method_timeout)
                log["runs"].append(rec)
                print(f"[run ] {m}: rc {rec['returncode']} in {rec['wall_time_s']} s", flush=True)
                if rec["returncode"] != 0:
                    print(rec["stderr_tail"], flush=True)
                    continue
            if not args.skip_eval:
                rec = evaluate_method(m, args.bundle, args.n_replicates, args.workers, args.t_end, args.eval_timeout)
                log["evals"].append(rec)
                print(f"[eval] {m}: rc {rec.get('returncode')} in {rec.get('wall_time_s')} s", flush=True)
                if rec.get("returncode") not in (0, None):
                    print(rec["stderr_tail"], flush=True)
        log["wall_time_s"] = round(time.time() - t0, 1)
        (RESULTS / "run_log.json").write_text(json.dumps(log, indent=1) + "\n", encoding="utf-8", newline="\n")
    summary = summarise(METHODS, args.bundle)
    summary["driver_wall_time_s"] = round(time.time() - t0, 1)
    (RESULTS / "baselines_summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8", newline="\n")
    (RESULTS / "baselines_summary.md").write_text(to_markdown(summary) + "\n", encoding="utf-8", newline="\n")
    print(to_markdown(summary))


if __name__ == "__main__":
    main()
