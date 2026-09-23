"""Archive large result files for version control: <name>.json -> <name>.json.gz (full, byte-identical after decompression)
plus <name>_summary.json (everything except per-run records).

    uv run python scripts/archive_results.py research/phase2/tournament/sel_mech_b1000_part1.json [...]
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

RECORD_KEYS = ("records", "rows", "runs")


def main(argv=None) -> int:
    paths = [Path(p) for p in (argv if argv is not None else sys.argv[1:])]
    for p in paths:
        raw = p.read_bytes()
        gz = p.with_suffix(".json.gz")
        with gzip.GzipFile(filename=p.name, mode="wb", fileobj=open(gz, "wb"), mtime=0) as fh:
            fh.write(raw)
        d = json.loads(raw)
        summ = {k: v for k, v in d.items() if k not in RECORD_KEYS}
        summ["n_records"] = sum(len(d.get(k) or []) for k in RECORD_KEYS)
        summ["full_records"] = gz.name
        p.with_name(p.stem + "_summary.json").write_text(json.dumps(summ, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
        print(f"{p.name}: {len(raw) / 1e6:.1f} MB -> {gz.name} {gz.stat().st_size / 1e6:.1f} MB + {p.stem}_summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
