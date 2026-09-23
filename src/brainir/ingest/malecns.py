"""MaleCNS (Janelia 'male-cns') raw official files -> BrainIR canonical tables.

Inputs (all under raw/<dataset>/<version>/, see brainir.sources.registry):

* database/neuprint-inputs/Neuprint_Meta_debug.json      ROI hierarchy, thresholds, totals
* connectome-data/flat-connectome/body-annotations-*.feather   curated annotations
* connectome-data/flat-connectome/body-neurotransmitters-*.feather
* database/neuprint-inputs/Neuprint_Neurons.feather      per-segment stats + roiInfo + :LABEL
* database/neuprint-inputs/Neuprint_Neuron_Connections.feather   :ConnectsTo edges (+roiInfo)
* connectome-data/flat-connectome/connectome-weights-*.feather   independent cross-check
* connectome-data/flat-connectome/syn-partners-*.feather         optional synapse-level checks

Node definition: the source paper defines neurons as bodies with a
``superclass`` annotation; all other synaptic bodies are fragments. BrainIR's
``neurons`` table follows the source definition; connections are kept only when
both endpoints are neurons. Connectivity to fragments is not dropped silently:
per-neuron totals over *all* partners are kept (n_upstream/n_downstream) next
to totals over neuron partners (n_*_from/to_neurons).

Autapses (pre == post) are retained and flagged (``is_autapse``).
"""

from __future__ import annotations

import json
import logging
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as pads
import pyarrow.feather as feather
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components

from .. import __version__, paths
from ..io import write_canonical, write_parquet
from ..schema import tables as T
from ..schema.vocab import (
    NT_VALUES,
    STATUS_LABEL_ORDER,
    STATUS_LABEL_TO_NEUPRINT_STATUS,
    UNASSIGNED_NEUROPIL,
    normalize_side,
)
from ..sources.registry import MALECNS_V1_0, DatasetSource
from ..validation import INFO, PASS, WARN, ValidationReport

log = logging.getLogger(__name__)

PIPELINE_ID = "brainir.ingest.malecns"
PIPELINE_VERSION = "1.0.0"
ANIMAL_SEX = "male"

# raw column names -----------------------------------------------------------
NP_ID = ":ID(Body-ID)"
C_PRE, C_POST = ":START_ID(Body-ID)", ":END_ID(Body-ID)"

# annotation float columns that encode integers (checked, then cast to int64)
FLOAT_INT_COLS = ("group", "mancBodyid", "mancGroup", "mancSerial", "mcnsSerial", "assignedOlHex1", "assignedOlHex2")

# columns compared between the flat annotation export and the neuPrint neuron table
CROSSCHECK_ANN = {
    "type": "type:string", "instance": "instance:string", "superclass": "superclass:string",
    "class": "class:string", "subclass": "subclass:string", "somaSide": "somaSide:string",
    "rootSide": "rootSide:string", "status": "status:string", "statusLabel": "statusLabel:string",
    "group": "group:long", "flywireType": "flywireType:string", "mancType": "mancType:string",
    "hemibrainType": "hemibrainType:string", "synonyms": "synonyms:string",
}
CROSSCHECK_NT = {
    "predicted_nt": "predictedNt:string", "consensus_nt": "consensusNt:string",
    "celltype_predicted_nt": "celltypePredictedNt:string",
    "predicted_nt_confidence": "predictedNtConfidence:float",
    "celltype_predicted_nt_confidence": "celltypePredictedNtConfidence:float",
    "total_nt_predictions": "totalNtPredictions:float",
}


class IngestAborted(RuntimeError):
    """Raised when a critical integrity check fails and later steps would be meaningless.
    The validation report is written before raising."""

    def __init__(self, message: str, report: ValidationReport):
        super().__init__(message)
        self.report = report


CRITICAL_CHECKS = ("duplicates.annotations.bodyId", "duplicates.nt.body", "ids.annotations.non_null_positive",
                   "types.annotation_float_ids_integral",
                   "provenance.meta_dataset_tag", "provenance.acquisition_dataset", "provenance.raw_inputs_verified")


@dataclass
class IngestConfig:
    source: DatasetSource = MALECNS_V1_0
    raw_dir: Path | None = None
    out_dir: Path | None = None
    verify_acquisition: bool = True
    synapse_checks: bool = True
    synapse_sample_neurons: int = 300
    seed: int = 20260922
    duckdb_memory_limit: str = "8GB"
    threads: int = 8

    def raw(self) -> Path:
        return Path(self.raw_dir) if self.raw_dir else paths.raw_dir(self.source.dataset, self.source.version)

    def out(self) -> Path:
        return Path(self.out_dir) if self.out_dir else paths.processed_dir(self.source.dataset, self.source.version)

    def raw_file(self, key: str) -> Path:
        return self.raw() / self.source.local_relpath(self.source.file(key))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _duck(cfg: IngestConfig) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    tmp = paths.cache_dir() / "duckdb_tmp" / f"pid{os.getpid()}"  # per-process: concurrent runs never share spill files
    tmp.mkdir(parents=True, exist_ok=True)
    con.execute(f"SET memory_limit='{cfg.duckdb_memory_limit}'")
    con.execute(f"SET threads={int(cfg.threads)}")
    con.execute(f"SET temp_directory='{tmp.as_posix()}'")
    con.execute("SET preserve_insertion_order=false")
    return con


def _ipc_dataset(path: Path) -> pads.Dataset:
    return pads.dataset(str(path), format="ipc")


def _reg(con: duckdb.DuckDBPyConnection, name: str, obj) -> None:
    """Register (or replace) a Python object as a DuckDB view."""
    try:
        con.unregister(name)
    except Exception:  # noqa: BLE001 - not registered yet
        pass
    con.register(name, obj)


def _arrow(rel) -> pa.Table:
    t = rel.arrow()
    return t.read_all() if isinstance(t, pa.RecordBatchReader) else t


def _git_state() -> dict:
    root = paths.repo_root()
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "src"], cwd=root, capture_output=True,
                                    text=True, check=True).stdout.strip())
        return {"commit": commit, "src_dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "src_dirty": None}


def _float_to_int64(s: pd.Series, name: str) -> pd.Series:
    v = s.to_numpy(dtype="float64", na_value=np.nan)
    ok = np.isnan(v) | ((np.floor(v) == v) & (np.abs(v) < 2 ** 53))
    if not ok.all():
        raise ValueError(f"column {name}: {int((~ok).sum())} non-integral or >2^53 values; refusing lossy cast")
    mask = np.isnan(v)
    return pd.arrays.IntegerArray(np.where(mask, 0, v).astype("int64"), mask)


def _side_suffix(name: str) -> str | None:
    if name.endswith("(L)"):
        return "L"
    if name.endswith("(R)"):
        return "R"
    return None


# ---------------------------------------------------------------------------
# steps
# ---------------------------------------------------------------------------
def check_acquisition(cfg: IngestConfig, report: ValidationReport, needed: list[str]) -> dict:
    log_path = cfg.raw() / "_acquisition.json"
    if not cfg.verify_acquisition:
        report.add("provenance.acquisition_log", "provenance", "Acquisition log verification skipped (fixture/test mode).", INFO)
        return {}
    if not log_path.exists():
        raise FileNotFoundError(f"{log_path} not found: acquire the raw data first (`uv run brainir acquire "
                                f"--tier metadata --tier core --tier synapses`)")
    acq = json.loads(log_path.read_text())
    report.expect_equal("provenance.acquisition_dataset", "provenance", "Acquisition log dataset/version match the registry.",
                        [acq["dataset"], acq["version"]], [cfg.source.dataset, cfg.source.version])
    recs = {r["key"]: r for r in acq["files"]}
    problems = {}
    for key in needed:
        f = cfg.source.file(key)
        r = recs.get(key)
        path = cfg.raw_file(key)
        if r is None:
            problems[key] = "not in acquisition log"
            continue
        issues = []
        if not path.exists():
            issues.append("missing on disk")
        elif path.stat().st_size != f.size:
            issues.append(f"size {path.stat().st_size} != {f.size}")
        if r["local_digests"]["crc32c_b64"] != f.crc32c_b64:
            issues.append("crc32c differs from registry pin")
        if f.md5_b64 and r["local_digests"]["md5_b64"] != f.md5_b64:
            issues.append("md5 differs from registry pin")
        if r["remote_metadata"]["generation"] != f.generation:
            issues.append("GCS generation differs from registry pin")
        if issues:
            problems[key] = issues
    report.expect_true("provenance.raw_inputs_verified", "provenance",
                       "Every raw input exists, has the pinned size, and its recorded checksums match registry pins "
                       "(CRC32C for all, MD5 where available, GCS generation).",
                       not problems, observed=problems or "all ok", inputs=needed)
    return recs


def load_meta(cfg: IngestConfig, report: ValidationReport) -> dict:
    meta = json.loads(cfg.raw_file("neuprint_meta_json").read_text(encoding="utf-8"))
    report.expect_equal("provenance.meta_dataset_tag", "provenance",
                        "neuPrint :Meta dataset/tag equal the requested dataset/version (no cross-version mixing).",
                        [meta.get("dataset"), meta.get("tag")], [cfg.source.dataset, cfg.source.version])
    report.add("provenance.meta_identity", "provenance", "neuPrint snapshot identity (DVID uuid, mutation id, last edit).",
               INFO, observed={"uuid": meta.get("uuid"), "latestMutationId": meta.get("latestMutationId"),
                               "lastDatabaseEdit": meta.get("lastDatabaseEdit")})
    report.add("provenance.synapse_thresholds", "provenance",
               "Synapse confidence thresholds declared by neuPrint (weight: post>=postHighAccuracyThreshold; "
               "weightHP: post>=postHPThreshold). Flat files are pre-filtered at conf>=0.5 on BOTH pre and post.",
               INFO, observed={k: meta.get(k) for k in ("postHighAccuracyThreshold", "preHPThreshold", "postHPThreshold")})
    return meta


def build_neuropils(meta: dict, report: ValidationReport) -> tuple[pa.Table, list[str]]:
    """ROI catalogue. The neuPrint hierarchy is a DAG (some ROIs have two parents), so rows are keyed by name,
    with the authoritative single parent taken from roiInfo['parent'] and all parents listed."""
    occ: dict[str, list[tuple[str | None, int, str | None]]] = {}

    def walk(node, depth, parent, top):
        name = node["name"]
        this_top = name if depth == 1 else top  # depth-1 nodes are the top-level regions
        occ.setdefault(name, []).append((parent, depth, this_top))
        for ch in node.get("children", []) or []:
            walk(ch, depth + 1, name, this_top)

    walk(meta["roiHierarchy"], 0, None, None)
    primary = list(meta["primaryRois"])
    ri = meta["roiInfo"]
    multi = {n: sorted({p for p, _, _ in o if p}) for n, o in occ.items() if len({p for p, _, _ in o}) > 1}
    report.add("neuropils.hierarchy_is_dag", "uniqueness",
               "ROIs listed under more than one parent in the source hierarchy (merged into one row each; "
               "'parent' = roiInfo parent, 'all_parents' keeps every parent).", INFO,
               observed=len(multi), multi_parent_rois=multi)
    top_conflict = {n: sorted({t for _, _, t in o if t}) for n, o in occ.items() if len({t for _, _, t in o if t}) > 1}
    report.expect_true("neuropils.top_level_region_consistent", "uniqueness",
                       "Every ROI has a single top-level region across all its hierarchy paths.", not top_conflict,
                       observed=top_conflict)
    bad_parent = {n: [ri[n].get("parent"), sorted({p for p, _, _ in o if p})] for n, o in occ.items()
                  if n in ri and ri[n].get("parent") and ri[n].get("parent") not in {p for p, _, _ in o}}
    report.expect_true("neuropils.roiinfo_parent_consistent", "referential",
                       "The roiInfo 'parent' of each ROI is one of its hierarchy parents.", not bad_parent,
                       observed=bad_parent)
    in_h = set(occ)
    report.expect_true("referential.primary_rois_in_hierarchy", "referential", "All primary ROIs exist in the ROI hierarchy.",
                       set(primary) <= in_h, observed=sorted(set(primary) - in_h))
    stats_only = sorted(set(ri) - in_h)
    report.add("neuropils.stats_only_rois", "referential",
               "ROIs with statistics in roiInfo but absent from the hierarchy (kept, in_hierarchy=False).", INFO,
               observed=len(stats_only), rois=stats_only)
    names = sorted(in_h | set(ri))
    prim = set(primary)
    rows = []
    for n in names:
        o = occ.get(n, [])
        parents = sorted({p for p, _, _ in o if p})
        auth_parent = ri.get(n, {}).get("parent") or (o[0][0] if o else None)
        tops = [t for _, _, t in o if t]
        rows.append({
            "name": n, "parent": auth_parent, "all_parents": parents or None,
            "depth": min(d for _, d, _ in o) if o else None, "in_hierarchy": bool(o),
            "top_level_region": tops[0] if tops else None, "is_primary": n in prim,
            "is_nerve": bool(ri.get(n, {}).get("isNerve", False)), "side": _side_suffix(n),
            "n_pre_total": ri.get(n, {}).get("pre"), "n_post_total": ri.get(n, {}).get("post"),
        })
    tbl = pa.Table.from_pylist(rows, schema=pa.schema([
        ("name", pa.string()), ("parent", pa.string()), ("all_parents", pa.list_(pa.string())), ("depth", pa.int16()),
        ("in_hierarchy", pa.bool_()), ("top_level_region", pa.string()), ("is_primary", pa.bool_()),
        ("is_nerve", pa.bool_()), ("side", pa.string()), ("n_pre_total", pa.int64()), ("n_post_total", pa.int64())]))
    report.expect_equal("ids.neuropils.unique", "uniqueness", "ROI names are unique in the output catalogue.",
                        len(names) - len(set(names)), 0)
    sp_pre = sum(ri[p].get("pre", 0) for p in primary)
    sp_post = sum(ri[p].get("post", 0) for p in primary)
    report.add("coverage.primary_roi_synapse_fraction", "coverage",
               "Fraction of all T-bars / PSDs located inside some primary ROI (rest -> '<unassigned>').", INFO,
               observed={"pre": round(sp_pre / meta["totalPreCount"], 6), "post": round(sp_post / meta["totalPostCount"], 6)})
    return tbl, primary


def load_annotations(cfg: IngestConfig, report: ValidationReport) -> tuple[pd.DataFrame, pa.Table]:
    path = cfg.raw_file("body_annotations")
    raw = feather.read_table(path)
    df = raw.to_pandas()
    report.add("rows.raw.body_annotations", "ingestion", "Rows in the raw body annotation table.", INFO, observed=len(df))
    lossy = {}
    for c in FLOAT_INT_COLS:
        if c in df.columns:
            try:
                df[c] = _float_to_int64(df[c], c)
            except ValueError as exc:
                lossy[c] = str(exc)
    if "statusLabel" in df.columns:
        df["statusLabel"] = df["statusLabel"].astype("string")
    report.expect_true("types.annotation_float_ids_integral", "types",
                       "Float-encoded ID columns (group, mancBodyid, ...) are integral and < 2^53, so the cast to int64 "
                       "is lossless (a violation aborts the build).",
                       not lossy, observed=lossy or [c for c in FLOAT_INT_COLS if c in df.columns])
    ids = df["bodyId"]
    report.expect_true("ids.annotations.non_null_positive", "ids", "bodyId non-null and positive.",
                       bool(ids.notna().all() and (ids > 0).all()))
    dup = int(ids.duplicated().sum())
    report.expect_equal("duplicates.annotations.bodyId", "duplicates", "No duplicate bodyId rows in annotations.", dup, 0)
    labels = set(df["statusLabel"].dropna().unique())
    unknown = sorted(labels - set(STATUS_LABEL_ORDER))
    report.expect_true("types.status_label_vocabulary", "types", "All statusLabel values are known DVID labels.",
                       not unknown, observed=unknown)
    mapped = df["statusLabel"].map(lambda x: STATUS_LABEL_TO_NEUPRINT_STATUS.get(x) if isinstance(x, str) else None)
    st = df["status"].astype("string")
    both = mapped.notna() & st.notna()
    mism = int((mapped[both].astype("string") != st[both]).sum())
    empty_mapped_null_status = int((mapped.eq("") & st.isna()).sum())
    report.add("consistency.status_vs_status_label", "cross_source",
               "neuPrint 'status' equals the flyem-snapshot mapping of 'statusLabel' where both present.",
               PASS if mism == 0 else WARN, observed=mism, expected=0,
               note=f"{empty_mapped_null_status} bodies have a statusLabel mapping to '' and null status (expected).")
    # typed source table (verbatim columns, lossless int casts)
    src = pa.Table.from_pandas(df, preserve_index=False)
    return df, src


def load_nt(cfg: IngestConfig, report: ValidationReport) -> pd.DataFrame:
    nt = feather.read_table(cfg.raw_file("body_neurotransmitters")).to_pandas()
    report.add("rows.raw.body_neurotransmitters", "ingestion", "Rows (bodies) in the raw NT table.", INFO, observed=len(nt))
    report.expect_equal("duplicates.nt.body", "duplicates", "No duplicate bodies in NT table.", int(nt["body"].duplicated().sum()), 0)
    bad = {}
    for c in ("predicted_nt", "celltype_predicted_nt", "consensus_nt", "ground_truth"):
        vals = set(nt[c].dropna().unique())
        if vals - NT_VALUES:
            bad[c] = sorted(vals - NT_VALUES)
    report.expect_true("types.nt_vocabulary", "types", "All NT labels are in the controlled vocabulary.", not bad, observed=bad)
    conf_cols = ("predicted_nt_confidence", "celltype_predicted_nt_confidence")
    rng = {c: [float(nt[c].min()), float(nt[c].max())] for c in conf_cols}
    ok = all(0.0 <= lo and hi <= 1.0 for lo, hi in rng.values())
    report.expect_true("edge_values.nt_confidence_range", "edge_values", "NT confidences lie in [0, 1].", ok, observed=rng)
    # Consensus rule. Berg et al. Methods: consensus = celltype prediction, overridden by experimental ground truth,
    # with octopamine/serotonin model calls set to unclear. Observed in the released data (v1.0): untyped bodies fall
    # back to the body-level prediction, and some typed bodies carry expert/literature overrides that are NOT in the
    # 'ground_truth' column (e.g. Kenyon cells -> acetylcholine, motor neurons -> glutamate).
    def drop_om(x):
        return x.where(~x.isin(["octopamine", "serotonin"]), "unclear")
    typed = nt["cell_type"].notna()
    exp = drop_om(nt["celltype_predicted_nt"])
    exp = nt["ground_truth"].where(nt["ground_truth"].notna(), exp)
    exp = exp.where(typed, drop_om(nt["predicted_nt"]))
    diff = nt["consensus_nt"] != exp
    n_untyped_diff = int((diff & ~typed).sum())
    report.expect_equal("consistency.nt_consensus_rule_untyped", "cross_source",
                        "Untyped bodies: consensus_nt == body-level predicted_nt with octopamine/serotonin -> unclear "
                        "(behaviour observed in the data; the Methods text only describes typed bodies).",
                        n_untyped_diff, 0, on_mismatch=WARN)
    t_diff = nt.loc[diff & typed]
    by_type = (t_diff.groupby(["cell_type", "celltype_predicted_nt", "consensus_nt"]).size()
               .sort_values(ascending=False).head(60))
    report.add("consistency.nt_consensus_rule_typed", "cross_source",
               "Typed bodies whose consensus_nt is not explained by (ground_truth else celltype prediction with "
               "octopamine/serotonin -> unclear). These are expert/literature overrides absent from the ground_truth "
               "column (documented source discrepancy; consensus is still what neuPrint shows and recommends).",
               PASS if len(t_diff) == 0 else WARN, observed={"bodies": int(len(t_diff)),
                                                          "cell_types": int(t_diff["cell_type"].nunique())},
               expected={"bodies": 0},
               top_overrides=[{"cell_type": a, "celltype_predicted_nt": b, "consensus_nt": c, "bodies": int(v)}
                              for (a, b, c), v in by_type.items()])
    return nt


def scan_neuprint_neurons(con, cfg: IngestConfig, neuron_ids: np.ndarray, report: ValidationReport) -> pd.DataFrame:
    path = cfg.raw_file("neuprint_neurons")
    ds = _ipc_dataset(path)
    _reg(con, "np_neurons", ds)
    _reg(con, "nid", pa.table({"id": pa.array(neuron_ids, pa.int64())}))
    stats = con.execute(f"""
        SELECT count(*) AS n_segments,
               count(*) FILTER (WHERE ":LABEL" LIKE '%;Neuron;%') AS n_neuron_label,
               count(*) - count(DISTINCT "{NP_ID}") AS n_dup_ids,
               count(*) FILTER (WHERE "{NP_ID}" IS NULL) AS n_null_ids,
               count(*) FILTER (WHERE "{NP_ID}" <> "bodyId:long") AS n_id_mismatch,
               sum("pre:int") AS sum_pre, sum("post:int") AS sum_post,
               sum("downstream:int") AS sum_downstream, sum("upstream:int") AS sum_upstream
        FROM np_neurons""").fetchdf().iloc[0].to_dict()
    report.add("rows.raw.neuprint_neurons", "ingestion", "Synaptic segments in neuPrint and how many carry the :Neuron label.",
               INFO, observed={k: int(v) for k, v in stats.items() if k in ("n_segments", "n_neuron_label")})
    report.expect_equal("duplicates.neuprint_neurons.id", "duplicates", "No duplicate segment IDs in the neuPrint neuron table.",
                        int(stats["n_dup_ids"]), 0)
    report.expect_equal("ids.neuprint_neurons.id_consistent", "ids", ":ID(Body-ID) equals bodyId for every segment, no nulls.",
                        [int(stats["n_null_ids"]), int(stats["n_id_mismatch"])], [0, 0])
    report.expect_equal("consistency.upstream_equals_post", "directionality",
                        "Total upstream connections == total PSDs (each PSD has exactly one presynaptic partner).",
                        int(stats["sum_upstream"]), int(stats["sum_post"]))
    ann_cols = ", ".join(f'"{c}"' for c in CROSSCHECK_ANN.values())
    nt_cols = ", ".join(f'"{c}"' for c in CROSSCHECK_NT.values())
    df = con.execute(f"""
        SELECT n."{NP_ID}" AS id, n."pre:int" AS pre, n."post:int" AS post, n."downstream:int" AS downstream,
               n."upstream:int" AS upstream, n."synweight:int" AS synweight, n."size:long" AS size,
               n.":LABEL" LIKE '%;Neuron;%' AS neuron_label, n."roiInfo:string" AS roi_info, {ann_cols}, {nt_cols}
        FROM np_neurons n SEMI JOIN nid ON n."{NP_ID}" = nid.id""").fetchdf()
    con.unregister("np_neurons")
    return df, stats


def neuron_level_crosschecks(ann: pd.DataFrame, nt: pd.DataFrame, npn: pd.DataFrame, report: ValidationReport) -> None:
    m = ann.set_index("bodyId").join(npn.set_index("id"), how="inner")
    out = {}
    for a, b in CROSSCHECK_ANN.items():
        x = m[a].astype("string") if a != "group" else m[a].astype("Int64").astype("string")
        y = m[b]
        if b == "group:long":
            y = pd.Series(_float_to_int64(y, b), index=m.index).astype("string")
        else:
            y = y.astype("string")
        neq = ~((x == y).fillna(False) | (x.isna() & y.isna()))
        out[a] = int(neq.sum())
    status = PASS if not any(out.values()) else WARN
    report.add("cross_source.annotations_flat_vs_neuprint", "cross_source",
               "Annotation fields agree between flat body-annotations export (2026-06-03) and neuPrint neuron table "
               "(2026-06-08) for neurons (count of mismatching neurons per field).", status, observed=out)
    mm = nt.set_index("body").join(npn.set_index("id"), how="inner")
    out2 = {}
    for a, b in CROSSCHECK_NT.items():
        x, y = mm[a], mm[b]
        if "confidence" in a or a == "total_nt_predictions":
            neq = ~(np.isclose(x.astype("float64"), y.astype("float64"), rtol=0, atol=1e-6) | (x.isna() & y.isna()))
        else:
            neq = ~((x.astype("string") == y.astype("string")).fillna(False) | (x.isna() & y.isna()))
        out2[a] = int(neq.sum())
    report.add("cross_source.nt_flat_vs_neuprint", "cross_source",
               "Neurotransmitter fields agree between flat NT export and neuPrint neuron table (mismatch counts).",
               PASS if not any(out2.values()) else WARN, observed=out2)


def parse_neuron_roiinfo(con, npn: pd.DataFrame, primary: list[str], report: ValidationReport) -> pa.Table:
    _reg(con, "rin", pa.table({"id": pa.array(npn["id"].to_numpy(), pa.int64()),
                                  "ri": pa.array(npn["roi_info"].tolist(), pa.string())}))
    _reg(con, "prim", pa.table({"roi": pa.array(primary, pa.string())}))
    tbl = _arrow(con.execute("""
        WITH e AS (
          SELECT id, unnest(map_entries(json_transform(ri, '"MAP(VARCHAR, STRUCT(pre BIGINT, post BIGINT))"'))) AS kv FROM rin)
        SELECT id AS source_id, kv.key AS neuropil, coalesce(kv.value.pre, 0) AS n_pre, coalesce(kv.value.post, 0) AS n_post
        FROM e SEMI JOIN prim ON kv.key = prim.roi"""))
    con.unregister("rin")
    # remainder outside primary ROIs
    df = tbl.to_pandas()
    tot = df.groupby("source_id")[["n_pre", "n_post"]].sum()
    base = npn.set_index("id")[["pre", "post"]]
    rem = base.join(tot, how="left").fillna(0)
    rem_pre = (rem["pre"] - rem["n_pre"]).astype("int64")
    rem_post = (rem["post"] - rem["n_post"]).astype("int64")
    neg = int(((rem_pre < 0) | (rem_post < 0)).sum())
    report.expect_equal("consistency.neuron_neuropils_not_exceeding_totals", "coverage",
                        "Per-neuron primary-ROI pre/post counts never exceed the neuron's totals.", neg, 0)
    keep = (rem_pre > 0) | (rem_post > 0)
    un = pd.DataFrame({"source_id": rem.index[keep], "neuropil": UNASSIGNED_NEUROPIL,
                       "n_pre": rem_pre[keep].to_numpy(), "n_post": rem_post[keep].to_numpy()})
    full = pd.concat([df, un], ignore_index=True)
    full = full[(full.n_pre > 0) | (full.n_post > 0)]
    return pa.Table.from_pandas(full, preserve_index=False)


def scan_connections(con, cfg: IngestConfig, neuron_ids: np.ndarray, primary: list[str], report: ValidationReport,
                     meta: dict) -> tuple[pa.Table, pa.Table, pd.DataFrame, dict]:
    path = cfg.raw_file("neuprint_connections")
    _reg(con, "np_conn", _ipc_dataset(path))
    _reg(con, "nid", pa.table({"id": pa.array(neuron_ids, pa.int64())}))
    _reg(con, "prim", pa.table({"roi": pa.array(primary, pa.string())}))
    log.info("connections: global statistics over the full neuPrint connection table")
    g = con.execute(f"""
        SELECT count(*) AS n_rows,
               count(*) FILTER (WHERE "{C_PRE}" IS NULL OR "{C_POST}" IS NULL OR "weight:int" IS NULL) AS n_null,
               count(*) FILTER (WHERE "weight:int" < 0 OR "weightHP:int" < 0 OR "weightHR:int" < 0) AS n_negative,
               count(*) FILTER (WHERE "weight:int" = 0) AS n_weight_zero,
               count(*) FILTER (WHERE "weightHR:int" <> "weight:int") AS n_hr_ne_weight,
               count(*) FILTER (WHERE "weightHP:int" > "weight:int") AS n_hp_gt_weight,
               count(*) FILTER (WHERE "{C_PRE}" = "{C_POST}") AS n_self,
               sum("weight:int") FILTER (WHERE "{C_PRE}" = "{C_POST}") AS w_self,
               sum("weight:int") AS sum_weight, sum("weightHP:int") AS sum_weight_hp, sum("weightHR:int") AS sum_weight_hr,
               max("weight:int") AS max_weight
        FROM np_conn""").fetchdf().iloc[0].to_dict()
    g = {k: (int(v) if v == v and v is not None else None) for k, v in g.items()}
    report.add("rows.raw.neuprint_connections", "ingestion", "Rows in the raw neuPrint connection table (segment pairs).",
               INFO, observed=g["n_rows"])
    report.expect_equal("edge_values.no_nulls", "edge_values", "No null IDs/weights in raw connections.", g["n_null"], 0)
    report.expect_equal("edge_values.no_negative", "edge_values", "No negative weights in raw connections.", g["n_negative"], 0)
    report.expect_equal("edge_values.no_zero_weight", "edge_values",
                        "No connection rows with weight 0 (would indicate sub-threshold-only pairs).", g["n_weight_zero"], 0,
                        on_mismatch=WARN)
    report.expect_equal("edge_values.hp_le_weight", "edge_values", "weightHP <= weight for every row.", g["n_hp_gt_weight"], 0)
    report.add("edge_values.weight_hr_equals_weight", "edge_values",
               "weightHR == weight everywhere (expected: synapses were pre-filtered at conf>=0.5, so the "
               "'high-recall' tier adds nothing; BrainIR therefore does not store weightHR).",
               PASS if g["n_hr_ne_weight"] == 0 else WARN, observed=g["n_hr_ne_weight"], expected=0)
    report.expect_equal("consistency.total_weight_equals_psds", "cross_source",
                        "Sum of all connection weights equals neuPrint totalPostCount (every PSD in exactly one pair).",
                        g["sum_weight"], int(meta["totalPostCount"]), on_mismatch=WARN)
    report.add("autapses.raw", "autapses", "Self-connections (pre == post) in the raw table: kept, flagged is_autapse.",
               INFO, observed={"rows": g["n_self"], "synapses": g["w_self"]})

    log.info("connections: referential check of raw endpoints against the neuPrint segment table")
    _reg(con, "np_seg", _ipc_dataset(cfg.raw_file("neuprint_neurons")))
    orphan = con.execute(f"""
        SELECT count(*) FROM np_conn c
        WHERE NOT EXISTS (SELECT 1 FROM np_seg s WHERE s."{NP_ID}" = c."{C_PRE}")
           OR NOT EXISTS (SELECT 1 FROM np_seg s WHERE s."{NP_ID}" = c."{C_POST}")""").fetchone()[0]
    con.unregister("np_seg")
    report.expect_equal("referential.raw_edges_reference_segments", "referential",
                        "Every endpoint of every raw connection exists in the neuPrint segment table.", int(orphan), 0)

    log.info("connections: duplicate-pair check (full table)")
    ndup = con.execute(f"""SELECT count(*) FROM (SELECT "{C_PRE}", "{C_POST}" FROM np_conn
                           GROUP BY 1, 2 HAVING count(*) > 1)""").fetchone()[0]
    report.expect_equal("duplicates.raw_connections.pair", "duplicates",
                        "Each (pre, post) segment pair appears at most once in the raw connection table.", int(ndup), 0)

    log.info("connections: per-neuron totals over all partners")
    out_all = con.execute(f"""SELECT "{C_PRE}" AS id, sum("weight:int") AS w FROM np_conn
                              SEMI JOIN nid ON "{C_PRE}" = nid.id GROUP BY 1""").fetchdf()
    in_all = con.execute(f"""SELECT "{C_POST}" AS id, sum("weight:int") AS w FROM np_conn
                             SEMI JOIN nid ON "{C_POST}" = nid.id GROUP BY 1""").fetchdf()
    totals = pd.DataFrame({"id": neuron_ids}).set_index("id")
    totals["out_all"] = out_all.set_index("id")["w"]
    totals["in_all"] = in_all.set_index("id")["w"]
    totals = totals.fillna(0).astype("int64")

    log.info("connections: extracting neuron->neuron edges")
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE e AS
        SELECT c."{C_PRE}" AS pre_id, c."{C_POST}" AS post_id, c."weight:int" AS w, c."weightHP:int" AS whp,
               c."roiInfo:string" AS ri
        FROM np_conn c SEMI JOIN nid a ON c."{C_PRE}" = a.id SEMI JOIN nid b ON c."{C_POST}" = b.id""")
    n_e = con.execute("SELECT count(*) FROM e").fetchone()[0]
    ndup_e = con.execute("SELECT count(*) - count(DISTINCT (pre_id, post_id)) FROM e").fetchone()[0]
    report.expect_equal("duplicates.connections.pair", "duplicates", "Neuron->neuron edges are unique.", int(ndup_e), 0)
    report.add("rows.connections", "ingestion", "Neuron->neuron edges retained (both endpoints are neurons).", INFO, observed=int(n_e))

    log.info("connections: exploding per-edge roiInfo into primary neuropils")
    con.execute("""
        CREATE OR REPLACE TEMP TABLE cn AS
        WITH x AS (SELECT pre_id, post_id, unnest(map_entries(json_transform(ri, '"MAP(VARCHAR, STRUCT(post BIGINT))"'))) AS kv FROM e)
        SELECT pre_id, post_id, kv.key AS neuropil, coalesce(kv.value.post, 0) AS synapse_count
        FROM x SEMI JOIN prim ON kv.key = prim.roi WHERE coalesce(kv.value.post, 0) > 0""")
    con.execute("""
        CREATE OR REPLACE TEMP TABLE rem AS
        SELECT e.pre_id, e.post_id, e.w - coalesce(s.tot, 0) AS r
        FROM e LEFT JOIN (SELECT pre_id, post_id, sum(synapse_count) AS tot FROM cn GROUP BY 1, 2) s
          ON e.pre_id = s.pre_id AND e.post_id = s.post_id""")
    neg = con.execute("SELECT count(*) FROM rem WHERE r < 0").fetchone()[0]
    report.expect_equal("consistency.connection_neuropils_not_exceeding_weight", "coverage",
                        "Per-edge primary-neuropil counts never exceed the edge weight.", int(neg), 0)
    n_rem = con.execute("SELECT count(*), coalesce(sum(r), 0) FROM rem WHERE r > 0").fetchone()
    report.add("coverage.connection_unassigned", "coverage",
               "Edges with synapses outside primary ROIs (stored as neuropil '<unassigned>').", INFO,
               observed={"edges": int(n_rem[0]), "synapses": int(n_rem[1])})
    cn = _arrow(con.execute(f"""
        SELECT pre_id, post_id, neuropil, synapse_count FROM cn
        UNION ALL SELECT pre_id, post_id, '{UNASSIGNED_NEUROPIL}' AS neuropil, r AS synapse_count FROM rem WHERE r > 0
    """))
    dom = _arrow(con.execute(f"""
        WITH allc AS (SELECT pre_id, post_id, neuropil, synapse_count FROM cn
                      UNION ALL SELECT pre_id, post_id, '{UNASSIGNED_NEUROPIL}', r FROM rem WHERE r > 0),
        ranked AS (SELECT *, row_number() OVER (PARTITION BY pre_id, post_id ORDER BY synapse_count DESC, neuropil ASC) AS rk,
                          count(*) OVER (PARTITION BY pre_id, post_id) AS nn FROM allc)
        SELECT e.pre_id, e.post_id, e.w AS synapse_count, e.whp AS synapse_count_hp, e.pre_id = e.post_id AS is_autapse,
               r.neuropil AS dominant_neuropil, CAST(r.synapse_count AS DOUBLE) / e.w AS dominant_neuropil_fraction,
               coalesce(r.nn, 0) AS n_neuropils
        FROM e LEFT JOIN ranked r ON e.pre_id = r.pre_id AND e.post_id = r.post_id AND r.rk = 1"""))
    con.unregister("np_conn")
    return dom, cn, totals, g


def crosscheck_flat_weights(con, cfg: IngestConfig, report: ValidationReport, g: dict) -> None:
    path = cfg.raw_file("flat_connectome_weights")
    _reg(con, "flat", _ipc_dataset(path))
    fg = con.execute("SELECT count(*), sum(weight), count(*) FILTER (WHERE body_pre = body_post) FROM flat").fetchone()
    report.expect_equal("cross_source.flat_vs_neuprint_totals", "cross_source",
                        "Flat connectome-weights export and neuPrint connection table have the same number of pairs "
                        "and the same total weight.", [int(fg[0]), int(fg[1])], [g["n_rows"], g["sum_weight"]])
    diff = con.execute("""
        SELECT count(*) FILTER (WHERE f.body_pre IS NULL) AS only_neuprint,
               count(*) FILTER (WHERE e.pre_id IS NULL) AS only_flat,
               count(*) FILTER (WHERE f.body_pre IS NOT NULL AND e.pre_id IS NOT NULL AND f.weight <> e.w) AS weight_differs
        FROM e FULL OUTER JOIN (SELECT * FROM flat SEMI JOIN nid a ON body_pre = a.id SEMI JOIN nid b ON body_post = b.id) f
          ON e.pre_id = f.body_pre AND e.post_id = f.body_post""").fetchdf().iloc[0].to_dict()
    diff = {k: int(v) for k, v in diff.items()}
    report.expect_equal("cross_source.flat_vs_neuprint_neuron_edges", "cross_source",
                        "Every neuron->neuron edge has identical weight in the flat export and the neuPrint table.",
                        diff, {"only_neuprint": 0, "only_flat": 0, "weight_differs": 0})
    con.unregister("flat")


def synapse_checks(con, cfg: IngestConfig, report: ValidationReport, neuron_ids: np.ndarray, meta: dict,
                   neurons_np: pd.DataFrame) -> None:
    path = cfg.raw_file("syn_partners")
    if not path.exists():
        report.add("synapses.skipped", "synapses", "syn-partners not acquired; synapse-level checks skipped.", WARN)
        return
    _reg(con, "syn", _ipc_dataset(path))
    log.info("synapses: global pass over syn-partners")
    g = con.execute("""SELECT count(*), min(conf_pre), min(conf_post), count(*) FILTER (WHERE body_pre = 0 OR body_post = 0)
                       FROM syn""").fetchone()
    report.expect_equal("synapses.total_pairs", "synapses",
                        "Synaptic partner rows == neuPrint totalPostCount (one presynaptic partner per PSD).",
                        int(g[0]), int(meta["totalPostCount"]), on_mismatch=WARN)
    report.expect_true("synapses.min_confidence", "synapses", "All partner rows have conf_pre >= 0.5 and conf_post >= 0.5.",
                       bool(g[1] >= 0.5 - 1e-6 and g[2] >= 0.5 - 1e-6), observed=[float(g[1]), float(g[2])])
    report.add("synapses.body_zero", "synapses", "Partner rows touching body 0 (unsegmented).", INFO, observed=int(g[3]))
    rng = np.random.default_rng(cfg.seed)
    k = min(cfg.synapse_sample_neurons, len(neuron_ids))
    sample = np.sort(rng.choice(neuron_ids, size=k, replace=False))
    _reg(con, "samp", pa.table({"id": pa.array(sample, pa.int64())}))
    log.info("synapses: recomputing connectivity for %d random neurons", k)
    con.execute("""CREATE OR REPLACE TEMP TABLE ss AS
                   SELECT * FROM syn WHERE body_pre IN (SELECT id FROM samp) OR body_post IN (SELECT id FROM samp)""")
    # outgoing edges of sampled neurons to neurons: weight, weightHP, per-neuropil.
    # HP semantics reproduce neuPrint: the float32 confidence is compared in float64, so a PSD stored as
    # float32(0.7) = 0.699999988 is NOT high-precision (DuckDB's default FLOAT comparison would count it).
    hp = float(meta.get("postHPThreshold", 0.7))
    re = con.execute(f"""
        WITH r AS (SELECT body_pre AS pre_id, body_post AS post_id, count(*) AS w,
                          count(*) FILTER (WHERE CAST(conf_post AS DOUBLE) >= CAST({hp!r} AS DOUBLE)) AS whp
                   FROM ss WHERE body_pre IN (SELECT id FROM samp) AND body_post IN (SELECT id FROM nid) GROUP BY 1, 2)
        SELECT count(*) FILTER (WHERE e.pre_id IS NULL) AS only_synapses,
               count(*) FILTER (WHERE r.pre_id IS NULL) AS only_edges,
               count(*) FILTER (WHERE r.w <> e.w) AS weight_differs,
               count(*) FILTER (WHERE r.whp <> e.whp) AS weight_hp_differs,
               count(*) AS n_compared
        FROM r FULL OUTER JOIN (SELECT * FROM e WHERE pre_id IN (SELECT id FROM samp)) e
          ON r.pre_id = e.pre_id AND r.post_id = e.post_id""").fetchdf().iloc[0].to_dict()
    re = {kk: int(v) for kk, v in re.items()}
    n_cmp = re.pop("n_compared")
    report.expect_equal("synapses.recomputed_edge_weights", "synapses",
                        f"Edge weights (and HP weights at conf_post>=0.7) recomputed from individual synapses match the "
                        f"connection table for all outgoing edges of {k} random neurons ({n_cmp} edges).",
                        re, {"only_synapses": 0, "only_edges": 0, "weight_differs": 0, "weight_hp_differs": 0},
                        sample_seed=cfg.seed)
    rn = con.execute(f"""
        WITH r AS (SELECT s.body_pre AS pre_id, s.body_post AS post_id, coalesce(p.roi, '{UNASSIGNED_NEUROPIL}') AS neuropil,
                          count(*) AS c
                   FROM ss s LEFT JOIN prim p ON CAST(s.primary_post AS VARCHAR) = p.roi
                   WHERE s.body_pre IN (SELECT id FROM samp) AND s.body_post IN (SELECT id FROM nid) GROUP BY 1, 2, 3),
             c AS (SELECT * FROM cn_all WHERE pre_id IN (SELECT id FROM samp))
        SELECT count(*) FILTER (WHERE c.pre_id IS NULL) AS only_synapses,
               count(*) FILTER (WHERE r.pre_id IS NULL) AS only_table,
               count(*) FILTER (WHERE r.c <> c.synapse_count) AS count_differs
        FROM r FULL OUTER JOIN c ON r.pre_id = c.pre_id AND r.post_id = c.post_id AND r.neuropil = c.neuropil
    """).fetchdf().iloc[0].to_dict()
    rn = {kk: int(v) for kk, v in rn.items()}
    report.expect_equal("synapses.recomputed_edge_neuropils", "synapses",
                        "Per-edge neuropil counts recomputed from synapse primary_post ROIs match connection_neuropils "
                        "(sampled neurons' outgoing edges).", rn, {"only_synapses": 0, "only_table": 0, "count_differs": 0},
                        on_mismatch=WARN)
    per = con.execute("""
        SELECT samp.id, coalesce(d.c, 0) AS downstream, coalesce(u.c, 0) AS upstream, coalesce(t.c, 0) AS tbars_with_partner
        FROM samp
        LEFT JOIN (SELECT body_pre AS id, count(*) AS c FROM ss GROUP BY 1) d ON d.id = samp.id
        LEFT JOIN (SELECT body_post AS id, count(*) AS c FROM ss GROUP BY 1) u ON u.id = samp.id
        LEFT JOIN (SELECT body_pre AS id, count(DISTINCT (x_pre, y_pre, z_pre)) AS c FROM ss GROUP BY 1) t ON t.id = samp.id
        """).fetchdf().set_index("id")
    npv = neurons_np.set_index("id").reindex(per.index)[["downstream", "upstream", "pre"]].fillna(0).astype("int64")
    mism = {
        "downstream": int((per["downstream"] != npv["downstream"]).sum()),
        "upstream": int((per["upstream"] != npv["upstream"]).sum()),
        "pre_tbars_gt_neuprint_pre": int((per["tbars_with_partner"] > npv["pre"]).sum()),
    }
    report.expect_equal("synapses.recomputed_neuron_totals", "synapses",
                        "For sampled neurons, synapse-level counts reproduce neuPrint downstream/upstream, and T-bars with "
                        "partners never exceed neuPrint 'pre'.", mism,
                        {"downstream": 0, "upstream": 0, "pre_tbars_gt_neuprint_pre": 0})
    con.unregister("syn")


def graph_statistics(edges: pa.Table, ids: np.ndarray, report: ValidationReport) -> dict:
    pre = edges.column("pre_id").to_numpy()
    post = edges.column("post_id").to_numpy()
    w = edges.column("synapse_count").to_numpy().astype(np.int64)
    n = len(ids)
    ip = np.searchsorted(ids, pre)
    iq = np.searchsorted(ids, post)
    A = sp.csr_matrix((w, (ip, iq)), shape=(n, n))
    outdeg = np.diff(A.indptr)
    indeg = np.diff(A.tocsc().indptr)
    B = (A > 0).astype(np.int8)
    recip = B.multiply(B.T).sum()
    self_loops = int((pre == post).sum())
    ncc_w, lab_w = connected_components(B, directed=True, connection="weak")
    ncc_s, lab_s = connected_components(B, directed=True, connection="strong")
    isolated = int(((outdeg == 0) & (indeg == 0)).sum())
    stats = {
        "n_neurons": int(n), "n_edges": int(len(w)), "total_synapses": int(w.sum()),
        "density": float(len(w) / (n * n)) if n else 0.0,
        "weight": {"min": int(w.min()), "median": float(np.median(w)), "mean": float(w.mean()), "p99": float(np.percentile(w, 99)),
                   "max": int(w.max()), "n_weight_1": int((w == 1).sum()), "n_weight_ge_5": int((w >= 5).sum())},
        "out_degree": {"mean": float(outdeg.mean()), "median": float(np.median(outdeg)), "max": int(outdeg.max())},
        "in_degree": {"mean": float(indeg.mean()), "median": float(np.median(indeg)), "max": int(indeg.max())},
        "reciprocity_edges": float((recip - self_loops) / max(1, (len(w) - self_loops))),
        "autapses": {"edges": self_loops, "synapses": int(w[pre == post].sum())},
        "weakly_connected_components": int(ncc_w),
        "largest_wcc": int(np.bincount(lab_w).max()),
        "strongly_connected_components": int(ncc_s),
        "largest_scc": int(np.bincount(lab_s).max()),
        "isolated_neurons": isolated,
    }
    report.add("graph.basic_statistics", "graph_stats", "Basic statistics of the neuron->neuron graph.", INFO, observed=stats)
    return stats


def directionality_checks(neurons: pd.DataFrame, nn: pd.DataFrame, regions: dict[str, str], report: ValidationReport) -> None:
    # 1) exact: summing edge weights over all partners reproduces neuPrint's per-neuron downstream/upstream
    has = neurons["n_downstream"].notna()
    d_out = int((neurons.loc[has, "out_all"] != neurons.loc[has, "n_downstream"]).sum())
    d_in = int((neurons.loc[has, "in_all"] != neurons.loc[has, "n_upstream"]).sum())
    report.expect_equal("directionality.edge_sums_match_neuron_totals", "directionality",
                        "For every neuron, sum of outgoing edge weights (all partners) == neuPrint 'downstream' and incoming "
                        "== 'upstream'. A pre/post swap anywhere would break this.", [d_out, d_in], [0, 0])
    # 2) biological sanity: descending neurons output (T-bars) more in VNC than they receive there
    nn2 = nn.assign(region=nn["neuropil"].map(regions).fillna("<unassigned>"))
    by = nn2.groupby(["source_id", "region"])[["n_pre", "n_post"]].sum().unstack(fill_value=0)
    frac_pre_vnc = by["n_pre"].get("VNC", 0) / by["n_pre"].sum(axis=1).replace(0, np.nan)
    frac_post_vnc = by["n_post"].get("VNC", 0) / by["n_post"].sum(axis=1).replace(0, np.nan)
    res = {}
    for sc, expect_out_in_vnc in (("descending_neuron", True), ("ascending_neuron", False)):
        ids_sc = neurons.loc[neurons["super_class"] == sc, "source_id"]
        a = frac_pre_vnc.reindex(ids_sc).dropna()
        b = frac_post_vnc.reindex(ids_sc).dropna()
        common = a.index.intersection(b.index)
        ok_frac = float(((a[common] > b[common]) == expect_out_in_vnc).mean()) if len(common) else None
        res[sc] = {"n": int(len(common)), "median_frac_pre_in_vnc": float(a.median()) if len(a) else None,
                   "median_frac_post_in_vnc": float(b.median()) if len(b) else None,
                   "fraction_consistent": ok_frac}
    ok = all(v["fraction_consistent"] is not None and v["fraction_consistent"] > 0.8 for v in res.values())
    report.add("directionality.dn_an_polarity", "directionality",
               "Biological polarity sanity check: descending neurons have relatively more output (T-bars) than input in "
               "the VNC; ascending neurons the reverse (fraction of neurons consistent, expected > 0.8).",
               PASS if ok else WARN, observed=res)
    # 3) sensory neurons are output-dominated, motor neurons input-dominated
    ratio = {}
    for sc in ("vnc_sensory", "cb_sensory", "ol_sensory", "vnc_motor", "cb_motor"):
        sub = neurons[neurons["super_class"] == sc]
        if len(sub) == 0:
            continue
        r = (sub["n_downstream"] / (sub["n_downstream"] + sub["n_upstream"]).replace(0, np.nan)).dropna()
        ratio[sc] = {"n": int(len(r)), "median_output_fraction": float(r.median())}
    ok2 = all((v["median_output_fraction"] > 0.5) == (k.endswith("sensory")) for k, v in ratio.items())
    report.add("directionality.sensory_motor_polarity", "directionality",
               "Sensory neurons are output-dominated (median output fraction > 0.5) and motor neurons input-dominated.",
               PASS if ok2 else WARN, observed=ratio)


def assemble_neurons(cfg: IngestConfig, ann: pd.DataFrame, nt: pd.DataFrame, npn: pd.DataFrame, totals: pd.DataFrame,
                     edges: pa.Table) -> pd.DataFrame:
    a = ann[ann["superclass"].notna()].copy()
    a = a.merge(nt, left_on="bodyId", right_on="body", how="left")
    a = a.merge(npn[["id", "pre", "post", "downstream", "upstream", "size", "neuron_label"]], left_on="bodyId",
                right_on="id", how="left")
    ds, ver = cfg.source.dataset, cfg.source.version
    soma = a["somaLocation"]

    def sxyz(i):
        return pd.array([(x[i] if x is not None and len(x) == 3 else None) for x in soma], dtype="Int64")

    soma_side = a["somaSide"].map(normalize_side)
    root_side = a["rootSide"].map(normalize_side)
    side = soma_side.where(soma_side.notna(), root_side)
    side_basis = pd.Series(np.where(soma_side.notna(), "soma", np.where(root_side.notna(), "root", None)), index=a.index)
    # derived totals over neuron partners
    pre = edges.column("pre_id").to_numpy()
    post = edges.column("post_id").to_numpy()
    w = edges.column("synapse_count").to_numpy().astype(np.int64)
    out_n = pd.Series(w).groupby(pre).sum()
    in_n = pd.Series(w).groupby(post).sum()
    ids = a["bodyId"].astype("int64")
    df = pd.DataFrame({
        "neuron_uid": [f"{ds}:{ver}:{int(i)}" for i in ids],
        "dataset": ds, "dataset_version": ver, "source_id": ids,
        "cell_type": a["type"], "instance": a["instance"], "super_class": a["superclass"],
        "cell_class": a["class"], "sub_class": a["subclass"],
        "hemilineage_ito_lee": a["itoleeHl"], "hemilineage_truman": a["trumanHl"],
        "soma_side": soma_side, "root_side": root_side, "side": side, "side_basis": side_basis,
        "soma_neuromere": a["somaNeuromere"], "soma_x": sxyz(0), "soma_y": sxyz(1), "soma_z": sxyz(2),
        "animal_sex": ANIMAL_SEX, "status": a["status"], "status_label": a["statusLabel"],
        "is_traced": a["status"].eq("Traced").fillna(False).astype(bool),
        "neuprint_neuron_label": a["neuron_label"].fillna(False).astype(bool),
        "n_pre": a["pre"].astype("Int64"), "n_post": a["post"].astype("Int64"),
        "n_downstream": a["downstream"].astype("Int64"), "n_upstream": a["upstream"].astype("Int64"),
        "n_downstream_to_neurons": ids.map(out_n).fillna(0).astype("int64").to_numpy(),
        "n_upstream_from_neurons": ids.map(in_n).fillna(0).astype("int64").to_numpy(),
        "size_voxels": _float_to_int64(a["size"], "size") if a["size"].dtype.kind == "f" else a["size"].astype("Int64"),
        "nt_consensus": a["consensus_nt"], "nt_body_prediction": a["predicted_nt"],
        "nt_body_confidence": a["predicted_nt_confidence"].astype("float64"),
        "nt_body_n_tbars": a["total_nt_predictions"].astype("Int32"),
        "nt_type_prediction": a["celltype_predicted_nt"],
        "nt_type_confidence": a["celltype_predicted_nt_confidence"].astype("float64"),
        "nt_type_n_tbars": a["celltype_total_nt_predictions"].astype("Int32"),
        "nt_literature_label": a["ground_truth"],
        "group_id": a["group"], "synonyms": a["synonyms"], "flywire_type": a["flywireType"],
        "hemibrain_type": a["hemibrainType"], "manc_type": a["mancType"], "manc_body_id": a["mancBodyid"],
        "dimorphism": a["dimorphism"], "fru_dsx": a["fruDsx"],
    })
    t = totals.reindex(ids.to_numpy())
    df["out_all"] = t["out_all"].to_numpy()
    df["in_all"] = t["in_all"].to_numpy()
    return df


def coverage(neurons: pd.DataFrame, report: ValidationReport) -> dict:
    fields = ["cell_type", "instance", "cell_class", "sub_class", "hemilineage_ito_lee", "hemilineage_truman", "side",
              "soma_neuromere", "soma_x", "nt_consensus", "nt_literature_label", "group_id", "flywire_type",
              "manc_type", "hemibrain_type", "synonyms"]
    cov = {f: round(float(neurons[f].notna().mean()), 4) for f in fields}
    cov["nt_consensus_not_unclear"] = round(float((neurons["nt_consensus"].notna() & (neurons["nt_consensus"] != "unclear")).mean()), 4)
    cov["is_traced"] = round(float(neurons["is_traced"].mean()), 4)
    by_sc = (neurons.assign(typed=neurons["cell_type"].notna(),
                            nt_known=neurons["nt_consensus"].notna() & (neurons["nt_consensus"] != "unclear"))
             .groupby("super_class")[["typed", "nt_known"]].mean().round(4))
    by_sc["n"] = neurons.groupby("super_class").size()
    report.add("coverage.annotation_fields", "coverage", "Fraction of neurons with each annotation populated.", INFO, observed=cov)
    report.add("coverage.by_superclass", "coverage", "Per-superclass neuron count, fraction typed, fraction with a known "
               "(non-unclear) consensus NT.", INFO, observed=by_sc.reset_index().to_dict(orient="records"))
    nt_counts = neurons["nt_consensus"].value_counts(dropna=False).to_dict()
    report.add("coverage.nt_consensus_distribution", "coverage", "Distribution of consensus NT over neurons.", INFO,
               observed={str(k): int(v) for k, v in nt_counts.items()})
    return {"fields": cov, "by_superclass": by_sc.reset_index().to_dict(orient="records")}


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------
def build(cfg: IngestConfig) -> dict:
    t_start = time.time()
    timings: dict[str, float] = {}
    out = cfg.out()
    out.mkdir(parents=True, exist_ok=True)
    report = ValidationReport(title=f"BrainIR ingestion validation — {cfg.source.dataset}:{cfg.source.version}")
    needed = ["neuprint_meta_json", "body_annotations", "body_neurotransmitters", "neuprint_neurons",
              "neuprint_connections", "flat_connectome_weights"]
    if cfg.synapse_checks and cfg.raw_file("syn_partners").exists():
        needed.append("syn_partners")

    def abort_if_critical(stage: str) -> None:
        bad = [c.check_id for c in report.failures if c.check_id in CRITICAL_CHECKS]
        if bad:
            report.context = {"aborted_at": stage, "critical_failures": bad}
            report.write(out / "validation_report.json", out / "validation_report.md")
            raise IngestAborted(f"critical validation failures at {stage}: {bad}", report)

    def lap(name, t0):
        timings[name] = round(time.time() - t0, 2)
        log.info("step %-28s %8.1fs", name, timings[name])

    t0 = time.time(); acq = check_acquisition(cfg, report, needed); lap("acquisition_check", t0)
    t0 = time.time(); meta = load_meta(cfg, report); neuropils, primary = build_neuropils(meta, report); lap("meta_neuropils", t0)
    t0 = time.time(); ann, ann_src = load_annotations(cfg, report); lap("annotations", t0)
    t0 = time.time(); nt = load_nt(cfg, report); lap("neurotransmitters", t0)
    abort_if_critical("inputs")

    neuron_ids = np.sort(ann.loc[ann["superclass"].notna(), "bodyId"].astype("int64").to_numpy())
    report.add("rows.neurons", "ingestion", "Neurons = bodies with a superclass (source definition).", INFO, observed=int(len(neuron_ids)))
    report.expect_equal("ids.neurons.unique", "uniqueness", "Neuron IDs unique.", int(len(neuron_ids) - len(np.unique(neuron_ids))), 0)
    nt_missing = int((~np.isin(neuron_ids, nt["body"].to_numpy())).sum())
    report.add("coverage.neurons_without_nt_row", "coverage", "Neurons absent from the NT table (no T-bars => no prediction).",
               INFO, observed=nt_missing)

    con = _duck(cfg)
    t0 = time.time(); npn, np_stats = scan_neuprint_neurons(con, cfg, neuron_ids, report); lap("neuprint_neurons_scan", t0)
    missing_np = int((~np.isin(neuron_ids, npn["id"].to_numpy())).sum())
    report.add("referential.neurons_in_neuprint", "referential",
               "Neurons missing from the neuPrint segment table (non-synaptic bodies are not exported by neuPrint).",
               PASS if missing_np == 0 else WARN, observed=missing_np)
    t0 = time.time(); neuron_level_crosschecks(ann, nt, npn, report); lap("neuron_crosschecks", t0)
    t0 = time.time(); nn = parse_neuron_roiinfo(con, npn, primary, report); lap("neuron_neuropils", t0)
    t0 = time.time(); edges, cn, totals, g = scan_connections(con, cfg, neuron_ids, primary, report, meta); lap("connections", t0)
    _reg(con, "cn_all", cn)
    report.expect_equal("consistency.segment_totals_equal_edge_totals", "directionality",
                        "Sum over all segments of neuPrint 'downstream' and of 'upstream' each equal the total weight of the "
                        "connection table (conservation: every counted pair has an existing pre and post segment).",
                        [int(np_stats["sum_downstream"]), int(np_stats["sum_upstream"])], [g["sum_weight"], g["sum_weight"]])
    t0 = time.time(); crosscheck_flat_weights(con, cfg, report, g); lap("flat_crosscheck", t0)
    if cfg.synapse_checks:
        t0 = time.time(); synapse_checks(con, cfg, report, neuron_ids, meta, npn); lap("synapse_checks", t0)

    # referential integrity of the retained graph
    ep = edges.column("pre_id").to_numpy(); eq = edges.column("post_id").to_numpy()
    report.expect_equal("referential.edges_reference_neurons", "referential", "Every edge endpoint is a neuron.",
                        int((~np.isin(ep, neuron_ids)).sum() + (~np.isin(eq, neuron_ids)).sum()), 0)
    w = edges.column("synapse_count").to_numpy()
    report.expect_equal("edge_values.connections_positive", "edge_values", "All retained edges have synapse_count >= 1.",
                        int((w < 1).sum()), 0)
    hp = edges.column("synapse_count_hp").to_numpy()
    report.expect_equal("edge_values.connections_hp_le_count", "edge_values", "synapse_count_hp <= synapse_count.",
                        int((hp > w).sum()), 0)

    t0 = time.time()
    neurons = assemble_neurons(cfg, ann, nt, npn, totals, edges)
    regions = dict(zip(neuropils.column("name").to_pylist(), neuropils.column("top_level_region").to_pylist()))
    directionality_checks(neurons, nn.to_pandas(), regions, report)
    stats = graph_statistics(edges, neuron_ids, report)
    cov = coverage(neurons, report)
    lap("assemble_validate", t0)

    # --- write outputs (deterministic) ---
    t0 = time.time()
    common_md = {"brainir_dataset": cfg.source.dataset, "brainir_dataset_version": cfg.source.version,
                 "brainir_pipeline": f"{PIPELINE_ID}@{PIPELINE_VERSION}"}
    outputs = {}
    ncols = T.NEURONS.column_names
    outputs["neurons"] = write_canonical(pa.Table.from_pandas(neurons[ncols], preserve_index=False), T.NEURONS,
                                         out / "neurons.parquet", common_md)
    outputs["connections"] = write_canonical(edges, T.CONNECTIONS, out / "connections.parquet", common_md)
    outputs["connection_neuropils"] = write_canonical(cn, T.CONNECTION_NEUROPILS, out / "connection_neuropils.parquet", common_md)
    outputs["neuron_neuropils"] = write_canonical(nn, T.NEURON_NEUROPILS, out / "neuron_neuropils.parquet", common_md)
    outputs["neuropils"] = write_canonical(neuropils, T.NEUROPILS, out / "neuropils.parquet", common_md)
    ann_sorted = ann_src.take(pc.sort_indices(ann_src, [("bodyId", "ascending")]))
    outputs[T.NEURON_ANNOTATIONS_SOURCE] = write_parquet(
        ann_sorted.replace_schema_metadata({"brainir_table": T.NEURON_ANNOTATIONS_SOURCE, **common_md}),
        out / f"{T.NEURON_ANNOTATIONS_SOURCE}.parquet")
    lap("write_outputs", t0)

    # post-write validation: re-read + schema conformance
    import pyarrow.parquet as pq
    for name, spec in T.CANONICAL_TABLES.items():
        p = out / f"{name}.parquet"
        if p.exists():
            sch = pq.read_schema(p)
            report.expect_true(f"types.schema_conformance.{name}", "types",
                               f"{name}.parquet schema equals the canonical schema (names, types, nullability).",
                               sch.remove_metadata().equals(spec.schema.remove_metadata(), check_metadata=False),
                               observed=str(sch.names[:5]) + "...")

    summary = report.summary()
    build_info = {
        "pipeline": PIPELINE_ID, "pipeline_version": PIPELINE_VERSION, "brainir_version": __version__,
        "schema_version": T.SCHEMA_VERSION, "dataset": cfg.source.dataset, "version": cfg.source.version,
        "config": {"synapse_checks": cfg.synapse_checks, "synapse_sample_neurons": cfg.synapse_sample_neurons,
                   "seed": cfg.seed},
        "git": _git_state(),
        "environment": {"python": sys.version.split()[0], "platform": platform.platform(),
                        "pyarrow": pa.__version__, "pandas": pd.__version__, "duckdb": duckdb.__version__,
                        "numpy": np.__version__},
        "timings_s": timings, "total_s": round(time.time() - t_start, 1),
        "inputs": {k: {"sha256": acq[k]["local_digests"]["sha256"], "generation": acq[k]["remote_metadata"]["generation"]}
                   for k in needed if k in acq},
        "outputs": outputs, "graph_statistics": stats, "coverage": cov, "validation_summary": summary,
        "neuprint_meta": {k: meta.get(k) for k in ("uuid", "latestMutationId", "lastDatabaseEdit", "totalPreCount",
                                                   "totalPostCount", "postHighAccuracyThreshold", "postHPThreshold")},
        "raw_connection_table": g, "neuprint_segment_stats": {k: int(v) for k, v in np_stats.items()},
    }
    report.context = {"dataset": cfg.source.dataset, "version": cfg.source.version, "pipeline": f"{PIPELINE_ID}@{PIPELINE_VERSION}",
                      "git": build_info["git"]}
    report.write(out / "validation_report.json", out / "validation_report.md")
    (out / "build_info.json").write_text(json.dumps(build_info, indent=2, default=str) + "\n", encoding="utf-8",
                                         newline="\n")
    con.close()
    import shutil
    shutil.rmtree(paths.cache_dir() / "duckdb_tmp" / f"pid{os.getpid()}", ignore_errors=True)
    log.info("validation summary: %s", summary)
    return {"report": report, "build_info": build_info, "out_dir": out}
