"""MANC (Male Adult Nerve Cord) raw official files -> BrainIR canonical tables.

Two adapters share this module:

``manc:v1.0`` (neuPrint bulk export, 2023-06)
    * ``Neuprint_Meta_manc_v1.ftr``                ROI hierarchy (flat), primary/nerve ROIs, thresholds, totals
    * ``manc-v1.0-neuron-properties.feather``      per-body annotations + body-level NT probabilities (all :Neuron bodies)
    * ``Neuprint_Neurons_manc_v1.ftr``             every synaptic segment as loaded into neuPrint (stats, roiInfo, :LABEL)
    * ``Neuprint_Neuron_Connections_manc_v1.ftr``  :ConnectsTo edges (weight, weightHP, weightHR, roiInfo)
    * ``manc-traced-adjacencies-v1.0/*.csv``       independent neuprint-python export (cross-check)
    * ``manc-synapse-partners-...-minconf-0.0.feather.bz2``  optional synapse-level checks + threshold inference

    Neuron definition: bodies carrying the neuPrint status ``Traced`` in the neuPrint neuron table (the database the
    MANC papers and neuprint-python queries operate on). The per-body property export made a week earlier labels 314
    of them ``RT Orphan``; the discrepancy is recorded, not hidden.

``manc:v1.2.1`` / ``manc:v1.2.3`` (rebuilt from public v1.2 files; no neuPrint bulk export exists)
    * ``manc-v1.2-synapse-partners-minconf-0.0.feather``  every T-bar->PSD pair of the v1.2 segmentation with confidences
    * a neuroglancer ``segment_properties`` annotation snapshot (v1.2.1: 2024-09-27; v1.2.3: 2025-10-26)
    * the ``manc:v1.0`` Meta (ROI catalogue; the ROI volumes are unchanged) and per-body NT probabilities (carried over
      to bodies of the same ID; the v1.2 segmentation is a light edit of v1.0)

    Neuron definition: bodies listed in the annotation snapshot. Connections are recounted from the partner table with
    an explicit confidence rule (``CountRule``) whose values were inferred on v1.0, where both raw synapses and the
    neuPrint weights are available (validation check ``synapses.inferred_count_rule``).

Autapses are retained and flagged. Edges are neuron->neuron; per-neuron totals over ALL partners are kept alongside.
"""

from __future__ import annotations

import bz2
import hashlib
import json
import logging
import re
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.feather as feather

from .. import paths
from ..schema.vocab import (
    NT_VALUES,
    STATUS_LABEL_ORDER,
    UNASSIGNED_NEUROPIL,
    normalize_class_label,
    normalize_side,
)
from ..sources.registry import MANC_V1_0, MANC_V1_2
from ..validation import INFO, PASS, WARN, ValidationReport
from .common import (
    NP_ID,
    BuildRun,
    IngestConfig,
    _arrow,
    _duck,
    _float_to_int64,
    _ipc_dataset,
    _reg,
    build_neuropils,
    check_acquisition,
    coverage,
    directionality_checks,
    finalize,
    graph_statistics,
    parse_neuron_roiinfo,
    retained_graph_checks,
    scan_connections,
    write_outputs,
)

log = logging.getLogger(__name__)

PIPELINE_ID = "brainir.ingest.manc"
PIPELINE_VERSION = "1.0.0"
ANIMAL_SEX = "male"

ROI_PARENT_ALIASES = {"ventral nerve core": "ventral nerve cord"}  # typo in the v1.0 Meta roiInfo
NULL_STRINGS = ("None", "TBD", "NA", "~")  # literal placeholders used by the source for 'no value'
FLOAT_INT_COLS = ("group", "serial", "subcluster")

CRITICAL_CHECKS = ("duplicates.properties.bodyId", "ids.properties.non_null_positive", "types.properties_float_ids_integral",
                   "provenance.meta_dataset_tag", "provenance.acquisition_dataset", "provenance.raw_inputs_verified",
                   "provenance.acquisition_dataset.v1_0", "provenance.raw_inputs_verified.v1_0",
                   "duplicates.snapshot.bodyId", "ids.snapshot.non_null_positive")

ANNOTATION_SNAPSHOTS = {
    "v1.2.1": {"files": ("segprops_v1_2_1_info",), "date": "2024-09-27", "neuprint_dataset": "manc:v1.2.1",
               "description": "neuroglancer segment_properties_v1.2.1 (type, PreSyn, PostSyn, tagged properties)"},
    "v1.2.3": {"files": ("segprops_v1_2_3_combined", "segprops_v1_2_3_instance", "segprops_v1_2_3_type"),
               "date": "2025-10-26", "neuprint_dataset": "manc:v1.2.3",
               "description": "neuroglancer segment_properties_v1.2.3/combined_properties (+ instance_property)"},
}


@dataclass(frozen=True)
class CountRule:
    """Confidence rule that turns raw T-bar->PSD pairs into neuPrint-equivalent counts.

    Comparisons are made in float64 on the float32 stored confidences (neuPrint semantics: float32(0.7)=0.69999999
    is NOT >= 0.7)."""
    conf_pre_min: float
    conf_post_min: float
    hp_conf_pre_min: float
    hp_conf_post_min: float
    basis: str

    def sql(self, pre="conf_pre", post="conf_post") -> str:
        return (f"CAST({pre} AS DOUBLE) >= CAST({self.conf_pre_min!r} AS DOUBLE) AND "
                f"CAST({post} AS DOUBLE) >= CAST({self.conf_post_min!r} AS DOUBLE)")

    def sql_hp(self, pre="conf_pre", post="conf_post") -> str:
        return (f"CAST({pre} AS DOUBLE) >= CAST({self.hp_conf_pre_min!r} AS DOUBLE) AND "
                f"CAST({post} AS DOUBLE) >= CAST({self.hp_conf_post_min!r} AS DOUBLE)")


# Inferred on manc:v1.0 (validation check synapses.inferred_count_rule, 2026-09-22): neuPrint weight = pairs with
# conf_post >= 0.4 (the Meta's postHighAccuracyThreshold; every T-bar in the table already has conf_pre >= 0.75),
# weightHP = pairs with conf_post >= 0.7, weightHR = every pair of the minconf-0.0 table. Applied unchanged to the v1.2
# partner table (same pipeline); the benchmark reproduction step checks it against the published v1.2.1 counts.
# Overridable via IngestConfig.options["count_rule"].
DEFAULT_COUNT_RULE = CountRule(conf_pre_min=0.0, conf_post_min=0.4, hp_conf_pre_min=0.0, hp_conf_post_min=0.7,
                               basis="inferred on manc:v1.0 (neuPrint weight/weightHP vs raw partner counts)")

# candidate rules tested during inference on v1.0 (weight and weightHR share the grid; HP uses its own)
_GRID = (0.0, 0.3, 0.4, 0.5, 0.6, 0.7)


def build(cfg: IngestConfig) -> dict:
    if cfg.source.dataset != "manc":
        raise ValueError(f"brainir.ingest.manc cannot build {cfg.source.dataset}:{cfg.source.version}")
    if cfg.source.version == "v1.0":
        return build_v10(cfg)
    if cfg.source.version == "v1.2":
        if cfg.build_version not in ANNOTATION_SNAPSHOTS:
            raise ValueError(f"manc v1.2 builds need build_version in {sorted(ANNOTATION_SNAPSHOTS)}, got {cfg.build_version!r}")
        return build_v12(cfg)
    raise ValueError(f"no MANC adapter for source version {cfg.source.version!r}")


# ---------------------------------------------------------------------------
# shared loaders
# ---------------------------------------------------------------------------
def _split_list(v) -> list[str]:
    if v is None or (isinstance(v, float) and v != v):
        return []
    return [x for x in str(v).split(";") if x]


def _json_or(v, default):
    if v is None or (isinstance(v, float) and v != v):
        return default
    return json.loads(v)


def load_meta_v10(path: Path, report: ValidationReport, expect_version: str = "v1.0") -> dict:
    """neuPrint :Meta feather (one row, neo4j-typed column names) -> the dict shape used by build_neuropils."""
    row = feather.read_table(path).to_pylist()[0]
    meta = {
        "dataset": row.get("dataset:string"), "tag": row.get("tag:string"), "uuid": row.get("uuid:string"),
        "latestMutationId": row.get("latestMutationId:int"), "lastDatabaseEdit": row.get("lastDatabaseEdit:string"),
        "totalPreCount": int(row["totalPreCount:int"]), "totalPostCount": int(row["totalPostCount:int"]),
        "postHighAccuracyThreshold": row.get("postHighAccuracyThreshold:float"),
        "preHPThreshold": row.get("preHPThreshold:float"), "postHPThreshold": row.get("postHPThreshold:float"),
        "primaryRois": _split_list(row.get("primaryRois:string[]")),
        "superLevelRois": _split_list(row.get("superLevelRois:string[]")),
        "roiHierarchy": _json_or(row.get("roiHierarchy:string"), {}),
        "roiInfo": _json_or(row.get("roiInfo:string"), {}),
        "nerveRois": _json_or(row.get("nerveRois:string"), []),
        "neuropilRois": _json_or(row.get("neuropilRois:string"), []),
        "voxelSize": _split_list(row.get("voxelSize:float[]")),
    }
    report.expect_equal("provenance.meta_dataset_tag", "provenance",
                        "neuPrint :Meta dataset/tag equal the expected dataset/version (no cross-version mixing).",
                        [meta["dataset"], meta["tag"]], ["manc", expect_version])
    report.add("provenance.meta_identity", "provenance", "neuPrint snapshot identity (DVID uuid, mutation id, last edit).",
               INFO, observed={k: meta.get(k) for k in ("uuid", "latestMutationId", "lastDatabaseEdit")})
    report.add("provenance.synapse_thresholds", "provenance",
               "Synapse confidence thresholds declared by the neuPrint Meta (informational; the effective rule is inferred "
               "from the data, see synapses.inferred_count_rule).", INFO,
               observed={k: meta.get(k) for k in ("postHighAccuracyThreshold", "preHPThreshold", "postHPThreshold")})
    return meta


def _nullify_placeholders(df: pd.DataFrame, cols: list[str], report: ValidationReport, check_id: str) -> None:
    """Replace the source's literal 'None'/'TBD'/'~' placeholders by nulls (counts recorded)."""
    counts = {}
    for c in cols:
        if c in df.columns and df[c].dtype == object or (c in df.columns and str(df[c].dtype) in ("string", "str")):
            m = df[c].isin(NULL_STRINGS)
            if m.any():
                counts[c] = int(m.sum())
                df.loc[m, c] = None
    report.add(check_id, "types", f"String placeholders {NULL_STRINGS} converted to null (per column).", INFO, observed=counts)


def load_properties_v10(cfg: IngestConfig, report: ValidationReport, raw_dir: Path | None = None) -> tuple[pd.DataFrame, pa.Table]:
    path = (raw_dir or cfg.raw()) / MANC_V1_0.local_relpath(MANC_V1_0.file("neuron_properties"))
    raw = feather.read_table(path)
    df = raw.drop([c for c in ("roiInfo",) if c in raw.column_names]).to_pandas()
    report.add("rows.raw.neuron_properties", "ingestion", "Rows (bodies) in the v1.0 per-body property export.", INFO, observed=len(df))
    ids = df["bodyId"]
    report.expect_true("ids.properties.non_null_positive", "ids", "bodyId non-null and positive.",
                       bool(ids.notna().all() and (ids > 0).all()))
    report.expect_equal("duplicates.properties.bodyId", "duplicates", "No duplicate bodyId rows in the property export.",
                        int(ids.duplicated().sum()), 0)
    lossy = {}
    for c in FLOAT_INT_COLS:
        if c in df.columns:
            try:
                df[c] = _float_to_int64(df[c], c)
            except ValueError as exc:
                lossy[c] = str(exc)
    report.expect_true("types.properties_float_ids_integral", "types",
                       "Float-encoded integer columns (group, serial, subcluster) are integral and < 2^53 (lossless int64 cast).",
                       not lossy, observed=lossy or list(FLOAT_INT_COLS))
    for c in ("type", "instance", "hemilineage", "somaNeuromere", "class", "subclass", "somaSide", "rootSide"):
        if c in df.columns:
            df[c] = df[c].astype("string")
    _nullify_placeholders(df, ["type", "hemilineage", "somaNeuromere", "class", "subclass"], report, "types.properties_placeholders")
    labels = set(df["statusLabel"].dropna().unique())
    unknown = sorted(labels - set(STATUS_LABEL_ORDER))
    report.expect_true("types.status_label_vocabulary", "types", "All statusLabel values are known DVID labels.",
                       not unknown, observed=unknown)
    bad = sorted(set(df["predictedNt"].dropna().unique()) - NT_VALUES)
    report.expect_true("types.nt_vocabulary", "types", "All predictedNt labels are in the controlled vocabulary.", not bad, observed=bad)
    probs = [c for c in df.columns if c.endswith("Prob")]
    rng = {c: [float(df[c].min()), float(df[c].max())] for c in probs if df[c].notna().any()}
    report.expect_true("edge_values.nt_confidence_range", "edge_values", "NT probabilities lie in [0, 1].",
                       all(0.0 <= lo and hi <= 1.0 + 1e-9 for lo, hi in rng.values()), observed=rng)
    # argmax consistency of the body-level call
    cls = {"ntAcetylcholineProb": "acetylcholine", "ntGabaProb": "gaba", "ntGlutamateProb": "glutamate", "ntUnknownProb": "unknown"}
    has = df[list(cls)].notna().all(axis=1) & df["predictedNt"].notna()
    am = df.loc[has, list(cls)].idxmax(axis=1).map(cls)
    n_bad = int((am != df.loc[has, "predictedNt"]).sum())
    report.expect_equal("consistency.nt_prediction_is_argmax", "cross_source",
                        "predictedNt equals the argmax over the four body-level class probabilities (ACh/GABA/Glu/unknown).",
                        n_bad, 0, on_mismatch=WARN)
    src = raw  # verbatim, typed
    return df, src


# ---------------------------------------------------------------------------
# manc:v1.0 (neuPrint-format) steps
# ---------------------------------------------------------------------------
NP_CROSSCHECK = {  # property export column -> neuPrint neuron table column
    "type": "type:string", "instance": "instance:string", "class": "class:string", "subclass": "subclass:string",
    "status": "status:string", "statusLabel": "statusLabel:string", "hemilineage": "hemilineage:string",
    "somaSide": "somaSide:string", "rootSide": "rootSide:string", "somaNeuromere": "somaNeuromere:string",
    "predictedNt": "predictedNt:string", "group": "group:int", "serial": "serial:int",
    "pre": "pre:int", "post": "post:int", "size": "size:long",
}


def scan_neuprint_neurons_v10(con, cfg: IngestConfig, report: ValidationReport) -> tuple[pd.DataFrame, dict]:
    ds = _ipc_dataset(cfg.raw_file("neuprint_neurons"))
    _reg(con, "np_neurons", ds)
    stats = con.execute(f"""
        SELECT count(*) AS n_segments,
               count(*) FILTER (WHERE ":LABEL" LIKE '%;Neuron;%') AS n_neuron_label,
               count(*) - count(DISTINCT "{NP_ID}") AS n_dup_ids,
               count(*) FILTER (WHERE "{NP_ID}" IS NULL) AS n_null_ids,
               count(*) FILTER (WHERE "{NP_ID}" <> "bodyId:long") AS n_id_mismatch,
               sum("pre:int") AS sum_pre, sum("post:int") AS sum_post,
               sum("downstream:int") AS sum_downstream, sum("upstream:int") AS sum_upstream
        FROM np_neurons""").fetchdf().iloc[0].to_dict()
    stats = {k: int(v) for k, v in stats.items()}
    report.add("rows.raw.neuprint_neurons", "ingestion", "Synaptic segments in neuPrint and how many carry the :Neuron label.",
               INFO, observed={k: stats[k] for k in ("n_segments", "n_neuron_label")})
    report.expect_equal("duplicates.neuprint_neurons.id", "duplicates", "No duplicate segment IDs in the neuPrint neuron table.",
                        stats["n_dup_ids"], 0)
    report.expect_equal("ids.neuprint_neurons.id_consistent", "ids", ":ID(Body-ID) equals bodyId for every segment, no nulls.",
                        [stats["n_null_ids"], stats["n_id_mismatch"]], [0, 0])
    report.expect_equal("consistency.upstream_equals_post", "directionality",
                        "Total upstream connections == total PSDs (each PSD has exactly one presynaptic partner).",
                        stats["sum_upstream"], stats["sum_post"])
    cols = ", ".join(f'n."{c}" AS "{c}"' for c in NP_CROSSCHECK.values())
    df = con.execute(f"""
        SELECT n."{NP_ID}" AS id, n."pre:int" AS pre, n."post:int" AS post, n."downstream:int" AS downstream,
               n."upstream:int" AS upstream, n."synweight:int" AS synweight, n."size:long" AS size,
               n.":LABEL" LIKE '%;Neuron;%' AS neuron_label, n."roiInfo:string" AS roi_info, n."status:string" AS status,
               {cols}
        FROM np_neurons n WHERE n.":LABEL" LIKE '%;Neuron;%'""").fetchdf()
    con.unregister("np_neurons")
    return df, stats


def crosscheck_properties_vs_neuprint(props: pd.DataFrame, npn: pd.DataFrame, report: ValidationReport) -> None:
    m = props.set_index("bodyId").join(npn.set_index("id"), how="inner", rsuffix="_np")
    report.expect_equal("referential.properties_are_neuprint_neurons", "referential",
                        "The per-body property export and the neuPrint :Neuron-labelled bodies are the same set.",
                        [int(len(props)), int(npn["neuron_label"].sum()), int(len(m))],
                        [int(len(props)), int(len(props)), int(len(props))])
    out = {}
    for a, b in NP_CROSSCHECK.items():
        x, y = m[a], m[b]
        if a in ("group", "serial"):
            x = pd.Series(x, index=m.index).astype("Int64").astype("string")
            y = pd.Series(_float_to_int64(y, b), index=m.index).astype("string")
        elif a in ("pre", "post", "size"):
            x, y = x.astype("Int64"), y.astype("Int64")
        else:  # placeholders ('None', 'TBD', 'NA') are nulls on both sides
            x, y = x.astype("string"), y.astype("string")
            x, y = x.where(~x.isin(NULL_STRINGS), pd.NA), y.where(~y.isin(NULL_STRINGS), pd.NA)
        neq = ~((x == y).fillna(False) | (x.isna() & y.isna()))
        out[a] = int(neq.sum())
    report.add("cross_source.properties_vs_neuprint", "cross_source",
               "Annotation fields agree between the per-body property export (2023-06-05) and the neuPrint neuron table "
               "(2023-06-12) (count of mismatching bodies per field). Status differences are analysed separately.",
               PASS if not any(v for k, v in out.items() if k not in ("status", "statusLabel")) else WARN, observed=out)
    st = m.groupby([m["status"].astype("string").fillna("<null>"), m["status:string"].astype("string").fillna("<null>")]).size()
    remap = [{"properties_status": a, "neuprint_status": b, "bodies": int(n)} for (a, b), n in st.items() if a != b]
    report.add("cross_source.status_remap_between_exports", "cross_source",
               "Bodies whose proofreading status differs between the two official exports (e.g. 'RT Orphan' in the "
               "2023-06-05 property export is 'Traced' in the 2023-06-12 neuPrint database).", INFO if remap else PASS,
               observed=remap)


def crosscheck_traced_adjacencies(con, cfg: IngestConfig, report: ValidationReport, neuron_ids: np.ndarray) -> None:
    tn = pd.read_csv(cfg.raw_file("traced_neurons"))
    tc = pd.read_csv(cfg.raw_file("traced_connections"))
    ids_csv = np.sort(tn["bodyId"].astype("int64").to_numpy())
    only_csv = int((~np.isin(ids_csv, neuron_ids)).sum())
    only_ours = int((~np.isin(neuron_ids, ids_csv)).sum())
    report.add("cross_source.traced_neuron_set", "cross_source",
               "Neuron set vs the independent neuprint-python traced-neuron export (2023-06-02; proofreading continued "
               "until the 2023-06-12 database export).", PASS if only_csv == 0 and only_ours <= 400 else WARN,
               observed={"neurons": int(len(neuron_ids)), "traced_csv": int(len(ids_csv)), "only_in_csv": only_csv,
                         "only_in_ours": only_ours})
    _reg(con, "tcsv", pa.table({"pre_id": pa.array(tc["bodyId_pre"].to_numpy(), pa.int64()),
                                 "post_id": pa.array(tc["bodyId_post"].to_numpy(), pa.int64()),
                                 "w": pa.array(tc["weight"].to_numpy(), pa.int64())}))
    _reg(con, "tid", pa.table({"id": pa.array(ids_csv, pa.int64())}))
    d = con.execute("""
        WITH ours AS (SELECT * FROM e SEMI JOIN tid a ON e.pre_id = a.id SEMI JOIN tid b ON e.post_id = b.id)
        SELECT count(*) FILTER (WHERE t.pre_id IS NULL) AS only_ours, count(*) FILTER (WHERE o.pre_id IS NULL) AS only_csv,
               count(*) FILTER (WHERE t.pre_id IS NOT NULL AND o.pre_id IS NOT NULL AND t.w <> o.w) AS weight_differs,
               count(*) AS compared
        FROM ours o FULL OUTER JOIN tcsv t ON o.pre_id = t.pre_id AND o.post_id = t.post_id""").fetchdf().iloc[0].to_dict()
    d = {k: int(v) for k, v in d.items()}
    report.add("cross_source.traced_connections_csv", "cross_source",
               "Edges between traced-CSV neurons: agreement of weights with the independent traced-connections.csv "
               "export (dates differ by 10 days; small differences reflect continued proofreading).",
               PASS if d["only_ours"] == 0 and d["only_csv"] == 0 and d["weight_differs"] == 0 else WARN, observed=d)
    per = pd.read_csv(cfg.raw_file("traced_connections_per_roi"))
    per["roi"] = per["roi"].where(per["roi"] != "NotPrimary", UNASSIGNED_NEUROPIL)
    _reg(con, "tper", pa.table({"pre_id": pa.array(per["bodyId_pre"].to_numpy(), pa.int64()),
                                 "post_id": pa.array(per["bodyId_post"].to_numpy(), pa.int64()),
                                 "neuropil": pa.array(per["roi"].astype(str).tolist(), pa.string()),
                                 "w": pa.array(per["weight"].to_numpy(), pa.int64())}))
    d2 = con.execute("""
        WITH ours AS (SELECT c.pre_id, c.post_id, CAST(c.neuropil AS VARCHAR) AS neuropil, c.synapse_count AS w FROM cn_all c
                      SEMI JOIN tid a ON c.pre_id = a.id SEMI JOIN tid b ON c.post_id = b.id)
        SELECT count(*) FILTER (WHERE t.pre_id IS NULL) AS only_ours, count(*) FILTER (WHERE o.pre_id IS NULL) AS only_csv,
               count(*) FILTER (WHERE t.pre_id IS NOT NULL AND o.pre_id IS NOT NULL AND t.w <> o.w) AS count_differs
        FROM ours o FULL OUTER JOIN tper t ON o.pre_id = t.pre_id AND o.post_id = t.post_id AND o.neuropil = t.neuropil
        """).fetchdf().iloc[0].to_dict()
    d2 = {k: int(v) for k, v in d2.items()}
    report.add("cross_source.traced_connections_per_roi_csv", "cross_source",
               "Per-edge neuropil counts vs traced-connections-per-roi.csv ('NotPrimary' == '<unassigned>').",
               PASS if not any(d2.values()) else WARN, observed=d2)
    for t in ("tcsv", "tid", "tper"):
        con.unregister(t)


def decompressed_partners_v10(cfg: IngestConfig, report: ValidationReport) -> Path | None:
    """The v1.0 partner table ships bzip2-compressed; decompress once into the cache (content-hashed)."""
    src = cfg.raw_file("syn_partners")
    if not src.exists():
        return None
    # content-addressed: the cache entry is keyed by the SHA-256 of the compressed input, so a fixture or a re-pinned
    # release can never pick up another file's decompressed table
    digest = snapshot_sha256(src)
    dest = paths.cache_dir() / "manc_v1.0" / f"{digest[:16]}_{src.name[:-4]}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        log.info("decompressing %s -> cache (once)", src.name)
        tmp = dest.with_suffix(".tmp")
        with bz2.open(src, "rb") as fi, open(tmp, "wb") as fo:
            shutil.copyfileobj(fi, fo, 64 * 1024 * 1024)
        tmp.replace(dest)
    report.add("provenance.syn_partners_decompressed", "provenance",
               "bzip2 partner table decompressed into the cache (derived, disposable; keyed by the SHA-256 of the compressed "
               "input, which the acquisition check verified).",
               INFO, observed={"cache_path": paths.relpath_for_record(dest), "size_bytes": dest.stat().st_size,
                               "input_sha256": digest})
    return dest


def infer_count_rule(con, report: ValidationReport, sample_ids: np.ndarray, meta: dict, default: CountRule,
                     syn_view: str = "ss") -> tuple[dict, CountRule]:
    """Test which confidence rule reproduces neuPrint weight / weightHP / weightHR from raw pairs (sampled neurons).

    Every (pre_min, post_min) grid point is evaluated against ALL pairs of the sampled neurons, including the
    HR-only pairs that carry weight 0 (temp table ``e_all``), with zero-filled counts on both sides."""
    grid = [(a, b) for a in _GRID for b in _GRID]
    cols = ", ".join(f"count(*) FILTER (WHERE CAST(conf_pre AS DOUBLE) >= CAST({a!r} AS DOUBLE) AND "
                     f"CAST(conf_post AS DOUBLE) >= CAST({b!r} AS DOUBLE)) AS c{i}" for i, (a, b) in enumerate(grid))
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE r_grid AS
        SELECT body_pre AS pre_id, body_post AS post_id, {cols} FROM {syn_view}
        WHERE body_pre IN (SELECT id FROM samp) AND body_post IN (SELECT id FROM nid) GROUP BY 1, 2""")
    sel = ", ".join(f"count(*) FILTER (WHERE coalesce(r.c{i}, 0) <> coalesce(e.w, 0)) AS bw{i}, "
                    f"count(*) FILTER (WHERE coalesce(r.c{i}, 0) <> coalesce(e.whr, 0)) AS bhr{i}, "
                    f"count(*) FILTER (WHERE coalesce(r.c{i}, 0) <> coalesce(e.whp, 0)) AS bhp{i}" for i in range(len(grid)))
    res = con.execute(f"""
        SELECT count(*) AS n, {sel}
        FROM r_grid r FULL OUTER JOIN (SELECT * FROM e_all WHERE pre_id IN (SELECT id FROM samp)) e
          ON r.pre_id = e.pre_id AND r.post_id = e.post_id""").fetchdf().iloc[0].to_dict()
    con.execute("DROP TABLE r_grid")
    rows = [{"conf_pre_min": a, "conf_post_min": b, "bad_weight": int(res[f"bw{i}"]), "bad_hr": int(res[f"bhr{i}"]),
             "bad_hp": int(res[f"bhp{i}"])} for i, (a, b) in enumerate(grid)]
    tbl = pd.DataFrame(rows)

    def exact(col):
        return [{"conf_pre_min": float(r.conf_pre_min), "conf_post_min": float(r.conf_post_min)}
                for r in tbl[tbl[col] == 0].itertuples()]

    def best(col):
        r = tbl.loc[tbl[col].idxmin()]
        return {"conf_pre_min": float(r.conf_pre_min), "conf_post_min": float(r.conf_post_min), "mismatching_pairs": int(r[col])}

    ex = {"weight": exact("bad_weight"), "weightHR": exact("bad_hr"), "weightHP": exact("bad_hp")}

    def choose(cands, declared):
        """Among exact rules prefer the Meta's declared post threshold, else the loosest rule (smallest thresholds)."""
        if not cands:
            return None
        for c in cands:
            if declared is not None and abs(c["conf_post_min"] - float(declared)) < 1e-9 and c["conf_pre_min"] == 0.0:
                return c
        return sorted(cands, key=lambda c: (c["conf_post_min"], c["conf_pre_min"]))[0]

    w_rule = choose(ex["weight"], meta.get("postHighAccuracyThreshold"))
    hp_rule = choose(ex["weightHP"], meta.get("postHPThreshold"))
    ok = w_rule is not None and hp_rule is not None
    if ok:
        chosen = CountRule(conf_pre_min=w_rule["conf_pre_min"], conf_post_min=w_rule["conf_post_min"],
                           hp_conf_pre_min=hp_rule["conf_pre_min"], hp_conf_post_min=hp_rule["conf_post_min"],
                           basis="inferred on this build's sampled neurons")
    else:
        chosen = default
    report.add("synapses.inferred_count_rule", "synapses",
               "Confidence rules (conf_pre >= a AND conf_post >= b over a grid) that reproduce neuPrint weight, weightHR and "
               "weightHP exactly from the raw minconf-0.0 partner table for every pair of the sampled neurons (HR-only pairs "
               "included). Several equivalent rules match when no synapse falls between two grid values; the chosen rule "
               "prefers the Meta's declared threshold, else the loosest matching one.",
               PASS if ok else WARN,
               observed={"exact_rules": ex, "chosen": asdict(chosen),
                         "best": {"weight": best("bad_weight"), "weightHR": best("bad_hr"), "weightHP": best("bad_hp")},
                         "n_pairs_compared": int(res["n"])})
    same = (chosen.conf_pre_min, chosen.conf_post_min, chosen.hp_conf_pre_min, chosen.hp_conf_post_min) == \
        (default.conf_pre_min, default.conf_post_min, default.hp_conf_pre_min, default.hp_conf_post_min)
    report.add("synapses.count_rule_matches_default", "synapses",
               "The rule inferred here equals DEFAULT_COUNT_RULE, the rule the v1.2.x builds apply to their partner table.",
               PASS if same else WARN, observed=asdict(chosen), expected=asdict(default))
    return {"grid": rows, "exact": ex, "chosen": asdict(chosen)}, chosen


def synapse_checks_v10(con, cfg: IngestConfig, report: ValidationReport, neuron_ids: np.ndarray, meta: dict,
                       npn: pd.DataFrame, partners: Path, conn_stats: dict) -> dict:
    _reg(con, "syn", _ipc_dataset(partners))
    cols = set(_ipc_dataset(partners).schema.names)
    g = con.execute("""SELECT count(*), min(conf_pre), min(conf_post), count(*) FILTER (WHERE body_pre = 0 OR body_post = 0),
                              count(DISTINCT (x_pre, y_pre, z_pre)) FROM syn""").fetchone()
    report.add("synapses.raw_partner_table", "synapses",
               "Raw partner rows (T-bar->PSD pairs at minconf 0.0), minimum confidences, rows touching body 0, distinct T-bars.",
               INFO, observed={"rows": int(g[0]), "min_conf_pre": float(g[1]), "min_conf_post": float(g[2]),
                               "rows_body_zero": int(g[3]), "distinct_tbars": int(g[4])})
    report.expect_equal("synapses.total_pairs_equal_weight_hr", "synapses",
                        "Raw partner rows == total neuPrint weightHR (the high-recall tier counts every pair of the minconf-0.0 "
                        "table; one presynaptic partner per PSD).", int(g[0]), int(conn_stats["sum_weight_hr"]), on_mismatch=WARN)
    report.expect_equal("synapses.distinct_tbars_equal_meta_pre", "synapses",
                        "Distinct T-bar coordinates in the partner table == Meta totalPreCount.", int(g[4]),
                        int(meta["totalPreCount"]), on_mismatch=WARN)
    rng = np.random.default_rng(cfg.seed)
    k = min(cfg.synapse_sample_neurons, len(neuron_ids))
    sample = np.sort(rng.choice(neuron_ids, size=k, replace=False))
    _reg(con, "samp", pa.table({"id": pa.array(sample, pa.int64())}))
    con.execute("""CREATE OR REPLACE TEMP TABLE ss AS
                   SELECT * FROM syn WHERE body_pre IN (SELECT id FROM samp) OR body_post IN (SELECT id FROM samp)""")
    default = cfg.options.get("count_rule", DEFAULT_COUNT_RULE)
    inferred, rule = infer_count_rule(con, report, sample, meta, default)
    # per-edge neuropil recomputation (only possible when the table carries the PSD ROI)
    roi_col = "roi_post" if "roi_post" in cols else ("primary_post" if "primary_post" in cols else None)
    if roi_col:
        rn = con.execute(f"""
            WITH r AS (SELECT s.body_pre AS pre_id, s.body_post AS post_id, coalesce(p.roi, '{UNASSIGNED_NEUROPIL}') AS neuropil,
                              count(*) AS c
                       FROM ss s LEFT JOIN prim p ON CAST(s.{roi_col} AS VARCHAR) = p.roi
                       WHERE s.body_pre IN (SELECT id FROM samp) AND s.body_post IN (SELECT id FROM nid) AND {rule.sql('s.conf_pre', 's.conf_post')}
                       GROUP BY 1, 2, 3),
                 c AS (SELECT pre_id, post_id, CAST(neuropil AS VARCHAR) AS neuropil, synapse_count FROM cn_all WHERE pre_id IN (SELECT id FROM samp))
            SELECT count(*) FILTER (WHERE c.pre_id IS NULL) AS only_synapses, count(*) FILTER (WHERE r.pre_id IS NULL) AS only_table,
                   count(*) FILTER (WHERE r.c <> c.synapse_count) AS count_differs
            FROM r FULL OUTER JOIN c ON r.pre_id = c.pre_id AND r.post_id = c.post_id AND r.neuropil = c.neuropil""").fetchdf().iloc[0].to_dict()
        rn = {kk: int(v) for kk, v in rn.items()}
        report.expect_equal("synapses.recomputed_edge_neuropils", "synapses",
                            f"Per-edge neuropil counts recomputed from synapse {roi_col} under the count rule match connection_neuropils "
                            "(sampled neurons' outgoing edges).", rn, {"only_synapses": 0, "only_table": 0, "count_differs": 0},
                            on_mismatch=WARN)
        # how good is 'T-bar ROI := ROI of its PSDs' (needed by the v1.2 builds, which lack T-bar ROIs)?
        span = con.execute(f"""
            WITH t AS (SELECT x_pre, y_pre, z_pre, count(DISTINCT coalesce(CAST({roi_col} AS VARCHAR), '{UNASSIGNED_NEUROPIL}')) AS n_roi
                       FROM ss WHERE body_pre IN (SELECT id FROM samp) AND {rule.sql()} GROUP BY 1, 2, 3)
            SELECT count(*), count(*) FILTER (WHERE n_roi > 1) FROM t""").fetchone()
        report.add("synapses.tbar_psd_roi_span", "synapses",
                   "T-bars (of sampled neurons) whose PSDs lie in more than one primary ROI. Quantifies the approximation "
                   "used by the v1.2.x builds, where a T-bar's neuropil is taken from its PSDs.", INFO,
                   observed={"tbars": int(span[0]), "tbars_spanning_multiple_rois": int(span[1]),
                             "fraction": round(float(span[1]) / max(1, int(span[0])), 6)})
    per = con.execute(f"""
        SELECT samp.id, coalesce(d.c, 0) AS downstream, coalesce(u.c, 0) AS upstream, coalesce(t.c, 0) AS tbars_with_partner
        FROM samp
        LEFT JOIN (SELECT body_pre AS id, count(*) AS c FROM ss WHERE {rule.sql()} GROUP BY 1) d ON d.id = samp.id
        LEFT JOIN (SELECT body_post AS id, count(*) AS c FROM ss WHERE {rule.sql()} GROUP BY 1) u ON u.id = samp.id
        LEFT JOIN (SELECT body_pre AS id, count(DISTINCT (x_pre, y_pre, z_pre)) AS c FROM ss WHERE {rule.sql()} GROUP BY 1) t ON t.id = samp.id
        """).fetchdf().set_index("id")
    npv = npn.set_index("id").reindex(per.index)[["downstream", "upstream", "pre"]].fillna(0).astype("int64")
    mism = {"downstream": int((per["downstream"] != npv["downstream"]).sum()),
            "upstream": int((per["upstream"] != npv["upstream"]).sum()),
            "pre_tbars_gt_neuprint_pre": int((per["tbars_with_partner"] > npv["pre"]).sum()),
            "pre_tbars_eq_neuprint_pre": int((per["tbars_with_partner"] == npv["pre"]).sum()), "n": int(len(per))}
    report.expect_equal("synapses.recomputed_neuron_totals", "synapses",
                        "For sampled neurons, synapse-level counts under the count rule reproduce neuPrint downstream/upstream, "
                        "and T-bars with partners never exceed neuPrint 'pre'.",
                        {k: mism[k] for k in ("downstream", "upstream", "pre_tbars_gt_neuprint_pre")},
                        {"downstream": 0, "upstream": 0, "pre_tbars_gt_neuprint_pre": 0}, on_mismatch=WARN, detail=mism)
    con.unregister("syn")
    return inferred


def _soma_xyz(series: pd.Series):
    def get(i):
        return pd.array([(int(x[i]) if x is not None and not (isinstance(x, float)) and len(x) == 3 else None) for x in series],
                        dtype="Int64")
    return get(0), get(1), get(2)


def assemble_neurons_v10(cfg: IngestConfig, props: pd.DataFrame, npn: pd.DataFrame, neuron_ids: np.ndarray,
                         totals: pd.DataFrame, edges: pa.Table) -> pd.DataFrame:
    n = npn.set_index("id").loc[neuron_ids]
    a = props.set_index("bodyId").reindex(neuron_ids)
    ds, ver = cfg.source.dataset, cfg.version
    soma_side = a["somaSide"].map(normalize_side)
    root_side = a["rootSide"].map(normalize_side)
    side = soma_side.where(soma_side.notna(), root_side)
    side_basis = pd.Series(np.where(soma_side.notna(), "soma", np.where(root_side.notna(), "root", None)), index=a.index)
    sx, sy, sz = _soma_xyz(a["somaLocation"])
    pre = edges.column("pre_id").to_numpy(); post = edges.column("post_id").to_numpy()
    w = edges.column("synapse_count").to_numpy().astype(np.int64)
    out_n = pd.Series(w).groupby(pre).sum(); in_n = pd.Series(w).groupby(post).sum()
    ids = pd.Series(neuron_ids, index=a.index)
    status = n["status"].astype("string")
    df = pd.DataFrame({
        "neuron_uid": [f"{ds}:{ver}:{int(i)}" for i in neuron_ids],
        "dataset": ds, "dataset_version": ver, "source_id": neuron_ids,
        "cell_type": a["type"].to_numpy(), "instance": a["instance"].to_numpy(),
        "super_class": a["class"].map(normalize_class_label).to_numpy(), "cell_class": None, "sub_class": a["subclass"].to_numpy(),
        "hemilineage_ito_lee": None, "hemilineage_truman": a["hemilineage"].to_numpy(),
        "soma_side": soma_side.to_numpy(), "root_side": root_side.to_numpy(), "side": side.to_numpy(), "side_basis": side_basis.to_numpy(),
        "soma_neuromere": a["somaNeuromere"].to_numpy(), "soma_x": sx, "soma_y": sy, "soma_z": sz,
        "animal_sex": ANIMAL_SEX, "status": status.to_numpy(), "status_label": n["statusLabel:string"].astype("string").to_numpy(),
        "is_traced": pd.array(status.eq("Traced").fillna(False).to_numpy(), dtype="boolean"),
        "neuprint_neuron_label": pd.array(n["neuron_label"].fillna(False).to_numpy(), dtype="boolean"),
        "n_pre": n["pre"].astype("Int64").to_numpy(), "n_post": n["post"].astype("Int64").to_numpy(),
        "n_downstream": n["downstream"].astype("Int64").to_numpy(), "n_upstream": n["upstream"].astype("Int64").to_numpy(),
        "n_downstream_to_neurons": ids.map(out_n).fillna(0).astype("int64").to_numpy(),
        "n_upstream_from_neurons": ids.map(in_n).fillna(0).astype("int64").to_numpy(),
        "size_voxels": n["size"].astype("Int64").to_numpy(),
        "nt_consensus": None, "nt_body_prediction": a["predictedNt"].to_numpy(),
        "nt_body_confidence": a["predictedNtProb"].astype("float64").to_numpy(), "nt_body_n_tbars": pd.array([None] * len(a), dtype="Int32"),
        "nt_type_prediction": None, "nt_type_confidence": pd.array([None] * len(a), dtype="Float64"),
        "nt_type_n_tbars": pd.array([None] * len(a), dtype="Int32"), "nt_literature_label": None,
        "group_id": a["group"].to_numpy(), "synonyms": a["synonyms"].to_numpy(), "flywire_type": None, "hemibrain_type": None,
        "manc_type": None, "manc_body_id": pd.array([None] * len(a), dtype="Int64"), "dimorphism": None, "fru_dsx": None,
    })
    t = totals.reindex(neuron_ids)
    df["out_all"] = t["out_all"].to_numpy(); df["in_all"] = t["in_all"].to_numpy()
    return df


DEFINITIONS_V10 = {
    "neuron": "body carrying the neuPrint :Neuron label with status 'Traced' in the neuPrint neuron table (the database queried "
              "by neuprint-python and the MANC papers). 314 of these bodies are 'RT Orphan' in the per-body property export "
              "of 2023-06-05; both statuses are stored (status = neuPrint, status_label = DVID label).",
    "synapse_count": "number of T-bar->PSD pairs counted by neuPrint (ConnectsTo.weight). The effective confidence rule is "
                     "inferred from the raw partner table (validation check synapses.inferred_count_rule).",
    "synapse_count_hp": "neuPrint weightHP (high-precision subset; rule inferred, see synapses.inferred_count_rule).",
    "edge_neuropil": "primary ROI containing the POSTsynaptic density (neuPrint convention).",
    "autapse": "pre_id == post_id; retained and flagged, not dropped.",
    "coordinates": "8 nm isotropic voxels in the MANC EM space (voxelSize 8,8,8 nm).",
    "hemilineage": "MANC hemilineage nomenclature (Truman-style, e.g. '17A') stored in hemilineage_truman.",
    "super_class": "MANC 'class' with spaces replaced by underscores (matches the v1.2.x tag vocabulary).",
}


def build_v10(cfg: IngestConfig) -> dict:
    run = BuildRun(cfg, PIPELINE_ID, PIPELINE_VERSION, CRITICAL_CHECKS)
    report = run.report
    needed = ["neuprint_meta", "neuron_properties", "neuprint_neurons", "neuprint_connections", "traced_neurons",
              "traced_connections", "traced_connections_per_roi"]
    if cfg.synapse_checks and cfg.raw_file("syn_partners").exists():
        needed.append("syn_partners")
    t0 = time.time(); acq = check_acquisition(cfg, report, needed); run.lap("acquisition_check", t0)
    t0 = time.time(); meta = load_meta_v10(cfg.raw_file("neuprint_meta"), report)
    neuropils, primary = build_neuropils(meta, report, ROI_PARENT_ALIASES, set(meta["nerveRois"]),
                                         hierarchy_authoritative=False, region_override="VNC")
    run.lap("meta_neuropils", t0)
    t0 = time.time(); props, ann_src = load_properties_v10(cfg, report); run.lap("properties", t0)
    run.abort_if_critical("inputs")

    con = _duck(cfg)
    t0 = time.time(); npn, np_stats = scan_neuprint_neurons_v10(con, cfg, report); run.lap("neuprint_neurons_scan", t0)
    neuron_ids = np.sort(npn.loc[npn["status"] == "Traced", "id"].astype("int64").to_numpy())
    report.add("rows.neurons", "ingestion", "Neurons = neuPrint :Neuron bodies with status 'Traced' (see definitions).", INFO,
               observed=int(len(neuron_ids)))
    report.expect_equal("ids.neurons.unique", "uniqueness", "Neuron IDs unique.", int(len(neuron_ids) - len(np.unique(neuron_ids))), 0)
    typed_untraced = int(((npn["status"] != "Traced") & npn["type:string"].notna()).sum())
    report.add("coverage.typed_bodies_outside_neuron_set", "coverage",
               ":Neuron bodies with a cell type but a status other than 'Traced' (excluded from the neuron table; e.g. PRT Orphan).",
               INFO, observed=typed_untraced)
    t0 = time.time(); crosscheck_properties_vs_neuprint(props, npn, report); run.lap("neuron_crosschecks", t0)
    npn_n = npn[npn["id"].isin(neuron_ids)].reset_index(drop=True)
    t0 = time.time(); nn = parse_neuron_roiinfo(con, npn_n, primary, report); run.lap("neuron_neuropils", t0)
    t0 = time.time()
    edges, cn, totals, g = scan_connections(con, cfg, neuron_ids, primary, report, meta, hr_equals_weight=False,
                                            weight_sum_equals_total_post=False)
    run.lap("connections", t0)
    _reg(con, "cn_all", cn)
    report.expect_equal("consistency.segment_totals_equal_edge_totals", "directionality",
                        "Sum over all segments of neuPrint 'downstream' and of 'upstream' each equal the total weight of the "
                        "connection table (conservation: every counted pair has an existing pre and post segment).",
                        [np_stats["sum_downstream"], np_stats["sum_upstream"]], [g["sum_weight"], g["sum_weight"]])
    t0 = time.time(); crosscheck_traced_adjacencies(con, cfg, report, neuron_ids); run.lap("traced_csv_crosscheck", t0)
    inferred = None
    if cfg.synapse_checks:
        t0 = time.time()
        partners = decompressed_partners_v10(cfg, report)
        if partners is None:
            report.add("synapses.skipped", "synapses", "syn_partners not acquired; synapse-level checks skipped.", WARN)
        else:
            inferred = synapse_checks_v10(con, cfg, report, neuron_ids, meta, npn_n, partners, g)
        run.lap("synapse_checks", t0)
    retained_graph_checks(edges, neuron_ids, report)

    t0 = time.time()
    neurons = assemble_neurons_v10(cfg, props, npn, neuron_ids, totals, edges)
    regions = dict(zip(neuropils.column("name").to_pylist(), neuropils.column("top_level_region").to_pylist()))
    directionality_checks(neurons, nn.to_pandas(), regions, report, vnc_regions=frozenset(v for v in regions.values() if v))
    stats = graph_statistics(edges, neuron_ids, report)
    cov = coverage(neurons, report)
    run.lap("assemble_validate", t0)
    t0 = time.time(); outputs = write_outputs(run, neurons, edges, cn, nn, neuropils, ann_src); run.lap("write_outputs", t0)
    extra = {"neuprint_meta": {k: meta.get(k) for k in ("uuid", "latestMutationId", "lastDatabaseEdit", "totalPreCount",
                                                        "totalPostCount", "postHighAccuracyThreshold", "postHPThreshold")},
             "raw_connection_table": g, "neuprint_segment_stats": np_stats, "inferred_count_rule": inferred}
    return finalize(run, con, outputs=outputs, needed=needed, acq=acq, stats=stats, cov=cov, extra=extra, definitions=DEFINITIONS_V10)


# ---------------------------------------------------------------------------
# manc:v1.2.x (synapse rebuild) steps
# ---------------------------------------------------------------------------
_CAMEL = re.compile(r"(?<=[a-z0-9])([A-Z])")


def _snake(name: str) -> str:
    return _CAMEL.sub(lambda m: "_" + m.group(1), name).lower()


def load_snapshot(cfg: IngestConfig, report: ValidationReport) -> tuple[pd.DataFrame, pa.Table, dict]:
    """neuroglancer segment_properties JSON snapshot(s) -> one row per body with one column per property/tag prefix."""
    snap = ANNOTATION_SNAPSHOTS[cfg.build_version]
    frames = []
    for key in snap["files"]:
        d = json.loads(cfg.raw_file(key).read_text(encoding="utf-8"))["inline"]
        ids = pd.Index(np.array(d["ids"], dtype=np.int64), name="bodyId")
        cols: dict[str, object] = {}
        for prop in d["properties"]:
            pid, ptype = prop["id"], prop["type"]
            if ptype == "tags":
                tags = prop["tags"]
                # deterministic column set and order: every prefix present in the tag vocabulary, sorted
                prefixes = sorted({_snake(t.partition(":")[0]) for t in tags})
                per_prefix: dict[str, list] = {k: [] for k in prefixes}
                for row in prop["values"]:
                    seen: dict[str, list[str]] = {}
                    for ti in row:
                        pref, _, val = tags[ti].partition(":")
                        seen.setdefault(_snake(pref), []).append(val)
                    for k in prefixes:
                        per_prefix[k].append("|".join(seen[k]) if k in seen else None)
                for k in prefixes:
                    cols[f"tag_{k}"] = pd.Series(per_prefix[k], index=ids, dtype="string")
            elif ptype == "number":
                cols[pid] = pd.Series(prop["values"], index=ids, dtype="float64")
            else:
                cols[pid] = pd.Series([x if x not in ("", *NULL_STRINGS) else None for x in prop["values"]], index=ids, dtype="string")
        frames.append(pd.DataFrame(cols, index=ids))
    df = frames[0]
    for f in frames[1:]:
        for c in f.columns:
            if c not in df.columns:
                df = df.join(f[[c]], how="outer")
            else:  # duplicated property between files: check agreement, keep the first
                both = df[c].notna() & f[c].notna()
                n_diff = int((df.loc[both, c].astype("string") != f.loc[both, c].astype("string")).sum())
                report.add(f"cross_source.snapshot_duplicate_property.{c}", "cross_source",
                           f"Property '{c}' present in several snapshot files agrees.", PASS if n_diff == 0 else WARN, observed=n_diff)
    df = df.reset_index()
    report.add("rows.raw.annotation_snapshot", "ingestion", f"Bodies in annotation snapshot {cfg.build_version} ({snap['description']}).",
               INFO, observed=int(len(df)), columns=sorted(df.columns))
    ids = df["bodyId"]
    report.expect_true("ids.snapshot.non_null_positive", "ids", "bodyId non-null and positive.", bool(ids.notna().all() and (ids > 0).all()))
    report.expect_equal("duplicates.snapshot.bodyId", "duplicates", "No duplicate bodies in the snapshot.", int(ids.duplicated().sum()), 0)
    multi = {c: int(df[c].str.contains("|", regex=False).sum()) for c in df.columns if c.startswith("tag_") and df[c].notna().any()}
    report.add("types.snapshot_multivalued_tags", "types", "Bodies with more than one tag value per prefix (joined with '|').", INFO,
               observed={k: v for k, v in multi.items() if v})
    if "tag_class" in df.columns:
        report.add("coverage.snapshot_classes", "coverage", "Distribution of the 'class' tag.", INFO,
                   observed=df["tag_class"].value_counts(dropna=False).astype(int).to_dict())
    src = pa.Table.from_pandas(df, preserve_index=False)
    return df, src, snap


def scan_partners_v12(con, cfg: IngestConfig, report: ValidationReport, neuron_ids: np.ndarray, primary: list[str],
                      rule: CountRule) -> tuple[pa.Table, pa.Table, pa.Table, pd.DataFrame, dict, pd.DataFrame]:
    """Rebuild connections, per-edge neuropils, per-neuron neuropils and totals from the raw partner table."""
    path = cfg.raw_file("syn_partners")
    _reg(con, "syn", _ipc_dataset(path))
    _reg(con, "nid", pa.table({"id": pa.array(neuron_ids, pa.int64())}))
    _reg(con, "prim", pa.table({"roi": pa.array(primary, pa.string())}))
    log.info("partners: global statistics")
    g = con.execute(f"""
        SELECT count(*) AS rows_total, count(*) FILTER (WHERE {rule.sql()}) AS rows_counted,
               count(*) FILTER (WHERE {rule.sql_hp()}) AS rows_hp,
               count(*) FILTER (WHERE body_pre = 0 OR body_post = 0) AS rows_body_zero,
               count(*) FILTER (WHERE body_pre IS NULL OR body_post IS NULL OR conf_pre IS NULL OR conf_post IS NULL) AS rows_null,
               min(conf_pre) AS min_conf_pre, min(conf_post) AS min_conf_post,
               count(DISTINCT (x_pre, y_pre, z_pre)) FILTER (WHERE {rule.sql()}) AS tbars_counted
        FROM syn""").fetchdf().iloc[0].to_dict()
    g = {k: (float(v) if k.startswith("min") else int(v)) for k, v in g.items()}
    report.add("rows.raw.syn_partners", "ingestion", "Raw T-bar->PSD pairs (minconf 0.0) and how many pass the count rule.",
               INFO, observed=g, count_rule=asdict(rule))
    report.expect_equal("edge_values.no_nulls", "edge_values", "No null bodies/confidences in the raw partner table.", g["rows_null"], 0)
    rois = con.execute("SELECT DISTINCT CAST(roi_post AS VARCHAR) AS r FROM syn").fetchdf()["r"].dropna().tolist()
    unknown = sorted(set(rois) - set(primary) - {"<unspecified>"})  # the export's own 'outside every ROI' marker
    report.expect_true("referential.partner_rois_are_primary", "referential",
                       "Every roi_post value of the partner table is a primary ROI of the ROI catalogue, null, or the export's "
                       "'<unspecified>' marker (mapped to '<unassigned>').",
                       not unknown, observed=unknown, n_rois=len(rois))
    log.info("partners: per-neuron totals over all partners")
    tot = con.execute(f"""
        SELECT n.id,
               coalesce(d.c, 0) AS out_all, coalesce(u.c, 0) AS in_all, coalesce(t.c, 0) AS n_pre,
               coalesce(d_all.c, 0) AS out_unfiltered, coalesce(u_all.c, 0) AS in_unfiltered, coalesce(t_all.c, 0) AS n_pre_unfiltered
        FROM nid n
        LEFT JOIN (SELECT body_pre AS id, count(*) AS c FROM syn WHERE {rule.sql()} GROUP BY 1) d ON d.id = n.id
        LEFT JOIN (SELECT body_post AS id, count(*) AS c FROM syn WHERE {rule.sql()} GROUP BY 1) u ON u.id = n.id
        LEFT JOIN (SELECT body_pre AS id, count(DISTINCT (x_pre, y_pre, z_pre)) AS c FROM syn WHERE {rule.sql()} GROUP BY 1) t ON t.id = n.id
        LEFT JOIN (SELECT body_pre AS id, count(*) AS c FROM syn GROUP BY 1) d_all ON d_all.id = n.id
        LEFT JOIN (SELECT body_post AS id, count(*) AS c FROM syn GROUP BY 1) u_all ON u_all.id = n.id
        LEFT JOIN (SELECT body_pre AS id, count(DISTINCT (x_pre, y_pre, z_pre)) AS c FROM syn GROUP BY 1) t_all ON t_all.id = n.id
        """).fetchdf().set_index("id")
    tot = tot.astype("int64")
    log.info("partners: neuron->neuron edges")
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE e AS
        SELECT body_pre AS pre_id, body_post AS post_id, count(*) AS w,
               count(*) FILTER (WHERE {rule.sql_hp()}) AS whp
        FROM syn WHERE {rule.sql()} AND body_pre IN (SELECT id FROM nid) AND body_post IN (SELECT id FROM nid)
        GROUP BY 1, 2""")
    n_e = con.execute("SELECT count(*) FROM e").fetchone()[0]
    report.add("rows.connections", "ingestion", "Neuron->neuron edges retained (both endpoints are neurons).", INFO, observed=int(n_e))
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE cn AS
        SELECT body_pre AS pre_id, body_post AS post_id,
               coalesce(p.roi, '{UNASSIGNED_NEUROPIL}') AS neuropil, count(*) AS synapse_count
        FROM syn s LEFT JOIN prim p ON CAST(s.roi_post AS VARCHAR) = p.roi
        WHERE {rule.sql('s.conf_pre', 's.conf_post')} AND body_pre IN (SELECT id FROM nid) AND body_post IN (SELECT id FROM nid)
        GROUP BY 1, 2, 3""")
    bad = con.execute("""SELECT count(*) FROM (SELECT pre_id, post_id, sum(synapse_count) s FROM cn GROUP BY 1, 2) x
                         JOIN e ON x.pre_id = e.pre_id AND x.post_id = e.post_id WHERE x.s <> e.w""").fetchone()[0]
    report.expect_equal("consistency.connection_neuropils_sum_to_weight", "coverage",
                        "Per-edge neuropil counts sum exactly to the edge synapse_count.", int(bad), 0)
    n_un = con.execute(f"SELECT count(*), coalesce(sum(synapse_count), 0) FROM cn WHERE neuropil = '{UNASSIGNED_NEUROPIL}'").fetchone()
    report.add("coverage.connection_unassigned", "coverage", "Edges with synapses outside primary ROIs (stored as neuropil '<unassigned>').",
               INFO, observed={"edges": int(n_un[0]), "synapses": int(n_un[1])})
    cn = _arrow(con.execute("SELECT pre_id, post_id, neuropil, synapse_count FROM cn"))
    dom = _arrow(con.execute("""
        WITH ranked AS (SELECT *, row_number() OVER (PARTITION BY pre_id, post_id ORDER BY synapse_count DESC, neuropil ASC) AS rk,
                               count(*) OVER (PARTITION BY pre_id, post_id) AS nn FROM cn)
        SELECT e.pre_id, e.post_id, e.w AS synapse_count, e.whp AS synapse_count_hp, e.pre_id = e.post_id AS is_autapse,
               r.neuropil AS dominant_neuropil, CAST(r.synapse_count AS DOUBLE) / e.w AS dominant_neuropil_fraction,
               coalesce(r.nn, 0) AS n_neuropils
        FROM e LEFT JOIN ranked r ON e.pre_id = r.pre_id AND e.post_id = r.post_id AND r.rk = 1"""))
    log.info("partners: per-neuron neuropil counts")
    nn = _arrow(con.execute(f"""
        WITH post AS (SELECT body_post AS source_id, coalesce(p.roi, '{UNASSIGNED_NEUROPIL}') AS neuropil, count(*) AS n_post
                      FROM syn s LEFT JOIN prim p ON CAST(s.roi_post AS VARCHAR) = p.roi
                      WHERE {rule.sql('s.conf_pre', 's.conf_post')} AND body_post IN (SELECT id FROM nid) GROUP BY 1, 2),
             pre AS (SELECT body_pre AS source_id, coalesce(p.roi, '{UNASSIGNED_NEUROPIL}') AS neuropil,
                            count(DISTINCT (x_pre, y_pre, z_pre)) AS n_pre
                     FROM syn s LEFT JOIN prim p ON CAST(s.roi_post AS VARCHAR) = p.roi
                     WHERE {rule.sql('s.conf_pre', 's.conf_post')} AND body_pre IN (SELECT id FROM nid) GROUP BY 1, 2)
        SELECT coalesce(a.source_id, b.source_id) AS source_id, coalesce(a.neuropil, b.neuropil) AS neuropil,
               coalesce(b.n_pre, 0) AS n_pre, coalesce(a.n_post, 0) AS n_post
        FROM post a FULL OUTER JOIN pre b ON a.source_id = b.source_id AND a.neuropil = b.neuropil"""))
    # ROI totals for the neuropil catalogue (PSD side exact; T-bar side approximated by PSD ROI)
    roi_tot = con.execute(f"""
        SELECT coalesce(CAST(roi_post AS VARCHAR), '{UNASSIGNED_NEUROPIL}') AS roi, count(*) AS n_post
        FROM syn WHERE {rule.sql()} GROUP BY 1""").fetchdf().set_index("roi")
    con.unregister("syn")
    return dom, cn, nn, tot, g, roi_tot


def crosscheck_snapshot_counts(snap_df: pd.DataFrame, tot: pd.DataFrame, report: ValidationReport) -> None:
    """Compare recomputed per-neuron counts with the counts published in the snapshot(s)."""
    s = snap_df.set_index("bodyId")
    t = tot.reindex(s.index)
    checks = {}
    for col, ours, label in (("syn_pre", "n_pre", "T-bars (rule)"), ("syn_post", "in_all", "PSDs (rule)"),
                             ("syn_downstream", "out_all", "downstream (rule)"),
                             ("PreSyn", "n_pre_unfiltered", "T-bars (unfiltered)"), ("PostSyn", "in_unfiltered", "PSDs (unfiltered)"),
                             ("PreSyn", "n_pre", "T-bars (rule)"), ("PostSyn", "in_all", "PSDs (rule)"),
                             ("syn_pre", "n_pre_unfiltered", "T-bars (unfiltered)"), ("syn_post", "in_unfiltered", "PSDs (unfiltered)")):
        if col in s.columns:
            have = s[col].notna()
            eq = int((s.loc[have, col].astype("int64") == t.loc[have, ours]).sum())
            checks[f"{col} == {label}"] = {"equal": eq, "n": int(have.sum()), "fraction": round(eq / max(1, int(have.sum())), 4)}
    report.add("cross_source.snapshot_synapse_counts", "cross_source",
               "Per-neuron synapse counts recomputed from the partner table vs the counts published in the annotation snapshot "
               "(both under the count rule and unfiltered). Tells which filtering the snapshot's counts used.",
               INFO, observed=checks)


def assemble_neurons_v12(cfg: IngestConfig, snap: pd.DataFrame, props10: pd.DataFrame, tot: pd.DataFrame, edges: pa.Table,
                         report: ValidationReport) -> pd.DataFrame:
    s = snap.set_index("bodyId")
    neuron_ids = np.sort(s.index.to_numpy())
    s = s.loc[neuron_ids]
    p = props10.set_index("bodyId").reindex(neuron_ids)
    ds, ver = cfg.source.dataset, cfg.version
    n_missing_nt = int(p["predictedNtProb"].isna().sum())
    n_absent = int((~np.isin(neuron_ids, props10["bodyId"].to_numpy())).sum())
    report.add("coverage.nt_carried_from_v1_0", "coverage",
               "Body-level NT predictions are carried over from the manc:v1.0 property export by body ID (same segmentation "
               "lineage). Neurons absent from v1.0 or without a v1.0 prediction have null nt_body_*.", INFO,
               observed={"neurons": int(len(neuron_ids)), "absent_from_v1_0": n_absent, "without_body_prediction": n_missing_nt})

    def tag(name):
        c = f"tag_{name}"
        return s[c] if c in s.columns else pd.Series([None] * len(s), index=s.index, dtype="string")

    soma_side = tag("soma_side").map(normalize_side)
    root_side = tag("root_side").map(normalize_side)
    side = soma_side.where(soma_side.notna(), root_side)
    side_basis = pd.Series(np.where(soma_side.notna(), "soma", np.where(root_side.notna(), "root", None)), index=s.index)
    pre = edges.column("pre_id").to_numpy(); post = edges.column("post_id").to_numpy()
    w = edges.column("synapse_count").to_numpy().astype(np.int64)
    out_n = pd.Series(w).groupby(pre).sum(); in_n = pd.Series(w).groupby(post).sum()
    ids = pd.Series(neuron_ids, index=s.index)
    t = tot.reindex(neuron_ids)
    group = s["group"] if "group" in s.columns else pd.Series([None] * len(s), index=s.index, dtype="string")
    group_id = pd.array([int(x) if isinstance(x, str) and x.isdigit() else None for x in group], dtype="Int64")
    ct_nt = tag("celltype_predicted_nt")
    nulls_i32 = pd.array([None] * len(s), dtype="Int32")
    df = pd.DataFrame({
        "neuron_uid": [f"{ds}:{ver}:{int(i)}" for i in neuron_ids],
        "dataset": ds, "dataset_version": ver, "source_id": neuron_ids,
        "cell_type": s["type"].to_numpy() if "type" in s.columns else None,
        "instance": s["instance"].to_numpy() if "instance" in s.columns else None,
        "super_class": tag("class").map(normalize_class_label).to_numpy(), "cell_class": None, "sub_class": tag("subclass").to_numpy(),
        "hemilineage_ito_lee": None, "hemilineage_truman": tag("hemilineage").to_numpy(),
        "soma_side": soma_side.to_numpy(), "root_side": root_side.to_numpy(), "side": side.to_numpy(), "side_basis": side_basis.to_numpy(),
        "soma_neuromere": tag("soma_neuromere").to_numpy(), "soma_x": pd.array([None] * len(s), dtype="Int64"),
        "soma_y": pd.array([None] * len(s), dtype="Int64"), "soma_z": pd.array([None] * len(s), dtype="Int64"),
        "animal_sex": ANIMAL_SEX, "status": None, "status_label": None,
        "is_traced": pd.array([None] * len(s), dtype="boolean"), "neuprint_neuron_label": pd.array([None] * len(s), dtype="boolean"),
        "n_pre": t["n_pre"].astype("Int64").to_numpy(), "n_post": t["in_all"].astype("Int64").to_numpy(),
        "n_downstream": t["out_all"].astype("Int64").to_numpy(), "n_upstream": t["in_all"].astype("Int64").to_numpy(),
        "n_downstream_to_neurons": ids.map(out_n).fillna(0).astype("int64").to_numpy(),
        "n_upstream_from_neurons": ids.map(in_n).fillna(0).astype("int64").to_numpy(),
        "size_voxels": pd.array([None] * len(s), dtype="Int64"),
        "nt_consensus": None, "nt_body_prediction": p["predictedNt"].astype("string").to_numpy(),
        "nt_body_confidence": p["predictedNtProb"].astype("float64").to_numpy(), "nt_body_n_tbars": nulls_i32,
        "nt_type_prediction": ct_nt.to_numpy(), "nt_type_confidence": pd.array([None] * len(s), dtype="Float64"),
        "nt_type_n_tbars": nulls_i32, "nt_literature_label": None,
        "group_id": group_id, "synonyms": None, "flywire_type": None, "hemibrain_type": None, "manc_type": None,
        "manc_body_id": pd.array([None] * len(s), dtype="Int64"), "dimorphism": None, "fru_dsx": None,
    })
    df["out_all"] = t["out_all"].to_numpy(); df["in_all"] = t["in_all"].to_numpy()
    # agreement between the carried body-level prediction and the snapshot's cell-type-level prediction (informational)
    both = df["nt_body_prediction"].notna() & df["nt_type_prediction"].notna()
    if both.any():
        agree = int((df.loc[both, "nt_body_prediction"] == df.loc[both, "nt_type_prediction"]).sum())
        report.add("cross_source.nt_body_vs_celltype", "cross_source",
                   "Neurons whose carried body-level NT prediction (v1.0) equals the snapshot's cell-type-level prediction.",
                   INFO, observed={"agree": agree, "n": int(both.sum()), "fraction": round(agree / int(both.sum()), 4)})
    return df


DEFINITIONS_V12 = {
    "neuron": "body listed in the neuroglancer segment_properties annotation snapshot of the requested version (the bodies "
              "neuPrint manc:v1.2.x exposes as annotated neurons). No proofreading status is published for v1.2.x; status, "
              "is_traced and neuprint_neuron_label are null.",
    "synapse_count": "number of T-bar->PSD pairs of the v1.2 partner table passing the count rule (see build_info.count_rule), "
                     "recomputed by BrainIR; neuPrint manc:v1.2.x weights are not publicly exported.",
    "synapse_count_hp": "pairs passing the high-precision rule (see build_info.count_rule).",
    "edge_neuropil": "primary ROI of the POSTsynaptic point (roi_post of the partner table; ROI catalogue from manc:v1.0).",
    "neuron_neuropils.n_pre": "APPROXIMATION: the partner table carries no T-bar ROI, so a T-bar is assigned the primary ROI of "
                              "its PSDs (counted once per ROI it reaches). n_post is exact.",
    "nt_body_prediction": "carried over from manc:v1.0 body-level predictions by body ID (same segmentation lineage).",
    "nt_type_prediction": "cell-type-level NT tag of the annotation snapshot (v1.2.3 only).",
    "autapse": "pre_id == post_id; retained and flagged, not dropped.",
    "coordinates": "8 nm isotropic voxels in the MANC EM space.",
}


def build_v12(cfg: IngestConfig) -> dict:
    run = BuildRun(cfg, PIPELINE_ID, PIPELINE_VERSION, CRITICAL_CHECKS)
    report = run.report
    snap_meta = ANNOTATION_SNAPSHOTS[cfg.build_version]
    rule: CountRule = cfg.options.get("count_rule", DEFAULT_COUNT_RULE)
    needed = ["syn_partners", *snap_meta["files"]]
    needed10 = ["neuprint_meta", "neuron_properties"]
    t0 = time.time()
    acq = check_acquisition(cfg, report, needed)
    acq10 = check_acquisition(cfg, report, needed10, source=MANC_V1_0, suffix=".v1_0")
    run.lap("acquisition_check", t0)
    raw10 = cfg.other_raw(MANC_V1_0)
    t0 = time.time()
    meta = load_meta_v10(raw10 / MANC_V1_0.local_relpath(MANC_V1_0.file("neuprint_meta")), report)
    neuropils, primary = build_neuropils(meta, report, ROI_PARENT_ALIASES, set(meta["nerveRois"]),
                                         hierarchy_authoritative=False, region_override="VNC")
    run.lap("meta_neuropils", t0)
    t0 = time.time(); snap, ann_src, _ = load_snapshot(cfg, report); run.lap("snapshot", t0)
    t0 = time.time(); props10, _src10 = load_properties_v10(cfg, report, raw_dir=raw10); run.lap("v1_0_properties", t0)
    run.abort_if_critical("inputs")

    neuron_ids = np.sort(snap["bodyId"].astype("int64").to_numpy())
    report.add("rows.neurons", "ingestion", f"Neurons = bodies of annotation snapshot {cfg.build_version} (see definitions).", INFO,
               observed=int(len(neuron_ids)))
    report.expect_equal("ids.neurons.unique", "uniqueness", "Neuron IDs unique.", int(len(neuron_ids) - len(np.unique(neuron_ids))), 0)
    con = _duck(cfg)
    t0 = time.time()
    edges, cn, nn, tot, g, roi_tot = scan_partners_v12(con, cfg, report, neuron_ids, primary, rule)
    run.lap("partners", t0)
    _reg(con, "cn_all", cn)
    report.add("autapses.raw", "autapses", "Self-connections (pre == post) among neuron->neuron edges: kept, flagged is_autapse.", INFO,
               observed={"edges": int(edges.filter(edges.column("is_autapse")).num_rows)})
    crosscheck_snapshot_counts(snap, tot, report)
    retained_graph_checks(edges, neuron_ids, report)
    # ROI catalogue totals: recomputed PSD counts (exact), T-bar counts unknown (null)
    names = neuropils.column("name").to_pylist()
    n_post_total = [int(roi_tot["n_post"].get(n, 0)) if n in roi_tot.index else None for n in names]
    neuropils = neuropils.set_column(neuropils.schema.get_field_index("n_post_total"), "n_post_total", pa.array(n_post_total, pa.int64()))
    neuropils = neuropils.set_column(neuropils.schema.get_field_index("n_pre_total"), "n_pre_total", pa.array([None] * len(names), pa.int64()))
    report.add("neuropils.totals_source", "provenance",
               "ROI catalogue from manc:v1.0 Meta; n_post_total recomputed from the v1.2 partner table under the count rule; "
               "n_pre_total null (T-bar ROIs are not published for v1.2).", INFO)

    t0 = time.time()
    neurons = assemble_neurons_v12(cfg, snap, props10, tot, edges, report)
    regions = dict(zip(names, neuropils.column("top_level_region").to_pylist()))
    directionality_checks(neurons, nn.to_pandas(), regions, report, vnc_regions=frozenset(v for v in regions.values() if v))
    stats = graph_statistics(edges, neuron_ids, report)
    cov = coverage(neurons, report)
    run.lap("assemble_validate", t0)
    t0 = time.time(); outputs = write_outputs(run, neurons, edges, cn, nn, neuropils, ann_src); run.lap("write_outputs", t0)
    extra = {"annotation_snapshot": {"version": cfg.build_version, **snap_meta},
             "count_rule": asdict(rule), "raw_partner_table": g,
             "inputs_v1_0": {k: {"sha256": acq10[k]["local_digests"]["sha256"], "generation": acq10[k]["remote_metadata"]["generation"]}
                             for k in needed10 if k in acq10},
             "neuprint_meta_v1_0": {k: meta.get(k) for k in ("uuid", "latestMutationId", "lastDatabaseEdit")}}
    return finalize(run, con, outputs=outputs, needed=needed, acq=acq, stats=stats, cov=cov, extra=extra, definitions=DEFINITIONS_V12)


def snapshot_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(16 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


__all__ = ["build", "build_v10", "build_v12", "CountRule", "DEFAULT_COUNT_RULE", "ANNOTATION_SNAPSHOTS", "MANC_V1_2", "PIPELINE_ID"]
