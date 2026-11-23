"""Run 6 campaigns on GitHub Actions (RUN6_PROMPT hard limit 8; PREREG v6 Part X): registers run 6's builders with the frozen
`gha.py` (pack) and runs them through run 4's runner and workflow unchanged (`gha_runner4.py`, `.github/workflows/ledger-gha4.yml`,
tags `gha4-run-<name>`), published with `publish6` and collected with run 4's `collect4` (module attribute swaps at run time, as
`gha5.py`; no frozen file is edited).

- The trust gate (Stage 0) is run 1's 100 locked jobs packed and published with the frozen `gha.py` (run 2's workflow);
  `trust-compare` writes `gates_v6/TRUST_GATE_v6.json`.
- The BANC build gate (`bg`, Stage 1) is the only BANC campaign allowed before the freeze (RUN6_PROMPT hard limit 2): the authors'
  BANC DNg100 alone at their current, intact and with each of their rhythm-circuit neurons silenced. Every other run 6 builder
  refuses before the tag `ledger-prereg-v6` exists and `LOCK_prereg_v6.json` verifies.
- Hard limit 8: at most 20 GitHub jobs queued or running (the campaign's chunks + its plan job + those active); `publish6` refuses
  otherwise.

    uv run --project ledger --no-sync python ledger/scripts/gha6.py trust-compare trust-run6        # -> gates_v6/TRUST_GATE_v6.json
    uv run --project ledger --no-sync python ledger/scripts/gha6.py pack bg-banc-run6 --chunk-jobs 32
    uv run --project ledger --no-sync python ledger/scripts/gha6.py publish6 bg-banc-run6
    uv run --project ledger --no-sync python ledger/scripts/gha6.py collect6 bg-banc-run6 [--wait]
    uv run --project ledger --no-sync python ledger/scripts/gha6.py active-jobs
    uv run --project ledger --no-sync python ledger/scripts/gha6.py runner-hours      # hard limit 8 (step time, LOG L102)
"""

from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gha as G  # noqa: E402
import gha4 as G4  # noqa: E402
import gha5 as G5  # noqa: E402

from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger.backend import read_log  # noqa: E402

GATES6 = RESEARCH / "gates_v6"
MAX_JOBS = 20
AREA = "thirdfly_v1"
GATE_SEEDS = tuple(range(64))


def require_freeze6(what: str) -> None:
    """RUN6_PROMPT hard limits 1-2: nothing governed by the rulebook runs before the freeze (tag pushed, lock verifies)."""
    import subprocess  # noqa: PLC0415

    if subprocess.run(["git", "rev-parse", "-q", "--verify", "refs/tags/ledger-prereg-v6"], cwd=G.REPO, capture_output=True).returncode != 0:
        raise SystemExit(f"{what}: the tag ledger-prereg-v6 does not exist; refused (declare first; BANC stays blind)")
    r = subprocess.run(["git", "ls-remote", "--tags", "origin", "refs/tags/ledger-prereg-v6"], cwd=G.REPO, capture_output=True, text=True)
    if "ledger-prereg-v6" not in (r.stdout or ""):
        raise SystemExit(f"{what}: the tag ledger-prereg-v6 is not on origin; refused")
    import lock6  # noqa: PLC0415

    if lock6.check(RESEARCH / "LOCK_prereg_v6.json") != 0:
        raise SystemExit(f"{what}: LOCK_prereg_v6.json does not verify; refused")


def silenced(W, positions):
    """The authors' `removeNeurons`: the rows (outputs) and columns (inputs) of the listed neurons masked to zero; the neurons stay
    as state variables (vnc_sim.py L1761-1764)."""
    import numpy as np  # noqa: PLC0415
    import scipy.sparse as sp  # noqa: PLC0415

    keep = np.ones(W.shape[0])
    keep[list(positions)] = 0.0
    D = sp.diags(keep)
    out = (D @ W @ D).tocsr()
    out.eliminate_zeros()
    out.sort_indices()
    return out


def build_bg(k=None):
    """RUN6 Stage 1 build gate (allowed before the freeze; LOG L177): the authors' BANC DNg100 (position 1605) alone at their current
    400, T = 2.0 s (their config: T 2.0, pulse 0.02-1.999), seeds 0..63, on the intact network and with E1 (1689), E2 (910) and I2
    (3334) silenced; read-out = the 139 front-leg motor neurons; B1's screen bounds label the verdict only (the gate reads scores)."""
    from brainir.compute.backend import Shared  # noqa: PLC0415
    from brainir.sim.model import ModelConfig  # noqa: PLC0415

    from brainir_ledger import arms as AR  # noqa: PLC0415
    from brainir_ledger import banc as B  # noqa: PLC0415

    net = B.network()
    if int(net.table.loc[B.AUTHORS_DNG100_POS, "pt_root_id"]) != 720575941500851362 or net.table.loc[B.AUTHORS_DNG100_POS, "cell_type"] != "DNg100":
        raise SystemExit("position 1605 is not the authors' DNg100")
    for lab, pos in B.CIRCUIT.items():
        if int(net.table.loc[pos, "pt_root_id"]) != B.CIRCUIT_ROOT[lab]:
            raise SystemExit(f"{lab}: position {pos} is not the published root id")
    cfg = ModelConfig(t_end=2.0)
    scfg = AR.b1_screen_cfg(10)
    watch = [B.AUTHORS_DNG100_POS, *B.CIRCUIT.values()]
    W0 = net.W.tocsr()
    W0.sort_indices()
    out = []
    for cond, pos in (("intact", None), ("E1", B.CIRCUIT["E1"]), ("E2", B.CIRCUIT["E2"]), ("I2", B.CIRCUIT["I2"])):
        W = W0 if pos is None else silenced(W0, [pos])
        shared = {"W": W, "sizes": net.sizes, "readout": net.readout}
        jobs = [{"key": f"BG|{cond}|DNg100-1605|I400|s{s}", "kind": "fixed", "W": Shared("W"), "sizes": Shared("sizes"),
                 "readout": Shared("readout"), "stim_indices": [B.AUTHORS_DNG100_POS], "currents": [B.AUTHORS_STIM_I], "seed": int(s),
                 "model": cfg.to_dict(), "screen": scfg.to_dict(), "extras": {"readout_traces": True, "watch": watch}} for s in GATE_SEEDS]
        out.append((shared, jobs))
    return out, AREA


RUN6_BUILDERS = {"bg": build_bg}
G.BUILDERS.update(RUN6_BUILDERS)
RUN6_PREFIXES = set(RUN6_BUILDERS)


def publish6(name: str, attempt: int = 0) -> None:
    """Run 4's `publish4` for a run 6 campaign (prefix check swapped at run time; gha4.py unchanged), after the 20-job check."""
    if name.split("-")[0] not in RUN6_PREFIXES or not name.endswith("-run6"):
        raise SystemExit(f"{name}: not a run 6 campaign")
    man = json.loads((G.GHA / name / "manifest.json").read_text())
    active = G4.active_jobs()
    if active + man["n_chunks"] + 1 > MAX_JOBS:
        raise SystemExit(f"{name}: {active} jobs active + {man['n_chunks']} chunks + plan > {MAX_JOBS}; wait (hard limit 8)")
    orig = G4.RUN4_PREFIXES
    G4.RUN4_PREFIXES = orig | RUN6_PREFIXES
    try:
        G4.publish4(name, attempt)
    finally:
        G4.RUN4_PREFIXES = orig


def results(name: str) -> dict[str, dict]:
    man = json.loads((G.GHA / name / "manifest.json").read_text())
    return {r["key"]: r for r in read_log(data_dir() / man["area"] / f"GHA_{name}" / "results.pkl") if isinstance(r, dict) and "key" in r}


def _write_once(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8", newline="\n") as fh:  # written once; never overwritten
        fh.write(json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n")


def trust_compare(name: str) -> dict:
    """Run 2's trust comparison (as `gha5.trust_compare`), written to gates_v6."""
    man = json.loads((G.GHA / name / "manifest.json").read_text())
    new = {r["key"]: r for r in read_log(data_dir() / man["area"] / f"GHA_{name}" / "results.pkl")}
    items = []
    for f in sorted((G.GHA / name).glob("chunk_*.pkl")):
        items += pickle.loads(f.read_bytes())
    origin = {j["key"]: j["origin"] for _, j in items}
    orig = {o: {r["key"]: r for r in read_log(data_dir() / o / "results.pkl")} for o in sorted(set(origin.values()))}
    ident, bad = 0, []
    for k in man["keys"]:
        a, b = orig[origin[k]].get(k), new.get(k)
        if b is None:
            bad.append((k, "missing on runner"))
        elif a["digest"] == b["digest"]:
            ident += 1
        else:
            bad.append((k, "digest differs"))
    meta = [json.loads(x) for x in (data_dir() / man["area"] / f"GHA_{name}" / "gha_meta.jsonl").read_text().splitlines() if x.strip()]
    out = {"campaign": name, "n": len(man["keys"]), "identical": ident, "different": len(bad), "different_keys": bad,
           "numerics_digests": sorted({m["probe"]["numerics_digest"][:12] for m in meta}),
           "cpu_models": sorted({m["probe"]["host"]["cpu"]["cpu_model"] for m in meta}),
           "git_head_packed": man.get("git_head"), "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "verdict": "identical" if ident == len(man["keys"]) else "fail"}
    _write_once(GATES6 / ("TRUST_GATE_v6.json" if name == "trust-run6" else f"TRUST_GATE_v6_{name}.json"), out)
    print(json.dumps({k: v for k, v in out.items() if k != "different_keys"}, indent=1))
    return out


def main() -> None:
    cmd, a = sys.argv[1:2], sys.argv[2:]
    if cmd == ["trust-compare"]:
        trust_compare(a[0])
    elif cmd == ["pack"]:
        name = a[0]
        if name.split("-")[0] not in RUN6_BUILDERS or not name.endswith("-run6"):
            raise SystemExit(f"{name}: no run 6 builder for this prefix")
        G.pack(name, int(a[a.index("--chunk-jobs") + 1]), int(a[a.index("--k") + 1]) if "--k" in a else None)
    elif cmd == ["publish6"]:
        publish6(a[0], int(a[a.index("--attempt") + 1]) if "--attempt" in a else 0)
    elif cmd == ["collect6"]:
        G4.collect4(a[0], "--wait" in a)
    elif cmd == ["active-jobs"]:
        print(G4.active_jobs())
    elif cmd == ["runner-hours"]:
        G5.runner_hours("run6")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
