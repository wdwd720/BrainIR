"""Synthetic MANC-shaped raw files derived from the same hand-derived synapse list as the MaleCNS fixture.

The seven neurons, their synapses and the expected canonical outputs are those of :mod:`brainir.testing.synthetic`
(EXPECTED_EDGES, EXPECTED_EDGE_NEUROPILS, EXPECTED_TOTALS), rendered in the MANC formats:

* ``manc:v1.0``  neuPrint bulk export (Meta feather, per-body property feather, neuPrint neuron/connection tables,
  traced-adjacency CSVs, bzip2 partner table). MANC-specific twists exercised on purpose:
  - two extra LOW-CONFIDENCE synapses (``LOWCONF``) that neuPrint counts in ``weightHR`` but not in ``weight``;
    one of them creates a pair with weight 0 (HR-only row) that must be dropped;
  - body 107 is ``RT Orphan`` in the property export but ``Traced`` in the neuPrint table (status remap);
  - literal ``'None'`` placeholders, MANC side labels (``RHS``/``LHS``), classes with spaces;
  - a stale ROI hierarchy (lists ``IntNp(T1)(L)`` instead of ``LegNp(T1)(L)``) and the ``'ventral nerve core'`` typo.
* ``manc:v1.2``  partner feather (same synapses) + annotation snapshots v1.2.1 / v1.2.3 (segment_properties JSON),
  built together with the v1.0 raw directory (ROI catalogue, carried NT).
"""

from __future__ import annotations

import bz2
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.feather as feather

from ..sources.registry import MANC_V1_0, MANC_V1_2
from . import synthetic as S

# (pre, post, PSD ROI, conf_pre, conf_post): counted by weightHR only (conf_post < 0.4, the MANC 'weight' threshold)
LOWCONF = [(104, 105, "LegNp(T1)(L)", 0.9, 0.30), (101, 102, "LegNp(T1)(L)", 0.9, 0.35)]
COUNT_RULE = dict(conf_pre_min=0.0, conf_post_min=0.4, hp_conf_pre_min=0.0, hp_conf_post_min=0.7)

MANC_CLASS = {"descending_neuron": "descending neuron", "vnc_intrinsic": "intrinsic neuron", "vnc_motor": "motor neuron",
              "vnc_sensory": "sensory neuron", "ascending_neuron": "ascending neuron", "cb_intrinsic": "intrinsic neuron"}
SIDE = {"L": "LHS", "R": "RHS", None: None}
# body: (predictedNt, [ACh, GABA, Glu, unknown] probabilities); None -> no prediction
MANC_NT = {101: ("acetylcholine", [0.90, 0.04, 0.05, 0.01]), 102: ("gaba", [0.10, 0.80, 0.08, 0.02]),
           103: ("glutamate", [0.10, 0.20, 0.70, 0.00]), 105: ("acetylcholine", [0.95, 0.02, 0.02, 0.01]),
           106: ("unknown", [0.20, 0.20, 0.20, 0.40]), 900: ("gaba", [0.1, 0.6, 0.2, 0.1])}
# body 107: neuPrint status Traced / statusLabel 'RT Orphan'; property export status 'RT Orphan'
PROPS_STATUS_OVERRIDE = {107: ("RT Orphan", "RT Orphan")}
NP_STATUS_OVERRIDE = {107: ("Traced", "RT Orphan")}

# MANC v1.0 expectations that differ from the MaleCNS fixture
EXPECTED_N_PRE_V10 = {101: 5, 102: 3, 103: 2, 104: 1, 105: 1, 106: 2, 107: 1}   # T-bars with conf_pre >= 0.5 (incl. the two LOWCONF T-bars)
EXPECTED_N_PRE_V12 = {101: 4, 102: 3, 103: 2, 104: 0, 105: 1, 106: 2, 107: 1}   # T-bars with a counted partner pair
EXPECTED_HR_ONLY_PAIRS = 1                                                     # (104, 105)
EXPECTED_V123_TYPE_PLACEHOLDER = 104                                            # type '~' -> null in v1.2.3


def _all_synapses() -> list[dict]:
    rows = S._synapses()
    tb = max(r["tb"] for r in rows) + 1
    for k, (pre, post, proi, cpre, cpost) in enumerate(LOWCONF):
        i = tb + k
        rows.append(dict(tb=i, pre=pre, troi=proi, cpre=cpre, xp=1000 + i, yp=2000 + i, zp=3000 + i, post=post, proi=proi,
                         cpost=cpost, xq=5900 + k, yq=6900 + k, zq=7900 + k))
    return rows


def _counted(s: dict) -> bool:
    return s["cpre"] >= COUNT_RULE["conf_pre_min"] and s["cpost"] >= COUNT_RULE["conf_post_min"]


def _hp(s: dict) -> bool:
    return float(np.float32(s["cpost"])) >= COUNT_RULE["hp_conf_post_min"]  # float32 storage, float64 comparison


def _partner_table(syn: list[dict]) -> pa.Table:
    cols = defaultdict(list)
    for s in syn:
        for k, v in (("x_pre", s["xp"]), ("y_pre", s["yp"]), ("z_pre", s["zp"]), ("conf_pre", s["cpre"]), ("body_pre", s["pre"]),
                     ("x_post", s["xq"]), ("y_post", s["yq"]), ("z_post", s["zq"]), ("conf_post", s["cpost"]),
                     ("body_post", s["post"])):
            cols[k].append(v)
        p = S.primary_of(s["proi"])
        cols["roi_post"].append(None if p == S.UNSPEC else p)
    t = pa.table({k: pa.array(v, pa.int32() if k[0] in "xyz" else pa.uint64() if k.startswith("body") else
                              pa.float32() if k.startswith("conf") else pa.string()) for k, v in cols.items()})
    idx = t.schema.get_field_index("roi_post")
    return t.set_column(idx, "roi_post", t.column("roi_post").dictionary_encode().cast(pa.dictionary(pa.int8(), pa.string())))


def _per_body(syn: list[dict]) -> tuple[dict, dict]:
    """neuPrint-style per-body counts (pre = T-bars with conf_pre >= 0.5; others under the count rule) and per-ROI roiInfo."""
    per = defaultdict(Counter)
    per_roi = defaultdict(lambda: defaultdict(Counter))
    seen = set()
    for s in syn:
        a, b = s["pre"], s["post"]
        if s["tb"] not in seen and s["cpre"] >= 0.5:
            seen.add(s["tb"])
            per[a]["pre"] += 1
            for r in S.roi_path(s["troi"]):
                per_roi[a][r]["pre"] += 1
        if not _counted(s):
            continue
        per[a]["downstream"] += 1
        per[b]["upstream"] += 1
        per[b]["post"] += 1
        for r in S.roi_path(s["troi"]):
            per_roi[a][r]["downstream"] += 1
        for r in S.roi_path(s["proi"]):
            per_roi[b][r]["upstream"] += 1
            per_roi[b][r]["post"] += 1
    return per, per_roi


def write_manc_v10_fixture(raw_dir: Path) -> Path:
    src = MANC_V1_0
    raw_dir = Path(raw_dir)

    def p(key):
        out = raw_dir / src.local_relpath(src.file(key))
        out.parent.mkdir(parents=True, exist_ok=True)
        return out

    syn = _all_synapses()
    bodies = sorted({s["pre"] for s in syn} | {s["post"] for s in syn})
    per, per_roi = _per_body(syn)

    # ---- Meta (one-row feather with neo4j-typed column names) ----
    roi_pre, roi_post = Counter(), Counter()
    for s in syn:
        if s["tb"] not in roi_pre or True:
            pass
    tb_seen = set()
    for s in syn:
        if s["tb"] not in tb_seen:
            tb_seen.add(s["tb"])
            for r in S.roi_path(s["troi"]):
                roi_pre[r] += 1
        for r in S.roi_path(s["proi"]):
            roi_post[r] += 1
    roi_info = {r: {"showHierarchy": True, "isPrimary": r in S.PRIMARY, "hasROI": True, "description": r,
                    "parent": "ventral nerve core", "pre": roi_pre.get(r, 0), "post": roi_post.get(r, 0)}
                for r in S.PARENT if r not in ("CNS", "CentralBrain", "VNC")}
    # stale hierarchy: 'IntNp(T1)(L)' instead of 'LegNp(T1)(L)' (as in the real v1.0 Meta)
    hier_children = [{"name": ("IntNp(T1)(L)" if r == "LegNp(T1)(L)" else r)} for r in roi_info]
    meta = {
        "tag:string": "v1.0", "dataset:string": "manc", "uuid:string": "synthetic", "latestMutationId:int": 1,
        "lastDatabaseEdit:string": "synthetic", "totalPreCount:int": len(tb_seen),
        "totalPostCount:int": sum(1 for s in syn if _counted(s)),  # neuPrint Meta counts PSDs above the database threshold
        "postHighAccuracyThreshold:float": 0.4, "preHPThreshold:float": 0.7, "postHPThreshold:float": 0.7,
        "primaryRois:string[]": ";".join(S.PRIMARY), "superLevelRois:string[]": ";".join(S.PRIMARY),
        "roiHierarchy:string": json.dumps({"name": "ventral nerve cord", "children": hier_children}),
        "roiInfo:string": json.dumps(roi_info), "nerveRois:string": json.dumps(["GNG"]),
        "neuropilRois:string": json.dumps([r for r in S.PRIMARY if r != "GNG"]), "voxelSize:float[]": "8.0;8.0;8.0",
        ":LABEL": "Meta;manc_Meta",
    }
    feather.write_feather(pa.table({k: pa.array([v], pa.int64() if k.endswith(":int") else pa.float64() if k.endswith(":float")
                                                 else pa.string()) for k, v in meta.items()}), p("neuprint_meta"))
    (p("neuprint_all_rois")).write_text("\n".join(S.PRIMARY) + "\n", encoding="utf-8")
    (p("neuprint_readme")).write_text("synthetic\n", encoding="utf-8")
    (p("traced_readme")).write_text("synthetic\n", encoding="utf-8")

    # ---- per-body property export (all :Neuron bodies = annotated neurons + fragment 900) ----
    prop_rows = []
    for b in [*S.NEURON_ANN, 900]:
        ann = S.NEURON_ANN.get(b)
        typ, sc, _cls, ss, rs, sl, st, thl, _ihl, neu, soma = ann if ann else (None,) * 11
        if b == 900:
            sl, st = "Orphan", "Orphan"
        if b in PROPS_STATUS_OVERRIDE:
            st, sl = PROPS_STATUS_OVERRIDE[b]
        nt = MANC_NT.get(b)
        c = per[b]
        prop_rows.append({
            "bodyId": b, "instance": f"{typ}_{'T1' if neu == 'T1' else 'x'}_{(ss or rs or 'M')}" if typ else None, "type": typ,
            "pre": c["pre"], "post": c["post"], "downstream": c["downstream"], "upstream": c["upstream"], "size": 1000 * b,
            "status": st, "cropped": False, "statusLabel": sl, "somaLocation": soma,
            "ntGabaProb": nt[1][1] if nt else None, "ntAcetylcholineProb": nt[1][0] if nt else None,
            "ntGlutamateProb": nt[1][2] if nt else None, "ntUnknownProb": nt[1][3] if nt else None,
            "predictedNtProb": max(nt[1]) if nt else None, "predictedNt": nt[0] if nt else None,
            "class": MANC_CLASS.get(sc) if sc else None, "subclass": None,
            "hemilineage": (thl if thl else ("None" if b == 104 else None)), "somaSide": SIDE.get(ss), "rootSide": SIDE.get(rs),
            "somaNeuromere": neu if neu else ("None" if b == 105 else None), "group": float(b) if ann else None,
            "serial": None, "subcluster": None, "synonyms": None, "entryNerve": None, "exitNerve": None, "birthtime": None,
            "longTract": None, "origin": None, "target": None, "modality": None, "transmission": None, "receptorType": None,
            "roiInfo": {"n": len(per_roi[b])},
        })
    schema = pa.schema([
        ("bodyId", pa.int64()), ("instance", pa.string()), ("type", pa.string()), ("pre", pa.int64()), ("post", pa.int64()),
        ("downstream", pa.int64()), ("upstream", pa.int64()), ("size", pa.int64()), ("status", pa.string()), ("cropped", pa.bool_()),
        ("statusLabel", pa.string()), ("somaLocation", pa.list_(pa.int64())), ("ntGabaProb", pa.float64()),
        ("ntAcetylcholineProb", pa.float64()), ("ntGlutamateProb", pa.float64()), ("ntUnknownProb", pa.float64()),
        ("predictedNtProb", pa.float64()), ("predictedNt", pa.string()), ("class", pa.string()), ("subclass", pa.string()),
        ("hemilineage", pa.string()), ("somaSide", pa.string()), ("rootSide", pa.string()), ("somaNeuromere", pa.string()),
        ("group", pa.float64()), ("serial", pa.float64()), ("subcluster", pa.float64()), ("synonyms", pa.string()),
        ("entryNerve", pa.string()), ("exitNerve", pa.string()), ("birthtime", pa.string()), ("longTract", pa.string()),
        ("origin", pa.string()), ("target", pa.string()), ("modality", pa.string()), ("transmission", pa.string()),
        ("receptorType", pa.string()), ("roiInfo", pa.struct([("n", pa.int64())]))])
    feather.write_feather(pa.Table.from_pylist(prop_rows, schema=schema), p("neuron_properties"))
    props = {r["bodyId"]: r for r in prop_rows}

    # ---- neuPrint neuron table (segments) ----
    nrows = []
    for b in bodies:
        c = per[b]
        ri = {}
        for r, cc in sorted(per_roi[b].items()):
            d = {k: v for k, v in cc.items() if v}
            if d.get("downstream", 0) or d.get("upstream", 0):
                d["synweight"] = d.get("downstream", 0) + d.get("upstream", 0)
            ri[r] = d
        a = props.get(b, {})
        st, sl = a.get("status"), a.get("statusLabel")
        if b in NP_STATUS_OVERRIDE:
            st, sl = NP_STATUS_OVERRIDE[b]
        label = "Segment;manc_Segment" + (";Neuron;manc_Neuron" if b in props else "")
        nrows.append({
            ":ID(Body-ID)": b, "bodyId:long": b, "pre:int": c["pre"], "post:int": c["post"], "upstream:int": c["upstream"],
            "downstream:int": c["downstream"], "synweight:int": c["downstream"] + c["upstream"], "status:string": st,
            "statusLabel:string": sl, "cropped:boolean": False, "instance:string": a.get("instance"), "synonyms:string": None,
            "type:string": a.get("type"), "hemilineage:string": a.get("hemilineage"), "somaSide:string": a.get("somaSide"),
            "class:string": a.get("class"), "subclass:string": a.get("subclass"), "group:int": a.get("group"),
            "serial:int": None, "rootSide:string": a.get("rootSide"), "somaNeuromere:string": a.get("somaNeuromere"),
            "size:long": 1000 * b, "predictedNtProb:float": a.get("predictedNtProb"), "predictedNt:string": a.get("predictedNt"),
            "roiInfo:string": json.dumps(ri), ":LABEL": label,
        })
    ints = {"pre:int", "post:int", "upstream:int", "downstream:int", "synweight:int", "size:long", ":ID(Body-ID)", "bodyId:long"}
    floats = {"group:int", "serial:int", "predictedNtProb:float"}
    nschema = pa.schema([(k, pa.int64() if k in ints else pa.float64() if k in floats else pa.bool_() if k == "cropped:boolean"
                          else pa.string()) for k in nrows[0]])
    feather.write_feather(pa.Table.from_pylist(nrows, schema=nschema), p("neuprint_neurons"))

    # ---- neuPrint connections: weight (rule), weightHP, weightHR (all), roiInfo (rule) ----
    w, whp, whr, proi_c = Counter(), Counter(), Counter(), defaultdict(Counter)
    for s in syn:
        k = (s["pre"], s["post"])
        whr[k] += 1
        if _counted(s):
            w[k] += 1
            whp[k] += _hp(s)
            for r in S.roi_path(s["proi"]):
                proi_c[k][r] += 1
    pairs = sorted(whr)
    conn = {":START_ID(Body-ID)": [a for a, _ in pairs], "weightHR:int": [whr[k] for k in pairs], "weight:int": [w[k] for k in pairs],
            "weightHP:int": [whp[k] for k in pairs], ":END_ID(Body-ID)": [b for _, b in pairs],
            "roiInfo:string": [json.dumps({r: {"pre": c, "post": c} for r, c in sorted(proi_c[k].items())}) for k in pairs]}
    feather.write_feather(pa.table({k: pa.array(v, pa.string() if k == "roiInfo:string" else pa.int64()) for k, v in conn.items()}),
                          p("neuprint_connections"))

    # ---- traced adjacency CSVs (neuPrint status Traced) ----
    traced = sorted(b for b in props if (NP_STATUS_OVERRIDE.get(b, (props[b]["status"],))[0]) == "Traced")
    with open(p("traced_neurons"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("bodyId,type,instance\n")
        for b in traced:
            fh.write(f"{b},{props[b]['type']},{props[b]['instance']}\n")
    with open(p("traced_connections"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("bodyId_pre,bodyId_post,weight\n")
        for (a, b) in pairs:
            if a in traced and b in traced and w[(a, b)] > 0:
                fh.write(f"{a},{b},{w[(a, b)]}\n")
    with open(p("traced_connections_per_roi"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("bodyId_pre,bodyId_post,roi,weight\n")
        for (a, b) in pairs:
            if a in traced and b in traced and w[(a, b)] > 0:
                by = Counter()
                for s in syn:
                    if (s["pre"], s["post"]) == (a, b) and _counted(s):
                        pr = S.primary_of(s["proi"])
                        by["NotPrimary" if pr == S.UNSPEC else pr] += 1
                for r, c in sorted(by.items()):
                    fh.write(f"{a},{b},{r},{c}\n")

    # ---- bzip2 partner table ----
    t = _partner_table(syn)
    import io
    buf = io.BytesIO()
    feather.write_feather(t, buf)
    with bz2.open(p("syn_partners"), "wb") as fo:
        fo.write(buf.getvalue())
    return raw_dir


def write_manc_v12_fixture(raw_dir: Path) -> Path:
    src = MANC_V1_2
    raw_dir = Path(raw_dir)

    def p(key):
        out = raw_dir / src.local_relpath(src.file(key))
        out.parent.mkdir(parents=True, exist_ok=True)
        return out

    syn = _all_synapses()
    feather.write_feather(_partner_table(syn), p("syn_partners"))
    neurons = sorted(S.NEURON_ANN)
    per, _ = _per_body(syn)
    # unfiltered and rule-based counts per body
    unf_pre, unf_post = Counter(), Counter()
    seen = set()
    rule_pre = Counter()
    seen_rule = set()
    for s in syn:
        if s["tb"] not in seen:
            seen.add(s["tb"]); unf_pre[s["pre"]] += 1
        unf_post[s["post"]] += 1
        if _counted(s) and s["tb"] not in seen_rule:
            seen_rule.add(s["tb"]); rule_pre[s["pre"]] += 1

    def tags_prop(prefix_style: str, extra_nt: bool) -> dict:
        tags, values = [], []
        idx = {}

        def ti(t):
            if t not in idx:
                idx[t] = len(tags); tags.append(t)
            return idx[t]

        pref = {"class": "class", "hemilineage": "hemilineage", "soma_side": "soma_side" if prefix_style == "snake" else "somaSide",
                "soma_neuromere": "soma_neuromere" if prefix_style == "snake" else "somaNeuromere",
                "root_side": "root_side" if prefix_style == "snake" else "rootSide"}
        for b in neurons:
            typ, sc, _cls, ss, rs, _sl, _st, thl, _ihl, neu, _soma = S.NEURON_ANN[b]
            row = [ti(f"{pref['class']}:{MANC_CLASS[sc].replace(' ', '_')}")]
            if thl:
                row.append(ti(f"{pref['hemilineage']}:{thl}"))
            if ss:
                row.append(ti(f"{pref['soma_side']}:{SIDE[ss]}"))
            if rs:
                row.append(ti(f"{pref['root_side']}:{SIDE[rs]}"))
            if neu:
                row.append(ti(f"{pref['soma_neuromere']}:{neu}"))
            if extra_nt and b in MANC_NT and MANC_NT[b][0] != "unknown":
                row.append(ti(f"celltypePredictedNt:{MANC_NT[b][0]}"))
            values.append(sorted(row))
        return {"id": "tags", "type": "tags", "tags": tags, "values": values}

    ids = [str(b) for b in neurons]
    types = [S.NEURON_ANN[b][0] for b in neurons]
    # v1.2.1 snapshot
    v121 = {"@type": "neuroglancer_segment_properties", "inline": {"ids": ids, "properties": [
        {"id": "type", "type": "label", "values": types},
        {"id": "PreSyn", "type": "number", "data_type": "int32", "values": [unf_pre[b] for b in neurons]},
        {"id": "PostSyn", "type": "number", "data_type": "int32", "values": [unf_post[b] for b in neurons]},
        tags_prop("snake", extra_nt=False)]}}
    p("segprops_v1_2_1_info").write_text(json.dumps(v121), encoding="utf-8")
    # v1.2.3 snapshot: combined + instance + type (type of 104 is the '~' placeholder)
    types123 = [("~" if b == EXPECTED_V123_TYPE_PLACEHOLDER else t) for b, t in zip(neurons, types)]
    v123 = {"@type": "neuroglancer_segment_properties", "inline": {"ids": ids, "properties": [
        {"id": "type", "type": "label", "values": types123},
        {"id": "group", "type": "string", "values": [str(b) for b in neurons]},
        {"id": "serial", "type": "string", "values": [""] * len(neurons)},
        {"id": "cluster", "type": "string", "values": [""] * len(neurons)},
        {"id": "origin", "type": "string", "values": ["brain" if b == 101 else "" for b in neurons]},
        {"id": "vfbId", "type": "string", "values": [f"VFB_{b}" for b in neurons]},
        {"id": "syn_post", "type": "number", "data_type": "int32", "values": [per[b]["post"] for b in neurons]},
        {"id": "syn_pre", "type": "number", "data_type": "int32", "values": [rule_pre[b] for b in neurons]},
        {"id": "syn_downstream", "type": "number", "data_type": "int32", "values": [per[b]["downstream"] for b in neurons]},
        {"id": "syn_connections", "type": "number", "data_type": "int32",
         "values": [per[b]["downstream"] + per[b]["upstream"] for b in neurons]},
        tags_prop("camel", extra_nt=True)]}}
    p("segprops_v1_2_3_combined").write_text(json.dumps(v123), encoding="utf-8")
    inst = {"@type": "neuroglancer_segment_properties", "inline": {"ids": ids, "properties": [
        {"id": "instance", "type": "label", "values": [f"{t}_T1_{SIDE.get(S.NEURON_ANN[b][3]) or 'M'}" for b, t in zip(neurons, types)]}]}}
    p("segprops_v1_2_3_instance").write_text(json.dumps(inst), encoding="utf-8")
    tp = {"@type": "neuroglancer_segment_properties", "inline": {"ids": ids, "properties": [
        {"id": "type", "type": "label", "values": types123}]}}
    p("segprops_v1_2_3_type").write_text(json.dumps(tp), encoding="utf-8")
    return raw_dir


def build_synthetic_manc(root: Path, version: str, synapse_checks: bool = True) -> dict:
    """Write both MANC raw fixtures under root/raw and build ``manc:<version>`` into root/out/<version>."""
    from ..ingest.common import IngestConfig
    from ..ingest.manc import build

    root = Path(root)
    raw10 = write_manc_v10_fixture(root / "raw" / "manc" / "v1.0")
    if version == "v1.0":
        cfg = IngestConfig(source=MANC_V1_0, build_version="v1.0", raw_dir=raw10, out_dir=root / "out" / version,
                           verify_acquisition=False, threads=2, duckdb_memory_limit="1GB", synapse_sample_neurons=50,
                           synapse_checks=synapse_checks)
    else:
        raw12 = write_manc_v12_fixture(root / "raw" / "manc" / "v1.2")
        cfg = IngestConfig(source=MANC_V1_2, build_version=version, raw_dir=raw12, out_dir=root / "out" / version,
                           verify_acquisition=False, threads=2, duckdb_memory_limit="1GB",
                           extra_raw_dirs={"manc:v1.0": raw10}, synapse_checks=synapse_checks)
    return build(cfg)
