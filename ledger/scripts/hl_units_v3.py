"""Hemilineage units for exam 2 (RUN3_PROMPT section 5, "Units and groups"), from the full-cord annotations ALONE: every
hemilineage label with at least one neuron in T1-T3, except `TBD`. For each unit: neuron counts per thoracic segment and side,
counts over all segments, postembryonic counts (MANC birthtime `secondary` or `early_secondary`), transmitter make-up, motor
neurons among the members, and the transmitter class (motor: >= 50 % motor neurons; else excitatory: >= 60 % acetylcholine;
inhibitory: >= 60 % GABA or glutamate; otherwise mixed). No simulation; no outcome.

    uv run --project ledger --no-sync python ledger/scripts/hl_units_v3.py   # -> research/ledger/hl_units/UNITS_v1.csv, .json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "src"))
from brainir_ledger import RESEARCH  # noqa: E402
from brainir_ledger import networks as N  # noqa: E402

OUT = RESEARCH / "hl_units"
THORAX = ("T1", "T2", "T3")


def birthtime() -> pd.Series:
    a = pd.read_parquet(REPO / "data" / "processed" / "manc" / "v1.2.1" / "neuron_annotations_source.parquet", columns=["bodyId", "tag_birthtime"])
    return a.set_index("bodyId")["tag_birthtime"]


def main() -> None:
    t = N.full_cord().table.reset_index(drop=True)
    bt = birthtime()
    t["birthtime"] = t["bodyId"].map(bt)
    th = t[t["somaNeuromere"].isin(THORAX)]
    rows = []
    for h in sorted(set(th["hemilineage"].dropna()) - {"TBD", ""}):
        d = th[th["hemilineage"] == h]
        nt = d["predictedNt"].value_counts()
        n = len(d)
        ach, gaba, glu = int(nt.get("acetylcholine", 0)), int(nt.get("gaba", 0)), int(nt.get("glutamate", 0))
        n_mn = int((d["class"] == "motor neuron").sum())
        # motor-neuron lineages first: fly motor neurons are glutamatergic, so the transmitter rule would call them inhibitory
        cls = "motor" if n_mn >= 0.5 * n else ("excitatory" if ach >= 0.6 * n else ("inhibitory" if gaba + glu >= 0.6 * n else "mixed"))
        rows.append({"unit": h, "components": ";".join(h.split(".")), "n_thoracic": n,
                     "T1": int((d.somaNeuromere == "T1").sum()), "T2": int((d.somaNeuromere == "T2").sum()), "T3": int((d.somaNeuromere == "T3").sum()),
                     "left": int((d.somaSide == "LHS").sum()), "right": int((d.somaSide == "RHS").sum()),
                     "midline": int((~d.somaSide.isin(["LHS", "RHS"])).sum()),
                     "n_all_segments": int((t["hemilineage"] == h).sum()),
                     "n_postembryonic_thoracic": int(d["birthtime"].isin(["secondary", "early_secondary"]).sum()),
                     "n_birthtime_missing": int(d["birthtime"].isna().sum()),
                     "acetylcholine": ach, "gaba": gaba, "glutamate": glu, "other_nt": n - ach - gaba - glu,
                     "n_motor_neurons": int((d["class"] == "motor neuron").sum()), "nt_class": cls})
    df = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "UNITS_v1.csv", index=False, lineterminator="\n")
    summ = {"n_units": len(df), "nt_class": df["nt_class"].value_counts().to_dict(),
            "units_with_motor_neurons": df.loc[df["n_motor_neurons"] > 0, "unit"].tolist(),
            "merged_units": [u for u in df["unit"] if "." in u], "excluded": ["TBD"]}
    (OUT / "UNITS_v1.json").write_text(json.dumps(summ, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(df.to_string(index=False))
    print(json.dumps(summ))


if __name__ == "__main__":
    main()
