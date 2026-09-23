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
import time

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.feather as feather

from ..schema.vocab import (
    NT_VALUES,
    STATUS_LABEL_ORDER,
    STATUS_LABEL_TO_NEUPRINT_STATUS,
    UNASSIGNED_NEUROPIL,
    normalize_side,
)
from ..validation import INFO, PASS, WARN, ValidationReport
from .common import (
    NP_ID,
    BuildRun,
    IngestAborted,
    IngestConfig,
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

__all__ = ["IngestAborted", "IngestConfig", "build", "CRITICAL_CHECKS", "PIPELINE_ID", "PIPELINE_VERSION"]

log = logging.getLogger(__name__)

PIPELINE_ID = "brainir.ingest.malecns"
PIPELINE_VERSION = "1.0.0"
ANIMAL_SEX = "male"

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


CRITICAL_CHECKS = ("duplicates.annotations.bodyId", "duplicates.nt.body", "ids.annotations.non_null_positive",
                   "types.annotation_float_ids_integral",
                   "provenance.meta_dataset_tag", "provenance.acquisition_dataset", "provenance.raw_inputs_verified")

DEFINITIONS = {
    "neuron": "body with non-null superclass (Berg et al. Methods: 'Bodies in the dataset are defined as neurons if they "
              "have a superclass. Bodies without one are fragments of neurons.')",
    "synapse_count": "number of T-bar->PSD pairs (synaptic connections) with conf_pre>=0.5 and conf_post>=0.5; polyadic: "
                     "one T-bar can contribute several pairs. Equals neuPrint ConnectsTo.weight.",
    "synapse_count_hp": "subset with conf_post>=0.7 (neuPrint weightHP).",
    "edge_neuropil": "primary ROI containing the POSTsynaptic density (neuPrint convention).",
    "autapse": "pre_id == post_id; retained and flagged, not dropped.",
    "coordinates": "8 nm isotropic voxels in the MaleCNS EM space (voxelSize 8,8,8 nm).",
}




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



# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------
def build(cfg: IngestConfig) -> dict:
    run = BuildRun(cfg, PIPELINE_ID, PIPELINE_VERSION, CRITICAL_CHECKS)
    report = run.report
    needed = ["neuprint_meta_json", "body_annotations", "body_neurotransmitters", "neuprint_neurons",
              "neuprint_connections", "flat_connectome_weights"]
    if cfg.synapse_checks and cfg.raw_file("syn_partners").exists():
        needed.append("syn_partners")

    t0 = time.time(); acq = check_acquisition(cfg, report, needed); run.lap("acquisition_check", t0)
    t0 = time.time(); meta = load_meta(cfg, report); neuropils, primary = build_neuropils(meta, report); run.lap("meta_neuropils", t0)
    t0 = time.time(); ann, ann_src = load_annotations(cfg, report); run.lap("annotations", t0)
    t0 = time.time(); nt = load_nt(cfg, report); run.lap("neurotransmitters", t0)
    run.abort_if_critical("inputs")

    neuron_ids = np.sort(ann.loc[ann["superclass"].notna(), "bodyId"].astype("int64").to_numpy())
    report.add("rows.neurons", "ingestion", "Neurons = bodies with a superclass (source definition).", INFO, observed=int(len(neuron_ids)))
    report.expect_equal("ids.neurons.unique", "uniqueness", "Neuron IDs unique.", int(len(neuron_ids) - len(np.unique(neuron_ids))), 0)
    nt_missing = int((~np.isin(neuron_ids, nt["body"].to_numpy())).sum())
    report.add("coverage.neurons_without_nt_row", "coverage", "Neurons absent from the NT table (no T-bars => no prediction).",
               INFO, observed=nt_missing)

    con = _duck(cfg)
    t0 = time.time(); npn, np_stats = scan_neuprint_neurons(con, cfg, neuron_ids, report); run.lap("neuprint_neurons_scan", t0)
    missing_np = int((~np.isin(neuron_ids, npn["id"].to_numpy())).sum())
    report.add("referential.neurons_in_neuprint", "referential",
               "Neurons missing from the neuPrint segment table (non-synaptic bodies are not exported by neuPrint).",
               PASS if missing_np == 0 else WARN, observed=missing_np)
    t0 = time.time(); neuron_level_crosschecks(ann, nt, npn, report); run.lap("neuron_crosschecks", t0)
    t0 = time.time(); nn = parse_neuron_roiinfo(con, npn, primary, report); run.lap("neuron_neuropils", t0)
    t0 = time.time(); edges, cn, totals, g = scan_connections(con, cfg, neuron_ids, primary, report, meta); run.lap("connections", t0)
    _reg(con, "cn_all", cn)
    report.expect_equal("consistency.segment_totals_equal_edge_totals", "directionality",
                        "Sum over all segments of neuPrint 'downstream' and of 'upstream' each equal the total weight of the "
                        "connection table (conservation: every counted pair has an existing pre and post segment).",
                        [int(np_stats["sum_downstream"]), int(np_stats["sum_upstream"])], [g["sum_weight"], g["sum_weight"]])
    t0 = time.time(); crosscheck_flat_weights(con, cfg, report, g); run.lap("flat_crosscheck", t0)
    if cfg.synapse_checks:
        t0 = time.time(); synapse_checks(con, cfg, report, neuron_ids, meta, npn); run.lap("synapse_checks", t0)

    retained_graph_checks(edges, neuron_ids, report)

    t0 = time.time()
    neurons = assemble_neurons(cfg, ann, nt, npn, totals, edges)
    regions = dict(zip(neuropils.column("name").to_pylist(), neuropils.column("top_level_region").to_pylist()))
    directionality_checks(neurons, nn.to_pandas(), regions, report)
    stats = graph_statistics(edges, neuron_ids, report)
    cov = coverage(neurons, report)
    run.lap("assemble_validate", t0)

    t0 = time.time()
    outputs = write_outputs(run, neurons, edges, cn, nn, neuropils, ann_src)
    run.lap("write_outputs", t0)

    extra = {
        "neuprint_meta": {k: meta.get(k) for k in ("uuid", "latestMutationId", "lastDatabaseEdit", "totalPreCount",
                                                   "totalPostCount", "postHighAccuracyThreshold", "postHPThreshold")},
        "raw_connection_table": g, "neuprint_segment_stats": {k: int(v) for k, v in np_stats.items()},
    }
    return finalize(run, con, outputs=outputs, needed=needed, acq=acq, stats=stats, cov=cov, extra=extra,
                    definitions=DEFINITIONS)
