"""Upload a suite's public FIT VIEW (train / val rows only) to the Modal fit volume as one tar, unpacked inside Modal (orchestrator
utility; the frozen backend scripts/p3/modal_tournament.py reads the view at /fitvol/views/<tier>).

    uv run --project phase3 --no-sync python scripts/p3/modal_upload_view.py --tier final

The view is built with the frozen SuiteData.fit_view (hard links), tarred, uploaded to /fitvol/_incoming/ and extracted by a minimal
function of this script's own app (standard library only), which commits the volume.
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
FIT_VOLUME = "brainir-p3-fit"


def _extractor():
    def extract_view(name: str, tier: str) -> dict:
        import shutil
        import tarfile as tf_
        from pathlib import Path as P

        import modal
        vol = modal.Volume.from_name("brainir-p3-fit")
        vol.reload()
        src, dest = P("/fitvol/_incoming") / name, P("/fitvol/views") / tier
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
        with tf_.open(src) as t:
            t.extractall(dest, filter="data")
        n = sum(1 for q in dest.rglob("*") if q.is_file())
        src.unlink()
        vol.commit()
        return {"files": n, "dest": str(dest)}
    return extract_view


def main(argv=None) -> int:
    import modal
    from brainir_state.suite_eval import SuiteData
    from tournament import suite_spec
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", required=True)
    args = ap.parse_args(argv)
    spec = suite_spec(args.tier)
    vol = modal.Volume.from_name(FIT_VOLUME, create_if_missing=True)
    t0 = time.time()
    work = ROOT / "data" / "phase3" / "_modal_upload"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(work)) as td:
        view = SuiteData(spec["public_dir"], kind="synthetic").fit_view(Path(td) / "view")
        tar = work / f"view_{args.tier}.tar"
        with tarfile.open(tar, "w") as tf:
            for q in sorted(p for p in view.rglob("*") if p.is_file()):
                tf.add(str(q), arcname=q.relative_to(view).as_posix())
    with vol.batch_upload(force=True) as b:
        b.put_file(str(tar), f"/_incoming/{tar.name}")
    print(f"uploaded {tar.name} ({tar.stat().st_size / 1e6:.0f} MB, {time.time() - t0:.0f} s)", flush=True)
    tar.unlink()
    app = modal.App("brainir-p3-upload-view", image=modal.Image.debian_slim(python_version="3.12"))
    fn = app.function(volumes={"/fitvol": vol}, timeout=1800, serialized=True)(_extractor())
    with modal.enable_output(), app.run():
        print(json.dumps(fn.remote(tar.name, args.tier)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
