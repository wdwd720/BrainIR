"""Custom evaluation item sets of the post-lock studies: PLANNED HERE (orchestrator side, where the salt is) and BUILT on Modal by
the benchmark's own builder (`suites.build_system_job`: simulation on gated hosts, twins, the onset / twin check, truth, onset states,
store publication) into CUSTOM TIERS on the eval volume (`common.custom_tier`; never public, never in a room).

PROTOCOLS come from the benchmark's sampler (`suites.FamilySampler.make`), so every item is a valid protocol of the system's
capability with the development conventions (onset window, pulse / window durations, stimulus range). Parameter seeds: public-range
seeds for the dry runs (dev tier), HIDDEN-range seeds from the salt for the confirmation tier / real hidden test (`seed_function`),
exactly as the hidden test sets draw theirs; the plan records the rule, never the salt.

COUNTEREXAMPLE GENOME (`random_genome`, `mutate`, `realize`): family (the system's supported intervention families: trained,
held-out and hidden-only; the model's own validity() decides what is in its domain), target set / edges (public and held-out
targets), magnitude multiplier m in [0.1, 3] of the moderate magnitude (the development range: the strong class ends at 3 x
moderate), onset fraction in [0.1, 0.6] of the duration, stimulus level fraction in the public stimulus range, parameter seed (a
new trajectory draw). Realisation is deterministic in (candidate id, genome).

ROBUSTNESS GRIDS (`robustness_specs`): the conditions of PROTOCOL 4.2 on finer level grids (goal5 section 75), in-family families,
ITEMS_PER_LEVEL items per (condition, level) plus a nominal anchor; told events differ from the simulated ones only for the amplitude
/ timing jitter conditions (meta model_events, as `suites.design_robust`).
"""

from __future__ import annotations

import hashlib
import json

import numpy as np

from brainir_causal import families as F
from brainir_causal import protocol as P
from brainir_causal import suites as SU

MULT_RANGE = (0.1, 3.0)
ONSET_RANGE = (0.1, 0.6)
ITEMS_PER_LEVEL = 8
#: robustness grids: condition -> levels (the PROTOCOL 4.2 levels are included; 'nominal' is the unperturbed anchor)
ROBUST_GRID = {
    "param_noise": (1.25, 1.5, 1.75, 2.0, 2.5),          # params_spread (hidden-range draws post-lock)
    "weight_noise": (0.025, 0.05, 0.075, 0.1, 0.15),     # weight-noise sd
    "process_noise": (0.025, 0.05, 0.1, 0.2),            # process-noise sd (only where the capability supports it)
    "obs_noise": (0.025, 0.05, 0.1, 0.2),                # observation-noise sd (fraction of obs_scale)
    "amplitude_jitter": (0.1, 0.2, 0.3, 0.5),            # untold relative amplitude jitter U(1 - j, 1 + j)
    "timing_jitter": (1, 2, 4, 8),                       # untold event-time jitter, +-k samples
}


def _h(*parts) -> int:
    return int(hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:16], 16)


def seed_function(hidden: bool, *parts):
    """Parameter-seed stream: hidden range from the salt (post-lock) or public range (dry runs)."""
    if hidden:
        SU.require_lock("hidden-range seeds of a post-lock item set")
    return SU.seed_counter(hidden, "p4post", *parts)


def targets_edges(pub: dict, internal: dict) -> tuple[list[int], list, list]:
    """(all targets: public + held-out, public edges (graph edges for systems without public edges), held-out edges)."""
    tg = sorted({int(t) for t in (pub.get("targets_public") or [])} | {int(t) for t in (internal.get("targets_heldout") or [])})
    e_pub = [list(map(int, e)) for e in (pub.get("edges_public") or [])]
    if not e_pub:
        try:
            e_pub = SU._graph_edges(pub)
        except Exception:  # noqa: BLE001 - no public connectivity summary
            e_pub = []
    e_hid = [list(map(int, e)) for e in (internal.get("edges_heldout") or [])]
    return tg, e_pub, e_hid


def sampler(pub: dict, internal: dict, rng: np.random.Generator, seed_fn) -> SU.FamilySampler:
    tg, e_pub, e_hid = targets_edges(pub, internal)
    return SU.FamilySampler(pub, rng, seed_fn, targets=tg, edges=e_pub + [e for e in e_hid if e not in e_pub])


def search_families(pub: dict, internal: dict, exclude: tuple | list = ()) -> list[str]:
    """The system's supported, feasible intervention families (trained first, then held-out and hidden-only), minus `exclude` (a
    recorded restriction, e.g. a dry run on a generator whose event kinds do not yet pass the builder's onset check)."""
    split = pub.get("split") or {}
    s = sampler(pub, internal, np.random.default_rng(0), lambda: 0)
    sup = set(F.supported_families(s.cap))
    order = list(split.get("families_train") or []) + list(split.get("families_heldout") or []) + list(split.get("hidden_only") or [])
    out = []
    for f in order + [f for f in F.INTERVENTION_FAMILIES if f not in order]:
        if (f in F.INTERVENTION_FAMILIES and f in sup and f not in out and f not in ("kick.hi", "pulse.hi") and f not in set(exclude)
                and SU.feasible(f, s.targets, s.edges)):
            out.append(f)
    return out


def _mclass_of(m: float) -> str:
    return "below" if m < 0.2 else ("weak" if m < 0.6 else ("moderate" if m < 2.0 else "strong"))


def _scale_events(events: list[dict], m: float, cap: dict) -> list[dict]:
    """Magnitudes x m, clipped to the capability maxima (kick / current); edge-scaling depth x m (<= 0.95); parameter changes x m."""
    out = json.loads(json.dumps(events))
    for e in out:
        k = e.get("kind")
        if k == "kick":
            mx = float((cap.get("kick") or {}).get("max") or np.inf)
            e["delta"] = {u: float(np.clip(float(v) * m, -mx, mx)) for u, v in e["delta"].items()}
        elif k == "current":
            mx = float((cap.get("current") or {}).get("max") or np.inf)
            e["targets"] = {u: float(np.clip(float(v) * m, -mx, mx)) for u, v in e["targets"].items()}
        elif k == "current_seq":
            mx = float((cap.get("current") or {}).get("max") or np.inf)
            e["targets"] = {u: [float(np.clip(float(v) * m, -mx, mx)) for v in lst] for u, lst in e["targets"].items()}
        elif k == "edge_scale" and float(e.get("factor", 1.0)) > 0:
            e["factor"] = float(1.0 - min(SU.EDGE_DEPTH_MAX, (1.0 - float(e["factor"])) * m))
        elif k == "param":
            e["targets"] = {u: {kk: (max(0.05, 1.0 + (float(x) - 1.0) * m) if kk in ("gain", "tau") else float(x) * m) for kk, x in v.items()}
                            for u, v in e["targets"].items()}
    return out


def random_genome(pub: dict, internal: dict, fams: list[str], rng: np.random.Generator, seed_fn, cid: str) -> dict:
    s = sampler(pub, internal, rng, seed_fn)
    fam = fams[int(rng.integers(len(fams)))]
    g = {"cid": cid, "family": fam, "mult": float(np.exp(rng.uniform(np.log(MULT_RANGE[0]), np.log(MULT_RANGE[1])))),
         "onset_frac": float(rng.uniform(*ONSET_RANGE)), "level_frac": float(rng.uniform(0.0, 1.0)), "params_seed": int(seed_fn()),
         "targets": None, "edges": None, "parent": None}
    g.update(_pick_targets(fam, s, rng))
    return g


def _pick_targets(fam: str, s: SU.FamilySampler, rng: np.random.Generator) -> dict:
    if fam in ("edge.w", "edge.rm"):
        k = min(len(s.edges), int(rng.integers(1, 3)))
        return {"edges": [list(s.edges[i]) for i in sorted(rng.choice(len(s.edges), size=k, replace=False))], "targets": None}
    n = {"kick.2": 2, "pulse.2": 2, "sil.2": 2, "kick.g": 3, "pulse.g": 3, "sil.g": 3}.get(fam, 2 if fam in F.COMP else 1)
    n = min(n, len(s.targets))
    return {"targets": sorted(int(x) for x in rng.choice(s.targets, size=n, replace=False)), "edges": None}


def mutate(g: dict, pub: dict, internal: dict, fams: list[str], rng: np.random.Generator, seed_fn, cid: str) -> dict:
    """A child of genome g: family switched with probability 0.15 (targets re-drawn), targets re-drawn with probability 0.3,
    log-magnitude + N(0, 0.35), onset + N(0, 0.08), level + N(0, 0.15), a new trajectory draw with probability 0.5."""
    s = sampler(pub, internal, rng, seed_fn)
    c = dict(g, cid=cid, parent=g["cid"])
    if rng.random() < 0.15 and len(fams) > 1:
        c["family"] = fams[int(rng.integers(len(fams)))]
        c.update(_pick_targets(c["family"], s, rng))
    elif rng.random() < 0.3:
        c.update(_pick_targets(c["family"], s, rng))
    c["mult"] = float(np.clip(np.exp(np.log(c["mult"]) + rng.normal(0, 0.35)), *MULT_RANGE))
    c["onset_frac"] = float(np.clip(c["onset_frac"] + rng.normal(0, 0.08), *ONSET_RANGE))
    c["level_frac"] = float(np.clip(c["level_frac"] + rng.normal(0, 0.15), 0.0, 1.0))
    if rng.random() < 0.5:
        c["params_seed"] = int(seed_fn())
    return c


def realize(g: dict, pub: dict, internal: dict, role: str) -> SU.Spec:
    """The candidate's test item (with twin): `FamilySampler.make` with the genome's family / targets / edges / onset / level / seed
    (moderate class), magnitudes scaled by the multiplier. Deterministic in the genome."""
    rng = np.random.default_rng(_h("realize", g["cid"], json.dumps(g, sort_keys=True, default=str)))
    s = sampler(pub, internal, rng, lambda: int(g["params_seed"]))
    lo, hi = s.stim_range
    fam = g["family"]
    p, info = s.make(fam, targets=g.get("targets"), edges=g.get("edges"), mclass=None if fam.startswith("sil.") else "moderate",
                     onset=float(g["onset_frac"]) * s.T, params_seed=int(g["params_seed"]), level=float(lo + g["level_frac"] * (hi - lo)))
    if fam not in ("sil.1", "sil.2", "sil.g", "sil.1p", "edge.rm"):
        m = float(g["mult"])
        p["events"] = _scale_events(p["events"], m, s.cap)
        info = dict(info, mclass=_mclass_of(m))
        if info.get("components"):                      # composition items: the single components scaled alike
            comp = dict(info["components"])
            comp["a"], comp["b"] = _scale_events(comp["a"], m, s.cap), _scale_events(comp["b"], m, s.cap)
            info["components"] = comp
    P.validate(p)
    return SU._spec(p, info, "test", role, twin=True, cell=f"{role}|{g['cid']}", state=0, p4post={"cid": g["cid"]})


def _jitter_told(events: list[dict], s: SU.FamilySampler, cond: str, level: float) -> list[dict]:
    out = json.loads(json.dumps(events))
    for e in out:
        if cond == "amplitude_jitter":
            f = float(s.rng.uniform(1.0 - level, 1.0 + level))
            out_e = _scale_events([e], f, s.cap)[0]
            e.clear()
            e.update(out_e)
        else:
            sh = int(s.rng.choice([k for k in range(-int(level), int(level) + 1) if k != 0])) * s.dt
            for key in ("t", "t0", "t1"):
                if e.get(key) is not None:
                    e[key] = round(min(s.T, max(s.dt, float(e[key]) + sh)), 9)
    return out


def robustness_specs(pub: dict, internal: dict, seed_fn, *, items_per_level: int = ITEMS_PER_LEVEL, grid: dict | None = None,
                     exclude: tuple | list = ()) -> tuple[list, dict]:
    """(specs, counts) of one system's robustness grid (module docstring). Levels a system cannot express (e.g. process noise without
    capability support, a protocol the validator refuses) are skipped and counted. `exclude`: families left out (recorded); when no
    in-family family remains, the first supported of kick.1 / pulse.1 / act.1 is used."""
    grid = grid or ROBUST_GRID
    rng = np.random.default_rng(_h("robust", pub["system_id"]))
    tg, e_pub, _ = targets_edges(pub, internal)
    s = SU.FamilySampler(pub, rng, seed_fn, targets=list(pub.get("targets_public") or tg), edges=e_pub)
    fams = [f for f in SU._in_family(s, pub, e_pub) if f not in set(exclude)]
    if not fams:
        kinds = {"kick.1": "kick", "pulse.1": "current", "act.1": "current"}
        fams = [f for f, k in kinds.items() if s.cap.get(k, {}).get("supported") and f not in set(exclude)][:1]
    counts_fams = list(fams)
    pn_ok = bool(s.cap.get("process_noise", {}).get("supported")) and SU.protocol_has("process_noise")
    specs: list = []
    counts = {"skipped": {}, "levels": {}, "families": counts_fams}

    def add(p, info, role, j, **meta):
        try:
            P.validate(p)
        except P.ProtocolError as e:
            counts["skipped"][role] = counts["skipped"].get(role, 0) + 1
            counts.setdefault("errors", []).append(f"{role}: {str(e)[:120]}")
            return
        specs.append(SU._spec(p, info, "test", role, twin=True, cell=f"{role}|{info['family']}", state=j, **meta))
        counts["levels"][role] = counts["levels"].get(role, 0) + 1

    for j in range(items_per_level):
        fam = fams[j % len(fams)]
        p, info = s.make(fam, params_seed=seed_fn())
        add(p, info, "robust:nominal@0", j)
    for cond, levels in grid.items():
        if cond == "process_noise" and not pn_ok:
            counts["skipped"][f"robust:{cond}"] = "not supported by the system's capability"
            continue
        for lv in levels:
            role = f"robust:{cond}@{lv}"
            for j in range(items_per_level):
                fam = fams[j % len(fams)]
                p, info = s.make(fam, params_seed=seed_fn())
                meta = {}
                if cond == "param_noise":
                    if not SU._spread(p, float(lv), seed_fn):
                        meta["proxy"] = True
                elif cond == "weight_noise":
                    p["weight_noise"] = {"sd": float(lv), "seed": int(seed_fn())}
                elif cond == "process_noise":
                    p["process_noise"] = {"sd": float(lv), "seed": int(seed_fn())}
                elif cond == "obs_noise":
                    p["obs_noise"] = {"sd": float(lv), "seed": int(seed_fn())}
                else:
                    told = p["events"]
                    p["events"] = _jitter_told(told, s, cond, float(lv))
                    meta["model_events"] = told
                add(p, info, role, j, **meta)
    return specs, counts


def build_job(sid: str, kind: str, tier: str, pub: dict, internal: dict, specs: list, *, workers: int = 16) -> dict:
    """A `suites.build_system_job` job for one system's custom item set (dest 'eval', sets 'tests', policy 'full')."""
    gen = [SU.GENERATOR_CONTAINER, "p4synth"] if kind == "synthetic" else None
    return {"sid": sid, "kind": kind, "tier": tier, "seed": int(internal.get("tier_seed") or 0), "level": "C", "pub": pub,
            "internal": internal, "parts": [{"dest": "eval", "sets": ["tests"], "policy": "full", "specs": [SU.spec_to_dict(x) for x in specs]}],
            "dirs": SU.remote_dirs(tier, kind=kind), "store_root": f"/tmp/p4build/{SU._safe(sid)}/store", "workers": int(workers),
            "generator": gen, "publish_store": SU.REMOTE["eval_store"], "with_truth": True}
