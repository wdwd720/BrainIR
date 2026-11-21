"""Motor map v1 for run 3 (RUN3_PROMPT section 5, "Motor map first"): every motor neuron of the authors' full-cord network ->
body part, segment, side, action and the phenotype pools it feeds. Built from the connectome annotations alone (MANC `class`,
`subclass`, `type`, `motor module`, `somaNeuromere`, `somaSide`) plus fixed name rules for wing, haltere and leg muscle names
(listed in RULES below, with their anatomical basis). No activation outcome of any group is used. Checked by a fresh reviewer and
frozen with PREREG v3.

    uv run --project ledger --no-sync python ledger/scripts/motor_map_v3.py   # -> research/ledger/motor_map/MOTOR_MAP_v1.csv, .json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
from brainir_ledger import RESEARCH  # noqa: E402
from brainir_ledger import networks as N  # noqa: E402

OUT = RESEARCH / "motor_map"

BODY = {"fl": "front_leg", "ml": "middle_leg", "hl": "hind_leg", "wm": "wing", "hm": "haltere", "ad": "abdomen", "nm": "neck", "xm": "unknown"}
LEG_SEG = {"front_leg": "T1", "middle_leg": "T2", "hind_leg": "T3"}
MODULE = {"tibia flex": "tibia_flexor", "femur/tr flex": "femur_trochanter_flexor", "tibia extend": "tibia_extensor",
          "femur/tr extend": "femur_trochanter_extensor", "coxa swing": "coxa_swing", "coxa stance": "coxa_stance",
          "femur reductor": "femur_reductor", "substrate grip": "substrate_grip", "tarsus control": "tarsus_control"}
# name rules for MNs whose action is not a leg motor module (anatomical basis: Dickinson & Tu 1997; Azevedo et al. 2024;
# Cheong et al. 2024; Marin et al. 2024 type names)
RULES = [
    (r"^DLMn", "wing_power_DLM", "indirect flight power muscle, dorsal longitudinal (wing depression)"),
    (r"^DVMn", "wing_power_DVM", "indirect flight power muscle, dorso-ventral (wing elevation)"),
    (r"^TTMn$", "jump_TTM", "tergotrochanteral muscle (the jump muscle; extends the mesothoracic leg)"),
    (r"^STTMm$", "jump_STTM", "satellite tergotrochanter muscle MN: a second, smaller MN of the jump muscle leaving by the TTMn "
                             "nerve, two per side (FlyBase FBbt:00053058; motor-map review, reviews_v3/MOTOR_MAP_REVIEW.md)"),
    (r"^(b1|b2|b3|i1|i2|iii1|iii3|hg1|hg2|hg3|hg4) MN$", "wing_steering", "direct (steering) flight muscle"),
    (r"^(ps1|ps2|tp1|tp2|tpn) MN$", "wing_tension", "direct flight muscle of the pleurosternal / tergopleural (tension) group"),
    (r"^MNwm", "wing_unassigned", "wing motor neuron without a named muscle"),
    (r"^hDVM MN$", "haltere_power", "haltere dorso-ventral muscle"),
    (r"^(hi1|hi2|hiii2) MN$", "haltere_steering", "haltere direct muscle"),
    (r"^MNhm", "haltere_unassigned", "haltere motor neuron without a named muscle"),
    (r"^MNad", "abdominal", "abdominal motor neuron"),
]

# phenotype pools (PREREG v3, "From model output to the vocabulary")
LEG_PARTS = ("front_leg", "middle_leg", "hind_leg")


def action_of(row) -> tuple[str, str]:
    body = BODY.get(row["subclass"], "unknown")
    if body in LEG_PARTS:
        mod = MODULE.get(str(row["motor module"] or ""))
        return (mod or "leg_unassigned"), ("annotation: motor module" if mod else "annotation: leg subclass, no module")
    for pat, act, basis in RULES:
        if re.search(pat, str(row["type"])):
            return act, f"type name rule: {basis}"
    if body == "neck":
        return "neck", "annotation: neck subclass"
    return "unknown", "no rule"


def main() -> None:
    fc = N.full_cord()
    t = fc.table.reset_index(drop=True)
    mn = t[t["class"] == "motor neuron"].copy()
    rows = []
    for idx, r in mn.iterrows():
        body = BODY.get(r["subclass"], "unknown")
        act, basis = action_of(r)
        if act in ("jump_TTM", "jump_STTM"):
            body = "middle_leg"  # the jump muscle (TTM) moves the middle leg; both MN types annotated in the wing subclass
        side = {"LHS": "L", "RHS": "R"}.get(str(r["somaSide"]), "mid")
        pools = []
        if body in LEG_PARTS:
            pools += ["any_body", body]
            if act in ("jump_TTM", "jump_STTM"):
                pools.append("jump")  # not a flexor/extensor pool member: those pools are the MANC leg motor modules only
            if act in ("tibia_flexor", "femur_trochanter_flexor"):
                pools.append(f"{body}_flexor")
            if act in ("tibia_extensor", "femur_trochanter_extensor"):
                pools.append(f"{body}_extensor")
        elif body == "wing":
            pools += ["any_body"]
            pools.append("wing_any")
            if act in ("wing_power_DLM", "wing_power_DVM"):
                pools.append("wing_power")
        elif body == "haltere":
            pools += ["any_body", "haltere"]
        elif body == "abdomen":
            pools += ["any_body", "abdomen"]
        rows.append({"index": int(idx), "bodyId": int(r["bodyId"]), "type": r["type"], "subclass": r["subclass"],
                     "segment": r["somaNeuromere"], "side": side, "body_part": body, "action": act, "basis": basis,
                     "pools": ";".join(pools)})
    df = pd.DataFrame(rows).sort_values(["body_part", "segment", "action", "type", "side", "bodyId"])
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "MOTOR_MAP_v1.csv", index=False, lineterminator="\n")
    pools = sorted({p for s in df["pools"] for p in s.split(";") if p})
    summ = {"n_motor_neurons": len(df), "by_body_part": df["body_part"].value_counts().to_dict(),
            "by_action": df["action"].value_counts().to_dict(),
            "pool_sizes": {p: int(df["pools"].str.split(";").apply(lambda x: p in x).sum()) for p in pools},
            "excluded_from_every_pool": df.loc[df["pools"] == "", "body_part"].value_counts().to_dict(),
            "notes": ["segment and side are the soma's: correct for every leg MN (the per-leg pools use them); wing, haltere and "
                      "abdominal pools use neither",
                      "neck MNs feed no pool (the preparation has no head); the 6 'xm' MNs feed no pool (no body part annotated)",
                      "middle and hind legs have MNs without a motor module (24 and 38): in their leg pools, in no flexor/extensor pool",
                      "abdomen pool = every abdominal-subclass MN, including those of the terminal segments"]}
    (OUT / "MOTOR_MAP_v1.json").write_text(json.dumps(summ, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
