"""Evaluate candidate methods on the review G suite (new adversarial traps unknown to the developers; pre-lock review G).

    uv run --project phase3 python scripts/p3/eval_review_g.py --label r1 --methods m1,m2 --method-dir <snapshot of the methods package>
        [--parallel 4] [--eval-workers 4]

Uses the frozen evaluation code (brainir_state.suite_eval / harness / evaluate_synth). Fits run in the sandbox without a simulator:
the review G systems are not served by the simulation service, and the contract requires fits to work with sim=None. Lifting is not
scored: the synthetic simulator module serves only the frozen catalogue. The output has, per method and system:
- the trap label;
- the verdict of PROTOCOL.md section 7 with the calibrated tolerances;
- K latent recovery and dimension recovery;
- L abstention.
It goes to research/phase3/review_g/results_<label>.json (answer-bearing: never into a room). Only per-trap pass / fail summaries are
relayed to developers, and only as generic requirements.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase3" / "src"))
from brainir_state.evaluate_synth import abstention_row, abstention_summary  # noqa: E402
from brainir_state.harness import verdict  # noqa: E402
from brainir_state.suite_eval import SuiteData, dump, evaluate_models, limit_threads, reference_results, run_fits  # noqa: E402

DATA = ROOT / "data" / "phase3" / "synthetic" / "review_g"
OUT = ROOT / "research" / "phase3" / "review_g"
RUN = Path(r"C:\Dev\BrainIR_p3run")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--methods", required=True)
    ap.add_argument("--method-dir", required=True)
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--eval-workers", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=1800.0)
    args = ap.parse_args(argv)
    limit_threads(4)
    t0 = time.time()
    spec = {"public_dir": str(DATA / "public"), "truth_dir": str(DATA / "truth"), "kind": "synthetic", "tier": "heldout", "suite_seed": -1}
    sd = SuiteData(spec["public_dir"], kind="synthetic", truth_dir=spec["truth_dir"])
    run_dir = RUN / f"review_g_{args.label}"
    view = sd.fit_view(run_dir / "fitview")
    taus = json.loads((ROOT / "benchmarks" / "state_discovery_v1" / "public" / "tolerances.json").read_text(encoding="utf-8"))
    mdir = Path(args.method_dir).resolve()
    out = {"label": args.label, "methods": {}, "tolerances": taus}
    for m in [x for x in args.methods.split(",") if x]:
        jobs = [dict(method_dir=mdir, method=m, datasets=[view], systems=[s], out=run_dir / m / f"{s}.pkl", seed=0, timeout_s=args.timeout)
                for s in sd.systems]
        recs = run_fits(jobs, parallel=args.parallel)
        ev_jobs = [{"suite": spec, "sid": s, "method_dir": str(mdir), "model_path": str(run_dir / m / f"{s}.pkl"), "lift": False}
                   for s in sd.systems if (run_dir / m / f"{s}.pkl").exists()]
        evs = evaluate_models(ev_jobs, workers=args.eval_workers)
        per, lrows = {}, []
        for e in evs:
            s = e["sid"]
            tr = sd.truth_system(s)
            if "error" in e:
                per[s] = {"name": tr.get("name"), "trap": tr.get("trap"), "error": e["error"]}
                lrows.append(abstention_row(tr, None, None))
                continue
            k = e.get("k")
            refs = reference_results(sd, s, int(k) if k else 1, OUT / "_refcache")
            ab = ((e.get("info") or {}).get("abstain") or {}).get(s)
            v = verdict(e["res"], refs, taus, len(sd.sysinfo(s)["observed"]), k, "synthetic", sd.cfg, abstain=ab)
            per[s] = {"name": tr.get("name"), "trap": tr.get("trap"), "k": k, "k_true": tr.get("k"), "verdict": v["verdict"],
                      "conditions": {c: v[c] for c in ("compact", "predictive", "interventional", "closed", "microstate_equivalent")},
                      "A_over_full": (v["A"] / v["A_full"]) if v.get("A_full") else None, "C": v["C"], "D": v["D_micro_gain"],
                      "E": v["E_ratio"], "K": e.get("K"), "K_dim": e.get("K_dim"), "abstain": ab}
            lrows.append(abstention_row(tr, ab, v))
        out["methods"][m] = {"per_system": per, "abstention": abstention_summary(lrows),
                             "fit_failures": sum(1 for r in recs if "error" in r)}
        print(m, json.dumps({s: (r.get("trap"), r.get("verdict"), r.get("k"), r.get("k_true")) for s, r in per.items()}), flush=True)
    out["wall_s"] = round(time.time() - t0, 1)
    dump(out, OUT / f"results_{args.label}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
