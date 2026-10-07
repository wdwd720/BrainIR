"""End-to-end run of the frozen earlier method (`brainir_causal.frozen_v1`, BrainIR State v1 behind the causal-state API): fit on a
system's PUBLIC training records and evaluate every metric family through the harness (`harness.evaluate_model`, in process: the
adapter is orchestrator code, a frozen baseline). ORCHESTRATOR SIDE; a smoke run, not a benchmark result.

    uv run --no-sync --project phase4 python scripts/p4/frozen_v1_smoke.py [--n-boot 200] [--out research/phase4/FROZEN_V1_SMOKE.json]

Systems: the toy system syn:toy:0 (the local toy tier: its public part for fitting, its orchestrator-held eval part for evaluation,
truth included) and one real mechanism (real:A:m1: public training data; evaluated on the PUBLIC evaluation subset of the public real
data, so no held-out real data is touched).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))

from brainir_causal import harness as H  # noqa: E402
from brainir_causal import frozen_v1 as V1  # noqa: E402
from brainir_causal import suites as SU  # noqa: E402

JOBS = {
    "syn:toy:0": {"sid": "syn:toy:0", "heldout_root": str(SU.SUITES), "heldout_tier": "toy", "part": "eval",
                  "internal_path": str(SU.SUITES / "toy" / "internal_records.json"), "store_root": str(SU.STORE)},
    "real:A:m1": {"sid": "real:A:m1", "heldout_root": str(SU.REAL_SETS), "heldout_tier": "real_public", "part": "public",
                  "internal_path": str(ROOT / "benchmarks" / "causal_state_v1" / "hidden" / "real_systems_internal.json"),
                  "store_root": str(ROOT / "data" / "phase4" / "store_real_smoke")},
}


def _num(d, *path):
    for p in path:
        if not isinstance(d, dict):
            return None
        d = d.get(p)
    return d


def summarize(res: dict) -> dict:
    """The headline numbers and every family's error state (a smoke check: does each family run?)."""
    fams = {}
    for fam in ("items", "items_verdict", "mediation", "micro", "truth", "capacity", "lift", "closure", "bisimulation"):
        v = res.get(fam)
        if v is None:
            fams[fam] = "not run"
        elif isinstance(v, dict) and "error" in v:
            fams[fam] = f"error: {str(v['error'])[:300]}"
        elif fam == "truth" and isinstance(v, dict):
            fams[fam] = {k: ("error: " + str(x["error"])[:200]) if isinstance(x, dict) and "error" in x else "ok" for k, x in v.items()}
        else:
            fams[fam] = "ok"
    return {"k": res.get("k"), "n_items": res.get("n_items"), "n_verdict_items": res.get("n_verdict_items"),
            "pred_errors": res.get("_preds_errors"), "families": fams, "eval_wall_s": res.get("eval_wall_s")}


def run_one(job: dict, n_boot: int) -> dict:
    t0 = time.time()
    inputs, internal, ctx, truth_obj = H.system_context(job)
    if truth_obj is not None:
        H.attach_states(inputs["items"], ctx.store, inputs.get("truth_dir"))
    train = H.training_records(inputs)
    t1 = time.time()
    model = V1.FrozenV1Baseline().fit(train, systems={job["sid"]: inputs["record"]}, config={}, seed=0)
    fit_s = time.time() - t1
    info = model.info()
    res = H.evaluate_model(model, inputs, simulate_many=H.simulate_many_for(ctx), truth_system=truth_obj, internal=internal, lift=True,
                           n_boot=n_boot, seed=0)
    out = {"n_train_records": len(train), "fit_s": round(fit_s, 1), "dropped_training_records": info["frozen_baseline"]["dropped_training_records"],
           "summary": summarize(res), "public_view": H.to_jsonable(H.public_view(res)), "wall_s": round(time.time() - t0, 1)}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", default="syn:toy:0,real:A:m1")
    ap.add_argument("--n-boot", type=int, default=200)
    ap.add_argument("--out", type=Path, default=ROOT / "research" / "phase4" / "FROZEN_V1_SMOKE.json")
    args = ap.parse_args(argv)
    rec = {"what": "frozen earlier method (frozen_v1 adapter) end to end: fit + harness evaluation (smoke; not a benchmark result)",
           "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sources": V1.verify_sources(), "n_boot": args.n_boot,
           "systems": {}}
    ok = True
    for sid in [s for s in args.systems.split(",") if s]:
        try:
            rec["systems"][sid] = run_one(JOBS[sid], args.n_boot)
            s = rec["systems"][sid]["summary"]
            bad = {f: v for f, v in s["families"].items() if isinstance(v, str) and v.startswith("error")}
            ok &= not bad
            print(f"{sid}: k={s['k']} items={s['n_items']} pred_errors={s['pred_errors']} families_with_errors={sorted(bad)} "
                  f"({rec['systems'][sid]['wall_s']} s)", flush=True)
        except Exception as e:  # noqa: BLE001 - recorded
            ok = False
            rec["systems"][sid] = {"error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()[-3000:]}
            print(f"{sid}: FAILED {type(e).__name__}: {e}", flush=True)
    rec["ok"] = bool(ok)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
