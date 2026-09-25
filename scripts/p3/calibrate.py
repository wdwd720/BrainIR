"""state_discovery_v1: the PRE-REGISTERED calibration of the verdict tolerances (PROTOCOL.md section 6; goal4 section 7).

    uv run --project phase3 python scripts/p3/calibrate.py [--workers 8]

Runs BEFORE any method agent starts, on the synthetic DEV suite only (never on real hidden data, never with a candidate method):
- the reference controls of PROTOCOL.md section 5 (full-state ceiling, input-only, readout-history, PCA-k, random-k with k = the true
  dimension), and
- the TRUE-LATENT reference (brainir_state.refmodels.TrueLatentModel: the true latent as encoder, learned transition / readout of the
  ceiling's class, events through a learned linear probe),
on every dev system whose truth says it is compressible (integer k) and closed (no hidden exogenous input). Tolerances:
    tau_A = max(0, 90th percentile of (A_truelatent - A_full) / A_full)
    tau_C = 75th percentile of the true-latent reference's held-out effect error
    tau_D = 90th percentile of the true-latent reference's task micro-gain (closure)
    tau_E = 90th percentile of the true-latent reference's microstate ratio
Writes benchmarks/state_discovery_v1/calibration.json (tolerances, per-system values of every reference = the baseline distributions,
code and data hashes). Only the tolerance values are public.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "phase3"
BENCH = ROOT / "benchmarks" / "state_discovery_v1"


def _calibrate_system(sid: str) -> dict:
    from brainir_state.suite_eval import limit_threads
    limit_threads(2)
    from brainir_state import evaluate as E
    from brainir_state.harness import SYNTH_CFG, SYNTH_ROLES, evaluate_system, fit_references, key_a, key_c, key_d, pca_basis
    from brainir_state.refmodels import TrueLatentModel
    from brainir_state.suite_eval import SuiteData
    sd = SuiteData(DATA / "synthetic_dev", kind="synthetic", truth_dir=DATA / "synthetic_truth" / "dev")
    tr = sd.truth_system(sid)
    k = int(tr["k"])
    train = sd.train_only(sid)
    info = sd.sysinfo(sid)
    hs = sd.hidden(sid)
    scale = E.readout_scale(train)
    pca = pca_basis(train)
    cfg = SYNTH_CFG
    refs = fit_references(sid, train, info["observed"], k, seed=0)
    ztrain = sd.z_true([t.key for t in train])
    tl = TrueLatentModel(info["observed"], seed=0).fit(sid, train, ztrain)
    # exact encoder on every held-out trajectory / twin / pool state of this system
    all_rows = [r for r in sd.pub.select(system_id=sid) if r["split"] in ("test", "twin", "pool")]
    zt = sd.z_true([r["key"] for r in all_rows if r["split"] != "pool"])
    pool_lat = {}
    pl = sd.truth_dir / "pools" / "pool_latents.npz"
    if pl.exists():
        with np.load(pl) as z:
            pool_lat = {k_: z[k_] for k_ in z.files if k_ in {r["key"] for r in all_rows if r["split"] == "pool"}}
    for r in all_rows:
        zz = zt.get(r["key"]) if r["split"] != "pool" else pool_lat.get(r["key"])
        if zz is not None:
            t = sd.pub.load(r)
            tl.register(t.x, zz)
    models = dict(refs)
    models["true_latent"] = tl
    out = {"sid": sid, "k": k, "trap": tr.get("trap"), "family": tr.get("family"), "n_observed": len(info["observed"])}
    for name, m in models.items():
        fam = ("A",) if name in ("input_only", "readout_hist") else ("A", "C", "D", "R", "E")
        res = evaluate_system(m, sid, hs, scale, pca, cfg, k=k, families=fam, roles=SYNTH_ROLES)
        out[name] = {"A": (res.get("A_B") or {}).get(key_a(cfg), {}).get("mean"),
                     "C": (res.get("C_heldout") or {}).get(key_c(cfg), {}).get("ratio"),
                     "D": ((res.get("D") or {}).get(key_d(cfg)) or {}).get("micro_gain"),
                     "E": (res.get("E") or {}).get("E_ratio_latent_to_random"),
                     "C_abstained": (res.get("C_heldout") or {}).get("n_abstained_unsupported")}
    return out


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args(argv)
    sys.path.insert(0, str(ROOT / "phase3" / "src"))
    truth = json.loads((DATA / "synthetic_truth" / "dev" / "truth.json").read_text(encoding="utf-8"))
    sids = sorted(s for s, t in truth["systems"].items() if t["k"] != "none" and t.get("closed_dynamics", True))
    print(f"calibrating on {len(sids)} compressible, closed dev systems", flush=True)
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        rows = list(ex.map(_calibrate_system, sids))

    def vals(model, key):
        v = np.array([r[model][key] for r in rows if r[model][key] is not None], float)
        return v[np.isfinite(v)]

    a_true, a_full = [], []
    for r in rows:
        at, af = r["true_latent"]["A"], r["full_state"]["A"]
        if at is not None and af is not None and np.isfinite(at) and np.isfinite(af) and af > 0:
            a_true.append((at - af) / af)
    taus = {"tau_A": float(max(0.0, np.percentile(a_true, 90))) if a_true else float("nan"),
            "tau_C": float(np.percentile(vals("true_latent", "C"), 75)),
            "tau_D": float(np.percentile(vals("true_latent", "D"), 90)),
            "tau_E": float(np.percentile(vals("true_latent", "E"), 90))}
    dist = {m: {k: {"median": float(np.median(vals(m, k))) if len(vals(m, k)) else None,
                    "p10": float(np.percentile(vals(m, k), 10)) if len(vals(m, k)) else None,
                    "p90": float(np.percentile(vals(m, k), 90)) if len(vals(m, k)) else None} for k in ("A", "C", "D", "E")}
            for m in ("full_state", "true_latent", "pca_k", "random_k", "input_only", "readout_hist")}
    code = {p: _sha(ROOT / p) for p in ("scripts/p3/calibrate.py", "phase3/src/brainir_state/refmodels.py", "phase3/src/brainir_state/evaluate.py",
                                          "phase3/src/brainir_state/harness.py")}
    rec = {"protocol_section": "PROTOCOL.md section 6", "suite": "synthetic dev", "n_systems": len(rows), "tolerances": taus,
           "relative_A_gap_truelatent_vs_full": a_true, "baseline_distributions": dist, "per_system": rows, "code_sha256": code,
           "dev_suite": json.loads((BENCH / "public" / "synthetic_dev_suite.json").read_text(encoding="utf-8"))}
    (BENCH / "calibration.json").write_text(json.dumps(rec, indent=1, default=float) + "\n", encoding="utf-8", newline="\n")
    (BENCH / "public" / "tolerances.json").write_text(json.dumps(taus, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(taus, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
