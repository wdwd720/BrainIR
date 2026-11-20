"""Gate G3 v2 (PREREG v2 P2): items 1-3 and 5 of PREREG v1 section 9 unchanged, item 4 replaced by 4' (coupling consistent with
the authors' own traces under the same test). PREDICTION SIDE, simulations only: our G3 v2 runs (GitHub Actions campaign
`g3v2`: both DNg100 at 380, T = 2 s, seeds 0..63, plus the B3 procedure on the DNg100 type, seeds 0..15) and the authors' run
33195857 (32 replicates, their Zenodo traces, cached by run 1's `g3_authors_coupling.py`). No fly data.

    uv run --project ledger --no-sync python ledger/scripts/g3v2_evaluate.py   # -> research/ledger/gates_v2/G3v2_REPORT.{json,md}
"""

from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE))
import g3_evaluate as G1  # noqa: E402  (run 1's constants AUTH_FRAC / AUTH_MED, recomputed from the pinned files there)
from brainir.metrics.rhythm import network_oscillation_score  # noqa: E402

from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger import legs as L  # noqa: E402
from brainir_ledger import networks as N  # noqa: E402
from brainir_ledger.backend import read_log  # noqa: E402

PERM_SEED, N_PERM = 20261202, 10_000
RUN = "33195857"


def _R(theta: np.ndarray) -> float:
    return float(np.abs(np.mean(np.exp(1j * np.asarray(theta, float))))) if len(theta) else float("nan")


def authors_offsets() -> dict[str, list[float]]:
    from brainir import paths

    member = f"simulations/DNg100_Stim_fullManc/hyak/run_id={RUN}/ckpt/DNg100_Stim_fullManc_Rs.npz"
    cache = paths.data_root() / "raw" / "external" / "pugliese_2026_zenodo" / "DNg100_Stim_fullManc" / member
    raw = cache.read_bytes()
    fc = N.full_cord()
    ls = N.leg_setup(fc)
    e1 = [ls["e1"][leg] for leg in L.LEGS]
    mn_idx = {leg: np.flatnonzero(ls["masks"][leg]) for leg in L.LEGS}
    keep = sorted(set(e1) | {int(i) for v in mn_idx.values() for i in v})
    with zipfile.ZipFile(io.BytesIO(raw)) as nz:
        arrs = {n.removesuffix(".npy"): np.load(io.BytesIO(nz.read(n)), allow_pickle=False) for n in nz.namelist()}
    coords, data, shape = arrs["coords"], arrs["data"], tuple(int(x) for x in arrs["shape"])
    if len(shape) == 4:
        coords = np.vstack([coords[0] * shape[1] + coords[1], coords[2], coords[3]])
        shape = (shape[0] * shape[1], shape[2], shape[3])
    n_sims, _, n_t = shape
    sel = np.isin(coords[1], keep)
    sub = np.zeros((n_sims, len(keep), n_t), dtype=np.float32)
    pos = {r: i for i, r in enumerate(keep)}
    sub[coords[0][sel], np.array([pos[int(x)] for x in coords[1][sel]]), coords[2][sel]] = data[sel]
    reps = []
    for s in range(n_sims):
        win = sub[s][:, 250:].T
        sc = {}
        for leg in L.LEGS:
            w = win[:, [pos[int(i)] for i in mn_idx[leg]]]
            sc[leg] = network_oscillation_score(w, w.max(axis=0) > 0.01, 0.05)[0]
        reps.append((sc, {leg: win[:, pos[e1[i]]].astype(np.float64) for i, leg in enumerate(L.LEGS)}))
    out = {}
    for a, b in L.REPORTED_PAIRS:
        out[f"{a}-{b}"] = [L.phase_offset(e[a], e[b]) for sc, e in reps if sc[a] >= 0.5 and sc[b] >= 0.5]
    return out


def load_g3(path: Path, prefix: str) -> tuple[list[dict], list[dict]]:
    res = [r for r in read_log(path) if "error" not in r]
    return sorted([r for r in res if r["key"].startswith(prefix)], key=lambda r: int(r["key"].rsplit("s", 1)[1])), res


def item4p(g3: list[dict]) -> tuple[dict, int, bool, dict]:
    """Item 4' (PREREG v2 P2): per reported leg pair, two-sample permutation test of |R_ours - R_authors| (offsets of runs where
    both legs score >= 0.5; evaluable if both sides have >= 8); governing rule: k >= 3 and every evaluable p >= 0.01."""
    sig = [L.unpack_traces(r["extras"]["leg_signals"]) for r in g3]
    auth = authors_offsets()
    rng = np.random.default_rng(PERM_SEED)
    pairs = {}
    for a, b in L.REPORTED_PAIRS:
        ia, ib = L.LEGS.index(a), L.LEGS.index(b)
        mine = [L.phase_offset(sig[i][:, ia], sig[i][:, ib]) for i, r in enumerate(g3)
                if r["extras"]["legs"][a]["score"] >= 0.5 and r["extras"]["legs"][b]["score"] >= 0.5]
        theirs = auth[f"{a}-{b}"]
        row = {"n_ours": len(mine), "n_authors": len(theirs), "R_ours": _R(mine), "R_authors": _R(theirs)}
        if len(mine) >= 8 and len(theirs) >= 8:
            pooled = np.array(mine + theirs, float)
            obs = abs(row["R_ours"] - row["R_authors"])
            ge = 0
            for _ in range(N_PERM):
                perm = rng.permutation(len(pooled))
                ge += abs(_R(pooled[perm[:len(mine)]]) - _R(pooled[perm[len(mine):]])) >= obs - 1e-12
            row.update({"evaluable": True, "abs_diff": obs, "p": (1 + ge) / (N_PERM + 1)})
        else:
            row["evaluable"] = False
        pairs[f"{a}-{b}"] = row
    k = sum(v["evaluable"] for v in pairs.values())
    alpha = 0.01  # PREREG v2 P2: v1 4.7's alpha, no multiplicity correction
    c4p = bool(k >= 3 and all(v["p"] >= alpha for v in pairs.values() if v["evaluable"]))
    variants = {"bonferroni_0.01_over_k": bool(k >= 3 and all(v["p"] >= 0.01 / k for v in pairs.values() if v["evaluable"]))}
    return pairs, k, c4p, variants


def main() -> None:
    g3, res = load_g3(data_dir() / "calibration" / "GHA_g3v2" / "results.pkl", "g3v2|")
    it5 = [r for r in res if r["key"].startswith("g3v2item5|")]
    ours = {leg: np.array([r["extras"]["legs"][leg]["score"] for r in g3]) for leg in L.LEGS}
    per_leg = {leg: {"frac_ge_0_5": float((ours[leg] >= 0.5).mean()), "median": float(np.median(ours[leg])), "mean": float(ours[leg].mean()),
                     "authors_frac_ge_0_5": G1.AUTH_FRAC[leg], "authors_median": G1.AUTH_MED[leg]} for leg in L.LEGS}
    c1 = all(v["frac_ge_0_5"] >= 0.10 for v in per_leg.values())
    c2 = all(abs(v["frac_ge_0_5"] - v["authors_frac_ge_0_5"]) <= 0.25 and abs(v["median"] - v["authors_median"]) <= 0.30 for v in per_leg.values())
    hind = (per_leg["T3L"]["mean"] + per_leg["T3R"]["mean"]) / 2
    front = (per_leg["T1L"]["mean"] + per_leg["T1R"]["mean"]) / 2
    c3 = hind < front
    # item 4' of the formal run: REPORTED only; item 4' is decided by the pre-freeze preview (`g3v2_preview.py`, PREREG v2 P2)
    pairs, k, c4p_formal, variants = item4p(g3)
    preview = json.loads((RESEARCH / "gates_v2" / "G3v2_PREVIEW.json").read_text())
    c4p = bool(preview["item4p_pass"])
    alpha = 0.01
    # item 5: the B3 procedure on the DNg100 type, accepted at 384 in >= 14 of 16 seeds, front-pair score >= 0.5 (mean over usable)
    acc384 = sum(1 for r in it5 if r.get("usable") and abs(float(r.get("current") or 0) - 384.0) < 1e-6)
    front_scores = [r["extras"]["legs"]["front"]["score"] for r in it5 if r.get("usable")]
    front_mean = float(np.mean(front_scores)) if front_scores else None
    c5 = bool(len(it5) == 16 and acc384 >= 14 and front_mean is not None and front_mean >= 0.5)
    out = {"gate": "G3 v2", "n_runs": len(g3), "n_item5": len(it5), "per_leg": per_leg, "hind_mean": hind, "front_mean": front,
           "item4p_decided_by": "gates_v2/G3v2_PREVIEW.json (PREREG v2 P2)", "item4p_preview_pass": c4p,
           "formal_run_coupling_consistency_reported": pairs, "formal_run_item4p_pass_reported": c4p_formal,
           "k_evaluable": k, "alpha_per_pair": alpha, "reported_variants": variants,
           "item5": {"accepted_at_384": acc384, "front_pair_mean_score": front_mean, "currents": sorted({float(r.get('current') or 0) for r in it5})},
           "criteria": {"1_every_leg_rhythmic": c1, "2_per_leg_agreement": c2, "3_hind_weaker": c3, "4p_coupling_consistent": c4p,
                        "5_dng100_b3_procedure": c5},
           "pass": bool(c1 and c2 and c3 and c4p and c5)}
    d = RESEARCH / "gates_v2"
    d.mkdir(parents=True, exist_ok=True)
    (d / "G3v2_REPORT.json").write_text(json.dumps(out, indent=1, default=float) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"criteria": out["criteria"], "pass": out["pass"], "k_evaluable": k}, indent=1))
    for kk, v in pairs.items():
        print(kk, {x: (round(y, 4) if isinstance(y, float) else y) for x, y in v.items()})


if __name__ == "__main__":
    main()
