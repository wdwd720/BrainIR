"""Features of a PUBLIC system record for the leakage tests (review round 3, B1): every numeric field of `public_record()` (the
capability record included, after the benchmark's normalisation: system-wide scalars), obs_scale, and statistics of the public
graph (edges) and of the per-unit lists (observed, targets). Per-unit features for the role test: observed, targetable, listed
in- and out-degree."""

from __future__ import annotations

import numpy as np

PER_UNIT_KEYS = {"observed", "targets", "edges", "units"}      # per-unit lists: summarised by graph / list statistics below


def _flatten(o, prefix, out):
    if isinstance(o, bool):
        out[prefix] = float(o)
    elif isinstance(o, (int, float, np.integer, np.floating)):
        out[prefix] = float(o)
    elif isinstance(o, dict):
        for k, v in o.items():
            if k in PER_UNIT_KEYS:
                continue
            _flatten(v, f"{prefix}.{k}" if prefix else str(k), out)
    elif isinstance(o, (list, tuple)):
        if len(o) <= 8:                                           # short numeric lists (ranges, nominal stimulus): element-wise
            for i, v in enumerate(o):
                _flatten(v, f"{prefix}[{i}]", out)
        else:
            out[prefix + ".len"] = float(len(o))


def graph_stats(rec: dict) -> dict:
    N = int(rec["n_units"])
    obs = np.zeros(N, bool)
    obs[list(rec["observed"])] = True
    tg = np.zeros(N, bool)
    tg[list(rec["targets"])] = True
    E = np.array(rec["edges"], int).reshape(-1, 2)
    indeg = np.bincount(E[:, 0], minlength=N) if E.size else np.zeros(N)
    outdeg = np.bincount(E[:, 1], minlength=N) if E.size else np.zeros(N)
    pairs = {(int(a), int(b)) for a, b in E}
    recip = np.mean([(b, a) in pairs for a, b in pairs]) if pairs else 0.0
    out = {"g.n_edges": float(len(E)), "g.edges_per_unit": len(E) / N, "g.recip": float(recip),
           "g.frac_obs": float(obs.mean()), "g.frac_tg": float(tg.mean()), "g.frac_tg_obs": float((tg & obs).mean()),
           "g.n_obs": float(obs.sum()), "g.n_tg": float(tg.sum())}
    for nm, d in (("in", indeg), ("out", outdeg)):
        out.update({f"g.{nm}.max": float(d.max()), f"g.{nm}.mean": float(d.mean()), f"g.{nm}.sd": float(d.std()),
                    f"g.{nm}.frac_pos": float((d > 0).mean()), f"g.{nm}.p90": float(np.percentile(d, 90))})
    if E.size:
        out["g.pre_obs"] = float(obs[E[:, 1]].mean())
        out["g.pre_tg"] = float(tg[E[:, 1]].mean())
        out["g.post_obs"] = float(obs[E[:, 0]].mean())
        out["g.distinct_pre_frac"] = len(set(E[:, 1].tolist())) / N
    return out


def record_features(rec: dict) -> dict:
    """{name: value} for every numeric public field + graph statistics + ratios of the published magnitudes."""
    out: dict = {}
    _flatten({k: v for k, v in rec.items() if k not in ("system_id", "kind", "engine_id", "content_hash", "public_graph")}, "", out)
    out.update(graph_stats(rec))
    cap = rec["capability"]
    fields = (cap.get("param") or {}).get("fields") or []            # published parameter fields (review v3.3, N7)
    out["cap.param.n_fields"] = float(len(fields))
    for f in ("gain", "threshold", "tau"):
        out[f"cap.param.has_{f}"] = float(f in fields)
    mk, mc = cap["kick"]["moderate"], cap["current"]["moderate"]
    ox, oy = rec["obs_scale"]["x"], rec["obs_scale"]["y"]
    lo, hi = cap["admissible_range"]["lo"], cap["admissible_range"]["hi"]
    for nm, v in (("r.range_over_mk", (hi - lo) / mk), ("r.ox_over_mk", ox / mk), ("r.mc_over_mk", mc / mk),
                  ("r.floor_over_oy", cap["readout_floor"] / oy), ("r.noise_over_mk", cap["process_noise"]["sd_per_sqrt_s"] / mk),
                  ("r.kfloor_over_mk", cap["kick"]["detection_floor"] / mk), ("r.cfloor_over_mc", cap["current"]["detection_floor"] / mc)):
        out[nm] = float(np.log10(max(v, 1e-12)))
    return out


def unit_features(rec: dict) -> np.ndarray:
    N = int(rec["n_units"])
    E = np.array(rec["edges"], int).reshape(-1, 2)
    indeg = np.bincount(E[:, 0], minlength=N) if E.size else np.zeros(N)
    outdeg = np.bincount(E[:, 1], minlength=N) if E.size else np.zeros(N)
    obs = np.isin(np.arange(N), rec["observed"]).astype(float)
    tg = np.isin(np.arange(N), rec["targets"]).astype(float)
    return np.column_stack([obs, tg, indeg, outdeg])


def suite_records(seed: int, n_per_type: int = 4, tier: str = "dev") -> list[dict]:
    """Public records (and truth labels) of one suite, for the leakage tests (a module-level function: usable in worker processes)."""
    from .suite import build_suite
    out = []
    for s in build_suite(tier, seed, n_per_type=n_per_type).values():
        out.append({"seed": seed, "type": s.info["type"], "k": str(s.info["k"]), "rec": s.public_record(),
                    "roles": s.spec.role.tolist()})
    return out
