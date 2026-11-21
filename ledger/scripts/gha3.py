"""Run 3 campaigns on GitHub Actions (RUN3_PROMPT section 3 item 5, PREREG v3 P7-P9): registers run 3's builders with the frozen
`gha.py` (P4b, LOCK_prereg_v2) and adds what the frozen file cannot do for run 3's job kinds.

- Kinds `group_v3` / `fixed_v3` run only through run 3's runner and workflow (`gha_runner3.py`, `.github/workflows/ledger-gha3.yml`,
  tags `gha3-run-<name>`); the frozen workflow (tags `gha-run-<name>`) would return an error for every such job. So campaigns
  with v3 jobs are published with `publish3` and collected with `collect3`; `pack` is the frozen one. `publish3` refuses a
  campaign whose builder is not a v3 builder, and the frozen `publish` must not be used for one (it would run the old runner).
- Hard limit 2: before the tag `ledger-prereg-v3` exists, only the trust gate (run 1's locked jobs) and `p7` (DNg100, DNb08 and
  random synthetic groups) may be built; every hemilineage builder refuses without the tag.

    uv run --project ledger --no-sync python ledger/scripts/gha3.py pack p7-run3 --chunk-jobs 13
    uv run --project ledger --no-sync python ledger/scripts/gha3.py publish3 p7-run3
    uv run --project ledger --no-sync python ledger/scripts/gha3.py collect3 p7-run3 --wait
    uv run --project ledger --no-sync python ledger/scripts/gha3.py p7-check p7-run3      # -> research/ledger/gates_v3/P7_*.json
    uv run --project ledger --no-sync python ledger/scripts/gha3.py trust-compare trust-run3
"""

from __future__ import annotations

import json
import pickle
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gha as G  # noqa: E402

from brainir.compute.backend import Shared  # noqa: E402
from brainir.sim.model import ModelConfig  # noqa: E402
from brainir.sim.screen import ScreenConfig  # noqa: E402
from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger import groups_h1 as GH  # noqa: E402
from brainir_ledger import networks as N  # noqa: E402
from brainir_ledger.backend import read_log  # noqa: E402

GATES3 = RESEARCH / "gates_v3"
FREEZE_TAG = "ledger-prereg-v3"
SCREEN = {"n_active_lower": 100, "n_active_upper": 7667, "n_high_fr_upper": 1022}  # LOG L14 / PREREG v1 3.7 (as g3v2 item 5)
T_END = 1.0
H_SEEDS = tuple(range(16))
LOW_SEEDS = tuple(range(4))  # H-C, sensitivity groups (PREREG v3 P4, P6)
HD_SEEDS = tuple(range(8))
HD_CURRENTS = (128.0, 256.0, 384.0, 512.0)
P7_RNG_SEED = 20261311
P7_SIZES = (50, 150, 300, 600, 1000)
CONTROLS = tuple(("rewire", s) for s in (101, 102, 103, 104, 105)) + tuple(("classshuffle", s) for s in (201, 202, 203, 204, 205))


def _tagged() -> bool:
    return subprocess.run(["git", "rev-parse", "-q", "--verify", f"refs/tags/{FREEZE_TAG}"], cwd=G.REPO, capture_output=True).returncode == 0


def require_freeze(what: str) -> None:
    """Hard limit 2: the tag must exist, be an ancestor of HEAD, and the prereg lock must verify (audit 13a)."""
    if _tagged():
        anc = subprocess.run(["git", "merge-base", "--is-ancestor", FREEZE_TAG, "HEAD"], cwd=G.REPO, capture_output=True).returncode == 0
        ok = subprocess.run([sys.executable, str(HERE / "lock3.py"), "check", str(RESEARCH / "LOCK_prereg_v3.json")], cwd=G.REPO,
                            capture_output=True).returncode == 0
        if not (anc and ok):
            raise SystemExit(f"{what}: the tag {FREEZE_TAG} is not an ancestor of HEAD or LOCK_prereg_v3.json does not verify; refused")
        return
    if not _tagged():
        raise SystemExit(f"{what}: before the tag {FREEZE_TAG} only DNg100, DNb08 and random synthetic groups may be simulated "
                         "(RUN3_PROMPT hard limit 2); refused, nothing built")


def _fc():
    fc = N.full_cord()
    mm = GH.load_motor_map()
    shared = {"W": fc.W, "sizes": fc.sizes, "readout": fc.readout, "legs": N.leg_setup(fc), "mn": GH.mn_positions(mm)}
    return fc, shared


EX_H = {"legs": Shared("legs"), "mn": Shared("mn")}  # read-out of hemilineage jobs (PREREG v3 P1)


def group_job(key: str, members, seed: int, extras: dict) -> dict:
    return {"key": key, "kind": "group_v3", "W": Shared("W"), "sizes": Shared("sizes"), "readout": Shared("readout"),
            "members": [int(m) for m in members], "seed": int(seed), "model": ModelConfig(t_end=T_END).to_dict(),
            "screen": ScreenConfig(**SCREEN).to_dict(), "extras": extras}


def fixed_job(key: str, members, current: float, seed: int, extras: dict) -> dict:
    return {"key": key, "kind": "fixed_v3", "W": Shared("W"), "sizes": Shared("sizes"), "readout": Shared("readout"),
            "stim_indices": [int(m) for m in members], "currents": [float(current)] * len(members), "seed": int(seed),
            "model": ModelConfig(t_end=T_END).to_dict(), "screen": ScreenConfig(**SCREEN).to_dict(), "extras": extras}


def p7_groups(table) -> dict[str, list[int]]:
    """PREREG v3 P7: DNg100, DNb08 and five random synthetic groups of thoracic intrinsic neurons."""
    out = {"DNg100": sorted(int(i) for i in table.index[table["type"] == "DNg100"]),
           "DNb08": sorted(int(i) for i in table.index[table["type"] == "DNb08"])}
    pool = sorted(int(i) for i in table.index[(table["class"] == "intrinsic neuron") & table["somaNeuromere"].isin(GH.THORAX)])
    rng = np.random.default_rng(P7_RNG_SEED)
    for size in P7_SIZES:
        out[f"rand{size}"] = sorted(int(x) for x in rng.choice(pool, size, replace=False))
    return out


def build_p7(k=None):
    """Allowed before the freeze: the DNg100 regression (B3 read-out, digests must equal run 2's g3v2item5), DNb08, random groups,
    and two fixed-current jobs (the H-D path)."""
    fc, shared = _fc()
    g = p7_groups(fc.table)
    dng = g["DNg100"]
    jobs = [group_job(f"p7reg|DNg100|s{s}", dng, s, {"legs": Shared("legs"), "readout_traces": True, "watch": dng, "mn": Shared("mn")})
            for s in H_SEEDS]
    jobs += [group_job(f"p7|DNb08|s{s}", g["DNb08"], s, EX_H) for s in H_SEEDS]
    jobs += [group_job(f"p7|rand{z}|s{s}", g[f"rand{z}"], s, EX_H) for z in P7_SIZES for s in LOW_SEEDS]
    jobs += [fixed_job(f"p7fixed|rand150|I{c:g}|s0", g["rand150"], c, 0, EX_H) for c in (128.0, 512.0)]
    return [(shared, jobs)], "calibration"


def _unit_groups(fc, variant: str) -> dict[str, list[int]]:
    bt = GH.birthtime(G.REPO)
    return {u: GH.members(fc.table, bt, u, variant) for u in GH.load_units()}


def build_hm(k=None):
    require_freeze("H-M")
    fc, shared = _fc()
    groups = _unit_groups(fc, "primary")
    return [(shared, [group_job(f"H-M|{u}|s{s}", m, s, EX_H) for u, m in groups.items() for s in H_SEEDS])], "arms_h1"


def build_hd(k=None):
    require_freeze("H-D")
    fc, shared = _fc()
    groups = _unit_groups(fc, "primary")
    return [(shared, [fixed_job(f"H-D-{c:g}|{u}|s{s}", m, c, s, EX_H) for c in HD_CURRENTS for u, m in groups.items()
                      for s in HD_SEEDS])], "arms_h1"


def sens_plan(fc) -> dict[str, dict[str, str]]:
    """Per sensitivity variant and unit: `run`, `empty` (zeros, U4) or `same_as_primary` (the primary result, seeds 0..3)."""
    prim = _unit_groups(fc, "primary")
    plan = {}
    for v in GH.SENS_VARIANTS:
        gv = _unit_groups(fc, v)
        plan[v] = {u: ("empty" if not gv[u] else "same_as_primary" if gv[u] == prim[u] else "run") for u in gv}
    return plan


def build_hsens(k=None):
    require_freeze("sensitivity groups")
    fc, shared = _fc()
    plan = sens_plan(fc)
    jobs = []
    for v in GH.SENS_VARIANTS:
        gv = _unit_groups(fc, v)
        jobs += [group_job(f"H-M-S-{v}|{u}|s{s}", gv[u], s, EX_H) for u in gv if plan[v][u] == "run" for s in LOW_SEEDS]
    return [(shared, jobs)], "arms_h1"


def build_hc(k=None):
    """One control network per campaign (`--k` = its seed: 101-105 rewire, 201-205 class shuffle), H-M on it, seeds 0..3."""
    require_freeze("H-C")
    kind = {s: kd for kd, s in CONTROLS}[int(k)]
    fc, shared = _fc()
    Wc, stats = GH.control_network(fc, kind, int(k))
    groups = _unit_groups(fc, "primary")
    jobs = [group_job(f"H-C-{kind}-{int(k)}|{u}|s{s}", m, s, EX_H) for u, m in groups.items() for s in LOW_SEEDS]
    print(json.dumps({"control": f"{kind}-{int(k)}", **{a: int(b) for a, b in stats.items()}}))
    return [({**shared, "W": Wc}, jobs)], "arms_h1"


DET_RNG_SEED = 20261312
DET_N = 50


def build_hmdet(k=None):
    """PREREG v3 P9.3: 50 H-M jobs drawn with default_rng(20261312) from the sorted H-M keys, re-run as a separate campaign (same
    keys, same specs); `det-compare` checks that every `digest_v3` is identical."""
    require_freeze("H-M determinism sample")
    (shared, jobs), area = build_hm()[0][0], "arms_h1"
    keys = sorted(j["key"] for j in jobs)
    pick = set(np.random.default_rng(DET_RNG_SEED).choice(keys, DET_N, replace=False).tolist())
    return [(shared, [j for j in jobs if j["key"] in pick])], area


V3_BUILDERS = {"p7": build_p7, "hm": build_hm, "hd": build_hd, "hsens": build_hsens, "hc": build_hc, "hmdet": build_hmdet}
G.BUILDERS.update(V3_BUILDERS)


# ------------------------------------------------------------------------------------------------ publish / collect (v3 tags)
RUN3_PREFIXES = {"p7", "hm", "hd", "hsens", "hc", "hmdet", "r3", "r4"}  # r3, r4: builders in gha3r.py (reliability study)
# everything a hosted runner executes for a run 3 campaign (the workflow, its runner script, the packages it imports)
RUNNER_SIDE = [".github/workflows/ledger-gha3.yml", "ledger/scripts/gha_runner3.py", "ledger/src/brainir_ledger", "src/brainir",
               ".github/ledger_gha_pub.pem"]


def publish3(name: str, attempt: int) -> None:
    if name.split("-")[0] not in RUN3_PREFIXES:
        raise SystemExit(f"{name}: not a run 3 campaign")
    man = json.loads((G.GHA / name / "manifest.json").read_text())
    G.sh("git", "fetch", "-q", "origin", "ledger/v1")
    origin = G.sh("git", "rev-parse", "origin/ledger/v1")
    # the runner checks out the TAGGED commit: tag the public origin commit (never a local one, which may hold exam 2 predictions
    # before the labels lock; PREREG v3 P10), after checking that everything the runner executes is identical there and at HEAD
    diff = subprocess.run(["git", "diff", "--quiet", origin, "HEAD", "--", *RUNNER_SIDE], cwd=G.REPO).returncode
    if diff != 0:
        raise SystemExit("runner-side code differs between origin/ledger/v1 and HEAD: push it first (before any prediction is "
                         "committed) or revert it; refused")
    leak = G.sh("git", "ls-tree", "-r", "--name-only", origin, "--", "research/ledger/predictions_h1",
                "research/ledger/LOCK_predictions_h1.json", "research/ledger/LOCK_predictions_h1b.json")
    if leak.strip() and not (RESEARCH / "LOCK_labels_h1.json").exists():
        raise SystemExit("origin holds exam 2 predictions before the labels lock: stop and investigate; refused")
    if not (G.REPO / ".github" / "workflows" / "ledger-gha3.yml").is_file():
        raise SystemExit("run 3 workflow missing")
    rel = f"ledgerdata-{name}"
    if subprocess.run(["gh", "release", "view", rel], cwd=G.REPO, capture_output=True).returncode != 0:
        assets = [str(p) for p in sorted((G.GHA / name).iterdir()) if p.is_file()]
        G.sh("gh", "release", "create", rel, *assets, "--target", origin, "--title", rel, "--prerelease",
             "--notes", "BrainIR ledger run 3: inputs of a GitHub Actions campaign (public connectome matrices and job specs only; "
                        "no result). Results come back encrypted. See research/ledger/LOG.md.")
    tag = f"gha3-run-{name}" + (f"-r{attempt}" if attempt else "")
    G.sh("git", "tag", tag, origin)
    G.sh("git", "push", "origin", tag)
    print("published", rel, "and pushed", tag, "at", origin[:12], "jobs", man["n_jobs"], "chunks", man["n_chunks"])


def runs_for3(name: str) -> list[dict]:
    q = G.sh("gh", "api", "repos/{owner}/{repo}/actions/runs?per_page=100&event=push")
    runs = json.loads(q)["workflow_runs"]
    return [r for r in runs if r["head_branch"] == f"gha3-run-{name}" or r["head_branch"].startswith(f"gha3-run-{name}-r")]


def collect3(name: str, wait: bool) -> dict:
    """The frozen `gha.collect` with the run lookup pointed at run 3's tags (module attribute swap at run time; gha.py unchanged)."""
    G.runs_for = runs_for3
    return G.collect(name, wait)


# ------------------------------------------------------------------------------------------------ checks
def _write_once(path: Path, obj: dict) -> None:
    """Gate files are written once (the prereg lock hashes those present at the freeze; audit 13d)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(obj, indent=1) + "\n")


def results(name: str) -> dict[str, dict]:
    man = json.loads((G.GHA / name / "manifest.json").read_text())
    return {r["key"]: r for r in read_log(data_dir() / man["area"] / f"GHA_{name}" / "results.pkl")}


def p7_check(name: str) -> dict:
    """P7 regression: each `p7reg|DNg100|s<k>` digest equals run 2's `g3v2item5|DNg100|s<k>` (the B3 procedure on DNg100); and every
    P7 job returned without error with the read-out the formulas need."""
    new = results(name)
    old = {r["key"]: r for r in read_log(data_dir() / "calibration" / "GHA_g3v2" / "results.pkl")}
    reg = {s: (old.get(f"g3v2item5|DNg100|s{s}", {}).get("digest"), new.get(f"p7reg|DNg100|s{s}", {}).get("digest")) for s in H_SEEDS}
    man = json.loads((G.GHA / name / "manifest.json").read_text())
    missing = sorted(set(man["keys"]) - set(new))
    readout_ok = all(("mn_peak" in (r.get("extras") or r.get("final_run_extras") or {})) for r in new.values())
    out = {"campaign": name, "n_expected": len(man["keys"]), "n_results": len(new), "missing_or_error": missing,
           "regression_identical": sum(a is not None and a == b for a, b in reg.values()), "regression_n": len(reg),
           "regression_different": [s for s, (a, b) in reg.items() if a is None or a != b], "readout_present_in_all": readout_ok,
           "verdict": "pass" if (not missing and all(a is not None and a == b for a, b in reg.values()) and readout_ok) else "fail"}
    _write_once(GATES3 / "P7_REGRESSION.json", out)
    print(json.dumps(out))
    return out


def det_compare(name: str, against: str) -> dict:
    """P9.3: every job of the re-run campaign `name` has the same `digest_v3` as in campaign `against`."""
    a, b = results(against), results(name)
    man = json.loads((G.GHA / name / "manifest.json").read_text())
    same = [k for k in man["keys"] if k in a and k in b and a[k].get("digest_v3") == b[k].get("digest_v3") and a[k].get("digest_v3")]
    out = {"campaign": name, "against": against, "n": len(man["keys"]), "identical": len(same),
           "different_or_missing": sorted(set(man["keys"]) - set(same)), "verdict": "identical" if len(same) == len(man["keys"]) else "fail"}
    _write_once(GATES3 / f"DETERMINISM_{name}.json", out)
    print(json.dumps(out))
    return out


def trust_compare(name: str) -> dict:
    """The run-2 trust comparison (`gha.trust_compare`) for a campaign of another name: every re-run job's digest against the
    locked run-1 result it reproduces."""
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
           "by_origin": {o: sum(1 for k in man["keys"] if origin[k] == o) for o in sorted(set(origin.values()))},
           "numerics_digests": sorted({m["probe"]["numerics_digest"][:12] for m in meta}),
           "cpu_models": sorted({m["probe"]["host"]["cpu"]["cpu_model"] for m in meta}),
           "verdict": "identical" if ident == len(man["keys"]) else "fail"}
    _write_once(GATES3 / f"TRUST_GATE_v3{'' if name == 'trust-run3' else '_' + name}.json", out)
    print(json.dumps({k: v for k, v in out.items() if k != "different_keys"}, indent=1))
    return out


if __name__ == "__main__":
    cmd = sys.argv[1:2]
    if cmd == ["trust-compare"]:
        trust_compare(sys.argv[2])
    elif cmd == ["publish3"]:
        a = sys.argv[2:]
        publish3(a[0], int(a[a.index("--attempt") + 1]) if "--attempt" in a else 0)
    elif cmd == ["collect3"]:
        collect3(sys.argv[2], "--wait" in sys.argv)
    elif cmd == ["p7-check"]:
        p7_check(sys.argv[2])
    elif cmd == ["det-compare"]:
        det_compare(sys.argv[2], sys.argv[3])
    elif cmd == ["publish"] and sys.argv[2:3] and sys.argv[2].split("-")[0] in RUN3_PREFIXES:
        raise SystemExit("a run 3 campaign is published with publish3: the frozen publish would run it on the old runner; refused")
    else:
        G.main()
