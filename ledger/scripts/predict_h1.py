"""Exam 2 prediction tables (PREREG v3 P1-P6, M2-M4, P10), frozen with the rulebook. Reads collected job results (never a label),
writes `research/ledger/predictions_h1/<arm>/predicted.csv`, `pools.csv` (simulated arms) and `provenance.json`. The raw results
(with the compressed motor-neuron traces) stay in the git-ignored data directory; provenance records their SHA-256.

    uv run --project ledger --no-sync python ledger/scripts/predict_h1.py hm --campaign hm-run3          # H-M and H-M-s0-3
    uv run --project ledger --no-sync python ledger/scripts/predict_h1.py hd --campaign hd-run3          # H-D-128 ... H-D-512
    uv run --project ledger --no-sync python ledger/scripts/predict_h1.py hc --campaign hc-101-run3      # one control network
    uv run --project ledger --no-sync python ledger/scripts/predict_h1.py hsens --campaign hsens-run3 --primary hm-run3
    uv run --project ledger --no-sync python ledger/scripts/predict_h1.py hs                            # the seven wiring baselines
    uv run --project ledger --no-sync python ledger/scripts/predict_h1.py p7 --campaign p7-run3 --out DIR  # pipeline test only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gha3  # noqa: E402

from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger import groups_h1 as GH  # noqa: E402
from brainir_ledger import networks as N  # noqa: E402
from brainir_ledger.backend import read_log  # noqa: E402

OUT = RESEARCH / "predictions_h1"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _results(campaign: str) -> tuple[dict[str, dict], dict]:
    man = json.loads((gha3.G.GHA / campaign / "manifest.json").read_text())
    p = data_dir() / man["area"] / f"GHA_{campaign}" / "results.pkl"
    res = {r["key"]: r for r in read_log(p)}
    missing = sorted(set(man["keys"]) - set(res))
    prov = {"campaign": campaign, "results_file": f"$DATA/ledger/{man['area']}/GHA_{campaign}/results.pkl", "results_sha256": _sha(p),
            "n_jobs": man["n_jobs"], "n_results": len(res), "missing_or_error": missing, "keys_sha256": man["keys_sha256"],
            "packed_at_git_head": man["git_head"],
            "digest_v3_sha256": hashlib.sha256("\n".join(f"{k} {res[k].get('digest_v3')}" for k in sorted(res)).encode()).hexdigest()}
    return res, prov


def _by_arm(res: dict[str, dict], seeds=None) -> dict[str, dict[str, list[dict]]]:
    out: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for k, r in res.items():
        arm, unit, s = k.split("|")
        if seeds is None or int(s[1:]) in seeds:
            out[arm][unit].append(r)
    return out


def _write(arm: str, pred, pools, prov: dict, out: Path = OUT) -> None:
    d = out / arm
    d.mkdir(parents=True, exist_ok=True)
    pred.to_csv(d / "predicted.csv", index=False, lineterminator="\n", float_format="%.10g")
    if pools is not None:
        pools.to_csv(d / "pools.csv", index=False, lineterminator="\n", float_format="%.10g")
    (d / "provenance.json").write_text(json.dumps({"arm": arm, **prov}, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    outc = {c: int(pred[c].sum()) for c in pred.columns if c.startswith("n_") and c not in ("n_members", "n_replicates")}
    print(json.dumps({"arm": arm, "units": len(pred), "replicates": int(pred["n_replicates"].sum()) if "n_replicates" in pred else None,
                      "outcomes": outc}))


def _strict(res_arm: dict[str, list[dict]], units, n_members, n_seeds) -> None:
    for u in units:
        if n_members[u] and len(res_arm.get(u, [])) != n_seeds:
            raise SystemExit(f"unit {u}: {len(res_arm.get(u, []))} results, expected {n_seeds}; table not written")
    extra = set(res_arm) - set(units)
    if extra:
        raise SystemExit(f"results for units not in the unit list: {sorted(extra)}")


def cmd_hm(a) -> None:
    gha3.require_freeze("H-M tables")
    res, prov = _results(a.campaign)
    fc = N.full_cord()
    units, masks = GH.load_units(), GH.pool_masks(GH.load_motor_map())
    groups = gha3._unit_groups(fc, "primary")
    nm = {u: len(g) for u, g in groups.items()}
    for arm, seeds in (("H-M", None), ("H-M-s0-3", set(gha3.LOW_SEEDS))):
        ra = _by_arm(res, seeds)["H-M"]
        _strict(ra, units, nm, len(gha3.H_SEEDS) if seeds is None else len(seeds))
        pred, pools = GH.arm_tables(ra, units, masks, nm)
        _write(arm, pred, pools, {**prov, "seeds": sorted(seeds) if seeds else list(gha3.H_SEEDS)})


def cmd_hd(a) -> None:
    gha3.require_freeze("H-D tables")
    res, prov = _results(a.campaign)
    fc = N.full_cord()
    units, masks = GH.load_units(), GH.pool_masks(GH.load_motor_map())
    nm = {u: len(g) for u, g in gha3._unit_groups(fc, "primary").items()}
    by = _by_arm(res)
    for c in gha3.HD_CURRENTS:
        arm = f"H-D-{c:g}"
        _strict(by[arm], units, nm, len(gha3.HD_SEEDS))
        pred, pools = GH.arm_tables(by[arm], units, masks, nm)
        _write(arm, pred, pools, {**prov, "current": c, "seeds": list(gha3.HD_SEEDS)})


def cmd_hc(a) -> None:
    gha3.require_freeze("H-C tables")
    res, prov = _results(a.campaign)
    fc = N.full_cord()
    units, masks = GH.load_units(), GH.pool_masks(GH.load_motor_map())
    nm = {u: len(g) for u, g in gha3._unit_groups(fc, "primary").items()}
    by = _by_arm(res)
    if len(by) != 1:
        raise SystemExit(f"one control network per campaign expected, got {sorted(by)}")
    (arm, ra), = by.items()
    _strict(ra, units, nm, len(gha3.LOW_SEEDS))
    pred, pools = GH.arm_tables(ra, units, masks, nm)
    _write(arm, pred, pools, {**prov, "seeds": list(gha3.LOW_SEEDS)})


def cmd_hsens(a) -> None:
    gha3.require_freeze("sensitivity tables")
    res, prov = _results(a.campaign)
    prim, prov_p = _results(a.primary)
    fc = N.full_cord()
    units, masks = GH.load_units(), GH.pool_masks(GH.load_motor_map())
    plan = gha3.sens_plan(fc)
    by, byp = _by_arm(res), _by_arm(prim, set(gha3.LOW_SEEDS))["H-M"]
    for v in GH.SENS_VARIANTS:
        arm = f"H-M-S-{v}"
        gv = gha3._unit_groups(fc, v)
        nm = {u: len(g) for u, g in gv.items()}
        ra = {u: (by[arm].get(u, []) if plan[v][u] == "run" else byp.get(u, []) if plan[v][u] == "same_as_primary" else [])
              for u in units}
        _strict({u: r for u, r in ra.items() if r or nm[u]}, units, nm, len(gha3.LOW_SEEDS))
        pred, pools = GH.arm_tables(ra, units, masks, nm)
        pred["source"] = [plan[v][u] for u in pred["unit"]]
        _write(arm, pred, pools, {**prov, "primary": prov_p, "plan": plan[v], "seeds": list(gha3.LOW_SEEDS)})


def cmd_hs(a) -> None:
    gha3.require_freeze("H-S tables")
    fc = N.full_cord()
    mm = GH.load_motor_map()
    groups = gha3._unit_groups(fc, "primary")
    tabs = GH.hs_tables(fc.W, groups, GH.mn_positions(mm), GH.pool_masks(mm))
    for arm, df in tabs.items():
        _write(arm, df, None, {"what": "wiring only: pool mean of (W^k s), full-cord signed count matrix (post x pre); k = 0 is "
                                       "the share of the pool inside the group; dims 5, 6, 7' constant 0 (PREREG v3 P3, M4)",
                               "network": fc.name, "W_nnz": int(fc.W.nnz)})


def cmd_p7(a) -> None:
    """Pipeline test only (allowed groups): the same tables for the P7 groups, written outside the predictions folder."""
    res, prov = _results(a.campaign)
    fc = N.full_cord()
    masks = GH.pool_masks(GH.load_motor_map())
    groups = gha3.p7_groups(fc.table)
    by: dict[str, list[dict]] = defaultdict(list)
    for k, r in res.items():
        if k.startswith(("p7|", "p7reg|")):
            by[k.split("|")[1]].append(r)
    names = sorted(by)
    pred, pools = GH.arm_tables(by, names, masks, {g: len(groups[g]) for g in names})
    _write("P7", pred, pools, prov, out=Path(a.out))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["hm", "hd", "hc", "hsens", "hs", "p7"])
    ap.add_argument("--campaign")
    ap.add_argument("--primary")
    ap.add_argument("--out")
    a = ap.parse_args()
    {"hm": cmd_hm, "hd": cmd_hd, "hc": cmd_hc, "hsens": cmd_hsens, "hs": cmd_hs, "p7": cmd_p7}[a.cmd](a)


if __name__ == "__main__":
    main()
