"""Freeze the curated MaleCNS <-> MANC correspondences of the benchmark networks into the oracle directory.

    uv run python benchmarks/dng100/build_cross_connectome_reference.py

Reads the public mapping tables (`brainir.mapping`, built without circuit knowledge) and keeps the `curated_body_match`
rows whose two endpoints are both members of the benchmark networks (node lists). The result,
`oracle/cross_connectome_reference.json`, is what the frozen evaluator uses to grade `CrossConnectomeClaim`s
*against curation* (a separate number from agreement with the paper's labels). It is hash-locked with the benchmark, so
the evaluator never depends on the rebuildable 450k-row parquet. Curated pairs are the MaleCNS release's own annotations
(two animals: no pair asserts identity).
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

import pandas as pd

from brainir.mapping import MAPPING_SCHEMA_VERSION, load_mapping, load_summary

HERE = Path(__file__).resolve().parent
NODES = HERE / "nodes"
OUT = HERE / "oracle" / "cross_connectome_reference.json"
A = ("male-cns", "v1.0")
B_VERSIONS = ("v1.2.1", "v1.2.3")


def _nodes(name: str) -> set[int]:
    df = pd.read_csv(NODES / f"{name}.csv")
    col = "bodyId" if "bodyId" in df.columns else "source_id" if "source_id" in df.columns else df.columns[0]
    return {int(i) for i in df[col]}


def main(argv=None) -> int:
    a_nodes = _nodes("male-cns_v1.0")
    out = {"schema": "cross_connectome_reference.1.0", "created_utc": _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
           "mapping_schema_version": MAPPING_SCHEMA_VERSION,
           "caveat": "curated_body_match rows restate the MaleCNS release's manc_body_id annotations; two animals, no identity; "
                     "agreement with these pairs is agreement with curation, not with the paper",
           "a": {"dataset": A[0], "version": A[1], "network": "male-cns_v1.0", "n_nodes": len(a_nodes)}, "b": {}, "pairs": []}
    for bv in B_VERSIONS:
        b_name = f"manc_{bv}"
        b_nodes = _nodes(b_name)
        table = load_mapping(A, ("manc", bv))
        summ = load_summary(A, ("manc", bv))
        rows = table[(table["mapping_kind"] == "curated_body_match") & table["a_source_id"].isin(a_nodes)
                     & table["b_source_id"].notna() & table["b_source_id"].astype("Int64").isin(list(b_nodes))]
        out["b"][b_name] = {"dataset": "manc", "version": bv, "n_nodes": len(b_nodes), "n_pairs": int(len(rows)),
                            "mapping_table_sha256": (summ.get("table") or {}).get("sha256")}
        for _, r in rows.iterrows():
            out["pairs"].append({
                "a": [A[0], A[1], int(r["a_source_id"])], "b": ["manc", bv, int(r["b_source_id"])],
                "mapping_kind": str(r["mapping_kind"]), "confidence": str(r["confidence"]), "evidence_kind": str(r["evidence_kind"]),
                "b_ambiguity": None if pd.isna(r.get("b_ambiguity")) else int(r["b_ambiguity"]),
                "side_consistent": None if pd.isna(r["side_consistent"]) else bool(r["side_consistent"]),
                "role_consistent": None if pd.isna(r["role_consistent"]) else bool(r["role_consistent"]),
                "manc_type_consistent": None if pd.isna(r.get("manc_type_consistent")) else bool(r["manc_type_consistent"]),
            })
    OUT.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT.name}: {len(out['pairs'])} curated pairs", {k: v["n_pairs"] for k, v in out["b"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
