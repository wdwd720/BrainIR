"""Projected wall time of the Level B rounds (research/phase4/LEVEL_B_EXECUTION.md section 7) from MEASURED per-job durations, via
scripts/p4/project_round.py (LPT list scheduling onto containers x slots). Assumptions are explicit in ASSUME.

    uv run --no-sync --project phase4 python scripts/p4/project_level_b.py OUT.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import project_round as PR  # noqa: E402

# measured (P1 dry runs, packed classes, 3 threads per fit job): median / p90 / max seconds
FIT = {"cand": {"syn": (678, 950, 2104), "mech": (494, 533, 612), "full": (902, 946, 972)},     # the FULL-STATE stand-in
       "base": {"syn": (407, 642, 864), "mech": (297, 381, 585), "full": (698, 1524, 1646)}}   # frozen_brainir_state_v1
EVAL = {"syn": (1025, 1300, 1600), "mech": (790, 875, 875), "full": (2000, 2000, 2000)}          # syn: dev round mean; full ASSUMED
REF = {"syn": 1280, "mech": 700, "full": 1400}                                                    # per (system, reference): syn = dev round mean; full ASSUMED
ASSUME = {"containers": 90, "slots": 8, "startup_s": 90, "fit_containers_while_refs": 60, "ref_containers": 30,
          "loop_s_budget200": 6500, "loop_s_budget100": 3800, "ckpt_eval_s": 900}


def groups_for(kind: str, n: int, dur: tuple, stage: str, cls: str, name: str) -> list:
    """n jobs of one kind: 70 % at the median, 20 % at the p90, 10 % at the max (a conservative tail)."""
    med, p90, mx = dur
    a, b = round(0.7 * n), round(0.2 * n)
    return [{"name": f"{name}:{kind}:med", "stage": stage, "n": a, "seconds": med, "cls": cls},
            {"name": f"{name}:{kind}:p90", "stage": stage, "n": b, "seconds": p90, "cls": cls},
            {"name": f"{name}:{kind}:max", "stage": stage, "n": n - a - b, "seconds": mx, "cls": cls}]


def round_spec(n_cand: int, n_base: int, n_syn: int, n_mech: int, n_full: int, seeds: int = 3, loops: dict | None = None) -> dict:
    g = []
    for who, nm in (("cand", n_cand), ("base", n_base)):
        for kind, ns in (("syn", n_syn), ("mech", n_mech), ("full", n_full)):
            if nm * ns:
                g += groups_for(kind, nm * ns * seeds, FIT[who][kind], "fits", "iso_pack_fit", f"fit:{who}")
                g += groups_for(kind, nm * ns * seeds, EVAL[kind], "evaluations", "iso_pack_eval", f"eval:{who}")
    for kind, ns in (("syn", n_syn), ("mech", n_mech), ("full", n_full)):
        if ns:
            g.append({"name": f"ref:{kind}", "stage": "references", "n": 7 * ns, "seconds": REF[kind], "cls": "pack_xl"})
    if loops:
        nl = loops["candidates"] * loops["designers"] * loops["seeds"]
        g.append({"name": "loops:b200", "stage": "loops", "n": nl * (n_syn + n_mech), "seconds": ASSUME["loop_s_budget200"], "cls": "iso_pack_loop"})
        g.append({"name": "loops:b100", "stage": "loops", "n": nl * n_full, "seconds": ASSUME["loop_s_budget100"], "cls": "iso_pack_loop"})
        g.append({"name": "ckpt:5", "stage": "checkpoint-evals", "n": 5 * nl * (n_syn + n_mech), "seconds": ASSUME["ckpt_eval_s"], "cls": "iso_pack_eval"})
        g.append({"name": "ckpt:4", "stage": "checkpoint-evals", "n": 4 * nl * n_full, "seconds": ASSUME["ckpt_eval_s"], "cls": "iso_pack_eval"})
    c = ASSUME["containers"]
    return {"containers": {"iso_pack_fit": ASSUME["fit_containers_while_refs"], "pack_xl": ASSUME["ref_containers"], "iso_pack_eval": c,
                           "iso_pack_loop": c},
            "slots": {"iso_pack_fit": ASSUME["slots"], "pack_xl": ASSUME["slots"], "iso_pack_eval": ASSUME["slots"], "iso_pack_loop": ASSUME["slots"]},
            "startup_s": ASSUME["startup_s"], "groups": g, "concurrent": [["fits", "references"]]}


ROUNDS = {  # PROTOCOL section 10 (8 candidates + 2 baselines in the pilot is an assumption)
    "pilot (8 cand + 2 base, 25 syn + 3 real mech)": dict(n_cand=8, n_base=2, n_syn=25, n_mech=3, n_full=0),
    "medium (4 cand + 2 base, 50 syn + 7 real mech)": dict(n_cand=4, n_base=2, n_syn=50, n_mech=7, n_full=0),
    "finalists, no loops (3 cand + 1 base, 50 syn + 10 real)": dict(n_cand=3, n_base=1, n_syn=50, n_mech=7, n_full=3),
    "full, 3 cand x 9 designers x 3 loop seeds": dict(n_cand=3, n_base=1, n_syn=50, n_mech=7, n_full=3,
                                                      loops={"candidates": 3, "designers": 9, "seeds": 3}),
    "full, 3 cand x 2 designers x 1 loop seed": dict(n_cand=3, n_base=1, n_syn=50, n_mech=7, n_full=3,
                                                     loops={"candidates": 3, "designers": 2, "seeds": 1}),
}
out = {"assumptions": ASSUME, "fit_s": FIT, "eval_s": EVAL, "ref_s": REF, "rounds": {}}
for name, kw in ROUNDS.items():
    res = PR.project(round_spec(**kw))
    out["rounds"][name] = res
    st = {k: v["makespan_s"] for k, v in res["stages"].items()}
    print(f"{name:58s} total {res['total_h']:6.2f} h  stages {st}")
Path(sys.argv[1]).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
