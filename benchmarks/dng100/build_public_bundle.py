"""Build the frozen public bundle of the DNg100 benchmark (tiers B and A) from BrainIR's processed datasets.

Network membership (which neurons form each simulated network) follows the published front-leg networks of
Pugliese et al. (node lists only — no circuit information); the connectivity, signs, sizes, stimulus and readout are
derived from BrainIR's own builds. The tier-A salt is written to the oracle directory, never into a bundle.

    uv run python benchmarks/dng100/build_public_bundle.py
"""

from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dng100_walking_cpg"))
from reproduce_manc_connectivity import authors_mcns, authors_t1, fetch_external  # noqa: E402

from brainir.benchmark.bundle import default_specs, export_bundle, spec_records, verify_bundle  # noqa: E402

HERE = Path(__file__).resolve().parent
NODES = HERE / "nodes"
ORACLE = HERE / "oracle"


def write_node_lists() -> dict[str, Path]:
    files = fetch_external()
    NODES.mkdir(exist_ok=True)
    wt1, _ = authors_t1(files)
    wtm, _ = authors_mcns(files)
    out = {}
    for name, wt in (("manc_v1.2.1", wt1), ("manc_v1.2.3", wt1), ("male-cns_v1.0", wtm)):
        p = NODES / f"{name}.csv"
        pd.DataFrame({"bodyId": wt["bodyId"].astype("int64")}).to_csv(p, index=False, lineterminator="\n")
        out[name] = p
    (NODES / "README.md").write_text(
        "# Network node lists\n\nOne body ID per line: the neurons that form each simulated front-leg network. Membership follows the\n"
        "published networks of Pugliese et al. (repository smpuglie/Pugliese_2026 @ 10e7661, files pinned by SHA-256 in\n"
        "`benchmarks/dng100_walking_cpg/reproduce_manc_connectivity.py`). These lists define WHICH neurons are simulated;\n"
        "they carry no information about which of them matter. Everything else in the bundle is derived from BrainIR builds.\n",
        encoding="utf-8", newline="\n")
    return out


def main() -> None:
    nodes = write_node_lists()
    specs = default_specs(nodes)
    ORACLE.mkdir(exist_ok=True)
    salt_path = ORACLE / "tier_a_salt.txt"
    if not salt_path.exists():
        salt_path.write_text(secrets.token_hex(16) + "\n", encoding="utf-8", newline="\n")
    salt = salt_path.read_text(encoding="utf-8").strip()
    out = {}
    for tier, root in (("B", HERE / "public"), ("A", HERE / "public_blind")):
        m = export_bundle(specs, root, tier=tier, salt=salt, private_dir=ORACLE / "tier_a_ids")
        v = verify_bundle(root)
        assert v["ok"], v
        out[tier] = {"root": root.name, "bundle_sha256": m["bundle_sha256"], "n_files": len(m["files"]),
                     "networks": [(n["name"], n["n_neurons"], n["n_edges"]) for n in m["networks"]]}
        print(f"tier {tier}: {root.name} bundle_sha256={m['bundle_sha256'][:16]} files={len(m['files'])}")
    (HERE / "manifests").mkdir(exist_ok=True)
    (HERE / "manifests" / "bundle_build.json").write_text(
        json.dumps({"specs": spec_records(specs), "bundles": out}, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
