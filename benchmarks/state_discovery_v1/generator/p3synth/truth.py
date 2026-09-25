"""Truth: per-system ground truth and the truth writer (the ONLY code that writes into a truth directory).

Truth directory layout (see SYNTHETIC_BENCHMARK.md):

    truth.json            {"suite": {...split design, groups, unrelated pairs...}, "systems": {system_id: system_truth}}
    systems/<sid>.npz     E (N,K), D (K,N), b (N,), phi_kind (N,), phi_scale (N,), observed, lam, sigma_priv, obs_sigma
    latents/<key>.npz     z (T,k) true latent, coords (T,K) all coordinates, exo (T,n_exo) if any, A (K,K) if weight noise
    truth_index.jsonl     one line per trajectory: key, system_id, split, family, effective theta, latent events, step
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .core import PHI_NAMES
from .systems import TRAPS

INTERVENTIONS = {
    "kick": "x_j += d at the event time (pre-kick sample recorded at t); for saturating neurons x is clipped to just "
            "inside the activation's range; moves the latent by D[:k, j] * dv_j, the off-manifold part decays at rate lam",
    "current": "extra drive I added to dv_j/dt (activation units per second) during [t0, t1); cut while the neuron is silenced",
    "silence": "during [t0, t1) the neuron's output is removed from every population sum (its (v_j - b_j) contributes 0) and "
               "all its inputs (population drive, stimulus, synaptic noise, injected current) are cut; its activation "
               "relaxes to baseline at rate lam; recorded x shows that relaxation; it rejoins at t1",
    "edge_remove": "post neuron i computes its population signal without pre neuron j during [t0, t1); an edge exists iff "
                   "D[:, j] != 0 (j is synaptically read) and E[i] != 0 (i is driven); removing a non-existent edge has no effect",
    "latent_set": "do(z_i := v): dv = E_act (D'_act E_act)^-1 dc with dc = (v - z_i) e_i, applied to the active neurons; "
                  "changes z_i exactly and no other coordinate",
    "latent_impulse": "same lifting with dc = delta",
}


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    return o


def observability(system) -> dict:
    im, m = system.impl, system.model
    k, K = m.k, m.K
    obs = system.observed
    E_obs = im.E[obs]
    r_all = np.linalg.matrix_rank(E_obs, tol=1e-9)
    r_rest = np.linalg.matrix_rank(E_obs[:, k:], tol=1e-9) if K > k else 0
    decodable = (r_all - r_rest) == k
    sv = np.linalg.svd(E_obs[:, :k], compute_uv=False)
    causal = [int(j) for j in range(system.n) if np.any(im.D[:k, j] != 0)]
    eff = np.linalg.norm(im.D[:k], axis=0)
    return {
        "z_linearly_decodable_from_observed_activations": bool(decodable),
        "note_decodability": "after inverting each neuron's activation (x -> v); noise-free; the latent embedding is linear "
                             "in activation space",
        "observed_latent_singular_values": sv.tolist(),
        "n_causal_neurons": len(causal),
        "causal_neurons": causal,
        "kick_effect_norm_per_neuron": eff.tolist(),
        "unobserved_neurons": sorted(set(range(system.n)) - set(obs)),
    }


def system_truth(system) -> dict:
    m, im, meta = system.model, system.impl, system.meta
    lat = m.latent
    li = lat.info()
    k_val = "none" if lat.family == "high_dimensional" else int(m.k)
    spec = dict(im.spec)
    spec.pop("blocks", None)
    roles = im.roles
    role_count = {r: roles.count(r) for r in sorted(set(roles))}
    obs_map = {
        "code": spec.get("code"), "activation": spec.get("phi"), "mixed_sign": spec.get("mixed_sign"),
        "n_core": spec.get("n_core"), "causal_frac": spec.get("causal_frac", 1.0), "core_gain": spec.get("core_gain", 1.0),
        "observation_noise_rel": spec.get("obs_noise", 0.05), "private_noise_rel": spec.get("priv_noise", 0.05),
        "frac_unobserved": spec.get("frac_unobserved", 0.0), "lam": im.lam,
        "activations_used": sorted({PHI_NAMES[int(q)] for q in im.phi.kind}),
        "neuron_role_counts": role_count,
        "blocks": [{"role": b.role, "dim": b.dim, "description": b.describe(), **(im.spec.get("blocks") or [{}] * len(m.blocks))[i]}
                   for i, b in enumerate(m.blocks)],
        "permuted": bool(spec.get("permute", True)),
    }
    trap = meta.get("trap")
    return _jsonable({
        "system_id": system.system_id,
        "name": meta.get("name"),
        "family_no": meta.get("family_no"),
        "family": meta.get("family"),
        "dynamics_type": f"{lat.family}/{lat.variant}",
        "trap": trap,
        "trap_description": TRAPS.get(trap) if trap else None,
        "k": k_val,
        "k_coordinates": int(m.k),
        "K_total_coordinates": int(m.K),
        "coordinates": [{"index": i, "name": nme, "role": r} for i, (nme, r) in enumerate(zip(m.coordinate_names(), m.coordinate_roles()))],
        "n": system.n,
        "n_observed": len(system.observed),
        "input_dim": m.n_u, "readout_dim": m.n_y, "exogenous_dim": m.n_exo,
        "latent": li,
        "input_pattern": lat.input_pattern.tolist(),
        "f": li["f"], "g": li["g"], "notes": " ".join(x for x in [li["notes"], meta.get("notes", "")] if x),
        "timescales": li["timescales"],
        "closed_dynamics": m.n_exo == 0,
        "observation_map": obs_map,
        "implementation_group": f"grp-{meta['group']}" if meta.get("group") else f"grp-{system.system_id}",
        "latent_key": meta.get("latent_key"),
        "unrelated_pair": meta.get("pair"),
        "neuron_roles": {str(i): r for i, r in enumerate(roles)},
        "observability": observability(system),
        "controllability": {
            "inputs": "u enters f as described in 'f' (input_pattern gives the nominal direction for scalar stimuli)",
            "micro": "a kick dx_j moves c by D'[:, j] dv_j; a current I_j drives dc/dt by D'[:, j] I_j; neurons with "
                     "zero D[:k, j] cannot move z (see observability.kick_effect_norm_per_neuron)",
            "latent": "latent_set / latent_impulse reach every latent direction exactly (lift_latent)",
        },
        "interventions": INTERVENTIONS,
        "weight_noise": "D' = D * (1 + sd xi) on existing synapses (xi ~ N(0,1) from the seed); the recorded latent is "
                        "c = D'(v - b), which obeys dc/dt = A F(c) - lam (I - A) c with A = D'E (stored per trajectory)",
        "integration": {"method": "classical RK4 on the neurons' activations with fixed substep h; additive noise added "
                                  "after each substep (Euler-Maruyama split)", "h_max": system.h_max},
        "readout_noise": system.readout_noise,
        "meta": meta,
    })


def write_system_arrays(out_truth: Path, system) -> None:
    im = system.impl
    d = Path(out_truth) / "systems"
    d.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(d / f"{system.system_id}.npz", E=im.E, D=im.D, b=im.b, phi_kind=im.phi.kind, phi_scale=im.phi.scale,
                        observed=np.asarray(system.observed), lam=np.asarray(im.lam), sigma_priv=im.sigma_priv,
                        obs_sigma=im.obs_sigma, roles=np.asarray(im.roles))


def write_latent(out_truth: Path, key: str, out: dict) -> dict:
    """Write one trajectory's truth arrays; return its truth-index entry (without key/system/split)."""
    d = Path(out_truth) / "latents"
    d.mkdir(parents=True, exist_ok=True)
    tr = out["info"]["truth"]
    arrs = {"z": np.asarray(out["z"], np.float32), "coords": np.asarray(tr["coords"], np.float32)}
    if "exo" in tr:
        arrs["exo"] = np.asarray(tr["exo"], np.float32)
    if "A" in tr:
        arrs["A"] = np.asarray(tr["A"], np.float64)
    np.savez_compressed(d / f"{key}.npz", **arrs)
    return {"theta": tr["theta"], "latent_events": tr["latent_events"], "h": tr["h"], "n_substeps": tr["n_substeps"]}


def write_truth(out_truth: Path, systems: list, suite: dict, rows: list[dict]) -> None:
    out_truth = Path(out_truth)
    out_truth.mkdir(parents=True, exist_ok=True)
    per = {}
    for s in systems:
        t = system_truth(s)
        partners = [o.system_id for o in systems if o is not s and o.meta.get("pair") and o.meta.get("pair") == s.meta.get("pair")]
        t["unrelated_partner"] = partners[0] if partners else None
        t["group_members"] = [o.system_id for o in systems if s.meta.get("group") and o.meta.get("group") == s.meta.get("group")]
        t["split_design"] = suite.get("split_design", {}).get(s.system_id)
        per[s.system_id] = t
        write_system_arrays(out_truth, s)
    (out_truth / "truth.json").write_text(json.dumps(_jsonable({"suite": suite, "systems": per}), indent=1, sort_keys=True) + "\n",
                                          encoding="utf-8", newline="\n")
    with open(out_truth / "truth_index.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(_jsonable(r), sort_keys=True) + "\n")
