"""Reliability sweep of a discovery method (registered, or the frozen greedy baseline script) on one public network.

    uv run python scripts/reliability_sweep.py --method greedy_prune_sim_frozen --bundle benchmarks/dng100/public_blind \
        --network manc_v1.2.1 --orders 8 --seeds 0 1 2 --workers 4 --label greedy_frozen_manc \
        --frozen-args "--budget-s 600 --replicates 2 --workers 1"
    uv run python scripts/reliability_sweep.py --method brainir_v1 --bundle ... --budget 1000 --backend modal

For each (order variant, seed) the method runs on a permuted copy of the network (positions shuffled; permutation kept
privately) and its prediction is mapped back to the common frame. Reported WITHOUT the oracle: identity consistency (across node
orders x parameter draws: a node-order variant re-assigns the per-neuron parameter draws of the position-indexed sampler, so the
two are confounded; both methods of a paired comparison face the same confound), size distribution, functional fidelity
(keep-only, fresh seeds), calls, wall time; failed runs are counted (as empty cores in the "incl. failures" consistency).

`--hidden-eval` / `--score-existing` add the frozen evaluator's structural families (no simulation) and append to
research/phase2/HIDDEN_EVAL_LOG.md. Refused unless research/phase2/METHOD_LOCK.json verifies and the tag brainir-v1-preblind
holds it, the sweep is of the locked method (source tree, configuration and budget equal to the lock's) or of the frozen
baseline (script hash equal to BENCHMARK_LOCK's), and this (method, network) has not been hidden-evaluated before
(research/phase2/hidden_eval_ledger.json).

Outputs: research/phase2/reliability/<label>.{json,md} (+ registry record).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from brainir import paths
from brainir.compute import ExperimentRecord, artifact_record, register_run
from brainir.discovery.problem import DiscoveryProblem
from brainir.discovery.provenance import launch_provenance
from brainir.discovery.reliability import FROZEN_NAME, consistency, functional_fidelity, make_permuted_bundle, pack_variants, sweep_job
from brainir.discovery.remote import get_discovery_backend as get_backend

ROOT = Path(__file__).resolve().parents[1]
FROZEN_GREEDY = ROOT / "benchmarks" / "dng100" / "baselines" / "greedy_prune_sim.py"
LEDGER = ROOT / "research" / "phase2" / "hidden_eval_ledger.json"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _make_variants(bundle: Path, network: str, orders: int, work: Path) -> list[tuple[Path, list[int], bool]]:
    variants = []
    for k in range(orders):
        vdir = work / "variants" / f"order{k}"
        info = make_permuted_bundle(bundle, network, seed=None if k == 0 else 1000 + k, dest_root=vdir)
        variants.append((vdir, [int(x) for x in info["perm"]], info["positional"]))
    return variants


def _method_provenance(args, config: dict) -> dict:
    """What produced this sweep (checked against the lock before any hidden evaluation; review F finding 7)."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import method_lock

    prov = {"method": args.method, "budget": args.budget, "locked_tree_sha256": method_lock.tree_hash(method_lock.source_hashes())}
    if args.method == FROZEN_NAME:
        prov["baseline_script_sha256"] = _sha(FROZEN_GREEDY)
        prov["frozen_args"] = args.frozen_args
    else:
        _cfg, cfg_hash = method_lock.effective_config(args.method, config)
        prov["config_sha256"] = cfg_hash
    return prov


def _f3(x):
    return "n/a" if x is None else f"{x:.3f}"


def _summary_md(args, summary: dict, cons: dict) -> list[str]:
    md = [f"# Reliability sweep — {args.label}", "",
          f"method `{args.method}` on `{args.network}` (bundle `{str(summary['bundle_sha256'])[:12]}`), {args.orders} node orders x seeds "
          f"{args.seeds}, budget {args.budget}; {summary['n_runs']} runs, {summary['n_failed']} failed; wall {summary['wall_total_s']} s", ""]
    if cons:
        md += [f"- identity consistency (node orders x parameter draws): pairwise Jaccard mean {_f3(cons['pairwise_jaccard_mean'])} "
               f"(min {_f3(cons['pairwise_jaccard_min'])}); modal core frequency {cons['modal_core_frequency']:.2f}; size "
               f"{cons['size_min']}-{cons['size_max']} (mean {cons['size_mean']:.2f})"]
        ci = summary.get("consistency_incl_failures")
        if ci and summary.get("n_failed"):
            md += [f"- incl. failures as empty cores: pairwise Jaccard mean {_f3(ci['pairwise_jaccard_mean'])}"]
    md += [f"- functional fidelity (keep-only, fresh seeds): mean {_f3(summary['functional_fidelity_mean'])}; "
           f"pass rate {_f3(summary['functional_pass_rate'])}",
           f"- simulator calls mean {summary['calls_mean']}; wall per run {summary['wall_s_mean']} s", ""]
    if "hidden_eval" in summary:
        h = summary["hidden_eval"]
        md += [f"- HIDDEN evaluation (logged): success rate {_f3(h.get('success_rate'))}, E-core recall mean {_f3(h.get('e_core_recall_mean'))}, "
               f"inhibitory slot rate {_f3(h.get('inhibitory_slot_rate'))}, precision mean {_f3(h.get('precision_mean'))}", ""]
    return md


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", required=True, help=f"registered method name or '{FROZEN_NAME}'")
    ap.add_argument("--bundle", type=Path, default=ROOT / "benchmarks" / "dng100" / "public_blind")
    ap.add_argument("--network", default="manc_v1.2.1")
    ap.add_argument("--orders", type=int, default=8, help="number of node-order variants (variant 0 = the bundle's own order)")
    ap.add_argument("--seeds", nargs="+", type=int, default=[0])
    ap.add_argument("--budget", type=int, default=1000)
    ap.add_argument("--config", default="{}", help="JSON config for registered methods")
    ap.add_argument("--frozen-args", default="", help="argv for the frozen baseline script, e.g. '--budget-s 600 --replicates 2 --workers 1'")
    ap.add_argument("--fidelity-seeds", nargs="+", type=int, default=[7000, 7001, 7002, 7003, 7004, 7005, 7006, 7007])
    ap.add_argument("--backend", choices=["local", "modal"], default="local")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--containers", type=int, default=100)
    ap.add_argument("--allow-dirty", action="store_true")
    ap.add_argument("--hidden-eval", action="store_true", help="score the predictions with the frozen evaluator (logged; only after the lock)")
    ap.add_argument("--score-existing", action="store_true", help="do not run: add the (logged, post-lock) hidden evaluation to an existing sweep")
    ap.add_argument("--new-attempt", action="store_true", help="allow a repeated hidden evaluation of the same (method, network) (logged)")
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "research" / "phase2" / "reliability")
    args = ap.parse_args(argv)
    config = json.loads(args.config)
    if args.score_existing:
        p = args.out / f"{args.label}.json"
        payload = json.loads(p.read_text(encoding="utf-8"))
        if payload["summary"].get("hidden_eval"):
            print(f"refusing: {p.name} already carries a hidden evaluation")
            return 1
        if payload["summary"].get("method") != args.method or payload["summary"].get("network") != args.network:
            print("refusing: --method/--network differ from the sweep file")
            return 1
        why = _hidden_eval_refusal(args, payload.get("provenance") or {})
        if why:
            print(f"refusing: {why}")
            return 1
        ok = [r for r in payload["runs"] if "core_common" in r]
        payload["summary"]["hidden_eval"] = _hidden_eval(args, ok)
        p.write_text(json.dumps(payload, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
        md = _summary_md(args, payload["summary"], payload["summary"].get("consistency") or {})
        (args.out / f"{args.label}.md").write_text("\n".join(md), encoding="utf-8", newline="\n")
        print("\n".join(md))
        return 0
    provenance = _method_provenance(args, config)
    if args.hidden_eval:
        why = _hidden_eval_refusal(args, provenance)
        if why:
            print(f"refusing: {why}")
            return 1
    code = launch_provenance()
    if args.backend == "modal" and code["dirty_src"] and not args.allow_dirty:
        print("refusing a remote campaign with uncommitted changes in src/; commit first or pass --allow-dirty")
        return 1
    work = paths.cache_dir() / "reliability" / args.label
    work.mkdir(parents=True, exist_ok=True)
    variants = _make_variants(args.bundle, args.network, args.orders, work)
    frozen_src = FROZEN_GREEDY.read_text(encoding="utf-8") if args.method == FROZEN_NAME else None
    jobs = [{"method": args.method, "variant_dir": str(v), "network": args.network, "seed": s, "budget": args.budget, "config": config,
             "perm": perm, "positional": positional, "frozen_args": args.frozen_args.split(), "frozen_script": frozen_src,
             "frozen_script_path": str(FROZEN_GREEDY), "fidelity_seeds": args.fidelity_seeds} for v, perm, positional in variants for s in args.seeds]
    t0 = time.time()
    backend = get_backend("modal", cpu=1.0, memory_mb=3072, timeout_s=7200, max_containers=args.containers) if args.backend == "modal" else None
    if backend is not None:
        from brainir.compute.backend import Shared, split_failures
        packs = pack_variants([v for v, _, _ in variants], args.network)
        remote_jobs = [{**j, "packs": Shared("packs")} for j in jobs]
        runs, failed = split_failures(backend.map(sweep_job, remote_jobs, shared={"packs": packs}))
        runs += [{"error": f["error"], "variant": Path(jobs[f["index"]]["variant_dir"]).name, "seed": jobs[f["index"]]["seed"]} for f in failed]
    elif args.workers > 1 and len(jobs) > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            runs = list(ex.map(sweep_job, jobs))
    else:
        runs = [sweep_job(j) for j in jobs]
    ok = [r for r in runs if "core_common" in r]
    for r in ok:  # keep the per-run predictions on disk (cache dir), not in the results JSON
        pdir = work / "predictions"
        pdir.mkdir(exist_ok=True)
        p_common = pdir / f"{r['variant']}_s{r['seed']}_common.json"
        p_common.write_text(json.dumps(r.pop("prediction_common_frame"), indent=1) + "\n", encoding="utf-8", newline="\n")
        (pdir / f"{r['variant']}_s{r['seed']}.json").write_text(json.dumps(r.pop("prediction"), indent=1) + "\n", encoding="utf-8", newline="\n")
        r["common_frame_path"] = str(p_common)
    cons = consistency([r["core_common"] for r in ok])
    cons_all = consistency([r.get("core_common", []) for r in runs])
    problem = DiscoveryProblem.from_bundle(args.bundle, args.network)
    for r in ok:  # functional fidelity (oracle-free); computed inside the job unless an older record lacks it
        if "functional_fidelity" not in r:
            pos_of = {int(i): k for k, i in enumerate(problem.public_ids)}
            r["functional_fidelity"] = functional_fidelity(problem, [pos_of[int(i)] for i in r["core_common"] if int(i) in pos_of],
                                                           args.fidelity_seeds, workers=args.workers)
    calls = [r["calls"] for r in ok if r.get("calls") is not None]
    manifest = json.loads((args.bundle / "manifest.json").read_text(encoding="utf-8"))
    summary = {"method": args.method, "network": args.network, "bundle_sha256": manifest.get("bundle_sha256"), "n_runs": len(runs),
               "n_failed": len(runs) - len(ok), "orders": args.orders, "seeds": args.seeds, "budget": args.budget, "consistency": cons,
               "consistency_incl_failures": cons_all,
               "functional_fidelity_mean": float(np.mean([r["functional_fidelity"] for r in ok])) if ok else None,
               "functional_pass_rate": float(np.mean([r["functional_fidelity"] >= 0.5 for r in ok])) if ok else None,
               "functional_pass_rate_incl_failures": float(np.sum([r["functional_fidelity"] >= 0.5 for r in ok]) / len(runs)) if runs else None,
               "calls_mean": float(np.mean(calls)) if calls else None,
               "wall_s_mean": float(np.mean([r["wall_s"] for r in ok])) if ok else None, "wall_total_s": round(time.time() - t0, 1)}
    if args.hidden_eval:
        summary["hidden_eval"] = _hidden_eval(args, ok)
    args.out.mkdir(parents=True, exist_ok=True)
    payload = {"summary": summary, "provenance": provenance, "code": code, "runs": runs, "config": config, "frozen_args": args.frozen_args}
    p = args.out / f"{args.label}.json"
    p.write_text(json.dumps(payload, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    md = _summary_md(args, summary, cons)
    (args.out / f"{args.label}.md").write_text("\n".join(md), encoding="utf-8", newline="\n")
    if backend is not None and backend.last_stats:
        backend_rec = backend.last_stats.to_dict()
    else:
        backend_rec = {"backend": "local", "n_workers": args.workers}
    rec = ExperimentRecord(name=f"reliability_{args.label}",
                           config={"method": args.method, "network": args.network, "orders": args.orders, "budget": args.budget, "config": config,
                                   "frozen_args": args.frozen_args},
                           seeds=args.seeds, inputs={"bundle_sha256": summary["bundle_sha256"], "source_tree_sha256": code["source_tree_sha256"],
                                                     "launched_utc": code["launched_utc"]},
                           backend=backend_rec, artifacts={"results": artifact_record(p)}, code=code,
                           summary={k: v for k, v in summary.items() if k not in ("consistency", "consistency_incl_failures")})
    register_run(rec, ROOT / "benchmarks" / "dng100" / "manifests" / "experiments")
    print("\n".join(md))
    return 0


def _hidden_eval_refusal(args, provenance: dict) -> str | None:
    """None when a hidden evaluation of this sweep is allowed (goal3 sections 27-29; review F finding 7), else the reason."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import method_lock

    if not method_lock.LOCK_PATH.exists() or method_lock.check(verbose=True):
        return "research/phase2/METHOD_LOCK.json is missing or does not verify"
    proc = subprocess.run(["git", "show", f"{method_lock.TAG}:research/phase2/METHOD_LOCK.json"], cwd=ROOT, capture_output=True)
    if proc.returncode != 0 or proc.stdout.replace(b"\r\n", b"\n") != method_lock.LOCK_PATH.read_bytes().replace(b"\r\n", b"\n"):
        return f"tag {method_lock.TAG} is missing or holds a different lock"
    lock = json.loads(method_lock.LOCK_PATH.read_text(encoding="utf-8"))
    if args.method == FROZEN_NAME:
        bench = json.loads((ROOT / "benchmarks" / "dng100" / "BENCHMARK_LOCK.json").read_text(encoding="utf-8"))
        frozen_sha = bench["files"].get("baselines/greedy_prune_sim.py")
        if _sha(FROZEN_GREEDY) != frozen_sha or provenance.get("baseline_script_sha256", frozen_sha) != frozen_sha:
            return "the baseline script differs from the one hashed in BENCHMARK_LOCK.json"
    elif args.method == lock["method"]["name"]:
        if provenance.get("locked_tree_sha256") != lock["source_tree_sha256"]:
            return "the sweep was not produced by the locked source tree"
        if provenance.get("config_sha256") != lock["method"]["config_sha256"] or int(provenance.get("budget", -1)) != int(
                lock["run_protocol"]["budget_calls_per_network"]):
            return "the sweep's configuration or budget differs from the lock"
    else:
        return f"only the locked method ({lock['method']['name']}) and the frozen baseline may be hidden-evaluated"
    ledger = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else {}
    if f"{args.method}|{args.network}" in ledger and not args.new_attempt:
        return f"{args.method} on {args.network} was already hidden-evaluated ({ledger[f'{args.method}|{args.network}']}); see goal3 section 29"
    return None


def _hidden_eval(args, ok: list[dict]) -> dict:
    """Score every prediction (already mapped to the ORIGINAL bundle frame) with the frozen evaluator, structural families only.

    Appends one line to research/phase2/HIDDEN_EVAL_LOG.md and records the (method, network) in the ledger."""
    evaluator = ROOT / "benchmarks" / "dng100" / "evaluator" / "evaluate.py"
    log = ROOT / "research" / "phase2" / "HIDDEN_EVAL_LOG.md"
    tmp = paths.cache_dir() / "reliability" / args.label / "_hidden"
    tmp.mkdir(parents=True, exist_ok=True)
    rows = []
    for r in ok:
        out = tmp / f"eval_{r['variant']}_s{r['seed']}.json"
        cmd = [sys.executable, str(evaluator), r["common_frame_path"], "--bundle", str(args.bundle), "--out", str(out), "--no-simulation"]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
        if proc.returncode != 0:
            rows.append({"variant": r["variant"], "seed": r["seed"], "error": proc.stderr[-300:]})
            continue
        ev = json.loads(out.read_text(encoding="utf-8"))["networks"][args.network]["structural"]
        rows.append({"variant": r["variant"], "seed": r["seed"], "e_core_recall": ev["excitatory_core_recall"],
                     "inhibitory_slot": ev["inhibitory_slot_filled"], "precision": ev["precision_vs_dng100_circuit_labels"],
                     "jaccard": ev["jaccard_vs_reference_core"]})
    good = [x for x in rows if "e_core_recall" in x]
    summ = {"n": len(rows), "success_rate": float(np.mean([x["e_core_recall"] == 1.0 and x["inhibitory_slot"] for x in good])) if good else None,
            "e_core_recall_mean": float(np.mean([x["e_core_recall"] for x in good])) if good else None,
            "inhibitory_slot_rate": float(np.mean([x["inhibitory_slot"] for x in good])) if good else None,
            "precision_mean": float(np.mean([x["precision"] for x in good if x["precision"] is not None])) if good else None, "rows": rows}
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    entry = (f"| {stamp} | reliability sweep `{args.label}` | `{args.method}` | `{args.network}` | {len(rows)} | success rate "
             f"{summ['success_rate']}, E-core recall mean {summ['e_core_recall_mean']} | baseline/final-method reliability "
             f"(structural families, no simulation) |\n")
    with open(log, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(entry)
    ledger = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else {}
    ledger[f"{args.method}|{args.network}"] = f"{stamp} {args.label}"
    LEDGER.write_text(json.dumps(ledger, indent=1) + "\n", encoding="utf-8", newline="\n")
    return summ


if __name__ == "__main__":
    sys.exit(main())
