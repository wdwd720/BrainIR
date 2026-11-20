"""DNg100-only check of the B2 network (DNg100 is the allowed calibration neuron; prediction side, never reads labels).

Fixed-current runs scored with the locked metric (`typescreen.fixed_run`): each DNg100 member alone at the paper's MaleCNS
current I = 400 (paper / Phase 1: mean 0.983-0.985 with the benchmark neuron), and the pair at 256 (where the B2 tuner
accepted) and at 512 (the tuner's next step). Seeds 0-3. Writes research/ledger/gates/B2_DNG100_CHECK.json.

    uv run --project ledger --no-sync python ledger/scripts/b2_dng100_check.py
"""
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def one(args):
    cond, stim, cur, seed = args
    from brainir.sim import ModelConfig
    from brainir.sim.model import sample_neuron_params
    from brainir_ledger import arms as AR
    from brainir_ledger.typescreen import fixed_run

    net, groups, info = AR.malecns_network()
    sel = json.loads((Path(__file__).resolve().parents[2] / "research" / "ledger" / "predictions" / "B1" / "selection.json").read_text())
    scfg = AR.b1_screen_cfg(int(sel["kept_lower_bound"]))
    mcfg = ModelConfig(t_end=1.0)
    params = sample_neuron_params(mcfg, net.W.shape[0], seed, net.sizes)
    r = fixed_run(net.W, params, mcfg, stim, [cur] * len(stim), np.asarray(net.readout, bool), cfg=scfg)
    return cond, seed, round(float(r["score"]), 3), r.get("n_active_readout"), r.get("n_active_all"), r.get("frequency_hz")


if __name__ == "__main__":
    from brainir_ledger import arms as AR
    from brainir_ledger.env import fingerprint

    net, groups, info = AR.malecns_network()
    dng = [int(m) for m in groups["DNg100"]]
    print("DNg100 members (positions, bodyIds):", dng, [int(net.table.loc[m, "bodyId"]) for m in dng])
    jobs = []
    for s in range(4):
        jobs += [(f"single_{dng[0]}_I400", [dng[0]], 400.0, s), (f"single_{dng[1]}_I400", [dng[1]], 400.0, s),
                 ("pair_I256", dng, 256.0, s), ("pair_I512", dng, 512.0, s)]
    rows = []
    with ProcessPoolExecutor(max_workers=8) as ex:
        for row in ex.map(one, jobs):
            print(row, flush=True)
            rows.append(dict(zip(("condition", "seed", "score", "n_active_readout", "n_active_all", "frequency_hz"), row)))
    out = {"network": "authors' MaleCNS front-leg network (B2)", "members_positions": dng,
           "members_bodyIds": [int(net.table.loc[m, "bodyId"]) for m in dng], "model": "ModelConfig(t_end=1.0)",
           "screen_cfg_for_scoring": "B1 kept procedure (lower bound from B1/selection.json)", "runs": rows,
           "computed_on": fingerprint(), "note": "computed locally (orchestrator machine), not on the locked Modal platform"}
    (Path(__file__).resolve().parents[2] / "research" / "ledger" / "gates" / "B2_DNG100_CHECK.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
