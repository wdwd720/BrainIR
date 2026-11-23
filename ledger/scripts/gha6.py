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


GRID = tuple(float(4.0 * 2 ** (k / 2)) for k in range(19))     # rulebook v4 fix 1 / B1.1: 4.0 ... 2048 (as gha4.GRID)
TUNED_SEEDS = tuple(range(16))
SWEEP_SEEDS = tuple(range(8))
HALF_SEEDS = tuple(range(8))
V_SEEDS = tuple(range(16))
COPY_SEEDS = (20261611, 20261612)                               # PREREG v6 C2: the two Poisson copies of BANC
DET6_SEED = 20261629                                            # PREREG v6 X4: 20 jobs per campaign
MALECNS_DNB08 = (328, 330, 345, 391)                            # B2r's DNb08 group (bodies 12044, 12075, 12189, 12550)
MALECNS_DNG100_AUTHORS = 9                                      # the authors' MaleCNS DNg100 config (Zenodo run 33241780)
MALECNS_DNB08_AUTHORS = (391, 250.0)                            # the authors' MaleCNS DNb08 config (Zenodo run 2026040200)


def _sweep_job(key: str, seed: int, members: list[int], readout: str = "readout") -> dict:
    """Rulebook v4 fix 1 exactly as `dx-1-run4` (`gha4._screen_jobs`, proc '1', gain 1): run 1's fixed run at each of the 19 grid
    currents, standard parameters (`sample_neuron_params` of the seed), B1's screen bounds, K = 1 for in-bounds, T = 1 s."""
    from brainir.compute.backend import Shared  # noqa: PLC0415
    from brainir.sim.model import ModelConfig  # noqa: PLC0415

    from brainir_ledger import arms as AR  # noqa: PLC0415

    return {"key": key, "seed": int(seed), "k_min": 1, "model": ModelConfig(t_end=1.0).to_dict(), "screen": AR.b1_screen_cfg(10).to_dict(),
            "W": Shared("W"), "sizes": Shared("sizes"), "readout": Shared(readout), "members": list(members), "kind": "sweep_v4",
            "params": {"mode": "standard"}, "gain": 1.0, "currents": list(GRID)}


def _tuned_jobs(arm: str, groups: dict, seeds, readout: str | None = None) -> list[dict]:
    """The tuned procedure exactly as B1r / B2r (`gha._v2_jobs`: run 2's `group_v2`, K = 1 never re-chosen, B1's screen, T = 1 s,
    read-out traces stored); keys `<arm>|<group>|s<seed>`; optionally another shared read-out (one-sided screens)."""
    from brainir.compute.backend import Shared  # noqa: PLC0415

    AR, MC, _, _ = G5.nets()
    jobs = G._v2_jobs(arm, groups, 1, AR, MC, seeds=[int(s) for s in seeds])
    return [dict(j, readout=Shared(readout)) for j in jobs] if readout else jobs


def _banc_payload(extra: dict | None = None) -> dict:
    from brainir_ledger import banc as B  # noqa: PLC0415

    net = B.network()
    W = net.W.tocsr()
    W.sort_indices()
    return {"W": W, "sizes": net.sizes, "readout": net.readout, **(extra or {})}


def build_bt(k=None):
    """PREREG v6 B1 (primary): the tuned whole-type screen on BANC, every group (excitatory DNs by MANC type), seeds 0..15, plus each
    DNb08 and DNg100 member alone (C5, same procedure)."""
    require_freeze6("BANC tuned screen")
    from brainir_ledger import banc as B  # noqa: PLC0415

    g = B.groups()
    singles = {f"{t}#{p}": [p] for t in ("DNb08", "DNg100") for p in g[t]}
    return [(_banc_payload(), _tuned_jobs("BT", g, TUNED_SEEDS) + _tuned_jobs("BT1", singles, TUNED_SEEDS))], AREA


def build_bs(k=None):
    """PREREG v6 B1 (companion): rulebook v4's fix 1 on BANC, every group, seeds 0..7."""
    require_freeze6("BANC sweep")
    from brainir_ledger import banc as B  # noqa: PLC0415

    jobs = [_sweep_job(f"BS|{t}|s{s}", s, m) for t, m in B.groups().items() for s in SWEEP_SEEDS]
    return [(_banc_payload(), jobs)], AREA


def build_bh(k=None):
    """PREREG v6 B2 / C1: the one-sided screens on BANC (rulebook v4 Part A design: that side's members, that side's front-leg motor
    neurons), every type with members on both sides, seeds 0..7."""
    require_freeze6("BANC one-sided screens")
    from brainir_ledger import banc as B  # noqa: PLC0415

    h = B.halves()
    sh = _banc_payload({"readout_L": B.readout_side("L"), "readout_R": B.readout_side("R")})
    jobs = []
    for side in ("L", "R"):
        jobs += _tuned_jobs(f"BH-{side}", h[side], HALF_SEEDS, readout=f"readout_{side}")
    return [(sh, jobs)], AREA


def banc_copy(seed: int):
    """PREREG v6 C2: every released count c >= 1 replaced by Poisson(c) (`fixes.poisson_copy`, run 4's B4.2 helper), the presynaptic
    sign carried over (`fixes.signed`), no floor (the authors' BANC network has none). The identity check: signing the unresampled
    counts must reproduce the released matrix entry for entry."""
    import numpy as np  # noqa: PLC0415

    from brainir_ledger import banc as B  # noqa: PLC0415
    from brainir_ledger import fixes as FX  # noqa: PLC0415

    C = B.raw_counts()
    sign = B.row_sign()
    W0 = FX.signed(C, sign).tocsr()
    W0.sort_indices()
    A = B.network().W.tocsr()
    A.sort_indices()
    if not (A.shape == W0.shape and A.nnz == W0.nnz and np.array_equal(A.indptr, W0.indptr) and np.array_equal(A.indices, W0.indices)
            and np.array_equal(A.data, W0.data)):
        raise SystemExit("signing BANC's unresampled counts does not reproduce the released matrix; refused")
    Wc = FX.signed(FX.poisson_copy(C, int(seed)), sign).tocsr().astype(np.float64)
    Wc.sort_indices()
    return Wc


def build_bn(k=None):
    """PREREG v6 C2: the left one-sided screen on each of the two Poisson copies of BANC, the C1 types, seeds 0..7."""
    require_freeze6("BANC count-noise copies")
    from brainir_ledger import banc as B  # noqa: PLC0415

    h = B.halves()
    out = []
    for i, cs in enumerate(COPY_SEEDS, start=1):
        sh = {"W": banc_copy(cs), "sizes": B.network().sizes, "readout_L": B.readout_side("L")}
        out.append((sh, _tuned_jobs(f"BN-c{i}", h["L"], HALF_SEEDS, readout="readout_L")))
    return out, AREA


def build_ms(k=None):
    """PREREG v6 Part H: the whole-type sweep of MaleCNS (B2r's network and 328 groups), rulebook v4 fix 1 exactly as MANC's
    `dx-1-run4`, seeds 0..7."""
    require_freeze6("Part H MaleCNS sweep")
    _, _, _, (net2, g2) = G5.nets()
    jobs = [_sweep_job(f"MS|{t}|s{s}", s, m) for t, m in sorted(g2.items()) for s in SWEEP_SEEDS]
    return [({"W": net2.W, "sizes": net2.sizes, "readout": net2.readout}, jobs)], "posthoc_v6"


def build_pv(k=None):
    """PREREG v6 Part V: V1 the authors' MaleCNS DNg100 configuration (position 9, 400, T = 2 s, seeds 0..63); V2 each of DNb08's four
    MaleCNS members alone at each of the 19 grid currents and at the authors' current 250 (their config: position 391), T = 2 s (their
    run length), seeds 0..15; fixed runs, all front-leg motor neurons read out."""
    require_freeze6("Part V")
    from brainir.compute.backend import Shared  # noqa: PLC0415
    from brainir.sim.model import ModelConfig  # noqa: PLC0415

    from brainir_ledger import arms as AR  # noqa: PLC0415

    _, _, _, (net2, g2) = G5.nets()
    if g2["DNb08"] != list(MALECNS_DNB08) or MALECNS_DNG100_AUTHORS not in g2["DNg100"]:
        raise SystemExit("MaleCNS positions differ from the authors' configs; refused")
    cfg, scfg = ModelConfig(t_end=2.0), AR.b1_screen_cfg(10)

    def fx(key, pos, cur, s):
        return {"key": key, "kind": "fixed", "W": Shared("W"), "sizes": Shared("sizes"), "readout": Shared("readout"), "stim_indices": [int(pos)],
                "currents": [float(cur)], "seed": int(s), "model": cfg.to_dict(), "screen": scfg.to_dict(), "extras": {"readout_traces": True, "watch": [int(pos)]}}

    jobs = [fx(f"V1|DNg100-{MALECNS_DNG100_AUTHORS}|I400|s{s}", MALECNS_DNG100_AUTHORS, 400.0, s) for s in range(64)]
    for p in MALECNS_DNB08:
        for c in (*GRID, MALECNS_DNB08_AUTHORS[1]):
            jobs += [fx(f"V2|DNb08-{p}|I{c:g}|s{s}", p, c, s) for s in V_SEEDS]
    return [({"W": net2.W, "sizes": net2.sizes, "readout": net2.readout}, jobs)], "thirdfly_v1"


DET6_STAGES: dict[int, list[str]] = {1: ["bg-banc-run6", "bt-banc-run6", "ms-mcns-run6", "pv-mcns-run6"],
                                     2: ["bh-banc-run6", "bs-banc-run6", "bn-banc-run6"]}


def build_det6(k=None):
    """PREREG v6 X3: 20 jobs of every campaign of determinism stage k that exists when packed (the gate `bg` included), drawn with default_rng(20261629) from
    its packed jobs, re-run with the same specification and payload; keys `D6~<campaign>~<key>` (as `gha5.build_det5`)."""
    import zlib  # noqa: PLC0415

    import numpy as np  # noqa: PLC0415

    require_freeze6("determinism re-run")
    groups = []
    for c in DET6_STAGES[int(k)]:
        if not (G.GHA / c / "manifest.json").exists():
            continue
        items = []
        for f in sorted((G.GHA / c).glob("chunk_*.pkl")):
            items += pickle.loads(f.read_bytes())
        keys = sorted(j["key"] for _, j in items)
        pick = set(np.random.default_rng(DET6_SEED).choice(keys, size=min(20, len(keys)), replace=False).tolist())
        by_payload: dict[str, list] = {}
        for pkey, j in items:
            if j["key"] in pick:
                by_payload.setdefault(pkey, []).append(dict(j, key=f"D6~{c}~{j['key']}", origin_campaign=c, origin_key=j["key"]))
        for pkey, jobs in by_payload.items():
            shared = pickle.loads(zlib.decompress((G.GHA / c / f"payload_{pkey}.bin").read_bytes()))
            groups.append((shared, jobs))
    return groups, AREA


def det_compare(stage: int) -> dict:
    """X4: the re-runs' digests against the originals' (`digest_v4` where the kind has it, else `digest`)."""
    name = f"det6-{stage}-run6"
    new = results(name)
    ident, bad = 0, []
    for k, r in sorted(new.items()):
        _, c, ok = k.split("~", 2)
        orig = results(c).get(ok)
        f = "digest_v4" if (r.get("digest_v4") or (orig or {}).get("digest_v4")) else "digest"
        if orig is not None and orig.get(f) == r.get(f):
            ident += 1
        else:
            bad.append(k)
    out = {"campaign": name, "n": len(new), "identical": ident, "different": bad, "verdict": "identical" if not bad and new else "fail"}
    _write_once(GATES6 / f"DETERMINISM_v6_stage{stage}.json", out)
    print(json.dumps(out, indent=1))
    return out


RUN6_BUILDERS = {"bg": build_bg, "bt": build_bt, "bs": build_bs, "bh": build_bh, "bn": build_bn, "ms": build_ms, "pv": build_pv,
                 "det6": build_det6}
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
    elif cmd == ["det-compare"]:
        det_compare(int(a[0]))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
