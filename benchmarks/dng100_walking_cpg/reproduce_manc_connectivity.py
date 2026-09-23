"""Reproduce the MANC connectivity matrices used by Pugliese et al. from BrainIR's processed MANC builds.

ANSWER-KEY-ADJACENT (benchmark tooling; never imported by src/). The authors' matrices are public derived data
(neuPrint synapse counts, signed by predicted neurotransmitter, floored at 5 synapses) that define the *network*
the paper simulated; they contain no circuit answer. Comparing them with BrainIR's independently rebuilt
`manc:v1.2.1` / `manc:v1.2.3` / `manc:v1.0` datasets tells us (a) which neuPrint release/threshold the paper used and
(b) how faithfully the benchmark can re-derive the paper's network from official files.

    uv run python benchmarks/dng100_walking_cpg/reproduce_manc_connectivity.py [--raw-thresholds]

Outputs (committed): tables/manc_reproduction_summary.json, tables/manc_reproduction_pairs_*.csv (mismatching pairs),
manc_reproduction.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import urllib.parse
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.feather as feather
import requests

from brainir import paths
from brainir.graph import Connectome
from brainir.schema.vocab import SIGN_RULE_ID, sign_for_nt

HERE = Path(__file__).resolve().parent
TABLES = HERE / "tables"

REPO = "smpuglie/Pugliese_2026"
COMMIT = "10e7661bf414ba7b4c2edf795cd36d0f878c17c0"
# pinned by SHA-256 of the canonical (LF) bytes served by raw.githubusercontent.com
EXTERNAL = {
    "t1_W": ("data/manc t1 connectome data/W_20250813_DNtoMN_unsorted.csv",
             "77d5f87c1596a40a7f46c8704008cb8c07c4efe663732034318ee98172d26d2d"),
    "t1_wtable": ("data/manc t1 connectome data/wTable_20250813_DNtoMN_unsorted_withModules.csv",
                  "279c1262cfe2896e5d5d3e79cccf5058f3d27a8e4e1f706a371f597fab7674a8"),
    "full_W": ("data/manc full vnc data/W_20251006.feather",
               "b36e50922b54e1c616cc736bfd81c76212a5582e386f531811a31bdb8eb2d936"),
    "full_wtable": ("data/manc full vnc data/wTable_20251006.feather",
                    "b223da73bd183c55c0d7d3a4dbfe94184a445d5e48d262ad8f0c44e3582bc766"),
    # MaleCNS front-leg network (VNC ROIs only), same pins as investigate_malecns.py
    "mcns_wtable": ("data/imac t1 connectome data/wTable_20260210_vncRoisOnly.csv",
                    "593a75c53f1c69600cac747364b8b623655699b1b83e16b41eeef6fe93dd5b2d"),
    "mcns_W": ("data/imac t1 connectome data/W_20260210_vncRoisOnly.csv",
               "255236baca7a24ead7360636a4ee98fd54d5423026c6ec864bbd717b8d58d3b4"),
}
EXT_DIR = paths.data_root() / "raw" / "external" / "pugliese_2026" / COMMIT[:10]
FLOOR = 5  # the paper's minimum synapse count per pair


def fetch_external() -> dict[str, Path]:
    EXT_DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    for key, (rel, sha) in EXTERNAL.items():
        dest = EXT_DIR / Path(rel).name
        if not dest.exists():
            url = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/{urllib.parse.quote(rel)}"
            r = requests.get(url, timeout=900)
            r.raise_for_status()
            tmp = dest.with_suffix(".partial")
            tmp.write_bytes(r.content)
            got = hashlib.sha256(tmp.read_bytes()).hexdigest()
            if got != sha:
                tmp.unlink()
                raise RuntimeError(f"{rel}: sha256 {got} != pinned {sha}")
            os.replace(tmp, dest)
            os.chmod(dest, stat.S_IREAD)
        elif hashlib.sha256(dest.read_bytes()).hexdigest() != sha:
            raise RuntimeError(f"{dest} does not match pinned sha256")
        out[key] = dest
    return out


# ----------------------------------------------------------------------------- authors' matrices -> sparse pair tables
def authors_t1(files: dict[str, Path]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Front-leg network (2025-08-13): W is pre (rows, bodyId_pre) x post (columns, positional index into the table)."""
    wt = pd.read_csv(files["t1_wtable"], index_col=0)
    W = pd.read_csv(files["t1_W"])
    assert (W["bodyId_pre"].to_numpy() == wt["bodyId"].to_numpy()).all(), "row order differs from the table"
    M = W.drop(columns="bodyId_pre").to_numpy()
    assert M.shape == (len(wt), len(wt))
    ids = wt["bodyId"].to_numpy().astype(np.int64)
    r, c = np.nonzero(M)
    pairs = pd.DataFrame({"pre_id": ids[r], "post_id": ids[c], "w_signed": M[r, c].astype(np.int64)})
    return wt, pairs


def authors_mcns(files: dict[str, Path]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """MaleCNS front-leg network (2026-02-10, VNC ROIs only): W columns are postsynaptic bodyIds; rows follow the table."""
    wt = pd.read_csv(files["mcns_wtable"], index_col=0)
    W = pd.read_csv(files["mcns_W"])
    assert (W["bodyId_pre"].to_numpy() == wt["bodyId"].to_numpy()).all(), "row order differs from the table"
    post_ids = np.array([int(c) for c in W.columns if c != "bodyId_pre"], dtype=np.int64)
    M = W.drop(columns="bodyId_pre").to_numpy()
    pre_ids = wt["bodyId"].to_numpy().astype(np.int64)
    assert set(post_ids) == set(pre_ids)
    r, c = np.nonzero(M)
    pairs = pd.DataFrame({"pre_id": pre_ids[r], "post_id": post_ids[c], "w_signed": np.rint(M[r, c]).astype(np.int64)})
    wt = wt.rename(columns={"consensusNt": "predictedNt_source"}) if "predictedNt" not in wt else wt
    return wt, pairs


def authors_full(files: dict[str, Path]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Full-VNC network (2025-10-06): W feather with one column per postsynaptic bodyId; rows follow the table."""
    wt = feather.read_table(files["full_wtable"]).to_pandas()
    t = feather.read_table(files["full_W"])
    id_cols = [c for c in t.column_names if c.isdigit()]
    other = [c for c in t.column_names if not c.isdigit()]
    if len(id_cols) != len(wt):
        raise RuntimeError(f"full W has {len(id_cols)} body columns vs {len(wt)} table rows; extra columns {other}")
    post_ids = np.array([int(c) for c in id_cols], dtype=np.int64)
    pre_ids = wt["bodyId"].to_numpy().astype(np.int64)
    rows, cols, vals = [], [], []
    step = 1000
    for start in range(0, len(id_cols), step):
        chunk = t.select(id_cols[start:start + step])
        arr = np.column_stack([chunk.column(i).to_numpy(zero_copy_only=False) for i in range(chunk.num_columns)])
        r, c = np.nonzero(arr)
        rows.append(r); cols.append(c + start); vals.append(arr[r, c])
    r = np.concatenate(rows); c = np.concatenate(cols); v = np.concatenate(vals)
    pairs = pd.DataFrame({"pre_id": pre_ids[r], "post_id": post_ids[c], "w_signed": np.rint(v).astype(np.int64)})
    return wt, pairs


# ----------------------------------------------------------------------------- comparison
def signs_from_nt(nt: pd.Series) -> pd.Series:
    """Paper rule: cholinergic +1, GABAergic/glutamatergic -1, anything else -> 0 (row zeroed)."""
    return nt.map({"acetylcholine": 1, "gaba": -1, "glutamate": -1}).fillna(0).astype(int)


def brainir_signs(cx: Connectome, ids: np.ndarray, field: str) -> pd.Series:
    """Sign hypothesis from a BrainIR NT field under SIGN_RULE_ID (None -> 0)."""
    nt = cx.neurons.loc[ids, field]
    out = []
    for v in nt:
        rule = sign_for_nt(None if v is None or (isinstance(v, float) and np.isnan(v)) else v)
        out.append(0 if rule is None or rule.sign is None else rule.sign)
    return pd.Series(out, index=ids)


def _our_counts(cx: Connectome, present: np.ndarray, roi_restrict: set[str] | None) -> pd.DataFrame:
    if roi_restrict is None:
        return cx.edges_between(present, present, annotate=False)[["pre_id", "post_id", "synapse_count"]]
    cn = cx.connection_neuropils(present, present)
    cn = cn[cn["neuropil"].isin(roi_restrict)]
    return cn.groupby(["pre_id", "post_id"], as_index=False)["synapse_count"].sum()


def compare_network(label: str, wt: pd.DataFrame, pairs_auth: pd.DataFrame, cx: Connectome, sign_fields: list[str],
                    nt_column: str = "predictedNt", roi_restrict: set[str] | None = None) -> dict:
    ids = wt["bodyId"].to_numpy().astype(np.int64)
    present = np.array([i for i in ids if cx.has(int(i))], dtype=np.int64)
    missing = sorted(set(ids.tolist()) - set(present.tolist()))
    sub_all = _our_counts(cx, present, roi_restrict)
    ours = sub_all[sub_all["synapse_count"] >= FLOOR][["pre_id", "post_id", "synapse_count"]]
    a = pairs_auth.assign(w_abs=lambda d: d["w_signed"].abs())
    m = a.merge(ours, on=["pre_id", "post_id"], how="outer", indicator=True)
    both = m[m["_merge"] == "both"]
    only_auth = m[m["_merge"] == "left_only"]
    only_ours = m[m["_merge"] == "right_only"]
    exact = int((both["w_abs"] == both["synapse_count"]).sum())
    diff = (both["synapse_count"] - both["w_abs"])
    # pairs the authors have that we count below the floor (or not at all): recover our raw count
    oa = only_auth[["pre_id", "post_id", "w_abs"]].merge(sub_all, on=["pre_id", "post_id"], how="left")
    oa["synapse_count"] = oa["synapse_count"].fillna(0).astype(int)
    # sign agreement (rows with output)
    auth_sign_row = a.groupby("pre_id")["w_signed"].apply(lambda s: int(np.sign(s.iloc[0])))
    nt_auth = wt.set_index("bodyId")[nt_column]
    sign_checks = {f"paper_rule_on_authors_{nt_column}": signs_from_nt(nt_auth.reindex(auth_sign_row.index))}
    for f in sign_fields:
        sign_checks[f"{SIGN_RULE_ID} on {f}"] = brainir_signs(cx, np.array([i for i in auth_sign_row.index if cx.has(int(i))]), f)
    sign_summary = {}
    for k, s in sign_checks.items():
        common = auth_sign_row.index.intersection(s.index)
        agree = int((auth_sign_row.loc[common].to_numpy() == s.loc[common].to_numpy()).sum())
        sign_summary[k] = {"rows_compared": int(len(common)), "agree": agree,
                           "fraction": round(agree / max(1, len(common)), 4)}
    res = {
        "network": label, "brainir_dataset": f"{cx.dataset}:{cx.version}",
        "roi_restrict": sorted(roi_restrict) if roi_restrict is not None else None,
        "neurons": {"authors": int(len(ids)), "present_in_brainir": int(len(present)), "missing": missing[:50],
                    "n_missing": len(missing)},
        "pairs": {"authors": int(len(a)), "brainir_ge_floor": int(len(ours)), "both": int(len(both)),
                  "only_authors": int(len(only_auth)), "only_brainir": int(len(only_ours)),
                  "exact_count_match": exact, "exact_fraction_of_both": round(exact / max(1, len(both)), 6),
                  "count_diff_distribution": {str(k): int(v) for k, v in diff.value_counts().sort_index().head(30).items()},
                  "abs_diff_gt_1": int((diff.abs() > 1).sum()),
                  "total_synapses_authors": int(a["w_abs"].sum()), "total_synapses_brainir": int(ours["synapse_count"].sum()),
                  "only_authors_our_raw_count_hist": {str(k): int(v) for k, v in oa["synapse_count"].value_counts().sort_index().head(20).items()},
                  "only_brainir_count_hist": {str(k): int(v) for k, v in only_ours["synapse_count"].value_counts().sort_index().head(20).items()}},
        "signs": sign_summary,
    }
    mism = pd.concat([
        both[both["w_abs"] != both["synapse_count"]].assign(kind="count_differs"),
        only_auth.assign(kind="only_authors"), only_ours.assign(kind="only_brainir")], ignore_index=True)
    mism = mism[["kind", "pre_id", "post_id", "w_signed", "w_abs", "synapse_count"]].sort_values(["kind", "pre_id", "post_id"])
    return res, mism


def raw_threshold_scan(ids: np.ndarray, pairs_auth: pd.DataFrame) -> dict:
    """Recount pairs of the authors' network from the raw v1.2 partner table under several confidence rules."""
    import duckdb
    import pyarrow.dataset as pads

    from brainir.sources.registry import MANC_V1_2

    path = paths.raw_dir("manc", "v1.2") / MANC_V1_2.local_relpath(MANC_V1_2.file("syn_partners"))
    con = duckdb.connect()
    con.execute("SET threads=8"); con.execute("SET memory_limit='10GB'")
    con.register("syn", pads.dataset(str(path), format="ipc"))
    con.register("nid", pa.table({"id": pa.array(ids, pa.int64())}))
    grid = [0.0, 0.3, 0.4, 0.5, 0.6, 0.7]
    cols = ", ".join(f"count(*) FILTER (WHERE CAST(conf_post AS DOUBLE) >= CAST({b!r} AS DOUBLE)) AS c{i}" for i, b in enumerate(grid))
    df = con.execute(f"""SELECT body_pre AS pre_id, body_post AS post_id, {cols} FROM syn
                         WHERE body_pre IN (SELECT id FROM nid) AND body_post IN (SELECT id FROM nid) GROUP BY 1, 2""").fetchdf()
    df["pre_id"] = df["pre_id"].astype("int64"); df["post_id"] = df["post_id"].astype("int64")
    a = pairs_auth.assign(w_abs=lambda d: d["w_signed"].abs())[["pre_id", "post_id", "w_abs"]]
    out = {}
    for i, b in enumerate(grid):
        ours = df[df[f"c{i}"] >= FLOOR][["pre_id", "post_id", f"c{i}"]].rename(columns={f"c{i}": "c"})
        m = a.merge(ours, on=["pre_id", "post_id"], how="outer", indicator=True)
        both = m[m["_merge"] == "both"]
        out[f"conf_post>={b}"] = {"pairs_recounted": int(len(ours)), "both": int(len(both)),
                                  "only_authors": int((m["_merge"] == "left_only").sum()),
                                  "only_recounted": int((m["_merge"] == "right_only").sum()),
                                  "exact_count_match": int((both["w_abs"] == both["c"]).sum())}
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-thresholds", action="store_true", help="also recount the T1 network from the raw v1.2 partner table")
    args = ap.parse_args(argv)
    files = fetch_external()
    TABLES.mkdir(exist_ok=True)
    summary = {"external_reference": {"repo": REPO, "commit": COMMIT, "files": {k: v[0] for k, v in EXTERNAL.items()}},
               "floor": FLOOR, "comparisons": []}
    wt1, p1 = authors_t1(files)
    wtf, pf = authors_full(files)
    summary["authors_networks"] = {
        "t1_2025-08-13": {"neurons": int(len(wt1)), "pairs": int(len(p1)), "total_synapses": int(p1["w_signed"].abs().sum()),
                          "predictedNt": wt1["predictedNt"].value_counts(dropna=False).to_dict()},
        "full_2025-10-06": {"neurons": int(len(wtf)), "pairs": int(len(pf)), "total_synapses": int(pf["w_signed"].abs().sum())},
    }
    plan = [("t1_2025-08-13", wt1, p1, ["v1.2.1", "v1.2.3", "v1.0"]), ("full_2025-10-06", wtf, pf, ["v1.2.3", "v1.2.1"])]
    for label, wt, pairs, versions in plan:
        for ver in versions:
            pdir = paths.processed_dir("manc", ver)
            if not (pdir / "connections.parquet").exists():
                print(f"skip {label} vs manc:{ver}: not built", file=sys.stderr)
                continue
            cx = Connectome(pdir)
            fields = ["nt_body_prediction"] + (["nt_type_prediction"] if ver == "v1.2.3" else [])
            res, mism = compare_network(label, wt, pairs, cx, fields)
            summary["comparisons"].append(res)
            mism.to_csv(TABLES / f"manc_reproduction_pairs_{label}_vs_{ver}.csv", index=False, lineterminator="\n")
            print(json.dumps({k: res[k] for k in ("network", "brainir_dataset", "pairs", "signs")}, indent=None)[:600])
    # MaleCNS front-leg network: counts restricted to VNC neuropils, signs from consensusNt (the paper's mCNS rule)
    mdir = paths.processed_dir("male-cns", "v1.0")
    if (mdir / "connections.parquet").exists():
        wtm, pm = authors_mcns(files)
        cx = Connectome(mdir)
        np_ = cx.neuropils
        vnc = set(np_.loc[np_["top_level_region"].eq("VNC") & np_["is_primary"], "name"])
        summary["authors_networks"]["mcns_t1_2026-02-10"] = {"neurons": int(len(wtm)), "pairs": int(len(pm)),
                                                             "total_synapses": int(pm["w_signed"].abs().sum())}
        res, mism = compare_network("mcns_t1_2026-02-10", wtm, pm, cx, ["nt_consensus", "nt_body_prediction"],
                                    nt_column="consensusNt", roi_restrict=vnc)
        summary["comparisons"].append(res)
        mism.to_csv(TABLES / "manc_reproduction_pairs_mcns_t1_2026-02-10_vs_male-cns_v1.0.csv", index=False, lineterminator="\n")
        print(json.dumps({k: res[k] for k in ("network", "brainir_dataset", "pairs", "signs")}, indent=None)[:600])
    if args.raw_thresholds:
        summary["raw_threshold_scan_t1"] = raw_threshold_scan(wt1["bodyId"].to_numpy().astype(np.int64), p1)
    (TABLES / "manc_reproduction_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n",
                                                            encoding="utf-8", newline="\n")
    write_markdown(summary)


def write_markdown(s: dict) -> None:
    lines = ["# MANC connectivity reproduction (Pugliese et al. matrices vs BrainIR builds)", "",
             f"Authors' repository `{REPO}` @ `{COMMIT[:10]}` (files pinned by SHA-256). Floor: {s['floor']} synapses per pair.", "",
             "| network | BrainIR build | neurons found | pairs (authors / ours) | both | only authors | only ours | exact count | Σsyn authors / ours |",
             "|---|---|---|---|---|---|---|---|---|"]
    for c in s["comparisons"]:
        p, n = c["pairs"], c["neurons"]
        lines.append(f"| {c['network']} | {c['brainir_dataset']} | {n['present_in_brainir']}/{n['authors']} | "
                     f"{p['authors']} / {p['brainir_ge_floor']} | {p['both']} | {p['only_authors']} | {p['only_brainir']} | "
                     f"{p['exact_count_match']} ({p['exact_fraction_of_both']:.4%}) | {p['total_synapses_authors']} / {p['total_synapses_brainir']} |")
    lines += ["", "## Sign agreement (presynaptic rows with output)", "",
              "| network | BrainIR build | sign source | rows | agree | fraction |", "|---|---|---|---|---|---|"]
    for c in s["comparisons"]:
        for k, v in c["signs"].items():
            lines.append(f"| {c['network']} | {c['brainir_dataset']} | {k} | {v['rows_compared']} | {v['agree']} | {v['fraction']:.4f} |")
    if "raw_threshold_scan_t1" in s:
        lines += ["", "## Raw-threshold scan (front-leg network recounted from the v1.2 partner table)", "",
                  "| rule | pairs >= floor | both | only authors | only recounted | exact |", "|---|---|---|---|---|---|"]
        for k, v in s["raw_threshold_scan_t1"].items():
            lines.append(f"| {k} | {v['pairs_recounted']} | {v['both']} | {v['only_authors']} | {v['only_recounted']} | {v['exact_count_match']} |")
    lines += ["", "Mismatching pairs are listed in `tables/manc_reproduction_pairs_*.csv`; full numbers in "
              "`tables/manc_reproduction_summary.json`.", ""]
    (HERE / "manc_reproduction.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
