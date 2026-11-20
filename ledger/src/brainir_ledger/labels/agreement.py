"""Inter-pass agreement (LABEL SIDE: never reads predictions)."""

from __future__ import annotations

from ..scoring.stats import cohen_kappa  # pure function, no file access
from .aggregate import COMPARED_FIELDS
from .schema import experiment_key


def agreement(pass1: list[dict], pass2: list[dict]) -> dict:
    p2 = {}
    for r in pass2:
        p2.setdefault(r.get("experiment_key") or experiment_key(r), r)
    pairs = [(r, p2[k]) for r in pass1 if (k := r.get("experiment_key") or experiment_key(r)) in p2]
    out = {"n_pass1": len(pass1), "n_pass2": len(pass2), "n_matched": len(pairs), "fields": {}}
    for f in COMPARED_FIELDS:
        a = [x.get(f) for x, _ in pairs]
        b = [y.get(f) for _, y in pairs]
        out["fields"][f] = {"raw_agreement": (sum(u == v for u, v in zip(a, b)) / len(a)) if a else None,
                            "kappa": cohen_kappa(a, b) if a else None}
    yn = [(x["front_leg_rhythm"], y["front_leg_rhythm"]) for x, y in pairs
          if x.get("front_leg_rhythm") in ("yes", "no") and y.get("front_leg_rhythm") in ("yes", "no")]
    out["primary_field_yes_no"] = {"n": len(yn), "raw_agreement": (sum(u == v for u, v in yn) / len(yn)) if yn else None,
                                   "kappa": cohen_kappa([u for u, _ in yn], [v for _, v in yn]) if yn else None}
    return out
