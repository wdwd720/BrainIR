"""Exam 2 groups and prediction rules (PREREG v3 Parts U, M and P3), frozen with the rulebook.

- `members`: the neurons of a unit's primary group (U3) or a sensitivity group (U4), as positions in the full-cord network;
- `pool_masks`: the motor pools of M1 and the per-leg flexor / extensor pools of M2, over the motor neurons in motor-map order
  (the order of the job read-out ``extras["mn"]``);
- `replicate_dims`: the per-replicate values of M2-M3 from a job result (the accepted run's read-out, or the last simulated run's
  for a replicate that is never accepted);
- `arm_tables`: the arm's `predicted.csv` (one row per unit: the mean over replicates of each primary dimension, tuner outcome
  counts) and `pools.csv` (per unit, replicate and pool);
- `hs_tables`: the wiring baselines of P3 (k = 0 membership, k = 1, 2, 3 hops, signed and unsigned) with M4's constants.
No outcome of any kind is read here.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import scipy.sparse as sp

from . import RESEARCH
from .scoring_h1 import DIMS

THORAX = ("T1", "T2", "T3")
SENS_VARIANTS = ("all", "post", "T1", "T2", "T3", "L", "R")
VARIANTS = ("primary",) + SENS_VARIANTS
POSTEMBRYONIC = ("secondary", "early_secondary")
LEGS = ("T1L", "T1R", "T2L", "T2R", "T3L", "T3R")
LEG_BODY = {"T1": "front_leg", "T2": "middle_leg", "T3": "hind_leg"}
FLEX = ("tibia_flexor", "femur_trochanter_flexor")
EXT = ("tibia_extensor", "femur_trochanter_extensor")
POOLS = ("any_body", "front_leg", "middle_leg", "hind_leg", "jump", "wing_any", "wing_power", "haltere", "abdomen")
BODY_POOLS = ("front_leg", "middle_leg", "hind_leg", "wing_any", "haltere", "abdomen")  # d1: any body part moves (max over these)
HS_ARMS = ["H-S-k0"] + [f"H-S-k{k}-{s}" for k in (1, 2, 3) for s in ("signed", "unsigned")] + ["H-S-lin"]
OUTCOMES = ("accepted", "too_weak", "saturating")


def load_units() -> list[str]:
    return pd.read_csv(RESEARCH / "hl_units" / "UNITS_v1.csv", dtype={"unit": str})["unit"].tolist()


def load_motor_map() -> pd.DataFrame:
    return pd.read_csv(RESEARCH / "motor_map" / "MOTOR_MAP_v1.csv", dtype={"pools": str}).fillna({"pools": ""})


def mn_positions(mm: pd.DataFrame) -> list[int]:
    return [int(i) for i in mm["index"]]


def birthtime(repo) -> pd.Series:
    a = pd.read_parquet(repo / "data" / "processed" / "manc" / "v1.2.1" / "neuron_annotations_source.parquet",
                        columns=["bodyId", "tag_birthtime"])
    return a.set_index("bodyId")["tag_birthtime"]


def members(table: pd.DataFrame, bt: pd.Series, unit: str, variant: str = "primary") -> list[int]:
    """U3 / U4. `table`: the full-cord node table (index = network position)."""
    h = table["hemilineage"] == unit
    th = table["somaNeuromere"].isin(THORAX)
    if variant == "primary":
        m = h & th
    elif variant == "all":
        m = h
    elif variant == "post":
        m = h & th & table["bodyId"].map(bt).isin(POSTEMBRYONIC)
    elif variant in THORAX:
        m = h & (table["somaNeuromere"] == variant)
    elif variant in ("L", "R"):
        m = h & th & (table["somaSide"] == {"L": "LHS", "R": "RHS"}[variant])
    else:
        raise ValueError(variant)
    return sorted(int(i) for i in table.index[m.to_numpy()])


def pool_masks(mm: pd.DataFrame) -> dict[str, np.ndarray]:
    pools = [set(p.split(";")) - {""} for p in mm["pools"]]
    out = {name: np.array([name in ps for ps in pools]) for name in POOLS}
    leg_part = mm["body_part"].isin(LEG_BODY.values()).to_numpy()
    for leg in LEGS:
        here = leg_part & (mm["segment"] == leg[:2]).to_numpy() & (mm["side"] == leg[2]).to_numpy()
        out[f"{leg}_flexor"] = here & mm["action"].isin(FLEX).to_numpy()
        out[f"{leg}_extensor"] = here & mm["action"].isin(EXT).to_numpy()
    return out


def replicate_readout(r: dict) -> tuple[dict, str]:
    """(read-out, outcome) of one job result: group jobs -> accepted / too_weak / saturating; fixed jobs (H-D) -> fixed_<verdict>."""
    if "error" in r:
        raise ValueError(f"{r.get('key')}: job error")
    if "usable" in r:
        if r["usable"]:
            return r["extras"], "accepted"
        return r["final_run_extras"], {"weak": "too_weak", "strong": "saturating"}[r["final_verdict"]]
    return r["extras"], f"fixed_{r['verdict']}"


def _act(active: np.ndarray, m: np.ndarray) -> float:
    return float(active[m].mean()) if m.any() else 0.0


def replicate_dims(ex: dict, masks: dict[str, np.ndarray]) -> tuple[dict, dict, dict]:
    """M2-M3 for one replicate: (pool activities, leg rhythm scores, dimension values)."""
    n = len(masks["any_body"])
    if len(ex["mn_peak"]) != n:
        raise ValueError("read-out does not cover the motor map")
    active = np.zeros(n, bool)
    active[np.asarray(ex["mn_active"], dtype=np.int64)] = True
    act = {k: _act(active, m) for k, m in masks.items()}
    rhy = {leg: float(ex["legs"][leg]["score"]) for leg in LEGS}
    d5 = float(np.mean([max(0.0, act[f"{g}_flexor"] - act[f"{g}_extensor"]) * (1.0 - rhy[g]) for g in LEGS]))
    d6 = float(np.mean([max(0.0, act[f"{g}_extensor"] - act[f"{g}_flexor"]) * (1.0 - rhy[g]) for g in LEGS]))
    dims = {"d1": max(act[b] for b in BODY_POOLS), "d2": act["front_leg"], "d3": act["middle_leg"], "d4": act["hind_leg"], "d5": d5, "d6": d6,
            "d7p": max(rhy.values()), "d10": act["jump"], "d11": act["wing_any"], "d13": act["wing_power"], "d14": act["haltere"],
            "d15": act["abdomen"]}
    return act, rhy, dims


def arm_tables(results: dict[str, list[dict]], units: list[str], masks: dict[str, np.ndarray],
               n_members: dict[str, int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """`results`: unit -> its job results (one per replicate). A unit whose group is empty (`n_members` 0; sensitivity groups
    only, PREREG v3 U4) gets zeros; any other unit without results is an error."""
    rows, prow = [], []
    for u in units:
        rs = results.get(u, [])
        if not rs:
            if n_members.get(u, 0) != 0:
                raise ValueError(f"unit {u}: no results for a non-empty group")
            rows.append({"unit": u, **{d: 0.0 for d in DIMS}, "n_members": 0, "n_replicates": 0})
            continue
        per, outc = [], []
        for r in sorted(rs, key=lambda x: int(x["seed"])):
            ex, oc = replicate_readout(r)
            act, rhy, dims = replicate_dims(ex, masks)
            per.append(dims)
            outc.append(oc)
            prow += [{"unit": u, "seed": int(r["seed"]), "outcome": oc, "pool": k, "value": v} for k, v in act.items()]
            prow += [{"unit": u, "seed": int(r["seed"]), "outcome": oc, "pool": f"rhythm_{g}", "value": v} for g, v in rhy.items()]
        row = {"unit": u, **{d: float(np.mean([p[d] for p in per])) for d in DIMS}, "n_members": int(n_members[u]),
               "n_replicates": len(per)}
        for oc in sorted(set(outc)):
            row[f"n_{oc}"] = outc.count(oc)
        rows.append(row)
    pred = pd.DataFrame(rows)
    for c in [c for c in pred.columns if c.startswith("n_")]:
        pred[c] = pred[c].fillna(0).astype(int)
    return pred, pd.DataFrame(prow)


def hs_values(W: sp.csr_matrix, group: list[int], mn: np.ndarray, masks: dict[str, np.ndarray], k: int, signed: bool) -> dict:
    """P3 / M4: pool value = mean over the pool's motor neurons of (W^k s) (k = 0: s itself, the share of the pool inside the
    group); dimensions 5, 6 and 7' are the constant 0."""
    x = np.zeros(W.shape[0])
    x[np.asarray(group, dtype=np.int64)] = 1.0
    A = W if signed else abs(W)
    for _ in range(k):
        x = A @ x
    v = x[mn]
    pool = {p: (float(v[masks[p]].mean()) if masks[p].any() else 0.0) for p in POOLS}
    return {"d1": max(pool[b] for b in BODY_POOLS), "d2": pool["front_leg"], "d3": pool["middle_leg"], "d4": pool["hind_leg"], "d5": 0.0, "d6": 0.0,
            "d7p": 0.0, "d10": pool["jump"], "d11": pool["wing_any"], "d13": pool["wing_power"], "d14": pool["haltere"],
            "d15": pool["abdomen"]}


def linear_operator(W, sizes) -> sp.csr_matrix:
    """A = diag(a) Wb: the model's mean size-scaled gains and its own coupling (`scaled_weights`), the linearisation of
    tau dr/dt = f(I + Wb r - theta) - r in the active range (f'(0) = a)."""
    from brainir.sim.model import ModelConfig, mean_neuron_params, scaled_weights  # noqa: PLC0415

    cfg = ModelConfig()
    a = mean_neuron_params(cfg, W.shape[0], sizes).a
    return (sp.diags(a) @ scaled_weights(sp.csr_matrix(W, dtype=np.float64), cfg)).tocsr()


def linear_factor(W, sizes):
    """Sparse LU of (I - A) (scipy `splu`, column order COLAMD), and a record of it."""
    from scipy.sparse.linalg import splu  # noqa: PLC0415

    A = linear_operator(W, sizes)
    M = (sp.identity(A.shape[0], format="csc") - A.tocsc()).tocsc()
    lu = splu(M, permc_spec="COLAMD")
    return lu, {"permc_spec": "COLAMD", "nnz_L": int(lu.L.nnz), "nnz_U": int(lu.U.nnz)}


def hs_linear_values(lu, a: np.ndarray, group: list[int], mn: np.ndarray, masks: dict[str, np.ndarray]) -> dict:
    """P3 H-S-lin: x = (I - A)^-1 (a * s); pool value = mean over the pool's motor neurons of x; dims 5, 6, 7' = 0."""
    s = np.zeros(len(a))
    s[np.asarray(group, dtype=np.int64)] = 1.0
    x = lu.solve(a * s)
    v = x[mn]
    pool = {p: (float(v[masks[p]].mean()) if masks[p].any() else 0.0) for p in POOLS}
    return {"d1": max(pool[b] for b in BODY_POOLS), "d2": pool["front_leg"], "d3": pool["middle_leg"], "d4": pool["hind_leg"], "d5": 0.0, "d6": 0.0,
            "d7p": 0.0, "d10": pool["jump"], "d11": pool["wing_any"], "d13": pool["wing_power"], "d14": pool["haltere"],
            "d15": pool["abdomen"]}


def hs_tables(W: sp.csr_matrix, groups: dict[str, list[int]], mn: list[int], masks: dict[str, np.ndarray],
              sizes: np.ndarray | None = None) -> dict[str, pd.DataFrame]:
    W = sp.csr_matrix(W, dtype=np.float64)
    mn = np.asarray(mn, dtype=np.int64)
    out = {}
    for arm in HS_ARMS:
        if arm == "H-S-lin":
            continue
        parts = arm.split("-")
        k = int(parts[2][1:])
        signed = k == 0 or parts[3] == "signed"
        out[arm] = pd.DataFrame([{"unit": u, **hs_values(W, g, mn, masks, k, signed), "n_members": len(g)} for u, g in groups.items()])
    if sizes is not None:
        from brainir.sim.model import ModelConfig, mean_neuron_params  # noqa: PLC0415

        lu, _ = linear_factor(W, sizes)
        a = mean_neuron_params(ModelConfig(), W.shape[0], sizes).a
        out["H-S-lin"] = pd.DataFrame([{"unit": u, **hs_linear_values(lu, a, g, mn, masks), "n_members": len(g)}
                                       for u, g in groups.items()])
    return out


def control_network(net, kind: str, seed: int):
    """H-C (P4): run 1's generators (`controls.build`) applied to the full cord: (matrix, construction statistics)."""
    from . import controls  # noqa: PLC0415

    if kind not in ("rewire", "classshuffle"):
        raise ValueError(kind)
    return controls.build(net, f"H-ctl-{kind}-{int(seed)}")
