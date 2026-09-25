"""Upload suite material to the Modal volumes as tars, unpacked inside Modal (orchestrator utility for slow uplinks; the frozen backend
scripts/p3/modal_tournament.py reads fit views at /fitvol/views/<name> and suites at /evalvol/suites/<name>/{public,truth}).

    uv run --project phase3 --no-sync python scripts/p3/modal_upload_view.py --tier final                  # the fit view of a frozen suite
    uv run --project phase3 --no-sync python scripts/p3/modal_upload_view.py --name review_g \
        --public-dir data/phase3/synthetic/review_g/public --truth-dir data/phase3/synthetic/review_g/truth  # view + suite of any suite

The view is built with the frozen SuiteData.fit_view (hard links). The truth part is the subset the evaluator reads (truth.json, the
truth index, per-system records, pool latents, test-split latents). A minimal function of this script's own app (standard library
only) extracts each tar into its volume and commits it.
"""

from __future__ import annotations

import argparse
import json
import sys
import tarfile
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase3" / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "p3"))
FIT_VOLUME, EVAL_VOLUME = "brainir-p3-fit", "brainir-p3-eval"


def _extractor():
    def extract(volume: str, name: str, dest: str) -> dict:
        import shutil
        import tarfile as tf_
        from pathlib import Path as P

        import modal
        vol = modal.Volume.from_name(volume)
        vol.reload()
        root = P("/fitvol" if volume == "brainir-p3-fit" else "/evalvol")
        src, out = root / "_incoming" / name, root / dest
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        with tf_.open(src) as t:
            t.extractall(out, filter="data")
        n = sum(1 for q in out.rglob("*") if q.is_file())
        src.unlink()
        vol.commit()
        return {"volume": volume, "files": n, "dest": str(out)}
    return extract


def _tar(files: list[Path], base: Path, tar: Path) -> None:
    with tarfile.open(tar, "w") as tf:
        for q in files:
            tf.add(str(q), arcname=q.relative_to(base).as_posix())


def main(argv=None) -> int:
    import modal
    from brainir_state.suite_eval import SuiteData
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default=None, help="a frozen suite (dev / heldout / final): uploads its fit view only")
    ap.add_argument("--name", default=None, help="a custom suite name (with --public-dir / --truth-dir): view, public and truth")
    ap.add_argument("--public-dir", default=None)
    ap.add_argument("--truth-dir", default=None)
    args = ap.parse_args(argv)
    if args.tier:
        from tournament import suite_spec
        name, pub, truth = args.tier, Path(suite_spec(args.tier)["public_dir"]), None
    else:
        name, pub = args.name, Path(args.public_dir)
        truth = Path(args.truth_dir) if args.truth_dir else None
    work = ROOT / "data" / "phase3" / "_modal_upload"
    work.mkdir(parents=True, exist_ok=True)
    jobs = []
    t0 = time.time()
    fitvol = modal.Volume.from_name(FIT_VOLUME, create_if_missing=True)
    evalvol = modal.Volume.from_name(EVAL_VOLUME, create_if_missing=True)
    with tempfile.TemporaryDirectory(dir=str(work)) as td:
        view = SuiteData(pub, kind="synthetic").fit_view(Path(td) / "view")
        tar = work / f"view_{name}.tar"
        _tar(sorted(p for p in view.rglob("*") if p.is_file()), view, tar)
    with fitvol.batch_upload(force=True) as b:
        b.put_file(str(tar), f"/_incoming/{tar.name}")
    tar.unlink()
    jobs.append((FIT_VOLUME, tar.name, f"views/{name}"))
    if args.name:
        from modal_tournament import _truth_subset
        parts = [("public", pub, sorted(q for q in pub.rglob("*") if q.is_file()))]
        if truth is not None:
            parts.append(("truth", truth, _truth_subset(pub, truth)))
        for part, base, files in parts:
            tar = work / f"{name}_{part}.tar"
            _tar(files, base, tar)
            with evalvol.batch_upload(force=True) as b:
                b.put_file(str(tar), f"/_incoming/{tar.name}")
            tar.unlink()
            jobs.append((EVAL_VOLUME, tar.name, f"suites/{name}/{part}"))
    print(f"uploaded {len(jobs)} tars ({time.time() - t0:.0f} s)", flush=True)
    app = modal.App("brainir-p3-upload-view", image=modal.Image.debian_slim(python_version="3.12"))
    fn = app.function(volumes={"/fitvol": fitvol, "/evalvol": evalvol}, timeout=1800, serialized=True)(_extractor())
    with modal.enable_output(), app.run():
        for v, n, d in jobs:
            print(json.dumps(fn.remote(v, n, d)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
