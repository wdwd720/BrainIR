"""Dry run of run 4's Part B-E analysis code on FAKE results (LOG L125): code check only, before the campaigns are collected.

Every campaign the analyses read that has not been analysed yet is replaced by fake results built from its packed job specifications
(right keys, right fields, random scores; Block 2's fake data are built so that its sanity checks pass, so every later code path
runs); Part A (already analysed) is read as it is. All outputs go to a temporary folder; nothing is written to research/ledger/;
no number is printed, only whether each command ran. A failure here is a code bug that can still be fixed before collection (X4).

    uv run --project ledger --no-sync python ledger/scripts/posthoc/dryrun_analyses_v4.py [--keep DIR]
"""

from __future__ import annotations

import hashlib
import json
import pickle
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "src"))
import gha4  # noqa: E402
import reliability_v2 as R2  # noqa: E402
import reliability_v2_bc as RB  # noqa: E402

FAKE_CAMPAIGNS = ["b1s-manc-run4", "b1s-mcns-run4", "b2-manc-run4", "b2-mcns-run4", "b3-manc-run4", "cn-run4", "fl-1-run4", "crw-run4",
                  "cx-1-run4", "cx-3a-run4", "cx-4-run4", "cx-5a-run4", "cx-5b-run4", "cx-7-run4", "dx-1-run4", "dx-4-run4", "dx-7-run4"]
RNG = np.random.default_rng(12345)


def _jobs(c: str) -> list[dict]:
    out = []
    for f in sorted((gha4.G.GHA / c).glob("chunk_*.pkl")):
        out += [j for _, j in pickle.loads(f.read_bytes())]
    return out


def _hex() -> str:
    return hashlib.sha256(RNG.bytes(16)).hexdigest()


def _template() -> list[dict]:
    """Real Part A results (all fields of a tuned group job, incl. read-out traces), used only for their structure; several, so that
    scores re-computed from traces (fix 2's pooled read-out) vary between fake results."""
    pa = gha4.part_a_results("MANC")
    out = [r for r in pa.values() if r.get("usable") and "readout_traces" in (r.get("extras") or {})][:400]
    if not out:
        raise SystemExit("no Part A template with traces")
    return out


def _fake_std(key: str, tmpl: list[dict]) -> dict:
    r = dict(tmpl[int(RNG.integers(0, len(tmpl)))])
    r.update(key=key, usable=bool(RNG.random() < 0.9), score=float(RNG.random()) if RNG.random() < 0.4 else 0.0,
             digest=_hex(), digest_v4=_hex(), n_tuning_runs=int(RNG.integers(2, 9)), current=float(RNG.choice([32.0, 64.0, 128.0])))
    return r


def _fake_sweep(job: dict) -> dict:
    runs = []
    for c in job["currents"]:
        ok = bool(RNG.random() < 0.7)
        runs.append({"current": float(c), "verdict": "ok" if ok else "weak", "score": float(RNG.random()) if ok else 0.0, "in_bounds": ok,
                     "n_active_all": int(RNG.integers(10, 500)), "n_high_fr": 0, "frequency_hz": 6.0, "n_active_readout": 3 if ok else 0,
                     "solver_success": True, "wall_time_s": 1.0})
    return {"key": job["key"], "members": list(job.get("members") or []), "seed": int(job["seed"]), "runs": runs, "runs_digest": _hex(),
            "digest_v4": _hex(), "params_mode": "standard", "gain": 1.0}


def _fake_b2(c: str, jobs: list[dict], tmpl: dict) -> list[dict]:
    """Block 2 fakes that pass B2.3: L on M = R on W, the relabelled run = L on W, identity = L on W (same digests and outcomes)."""
    by = {j["key"]: _fake_std(j["key"], tmpl) for j in jobs}
    pre = {"manc": "B2-MANC", "mcns": "B2-MCNS"}[c.split("-")[1]]
    for k in list(by):
        arm, rest = k.split("|", 1)
        src = {f"{pre}-LM": f"{pre}-RW", f"{pre}-PERM": f"{pre}-LW", f"{pre}-ID": f"{pre}-LW"}.get(arm)
        if src and f"{src}|{rest}" in by:
            s = by[f"{src}|{rest}"]
            by[k].update({f: s[f] for f in ("usable", "score", "current", "n_tuning_runs", "digest", "n_active_all") if f in s})
    return list(by.values())


def main() -> None:
    keep = sys.argv[sys.argv.index("--keep") + 1] if "--keep" in sys.argv else None
    tmp = Path(keep) if keep else Path(tempfile.mkdtemp(prefix="dryrun_v4_"))
    rel2, fwd = tmp / "reliability_v2", tmp / "forward"
    rel2.mkdir(parents=True, exist_ok=True)
    for f in gha4.REL2.glob("*.json"):
        shutil.copy(f, rel2 / f.name)
    # redirect every write and every REL2 read to the temporary folder
    R2.REL2 = RB.REL2 = gha4.REL2 = rel2
    gha4.ANALYSED_X9 = rel2 / "ANALYSED_SET_X9.json"
    tmpl = _template()
    fake = {}
    for c in FAKE_CAMPAIGNS:
        jobs = _jobs(c)
        if not jobs:
            print(f"[skip] {c}: no packed jobs")
            continue
        if c.startswith("b2-"):
            fake[c] = _fake_b2(c, jobs, tmpl)
        else:
            fake[c] = [(_fake_sweep(j) if j.get("kind") == "sweep_v4" else _fake_std(j["key"], tmpl)) for j in jobs]
    real_load = gha4.load_results
    gha4.load_results = lambda campaign, area="reliability_v2": fake[campaign] if campaign in fake else real_load(campaign, area)
    steps = [("b1 MANC", lambda: RB.cmd_b1("MANC")), ("b1 MaleCNS", lambda: RB.cmd_b1("MaleCNS")),
             ("b2 MANC", lambda: RB.cmd_b2("MANC")), ("b2 MaleCNS", lambda: RB.cmd_b2("MaleCNS")),
             ("b3 MANC", lambda: RB.cmd_b3("MANC")), ("noise", RB.cmd_noise), ("c (fixes 1-8)", lambda: RB.cmd_c(False)),
             ("c --final", lambda: RB.cmd_c(True)), ("rescue", RB.cmd_rescue)]
    import forward_v1 as FV  # noqa: PLC0415

    for robust in (None, "2", "4", "1"):
        steps.append((f"forward build --robust {robust}", lambda r=robust: (setattr(FV, "FWD", fwd / f"robust_{r}"), FV.build(r))))
        steps.append((f"forward decisive ({robust})", lambda r=robust: (setattr(FV, "FWD", fwd / f"robust_{r}"), FV.decisive())))
    import rescore_v4 as RS  # noqa: PLC0415  (Part D; only on FAKE whole-type screens: a real variant is scored once, hard limit 3)

    for fx in ("4", "1"):
        steps.append((f"rescore exam1 {fx} (fake screen)", lambda f=fx: (setattr(RS, "OUT", tmp / "results_run4"), RS.exam1(f))))
    ok = True
    if "--only" in sys.argv:
        want = sys.argv[sys.argv.index("--only") + 1]
        steps = [x for x in steps if x[0].startswith(want) or x[0].startswith("b") or x[0] == "noise"]
    for name, fn in steps:
        try:
            fn()
            print(f"[ok]   {name}", flush=True)
        except BaseException as e:  # noqa: BLE001 - report every failure, keep going
            ok = False
            print(f"[FAIL] {name}: {type(e).__name__}: {e}", flush=True)
            print("       " + "\n       ".join(x[:200] for x in traceback.format_exc().strip().splitlines()[-14:]), flush=True)
    print("DRYRUN", "ALL_OK" if ok else "FAILURES", "outputs in", tmp)


if __name__ == "__main__":
    main()
