"""Bit-identity of two Level B rounds (research/phase4/LEVEL_B_EXECUTION.md; fork P1): the same methods / systems / seeds run PACKED and
UNPACKED (`tournament.py run --pack` / `--no-pack`) must produce identical evaluation results and identical reference results.

    uv run --no-sync --project phase4 python scripts/p4/compare_rounds.py --a <run_root>/<round_packed> --b <run_root>/<round_unpacked>
        [--intersection]

Compares every `<method>/evals/<sid>_s<seed>.pkl` and every `refs/<sid>.pkl` (records with their timing / host fields removed, compared
exactly with NaN = NaN): this GATES the verdict, since the evaluations run the fitted models on the held-out items and any numerical
difference of a fit shows there. Every `<method>/fits/<sid>_s<seed>.pkl` is compared by sha256 too and reported as
`model_bytes_identical`, NOT gating: a method may embed its own wall-clock timings in its model (e.g. a train_cost record), so the bytes
can differ between ANY two runs. The model bytes are never unpickled (opaque method bytes); the records are the trusted driver's output.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import pickle
import sys
from pathlib import Path

#: fields of an evaluation record that legitimately differ between two runs (wall / CPU times, hosts, worker bookkeeping): an explicit
#: set, plus every key that NAMES A DURATION (…wall_s, …cpu_s, …gpu_s, …closed_s, …load_s, …elapsed_s, …train_s: the per-family
#: `_wall_s`, `eval_job_wall_s`, the model's own train_cost timings). Scientific values are never named like that.
VOLATILE = {"seconds", "peak_container_mb", "peak_mb", "__host__", "__tag", "__task", "__span", "__boot", "__share_s", "__selftest", "host", "pid", "worker", "isolation", "t0", "t1",
            "worker_restarts", "n_restarts", "timings", "stderr_tail", "stdout_tail", "created_utc", "platform"}
_DURATION = ("wall_s", "cpu_s", "gpu_s", "closed_s", "load_s", "elapsed_s", "train_s")


def volatile(k) -> bool:
    return isinstance(k, str) and (k in VOLATILE or k.endswith(_DURATION))


def _norm(o):
    if isinstance(o, dict):
        return {k: _norm(v) for k, v in sorted(o.items(), key=lambda kv: str(kv[0])) if not volatile(k)}
    if isinstance(o, (list, tuple)):
        return [_norm(v) for v in o]
    if dataclasses.is_dataclass(o) and not isinstance(o, type):      # e.g. stats.Estimate (its reps array compared by content)
        return {"__dataclass__": type(o).__name__, **_norm({f.name: getattr(o, f.name) for f in dataclasses.fields(o)})}
    if isinstance(o, float) and math.isnan(o):
        return "NaN"
    try:
        import numpy as np
        if isinstance(o, np.ndarray):
            return {"__ndarray__": o.dtype.str, "shape": list(o.shape), "sha": hashlib.sha256(np.ascontiguousarray(o).tobytes()).hexdigest()}
        if isinstance(o, np.generic):
            return _norm(o.item())
    except ImportError:
        pass
    return o


def _first_diff(a, b, path="") -> str | None:
    if type(a) is not type(b):
        return f"{path}: type {type(a).__name__} != {type(b).__name__}"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                return f"{path}/{k}: only in {'b' if k not in a else 'a'}"
            d = _first_diff(a[k], b[k], f"{path}/{k}")
            if d:
                return d
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: length {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = _first_diff(x, y, f"{path}[{i}]")
            if d:
                return d
        return None
    return None if a == b else f"{path}: {str(a)[:100]} != {str(b)[:100]}"


def compare(a: Path, b: Path, intersection: bool = False) -> dict:
    """intersection: compare only the files present in BOTH rounds (a sample round against a full one); the files of one round only are
    counted, not treated as failures."""
    out = {"fits": {"identical": 0, "different": [], "missing": []}, "evals": {"identical": 0, "different": [], "missing": []},
           "refs": {"identical": 0, "different": [], "missing": []}, "intersection": bool(intersection)}
    for sub, kind in (("fits", "fits"), ("evals", "evals"), ("refs", "refs")):
        pat = "refs/*.pkl" if kind == "refs" else f"*/{sub}/*.pkl"       # the round's reference results (per system)
        fa = {p.relative_to(a).as_posix(): p for p in a.glob(pat)}
        fb = {p.relative_to(b).as_posix(): p for p in b.glob(pat)}
        names = sorted(set(fa) & set(fb)) if intersection else sorted(set(fa) | set(fb))
        if intersection:
            out[kind]["only_in_one_round"] = len(set(fa) ^ set(fb))
        for rel in names:
            if rel not in fa or rel not in fb:
                out[kind]["missing"].append({"file": rel, "only_in": "b" if rel not in fa else "a"})
                continue
            if kind == "fits":
                ha = hashlib.sha256(fa[rel].read_bytes()).hexdigest()
                hb = hashlib.sha256(fb[rel].read_bytes()).hexdigest()
                if ha == hb:
                    out[kind]["identical"] += 1
                else:
                    out[kind]["different"].append({"file": rel, "sha_a": ha[:16], "sha_b": hb[:16]})
            else:
                with open(fa[rel], "rb") as fh:
                    ea = _norm(pickle.load(fh))
                with open(fb[rel], "rb") as fh:
                    eb = _norm(pickle.load(fh))
                d = _first_diff(ea, eb)
                if d is None:
                    out[kind]["identical"] += 1
                else:
                    out[kind]["different"].append({"file": rel, "first_difference": d})
    # the SCIENTIFIC bit-identity is on the evaluation records and the reference results (timings excluded): they run the fitted models
    # on the held-out items, so any numerical difference of a fit shows there. The model FILES are compared byte for byte too, but a
    # method may embed its own wall-clock timings (e.g. train_cost), so their bytes can differ between ANY two runs; reported, not gating.
    out["model_bytes_identical"] = not out["fits"]["different"] and not out["fits"]["missing"] and out["fits"]["identical"] > 0
    out["loops"] = _compare_loops(a, b, intersection)
    gate = ("evals", "refs", "loops") if out["loops"]["compared"] else ("evals", "refs")
    out["bit_identical"] = (all(not out[k]["different"] and not out[k]["missing"] for k in gate)
                            and out["evals"]["identical"] > 0 and not out["fits"]["missing"])
    return out


def _load_loop_file(f: Path):
    if f.name.endswith(".eval.pkl"):                     # a checkpoint evaluation record (the trusted driver's output)
        with open(f, "rb") as fh:
            return _norm(pickle.load(fh))
    if f.suffix == ".jsonl":
        return [_norm(json.loads(line)) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
    return _norm(json.loads(f.read_text(encoding="utf-8")))


def _compare_loops(a: Path, b: Path, intersection: bool) -> dict:
    """The experiment loops of both rounds (when both ran them): every `<method>/loops/<loop>/` file and the round's `loops_rows.json`.
    The experiments (designs and their outcomes), the loop records and the checkpoint evaluations GATE (timings removed); the checkpoint
    model files are compared by sha256 and reported only (a model may embed its own timings, as for the fits)."""
    res = {"compared": False, "identical": 0, "different": [], "missing": [], "checkpoint_models": {"identical": 0, "different": 0}}
    fa = {p.relative_to(a).as_posix(): p for p in a.glob("*/loops/*/*") if p.is_file()}
    fb = {p.relative_to(b).as_posix(): p for p in b.glob("*/loops/*/*") if p.is_file()}
    for f in ("loops_rows.json",):
        if (a / f).is_file():
            fa[f] = a / f
        if (b / f).is_file():
            fb[f] = b / f
    if not fa or not fb:
        return res                          # one round ran no loops: nothing to compare (not a failure)
    res["compared"] = True
    names = sorted(set(fa) & set(fb)) if intersection else sorted(set(fa) | set(fb))
    for rel in names:
        if rel not in fa or rel not in fb:
            res["missing"].append({"file": rel, "only_in": "b" if rel not in fa else "a"})
            continue
        if rel.endswith(".pkl") and not rel.endswith(".eval.pkl"):
            same = hashlib.sha256(fa[rel].read_bytes()).digest() == hashlib.sha256(fb[rel].read_bytes()).digest()
            res["checkpoint_models"]["identical" if same else "different"] += 1
            continue
        if not rel.endswith((".json", ".jsonl", ".eval.pkl")):
            continue
        d = _first_diff(_load_loop_file(fa[rel]), _load_loop_file(fb[rel]))
        if d is None:
            res["identical"] += 1
        else:
            res["different"].append({"file": rel, "first_difference": d})
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, type=Path)
    ap.add_argument("--b", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--intersection", action="store_true", help="compare only the files present in both rounds (a sample round)")
    args = ap.parse_args(argv)
    res = compare(args.a, args.b, intersection=args.intersection)
    if args.out:
        args.out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: ({kk: (vv[:5] if isinstance(vv, list) else vv) for kk, vv in v.items()} if isinstance(v, dict) else v)
                      for k, v in res.items()}, indent=1))
    return 0 if res["bit_identical"] else 1


if __name__ == "__main__":
    sys.exit(main())
