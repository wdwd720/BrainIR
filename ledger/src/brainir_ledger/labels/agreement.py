"""Inter-pass agreement (LABEL SIDE: never reads predictions). Records are matched by `exp_id` only."""

from __future__ import annotations

from ..scoring.stats import cohen_kappa  # pure function, no file access
from .aggregate import COMPARED_FIELDS


def agreement(pass1: list[dict], pass2: list[dict]) -> dict:
    p2 = {}
    for r in pass2:
        p2.setdefault(r["exp_id"], r)
    pairs = [(r, p2[r["exp_id"]]) for r in pass1 if r["exp_id"] in p2]
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
    allf = [(x.get("front_leg_rhythm"), y.get("front_leg_rhythm")) for x, y in pairs]
    out["primary_field_all_values"] = {"n": len(allf), "raw_agreement": (sum(u == v for u, v in allf) / len(allf)) if allf else None,
                                       "kappa": cohen_kappa([u for u, _ in allf], [v for _, v in allf]) if allf else None}
    return out
