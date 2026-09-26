"""Synthetic family H on the FINAL suite (post-lock review R, M10). ORCHESTRATOR SIDE; ANSWER-BEARING output.

PROTOCOL.md section 4 H pre-registers robustness as A (and C) on the out-of-distribution families relative to in-distribution; for
the synthetic suites the OOD family is `noise_heldout` (held-out structural noise). The FINAL confirmation computed it inside
`suite_eval.evaluate_model_job` (res["H_ood"]), but the frozen tournament summariser keeps only verdicts, K, dimension and lifting
per system, so the numbers were not retained. This script re-evaluates the STORED seed-0 FINAL fits of the locked method and of the
comparator (no refit; the same frozen evaluation job on Modal) and extracts family H. The in-distribution A is compared with the
stored verdict A as a reproduction check. Logged in research/phase3/HIDDEN_EVALUATIONS.md as a post-hoc extraction of a
pre-registered readout; nothing is selected or tuned on it.

    uv run --project phase3 --no-sync python scripts/p3/final_h_family.py [--containers 100]
        -> research/phase3/tournament/final_b_H/FINAL_H_FAMILY.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "p3"))
sys.path.insert(0, str(ROOT / "phase3" / "src"))
import modal_tournament as MT  # noqa: E402
import tournament as T  # noqa: E402

P3 = ROOT / "research" / "phase3"
RUN = Path(r"C:\Dev\BrainIR_p3run")
MODELS = ("brainir_state_v1", "lin_dmdc_t")
OUT = P3 / "tournament" / "final_b_H" / "FINAL_H_FAMILY.json"
PRIMARY = "1000ms"   # harness.key_a(SYNTH_CFG): the synthetic primary horizon is 1 s (dt 10 ms)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--containers", type=int, default=100)
    a = ap.parse_args(argv)
    spec = T.suite_spec("final")
    ag = json.loads((P3 / "tournament" / "final_b" / "AGGREGATE_developer_facing.json").read_text(encoding="utf-8"))
    comp = list(ag["design"]["compressible"])
    stored = {m: json.loads((P3 / "tournament" / "final_b" / f"{m}.json").read_text(encoding="utf-8"))["per_system"] for m in MODELS}
    jobs = []
    for m in MODELS:
        for s in comp:
            p = RUN / f"final_b_{m}" / m / "indep" / f"{s}_s0.pkl"
            if p.exists():
                jobs.append({"suite": spec, "sid": s, "method_dir": str(RUN / f"final_b_{m}" / "methods"), "model_path": str(p), "lift": False,
                             "tag": f"H:{m}"})
    print(f"{len(jobs)} evaluation jobs", flush=True)
    MT._STATE.update(tier="final", sim_budget=250)
    app = MT._open_app(a.containers)
    t0 = time.time()
    with MT._output(), app.run():
        evs = MT.modal_evaluate_models(jobs)
    wall = round(time.time() - t0, 1)
    rows = {m: {} for m in MODELS}
    for j, r in zip(jobs, evs):
        m = j["tag"].split(":", 1)[1]
        s = j["sid"]
        if "error" in r:
            rows[m][s] = {"error": str(r["error"])[:300]}
            continue
        res = r.get("res") or {}
        ab = res.get("A_B") or {}
        ood = (res.get("H_ood") or {}).get("noise_heldout") or {}
        rec = {}
        for key in sorted(k for k in ab if k.startswith("A_nmse_h")):
            h = key[len("A_nmse_h"):]
            ind, oo = (ab.get(key) or {}).get("mean"), (ood.get(key) or {}).get("mean")
            rec[f"A_in_h{h}"] = ind
            rec[f"A_noise_heldout_h{h}"] = oo
            rec[f"capped_windows_h{h}"] = (ood.get(key) or {}).get("n_windows_capped")
            rec[f"ratio_h{h}"] = (oo / ind) if (ind and oo is not None) else None
        rec["n_noise_heldout_trajectories"] = ood.get("n_trajectories")
        sv = (stored[m].get(s) or {}).get("verdict") or {}
        rec["stored_verdict_A"] = sv.get("A")
        prim = rec.get(f"A_in_h{PRIMARY}")
        rec["A_reproduced_rel_diff"] = (abs(prim - sv["A"]) / max(abs(sv["A"]), 1e-12)
                                        if prim is not None and sv.get("A") is not None else None)
        rows[m][s] = rec

    def med(m, key):
        v = [x[key] for x in rows[m].values() if isinstance(x.get(key), (int, float)) and np.isfinite(x[key])]
        return (float(np.median(v)), len(v)) if v else (None, 0)
    summary = {m: {k: med(m, k) for k in (f"A_in_h{PRIMARY}", f"A_noise_heldout_h{PRIMARY}", f"ratio_h{PRIMARY}", "ratio_h250ms", "A_reproduced_rel_diff")}
               for m in MODELS}
    both = [s for s in comp if all(isinstance(rows[m].get(s, {}).get(f"ratio_h{PRIMARY}"), float) for m in MODELS)]
    d = np.array([rows["brainir_state_v1"][s][f"A_noise_heldout_h{PRIMARY}"] - rows["lin_dmdc_t"][s][f"A_noise_heldout_h{PRIMARY}"] for s in both])
    rng = np.random.default_rng(0)
    bm = [float(np.median(d[rng.integers(0, len(d), len(d))])) for _ in range(2000)] if len(d) else []
    summary[f"paired_noise_heldout_A_method_minus_comparator_h{PRIMARY}"] = {
        "median": float(np.median(d)) if len(d) else None, "ci95": [float(np.percentile(bm, 2.5)), float(np.percentile(bm, 97.5))] if bm else None,
        "n": int(len(d))}
    rec = {"script": "scripts/p3/final_h_family.py", "answer_bearing": True, "suite": "final", "family": "noise_heldout (PROTOCOL.md section 4 H)",
           "note": "post-hoc extraction of a pre-registered readout from the STORED FINAL fits; no refit; descriptive. Primary horizon 1 s "
                   "(SYNTH_CFG); a first run of this script read the real-system horizon keys and its summary was discarded",
           "wall_s": wall, "modal_costs": MT._STATE.get("costs"), "summary": summary, "per_system": rows,
           "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"wall_s": wall, "summary": summary}, default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
