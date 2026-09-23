"""Generic ingestion machinery shared by all dataset adapters.

Everything here is source-agnostic: DuckDB session helpers, the acquisition-log check, the ROI catalogue builder
(neuPrint-style Meta dict), neuPrint-format roiInfo/connection scanning, graph statistics, directionality and
coverage checks, and the build/finalisation steps. Dataset adapters (:mod:`brainir.ingest.malecns`,
:mod:`brainir.ingest.manc`) provide the loaders and source-specific cross-checks and call into this module.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as pads
import pyarrow.parquet as pq
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components

from .. import __version__, paths
from ..io import write_canonical, write_parquet
from ..schema import tables as T
from ..schema.vocab import UNASSIGNED_NEUROPIL, role_class_for
from ..sources.registry import MALECNS_V1_0, DatasetSource
from ..validation import INFO, PASS, WARN, ValidationReport

log = logging.getLogger(__name__)

# raw column names of neuPrint-format inputs (MaleCNS and MANC v1.0 bulk exports share them) --------------------
NP_ID = ":ID(Body-ID)"
C_PRE, C_POST = ":START_ID(Body-ID)", ":END_ID(Body-ID)"


class IngestAborted(RuntimeError):
    """Raised when a critical integrity check fails and later steps would be meaningless.
    The validation report is written before raising."""

    def __init__(self, message: str, report: ValidationReport):
        super().__init__(message)
        self.report = report


@dataclass
class IngestConfig:
    source: DatasetSource = MALECNS_V1_0
    build_version: str | None = None
    """Version label of the processed build (default: source.version). MANC v1.2 raw data yield several builds
    (v1.2.1, v1.2.3) that differ in the annotation snapshot."""
    raw_dir: Path | None = None
    out_dir: Path | None = None
    verify_acquisition: bool = True
    synapse_checks: bool = True
    synapse_sample_neurons: int = 300
    seed: int = 20260922
    duckdb_memory_limit: str = "8GB"
    threads: int = 8
    extra_raw_dirs: dict[str, Path] = field(default_factory=dict)
    """Raw directories of *other* registered sources an adapter needs (key = '<dataset>:<version>'); defaults to
    the standard layout when absent."""
    options: dict = field(default_factory=dict)
    """Adapter-specific parameters (e.g. MANC v1.2 'count_rule'); recorded in build_info by the adapter."""

    @property
    def version(self) -> str:
        return self.build_version or self.source.version

    def raw(self) -> Path:
        return Path(self.raw_dir) if self.raw_dir else paths.raw_dir(self.source.dataset, self.source.version)

    def out(self) -> Path:
        return Path(self.out_dir) if self.out_dir else paths.processed_dir(self.source.dataset, self.version)

    def raw_file(self, key: str) -> Path:
        return self.raw() / self.source.local_relpath(self.source.file(key))

    def other_raw(self, source: DatasetSource) -> Path:
        k = f"{source.dataset}:{source.version}"
        return Path(self.extra_raw_dirs[k]) if k in self.extra_raw_dirs else paths.raw_dir(source.dataset, source.version)


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


# Source files whose content determines the processed outputs (hashed into build_info as a code fingerprint).
PIPELINE_SOURCES = ("ingest/common.py", "ingest/malecns.py", "ingest/manc.py", "io.py", "schema/tables.py",
                    "schema/vocab.py", "schema/evidence.py",
                    "sources/registry.py", "validation.py", "paths.py")


def _code_fingerprint() -> dict:
    """SHA-256 of each pipeline source file (LF-normalised) + a combined digest; exact even if git is dirty."""
    import hashlib

    base = Path(__file__).resolve().parents[1]
    files = {rel: hashlib.sha256((base / rel).read_bytes().replace(b"\r\n", b"\n")).hexdigest() for rel in PIPELINE_SOURCES}
    combined = hashlib.sha256("".join(f"{k}:{v}\n" for k, v in sorted(files.items())).encode()).hexdigest()
    return {"combined_sha256": combined, "files": files}


def _git_state() -> dict:
    root = paths.repo_root()
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "src"], cwd=root, capture_output=True,
                                    text=True, check=True).stdout.strip())
        return {"commit": commit, "src_dirty": dirty, "pipeline_code": _code_fingerprint()}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "src_dirty": None, "pipeline_code": _code_fingerprint()}


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
def check_acquisition(cfg: IngestConfig, report: ValidationReport, needed: list[str], *, source: DatasetSource | None = None,
                      raw_dir: Path | None = None, suffix: str = "") -> dict:
    """Verify that every needed raw file of ``source`` (default: the build's source) is on disk with the pinned size and
    that the acquisition log's checksums match the registry pins. ``suffix`` distinguishes secondary sources' checks."""
    source = source or cfg.source
    raw_dir = raw_dir or (cfg.raw() if source is cfg.source else cfg.other_raw(source))
    log_path = raw_dir / "_acquisition.json"
    if not cfg.verify_acquisition:
        report.add("provenance.acquisition_log" + suffix, "provenance",
                   "Acquisition log verification skipped (fixture/test mode).", INFO)
        return {}
    if not log_path.exists():
        raise FileNotFoundError(f"{log_path} not found: acquire the raw data first (`uv run brainir acquire --dataset "
                                f"{source.dataset} --version {source.version} --tier metadata --tier core --tier synapses`)")
    acq = json.loads(log_path.read_text())
    report.expect_equal("provenance.acquisition_dataset" + suffix, "provenance",
                        "Acquisition log dataset/version match the registry.",
                        [acq["dataset"], acq["version"]], [source.dataset, source.version])
    recs = {r["key"]: r for r in acq["files"]}
    problems = {}
    for key in needed:
        f = source.file(key)
        r = recs.get(key)
        path = raw_dir / source.local_relpath(f)
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
    report.expect_true("provenance.raw_inputs_verified" + suffix, "provenance",
                       "Every raw input exists, has the pinned size, and its recorded checksums match registry pins "
                       "(CRC32C for all, MD5 where available, GCS generation).",
                       not problems, observed=problems or "all ok", inputs=needed)
    return recs


def build_neuropils(meta: dict, report: ValidationReport, parent_aliases: dict[str, str] | None = None,
                    nerve_rois: set[str] | None = None, *, hierarchy_authoritative: bool = True,
                    region_override: str | None = None) -> tuple[pa.Table, list[str]]:
    """ROI catalogue. The neuPrint hierarchy is a DAG (some ROIs have two parents), so rows are keyed by name,
    with the authoritative single parent taken from roiInfo['parent'] and all parents listed.

    ``parent_aliases`` maps misspelt roiInfo parents to their hierarchy name (a documented source typo, e.g. MANC
    v1.0 'ventral nerve core'); ``nerve_rois`` marks nerves when roiInfo lacks an 'isNerve' flag (MANC).
    ``hierarchy_authoritative=False`` (MANC v1.0): the Meta roiHierarchy is known to be inconsistent with
    roiInfo/primaryRois (it lists 'IntNp(T*)'/'AMNp' instead of 'LegNp(T*)'/'Ov'); roiInfo + primaryRois define the
    catalogue, hierarchy-only names are reported and dropped, and primary ROIs missing from the hierarchy are a
    documented WARN instead of a failure. ``region_override`` sets top_level_region for every ROI (VNC-only volumes)."""
    parent_aliases = parent_aliases or {}
    nerve_rois = nerve_rois or set()
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
    def ri_parent(n):
        p = ri.get(n, {}).get("parent")
        return parent_aliases.get(p, p) if p else p

    aliased = sorted({ri[n]["parent"] for n in ri if ri[n].get("parent") in parent_aliases})
    if aliased:
        report.add("neuropils.roiinfo_parent_aliases", "referential",
                   "roiInfo 'parent' values that are misspellings of hierarchy names in the source (mapped by alias).", INFO,
                   observed={a: parent_aliases[a] for a in aliased})
    bad_parent = {n: [ri_parent(n), sorted({p for p, _, _ in o if p})] for n, o in occ.items()
                  if n in ri and ri_parent(n) and ri_parent(n) not in {p for p, _, _ in o}}
    report.expect_true("neuropils.roiinfo_parent_consistent", "referential",
                       "The roiInfo 'parent' of each ROI is one of its hierarchy parents.", not bad_parent,
                       observed=bad_parent)
    in_h = set(occ)
    missing_primary = sorted(set(primary) - in_h)
    if hierarchy_authoritative:
        report.expect_true("referential.primary_rois_in_hierarchy", "referential", "All primary ROIs exist in the ROI hierarchy.",
                           not missing_primary, observed=missing_primary)
    else:
        hier_only = sorted(in_h - set(ri) - {meta["roiHierarchy"].get("name")})
        report.add("referential.primary_rois_in_hierarchy", "referential",
                   "Primary ROIs absent from the source roiHierarchy, and hierarchy names without roiInfo statistics. Known "
                   "source inconsistency (stale hierarchy); roiInfo/primaryRois are taken as authoritative and hierarchy-only "
                   "names are not included in the catalogue.", WARN if missing_primary or hier_only else PASS,
                   observed={"primary_not_in_hierarchy": missing_primary, "hierarchy_only": hier_only})
        in_h = in_h & set(ri)
        occ = {k: v for k, v in occ.items() if k in in_h}
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
        auth_parent = ri_parent(n) or (o[0][0] if o else None)
        tops = [t for _, _, t in o if t]
        rows.append({
            "name": n, "parent": auth_parent, "all_parents": parents or None,
            "depth": min(d for _, d, _ in o) if o else None, "in_hierarchy": bool(o),
            "top_level_region": region_override or (tops[0] if tops else None), "is_primary": n in prim,
            "is_nerve": bool(ri.get(n, {}).get("isNerve", False)) or n in nerve_rois, "side": _side_suffix(n),
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
                     meta: dict, *, hr_equals_weight: bool = True,
                     weight_sum_equals_total_post: bool = True) -> tuple[pa.Table, pa.Table, pd.DataFrame, dict]:
    """neuPrint-format :ConnectsTo table -> neuron->neuron edges, per-edge neuropils, per-neuron totals, raw stats.

    ``hr_equals_weight``: the source pre-filtered synapses so that the high-recall tier adds nothing (MaleCNS).
    ``weight_sum_equals_total_post``: every PSD counted in Meta.totalPostCount is in some pair (MaleCNS); false when
    the Meta totals count unfiltered synapses (MANC v1.0)."""
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
               count(*) FILTER (WHERE "weightHR:int" < "weight:int") AS n_hr_lt_weight,
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
    if hr_equals_weight:
        report.expect_equal("edge_values.no_zero_weight", "edge_values",
                            "No connection rows with weight 0 (would indicate sub-threshold-only pairs).", g["n_weight_zero"], 0,
                            on_mismatch=WARN)
    else:
        report.add("edge_values.zero_weight_rows", "edge_values",
                   "Connection rows with weight 0 (pairs supported only by synapses below the database confidence threshold; "
                   "weightHR > 0). Expected for sources that keep a high-recall tier.", INFO, observed=g["n_weight_zero"])
    report.expect_equal("edge_values.hp_le_weight", "edge_values", "weightHP <= weight for every row.", g["n_hp_gt_weight"], 0)
    if hr_equals_weight:
        report.add("edge_values.weight_hr_equals_weight", "edge_values",
                   "weightHR == weight everywhere (expected: synapses were pre-filtered at conf>=0.5, so the "
                   "'high-recall' tier adds nothing; BrainIR therefore does not store weightHR).",
                   PASS if g["n_hr_ne_weight"] == 0 else WARN, observed=g["n_hr_ne_weight"], expected=0)
    else:
        report.expect_equal("edge_values.weight_hr_ge_weight", "edge_values",
                            "weightHR >= weight for every row (the high-recall tier adds lower-confidence synapses; "
                            "BrainIR stores weight and weightHP only).", g["n_hr_lt_weight"], 0)
        report.add("edge_values.weight_hr_summary", "edge_values",
                   "Rows where weightHR differs from weight, and the two totals.", INFO,
                   observed={"rows_hr_ne_weight": g["n_hr_ne_weight"], "sum_weight": g["sum_weight"],
                             "sum_weight_hr": g["sum_weight_hr"]})
    if weight_sum_equals_total_post:
        report.expect_equal("consistency.total_weight_equals_psds", "cross_source",
                            "Sum of all connection weights equals neuPrint totalPostCount (every PSD in exactly one pair).",
                            g["sum_weight"], int(meta["totalPostCount"]), on_mismatch=WARN)
    else:
        report.expect_equal("consistency.total_weight_equals_psds", "cross_source",
                            "Sum of connection weights equals neuPrint totalPostCount (the Meta counts PSDs above the database "
                            "confidence threshold; the high-recall total is larger).",
                            g["sum_weight"], int(meta["totalPostCount"]), on_mismatch=WARN, sum_weight_hr=g["sum_weight_hr"])
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
               c."weightHR:int" AS whr, c."roiInfo:string" AS ri
        FROM np_conn c SEMI JOIN nid a ON c."{C_PRE}" = a.id SEMI JOIN nid b ON c."{C_POST}" = b.id""")
    if not hr_equals_weight:
        # neuPrint keeps a row for pairs supported only by low-confidence synapses (weight 0, weightHR > 0). Under the
        # 'weight' definition of synapse_count they are not connections; they are counted here and dropped.
        n_zero = con.execute("SELECT count(*) FROM e WHERE w = 0").fetchone()[0]
        con.execute("CREATE OR REPLACE TEMP TABLE e_all AS SELECT pre_id, post_id, w, whp, whr FROM e")  # incl. HR-only pairs
        con.execute("DELETE FROM e WHERE w = 0")
        report.add("rows.connections_zero_weight_dropped", "ingestion",
                   "Neuron->neuron pairs whose neuPrint weight is 0 (only high-recall/low-confidence synapses); excluded "
                   "from connections because synapse_count follows neuPrint 'weight'.", INFO, observed=int(n_zero))
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


def directionality_checks(neurons: pd.DataFrame, nn: pd.DataFrame, regions: dict[str, str], report: ValidationReport,
                          vnc_regions: frozenset[str] = frozenset({"VNC"})) -> None:
    """Exact conservation check plus biological polarity sanity checks expressed in role classes (ROLE_RULE_ID)."""
    # 1) exact: summing edge weights over all partners reproduces the source's per-neuron downstream/upstream
    has = neurons["n_downstream"].notna()
    d_out = int((neurons.loc[has, "out_all"] != neurons.loc[has, "n_downstream"]).sum())
    d_in = int((neurons.loc[has, "in_all"] != neurons.loc[has, "n_upstream"]).sum())
    report.expect_equal("directionality.edge_sums_match_neuron_totals", "directionality",
                        "For every neuron, sum of outgoing edge weights (all partners) == source 'downstream' and incoming "
                        "== 'upstream'. A pre/post swap anywhere would break this.", [d_out, d_in], [0, 0])
    roles = neurons["super_class"].map(role_class_for)
    # 2) biological sanity: descending neurons output (T-bars) more in the VNC than they receive there; ascending the
    #    reverse. Only meaningful when the volume also contains non-VNC regions (whole-CNS datasets).
    region_of = {k: ("VNC" if v in vnc_regions else v) for k, v in regions.items()}
    has_non_vnc = any(v != "VNC" for v in region_of.values())
    nn2 = nn.assign(region=nn["neuropil"].map(region_of).fillna("<unassigned>"))
    by = nn2.groupby(["source_id", "region"])[["n_pre", "n_post"]].sum().unstack(fill_value=0)
    frac_pre_vnc = by["n_pre"].get("VNC", 0) / by["n_pre"].sum(axis=1).replace(0, np.nan)
    frac_post_vnc = by["n_post"].get("VNC", 0) / by["n_post"].sum(axis=1).replace(0, np.nan)
    res = {}
    for role, expect_out_in_vnc in (("descending", True), ("ascending", False)):
        ids_sc = neurons.loc[roles == role, "source_id"]
        a = frac_pre_vnc.reindex(ids_sc).dropna()
        b = frac_post_vnc.reindex(ids_sc).dropna()
        common = a.index.intersection(b.index)
        ok_frac = float(((a[common] > b[common]) == expect_out_in_vnc).mean()) if len(common) else None
        res[role] = {"n": int(len(common)), "median_frac_pre_in_vnc": float(a.median()) if len(a) else None,
                     "median_frac_post_in_vnc": float(b.median()) if len(b) else None,
                     "fraction_consistent": ok_frac}
    if has_non_vnc:
        ok = all(v["fraction_consistent"] is not None and v["fraction_consistent"] > 0.8 for v in res.values())
        report.add("directionality.dn_an_polarity", "directionality",
                   "Biological polarity sanity check: descending neurons have relatively more output (T-bars) than input in "
                   "the VNC; ascending neurons the reverse (fraction of neurons consistent, expected > 0.8).",
                   PASS if ok else WARN, observed=res)
    else:
        # VNC-only volume: descending neurons are outputs of the volume (their somata and inputs are in the brain).
        # Ascending neurons carry NO expectation here: in MANC v1.0 most ANs are output-dominated inside the VNC
        # (median output fraction 0.60), so they are reported for information only.
        out_frac = (neurons["n_downstream"] / (neurons["n_downstream"] + neurons["n_upstream"]).replace(0, np.nan))
        obs = {}
        for role, expect_out in (("descending", True), ("ascending", None)):
            r = out_frac[roles == role].dropna()
            obs[role] = {"n": int(len(r)), "median_output_fraction": float(r.median()) if len(r) else None,
                         "fraction_output_dominated": float((r > 0.5).mean()) if len(r) else None,
                         "expectation": "output_dominated" if expect_out else "none (informational)"}
        d = obs["descending"]
        ok = d["n"] < 10 or (d["fraction_output_dominated"] is not None and d["fraction_output_dominated"] > 0.8)
        report.add("directionality.dn_an_polarity", "directionality",
                   "VNC-only volume: descending neurons are output-dominated (fraction of synaptic connections that are "
                   "outgoing > 0.5 for > 80% of DNs; judged only with >= 10 DNs). Ascending neurons: informational.",
                   PASS if ok else WARN, observed=obs)
    # 3) sensory neurons are output-dominated, motor neurons input-dominated
    ratio = {}
    for role in ("vnc_sensory", "cb_sensory", "ol_sensory", "vnc_motor", "cb_motor"):
        sub = neurons[roles == role]
        if len(sub) == 0:
            continue
        r = (sub["n_downstream"] / (sub["n_downstream"] + sub["n_upstream"]).replace(0, np.nan)).dropna()
        ratio[role] = {"n": int(len(r)), "median_output_fraction": float(r.median())}
    ok2 = all((v["median_output_fraction"] > 0.5) == (k.endswith("sensory")) for k, v in ratio.items())
    report.add("directionality.sensory_motor_polarity", "directionality",
               "Sensory neurons are output-dominated (median output fraction > 0.5) and motor neurons input-dominated "
               "(roles from ROLE_RULE_ID).",
               PASS if ok2 else WARN, observed=ratio)


def coverage(neurons: pd.DataFrame, report: ValidationReport) -> dict:
    fields = ["cell_type", "instance", "cell_class", "sub_class", "hemilineage_ito_lee", "hemilineage_truman", "side",
              "soma_neuromere", "soma_x", "nt_consensus", "nt_literature_label", "group_id", "flywire_type",
              "manc_type", "hemibrain_type", "synonyms"]
    cov = {f: round(float(neurons[f].notna().mean()), 4) for f in fields}
    cov["nt_consensus_not_unclear"] = round(float((neurons["nt_consensus"].notna() & (neurons["nt_consensus"] != "unclear")).mean()), 4)
    traced = neurons["is_traced"].dropna()
    cov["is_traced"] = round(float(traced.astype(bool).mean()), 4) if len(traced) else None  # null when the source has no status
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
# build orchestration helpers shared by the adapters
# ---------------------------------------------------------------------------
class BuildRun:
    """Timing, critical-abort and output bookkeeping for one build."""

    def __init__(self, cfg: IngestConfig, pipeline_id: str, pipeline_version: str, critical_checks: tuple[str, ...]):
        self.cfg = cfg
        self.pipeline_id, self.pipeline_version = pipeline_id, pipeline_version
        self.critical_checks = critical_checks
        self.t_start = time.time()
        self.timings: dict[str, float] = {}
        self.out = cfg.out()
        self.out.mkdir(parents=True, exist_ok=True)
        self.report = ValidationReport(title=f"BrainIR ingestion validation - {cfg.source.dataset}:{cfg.version}")

    def abort_if_critical(self, stage: str) -> None:
        bad = [c.check_id for c in self.report.failures if c.check_id in self.critical_checks]
        if bad:
            self.report.context = {"aborted_at": stage, "critical_failures": bad}
            self.report.write(self.out / "validation_report.json", self.out / "validation_report.md")
            raise IngestAborted(f"critical validation failures at {stage}: {bad}", self.report)

    def lap(self, name: str, t0: float) -> None:
        self.timings[name] = round(time.time() - t0, 2)
        log.info("step %-28s %8.1fs", name, self.timings[name])


def retained_graph_checks(edges: pa.Table, neuron_ids: np.ndarray, report: ValidationReport) -> None:
    """Referential integrity and value checks of the neuron->neuron graph that will be written."""
    ep = edges.column("pre_id").to_numpy(); eq = edges.column("post_id").to_numpy()
    report.expect_equal("referential.edges_reference_neurons", "referential", "Every edge endpoint is a neuron.",
                        int((~np.isin(ep, neuron_ids)).sum() + (~np.isin(eq, neuron_ids)).sum()), 0)
    w = edges.column("synapse_count").to_numpy()
    report.expect_equal("edge_values.connections_positive", "edge_values", "All retained edges have synapse_count >= 1.",
                        int((w < 1).sum()), 0)
    hp = edges.column("synapse_count_hp").to_numpy()
    report.expect_equal("edge_values.connections_hp_le_count", "edge_values", "synapse_count_hp <= synapse_count.",
                        int((hp > w).sum()), 0)


def write_outputs(run: BuildRun, neurons: pd.DataFrame, edges: pa.Table, cn: pa.Table, nn: pa.Table, neuropils: pa.Table,
                  ann_src: pa.Table, ann_sort_key: str = "bodyId") -> dict:
    """Write the canonical tables deterministically (see brainir.io) and the verbatim annotation copy."""
    cfg, out = run.cfg, run.out
    common_md = {"brainir_dataset": cfg.source.dataset, "brainir_dataset_version": cfg.version,
                 "brainir_pipeline": f"{run.pipeline_id}@{run.pipeline_version}"}
    outputs = {}
    ncols = T.NEURONS.column_names
    outputs["neurons"] = write_canonical(pa.Table.from_pandas(neurons[ncols], preserve_index=False), T.NEURONS,
                                         out / "neurons.parquet", common_md)
    outputs["connections"] = write_canonical(edges, T.CONNECTIONS, out / "connections.parquet", common_md)
    outputs["connection_neuropils"] = write_canonical(cn, T.CONNECTION_NEUROPILS, out / "connection_neuropils.parquet", common_md)
    outputs["neuron_neuropils"] = write_canonical(nn, T.NEURON_NEUROPILS, out / "neuron_neuropils.parquet", common_md)
    outputs["neuropils"] = write_canonical(neuropils, T.NEUROPILS, out / "neuropils.parquet", common_md)
    ann_sorted = ann_src.take(pc.sort_indices(ann_src, [(ann_sort_key, "ascending")]))
    outputs[T.NEURON_ANNOTATIONS_SOURCE] = write_parquet(
        ann_sorted.replace_schema_metadata({"brainir_table": T.NEURON_ANNOTATIONS_SOURCE, **common_md}),
        out / f"{T.NEURON_ANNOTATIONS_SOURCE}.parquet")
    return outputs


def finalize(run: BuildRun, con, *, outputs: dict, needed: list[str], acq: dict, stats: dict, cov: dict,
             extra: dict, definitions: dict) -> dict:
    """Post-write schema conformance, build_info.json, validation report; returns the build result dict."""
    cfg, out, report = run.cfg, run.out, run.report
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
        "pipeline": run.pipeline_id, "pipeline_version": run.pipeline_version, "brainir_version": __version__,
        "schema_version": T.SCHEMA_VERSION, "dataset": cfg.source.dataset, "version": cfg.version,
        "source_version": cfg.source.version,
        "config": {"synapse_checks": cfg.synapse_checks, "synapse_sample_neurons": cfg.synapse_sample_neurons,
                   "seed": cfg.seed},
        "git": _git_state(),
        "environment": {"python": sys.version.split()[0], "platform": platform.platform(),
                        "pyarrow": pa.__version__, "pandas": pd.__version__, "duckdb": duckdb.__version__,
                        "numpy": np.__version__},
        "timings_s": run.timings, "total_s": round(time.time() - run.t_start, 1),
        "inputs": {k: {"sha256": acq[k]["local_digests"]["sha256"], "generation": acq[k]["remote_metadata"]["generation"]}
                   for k in needed if k in acq},
        "outputs": outputs, "graph_statistics": stats, "coverage": cov, "validation_summary": summary,
        "definitions": definitions,
        **extra,
    }
    report.context = {"dataset": cfg.source.dataset, "version": cfg.version,
                      "pipeline": f"{run.pipeline_id}@{run.pipeline_version}", "git": build_info["git"]}
    report.write(out / "validation_report.json", out / "validation_report.md")
    (out / "build_info.json").write_text(json.dumps(build_info, indent=2, default=str) + "\n", encoding="utf-8",
                                         newline="\n")
    con.close()
    shutil.rmtree(paths.cache_dir() / "duckdb_tmp" / f"pid{os.getpid()}", ignore_errors=True)
    log.info("validation summary: %s", summary)
    return {"report": report, "build_info": build_info, "out_dir": out}
