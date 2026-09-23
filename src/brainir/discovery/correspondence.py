"""Cross-network neuron correspondence from PUBLIC evidence only (works in the blind tier).

Two networks from different animals/releases have no shared neuron ids and, in the blind tier, no shared interneuron
type tokens. What they do share are the *labelled anchors*: neurons whose public ``cell_type`` is a real label in both
networks (descending, motor and sensory neurons keep their labels) — and the coarse per-neuron annotations
(``hemilineage``, ``soma_neuromere``, ``side``, ``nt_label`` / ``sign``, ``sub_class``).

A neuron's **anchor fingerprint** is its synaptic input from and output to each shared anchor type (log-compressed
synapse counts, L2-normalised). Candidate counterparts of a neuron of network A are the neurons of network B ranked by
a similarity that combines the fingerprint cosine (in and out) with annotation agreement. Scores are reported together
with their z-score against every other B candidate so that "distinctive" matches can be told from "everything looks
alike". Nothing here asserts identity: this is a ranked hypothesis table, exactly like :mod:`brainir.mapping`, but
built from the public bundle alone.

The same code serves the synthetic pair suite, whose exported neuron tables use the same columns.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import scipy.sparse as sp

from .problem import DiscoveryProblem

TOKEN_PREFIX = "T#"
META_COLUMNS = ("hemilineage", "soma_neuromere", "side", "sign", "sub_class")
DEFAULT_WEIGHTS = {"in": 1.0, "out": 1.0, "hemilineage": 0.6, "soma_neuromere": 0.2, "side": 0.1, "sign": 0.4, "sub_class": 0.2}


def is_labelled(cell_type: pd.Series) -> np.ndarray:
    """True for neurons whose public cell type is a real label (not an opaque token, not missing)."""
    s = cell_type.astype("string")
    return (s.notna() & ~s.str.startswith(TOKEN_PREFIX, na=False) & (s.str.len() > 0)).to_numpy()


def shared_anchor_types(a: DiscoveryProblem, b: DiscoveryProblem) -> list[str]:
    la = set(a.neurons.loc[is_labelled(a.neurons["cell_type"]), "cell_type"].astype(str))
    lb = set(b.neurons.loc[is_labelled(b.neurons["cell_type"]), "cell_type"].astype(str))
    return sorted(la & lb)


@dataclass
class Fingerprints:
    """Anchor fingerprints of one network: rows = positions, columns = shared anchor types (in-block then out-block)."""
    anchor_types: list[str]
    inp: np.ndarray
    """(n, k) log1p synapse counts received from each anchor type."""
    out: np.ndarray
    """(n, k) log1p synapse counts sent to each anchor type."""
    meta: pd.DataFrame = field(repr=False)

    @property
    def n(self) -> int:
        return self.inp.shape[0]

    def coverage(self, positions) -> np.ndarray:
        """Total anchor synapses (in + out) per queried position — a neuron with no anchor contact cannot be matched."""
        idx = np.asarray(list(positions), dtype=int)
        return np.expm1(self.inp[idx]).sum(axis=1) + np.expm1(self.out[idx]).sum(axis=1)


def fingerprints(problem: DiscoveryProblem, anchor_types: list[str]) -> Fingerprints:
    types = problem.neurons["cell_type"].astype("string")
    lab = is_labelled(problem.neurons["cell_type"])
    col = {t: j for j, t in enumerate(anchor_types)}
    n, k = problem.n, len(anchor_types)
    # anchor indicator matrix (n x k): A[i, j] = 1 if neuron i is an anchor of type j
    rows = [i for i in np.flatnonzero(lab) if str(types.iloc[i]) in col]
    cols = [col[str(types.iloc[i])] for i in rows]
    A = sp.csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, k))
    C = problem.C  # post x pre observed counts
    inp = np.log1p(np.asarray((C @ A).todense()))  # input to i from anchors of type j
    out = np.log1p(np.asarray((C.T @ A).todense()))  # output from i to anchors of type j
    meta = problem.neurons[[c for c in META_COLUMNS if c in problem.neurons.columns]].copy()
    return Fingerprints(anchor_types, inp, out, meta)


def _unit(x: np.ndarray) -> np.ndarray:
    nrm = np.linalg.norm(x, axis=1, keepdims=True)
    return np.divide(x, nrm, out=np.zeros_like(x), where=nrm > 0)


def _meta_agreement(fa: Fingerprints, ia: int, fb: Fingerprints, cand: np.ndarray, column: str) -> np.ndarray:
    """1 where the annotation is present in both and equal, 0 where present and different, 0.5 (uninformative) otherwise."""
    if column not in fa.meta.columns or column not in fb.meta.columns:
        return np.full(len(cand), 0.5)
    va = fa.meta[column].iloc[ia]
    vb = fb.meta[column].iloc[cand]
    if pd.isna(va) or (column == "sign" and int(va) == 0):
        return np.full(len(cand), 0.5)
    present = vb.notna().to_numpy().copy()
    if column == "sign":
        present = present & (vb.fillna(0).astype(int) != 0).to_numpy()
    eq = (vb.astype(object) == va).to_numpy()
    return np.where(present, eq.astype(float), 0.5)


def match_candidates(a: DiscoveryProblem, b: DiscoveryProblem, positions_a, *, k: int = 5, weights: dict | None = None,
                     fa: Fingerprints | None = None, fb: Fingerprints | None = None, candidates_b=None) -> dict:
    """Rank B neurons as counterparts of each queried A neuron.

    Returns {"anchor_types": [...], "per_neuron": {pos_a: {"candidates": [{"position", "score", "z", "cos_in", "cos_out", "meta"}], "coverage",
    "distinctiveness"}}}. ``distinctiveness`` = z-score of the best candidate against all others (large = a clear favourite).
    ``candidates_b`` defaults to B's discovery candidates (everything but stimulus and readout)."""
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    anchors = shared_anchor_types(a, b)
    fa = fa or fingerprints(a, anchors)
    fb = fb or fingerprints(b, anchors)
    cand = np.asarray(b.candidate_positions() if candidates_b is None else list(candidates_b), dtype=int)
    ua_in, ua_out = _unit(fa.inp), _unit(fa.out)
    ub_in, ub_out = _unit(fb.inp[cand]), _unit(fb.out[cand])
    out: dict = {"anchor_types": anchors, "n_anchor_types": len(anchors), "per_neuron": {}}
    for pa in [int(p) for p in positions_a]:
        cos_in = ub_in @ ua_in[pa]
        cos_out = ub_out @ ua_out[pa]
        score = w["in"] * cos_in + w["out"] * cos_out
        meta_terms = {}
        for c in ("hemilineage", "soma_neuromere", "side", "sign", "sub_class"):
            agree = _meta_agreement(fa, pa, fb, cand, c)
            meta_terms[c] = agree
            score = score + w[c] * (agree - 0.5) * 2  # +w for agreement, -w for disagreement, 0 when uninformative
        mu, sd = float(score.mean()), float(score.std() + 1e-12)
        order = np.argsort(-score)[:k]
        top = [{"position": int(cand[j]), "score": float(score[j]), "z": float((score[j] - mu) / sd), "cos_in": float(cos_in[j]),
                "cos_out": float(cos_out[j]), "meta": {c: float(v[j]) for c, v in meta_terms.items()}} for j in order]
        second = float(score[order[1]]) if len(order) > 1 else mu
        out["per_neuron"][pa] = {"candidates": top, "coverage": float(fa.coverage([pa])[0]),
                                 "distinctiveness": float((score[order[0]] - mu) / sd), "margin_to_second": float(score[order[0]] - second)}
    return out


def mutual_best(a: DiscoveryProblem, b: DiscoveryProblem, positions_a, positions_b, **kw) -> list[tuple[int, int, float]]:
    """Pairs (pos_a, pos_b, score) that are each other's best candidate within the two queried sets."""
    ab = match_candidates(a, b, positions_a, k=max(1, len(list(positions_b))), candidates_b=positions_b, **kw)["per_neuron"]
    ba = match_candidates(b, a, positions_b, k=max(1, len(list(positions_a))), candidates_b=positions_a, **kw)["per_neuron"]
    pairs = []
    for pa, info in ab.items():
        if not info["candidates"]:
            continue
        pb = info["candidates"][0]["position"]
        back = ba.get(pb, {}).get("candidates", [])
        if back and back[0]["position"] == pa:
            pairs.append((int(pa), int(pb), float(info["candidates"][0]["score"])))
    return pairs


def null_match_scores(a: DiscoveryProblem, b: DiscoveryProblem, positions_a, *, n_null: int = 50, seed: int = 0, **kw) -> dict:
    """Best-candidate score/z distribution for random A interneurons — the reference for 'is this match distinctive?'."""
    rng = np.random.default_rng(seed)
    pool = np.array([p for p in a.candidate_positions() if p not in set(int(x) for x in positions_a)])
    picks = rng.choice(pool, size=min(n_null, len(pool)), replace=False)
    res = match_candidates(a, b, picks, k=1, **kw)["per_neuron"]
    z = np.array([v["distinctiveness"] for v in res.values()])
    s = np.array([v["candidates"][0]["score"] for v in res.values() if v["candidates"]])
    return {"n": int(len(z)), "z_mean": float(z.mean()), "z_p95": float(np.percentile(z, 95)), "score_mean": float(s.mean()),
            "score_p95": float(np.percentile(s, 95))}
