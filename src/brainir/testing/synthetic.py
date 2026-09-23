"""Tiny synthetic dataset shaped exactly like the MaleCNS raw files.

Every raw table is *derived* from one explicit list of synapses, so the
expected canonical outputs can be written down by hand (see EXPECTED_* below)
and the ingestion pipeline can be tested end to end, including deliberately
corrupted variants (``mutate=``).

Topology (bodyId: role)::

    101 DNtest   descending, soma R (brain)   -> outputs mostly in VNC
    102 INa      VNC intrinsic, L, T1         (has an autapse)
    103 INb      VNC intrinsic, R, T1         (reciprocal with 102)
    104 MN1      VNC motor, L                 (no T-bars -> no NT row)
    105 SN1      VNC sensory, root L          (no soma)
    106 ANx      ascending, soma L (VNC)      -> outputs in brain
    107 CBx      central brain intrinsic, R
    900          fragment (Orphan) with neuPrint :Neuron label, no superclass
    901          tiny fragment, no annotation row, :Segment only
    950          glia annotation row, no synapses (absent from neuPrint tables)
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.feather as feather

from ..sources.registry import MALECNS_V1_0

ROI_TREE = {"name": "CNS", "children": [
    # SMP-sub(R) is listed under two parents, like CA(L)/IB/... in the real neuPrint hierarchy (a DAG)
    {"name": "CentralBrain", "children": [{"name": "GNG"}, {"name": "SMP(R)", "children": [{"name": "SMP-sub(R)"}]},
                                          {"name": "SMP-sub(R)"}]},
    {"name": "VNC", "children": [{"name": "LegNp(T1)(L)"}, {"name": "LegNp(T1)(R)"}, {"name": "VNC-unspecified"}]},
]}
PRIMARY = ["GNG", "SMP(R)", "LegNp(T1)(L)", "LegNp(T1)(R)", "VNC-unspecified"]
UNSPEC = "<unspecified>"


def _parents() -> dict[str, str | None]:
    out: dict[str, str | None] = {}

    def walk(n, p):
        out.setdefault(n["name"], p)  # first (depth-first) occurrence is the anatomical parent
        for c in n.get("children", []):
            walk(c, n["name"])
    walk(ROI_TREE, None)
    return out


PARENT = _parents()


def roi_path(roi: str) -> list[str]:
    """ROI plus all ancestors, excluding the root 'CNS' (neuPrint roiInfo convention)."""
    if roi == UNSPEC:
        return []
    out = []
    while roi is not None and roi != "CNS":
        out.append(roi)
        roi = PARENT[roi]
    return out


def primary_of(roi: str) -> str:
    for r in roi_path(roi):
        if r in PRIMARY:
            return r
    return UNSPEC


# (pre body, T-bar ROI, conf_pre, [(post body, PSD ROI, conf_post), ...])
TBARS = [
    (101, "LegNp(T1)(L)", 0.90, [(102, "LegNp(T1)(L)", 0.95), (102, "LegNp(T1)(L)", 0.80), (102, "LegNp(T1)(L)", 0.60)]),
    (101, "LegNp(T1)(L)", 0.85, [(102, "LegNp(T1)(L)", 0.90), (102, UNSPEC, 0.90), (102, UNSPEC, 0.75)]),
    (101, "LegNp(T1)(R)", 0.90, [(103, "LegNp(T1)(R)", 0.90), (103, "LegNp(T1)(R)", 0.90), (103, "LegNp(T1)(R)", 0.55)]),
    (101, "GNG", 0.70, [(106, "GNG", 0.80)]),
    (102, "LegNp(T1)(L)", 0.90, [(104, "LegNp(T1)(L)", 0.9)] * 4),
    (102, "LegNp(T1)(L)", 0.80, [(102, "LegNp(T1)(L)", 0.9)]),
    (102, "VNC-unspecified", 0.80, [(103, "VNC-unspecified", 0.9)]),
    (103, "VNC-unspecified", 0.90, [(102, "VNC-unspecified", 0.9), (102, "VNC-unspecified", 0.8)]),
    (103, "LegNp(T1)(R)", 0.90, [(901, "LegNp(T1)(R)", 0.9)] * 2),
    (105, "LegNp(T1)(L)", 0.90, [(102, "LegNp(T1)(L)", 0.9)] * 3),
    (106, "GNG", 0.90, [(101, "GNG", 0.9)] * 2),
    (106, "SMP(R)", 0.90, [(107, "SMP-sub(R)", 0.9)]),
    (107, "SMP(R)", 0.90, [(101, "SMP(R)", 0.9)] * 4),
    (900, "LegNp(T1)(L)", 0.90, [(102, "LegNp(T1)(L)", 0.9)] * 6),
    (900, "LegNp(T1)(R)", 0.90, [(901, "LegNp(T1)(R)", 0.9)]),
]

NEURON_ANN = {
    # bodyId: (type, superclass, class, somaSide, rootSide, statusLabel, status, trumanHl, itoleeHl, somaNeuromere, soma)
    101: ("DNtest", "descending_neuron", None, "R", None, "Roughly traced", "Traced", "17A", "SMPpv2", "CG", [100, 100, 10]),
    102: ("INa", "vnc_intrinsic", None, "L", None, "Roughly traced", "Traced", "17A", None, "T1", [200, 300, 900]),
    103: ("INb", "vnc_intrinsic", None, "R", None, "Prelim Roughly traced", "Traced", "16B", None, "T1", [210, 310, 900]),
    104: ("MN1", "vnc_motor", "leg_motor", "L", None, "Roughly traced", "Traced", None, None, "T1", [220, 320, 910]),
    105: ("SN1", "vnc_sensory", None, None, "L", "Roughly traced", "Traced", None, None, None, None),
    106: ("ANx", "ascending_neuron", None, "L", None, "Reviewed", "Traced", "06A", None, "T1", [230, 330, 920]),
    107: ("CBx", "cb_intrinsic", None, "R", None, "Anchor", "Anchor", None, "SMPad1", None, [120, 110, 20]),
}
NT = {  # body: (predicted_nt, conf, n, celltype_pred, ct_conf, ct_n, ground_truth, consensus)
    101: ("acetylcholine", 0.9, 4, "acetylcholine", 0.9, 4, None, "acetylcholine"),
    102: ("gaba", 0.8, 3, "gaba", 0.8, 3, None, "gaba"),
    103: ("glutamate", 0.7, 2, "glutamate", 0.7, 2, "glutamate", "glutamate"),
    105: ("acetylcholine", 0.95, 1, "acetylcholine", 0.95, 1, None, "acetylcholine"),
    106: ("serotonin", 0.9, 2, "serotonin", 0.9, 2, None, "unclear"),
    107: ("unclear", 0.4, 1, "unclear", 0.4, 1, None, "unclear"),
    900: ("unclear", 0.3, 2, "unclear", None, 2, None, "unclear"),
}

# --- expected canonical results (hand-derived from TBARS) ---
EXPECTED_NEURONS = [101, 102, 103, 104, 105, 106, 107]
EXPECTED_EDGES = {  # (pre, post): (synapse_count, synapse_count_hp)
    (101, 102): (6, 5), (101, 103): (3, 2), (101, 106): (1, 1), (102, 104): (4, 4), (102, 102): (1, 1),
    (102, 103): (1, 1), (103, 102): (2, 2), (105, 102): (3, 3), (106, 101): (2, 2), (106, 107): (1, 1),
    (107, 101): (4, 4),
}
EXPECTED_EDGE_NEUROPILS = {
    (101, 102): {"LegNp(T1)(L)": 4, "<unassigned>": 2}, (101, 103): {"LegNp(T1)(R)": 3}, (101, 106): {"GNG": 1},
    (102, 104): {"LegNp(T1)(L)": 4}, (102, 102): {"LegNp(T1)(L)": 1}, (102, 103): {"VNC-unspecified": 1},
    (103, 102): {"VNC-unspecified": 2}, (105, 102): {"LegNp(T1)(L)": 3}, (106, 101): {"GNG": 2},
    (106, 107): {"SMP(R)": 1}, (107, 101): {"SMP(R)": 4},
}
EXPECTED_TOTALS = {  # body: (downstream all, upstream all, downstream to neurons, upstream from neurons)
    101: (10, 6, 10, 6), 102: (6, 18, 6, 12), 103: (4, 4, 2, 4), 104: (0, 4, 0, 4),
    105: (3, 0, 3, 0), 106: (3, 1, 3, 1), 107: (4, 1, 4, 1),
}


def _synapses():
    rows, coord = [], 0
    for tb_i, (pre, troi, cpre, partners) in enumerate(TBARS):
        xp, yp, zp = 1000 + tb_i, 2000 + tb_i, 3000 + tb_i
        for post, proi, cpost in partners:
            coord += 1
            rows.append(dict(tb=tb_i, pre=pre, troi=troi, cpre=cpre, xp=xp, yp=yp, zp=zp,
                             post=post, proi=proi, cpost=cpost, xq=5000 + coord, yq=6000 + coord, zq=7000 + coord))
    return rows


def write_malecns_fixture(raw_dir: Path, mutate: str | None = None) -> Path:
    """Write all raw files under ``raw_dir`` using the real registry layout."""
    src = MALECNS_V1_0
    raw_dir = Path(raw_dir)

    def p(key):
        out = raw_dir / src.local_relpath(src.file(key))
        out.parent.mkdir(parents=True, exist_ok=True)
        return out

    syn = _synapses()
    tbars = {i: (pre, troi) for i, (pre, troi, _, _) in enumerate(TBARS)}
    bodies = sorted({s["pre"] for s in syn} | {s["post"] for s in syn})

    # ---- meta ----
    roi_pre, roi_post = Counter(), Counter()
    for i, (pre, troi) in tbars.items():
        for r in roi_path(troi):
            roi_pre[r] += 1
    for s in syn:
        for r in roi_path(s["proi"]):
            roi_post[r] += 1
    roi_info = {r: {"pre": roi_pre.get(r, 0), "post": roi_post.get(r, 0), "isPrimary": r in PRIMARY, "isNerve": False,
                    "parent": PARENT[r], "description": "", "excludeFromOverview": False}
                for r in PARENT if r != "CNS"}
    roi_info["AL-unspecified(L)"] = {"pre": 0, "post": 0, "isPrimary": False, "isNerve": False, "parent": None,
                                     "description": "", "excludeFromOverview": False}  # stats-only ROI
    meta = {"dataset": "male-cns", "tag": "v1.0", "uuid": "synthetic", "latestMutationId": 1,
            "lastDatabaseEdit": "synthetic", "postHighAccuracyThreshold": 0.5, "preHPThreshold": 0.0,
            "postHPThreshold": 0.7, "primaryRois": PRIMARY, "superLevelRois": PRIMARY, "roiHierarchy": ROI_TREE,
            "roiInfo": roi_info, "totalPreCount": len(TBARS), "totalPostCount": len(syn)}
    if mutate == "wrong_version":
        meta["tag"] = "v0.9"
    p("neuprint_meta_json").write_text(json.dumps(meta), encoding="utf-8")

    # ---- syn-partners ----
    cols = defaultdict(list)
    for s in syn:
        for k, v in (("x_pre", s["xp"]), ("y_pre", s["yp"]), ("z_pre", s["zp"]), ("body_pre", s["pre"]),
                     ("conf_pre", s["cpre"]), ("x_post", s["xq"]), ("y_post", s["yq"]), ("z_post", s["zq"]),
                     ("body_post", s["post"]), ("conf_post", s["cpost"]), ("primary_post", primary_of(s["proi"]))):
            cols[k].append(v)
    t = pa.table({k: pa.array(v, pa.int32() if k[0] in "xyz" else pa.int64() if k.startswith("body") else
                              pa.float32() if k.startswith("conf") else pa.string()) for k, v in cols.items()})
    t = t.set_column(t.schema.get_field_index("primary_post"), "primary_post",
                     t.column("primary_post").dictionary_encode().cast(pa.dictionary(pa.int16(), pa.string())))
    feather.write_feather(t, p("syn_partners"))

    # ---- connections ----
    pair_w, pair_hp, pair_roi = Counter(), Counter(), defaultdict(Counter)
    for s in syn:
        k = (s["pre"], s["post"])
        pair_w[k] += 1
        pair_hp[k] += s["cpost"] >= 0.7
        for r in roi_path(s["proi"]):
            pair_roi[k][r] += 1
    pairs = sorted(pair_w)
    conn = {":START_ID(Body-ID)": [a for a, _ in pairs], ":END_ID(Body-ID)": [b for _, b in pairs],
            "weightHR:int": [pair_w[k] for k in pairs], "weight:int": [pair_w[k] for k in pairs],
            "weightHP:int": [pair_hp[k] for k in pairs],
            "roiInfo:string": [json.dumps({r: {"post": c} for r, c in sorted(pair_roi[k].items())}) for k in pairs]}
    if mutate == "duplicate_edge":
        for c in conn:
            conn[c].append(conn[c][0])
    if mutate == "edge_missing_segment":
        for c, v in zip(conn, [777, 101, 1, 1, 1, "{}"]):
            conn[c].append(v)
    if mutate == "negative_weight":
        conn["weight:int"][1] = -1
        conn["weightHR:int"][1] = -1
    feather.write_feather(pa.table({k: pa.array(v, pa.string() if k == "roiInfo:string" else pa.int64())
                                    for k, v in conn.items()}), p("neuprint_connections"))
    flat_w = [pair_w[k] + (1 if (mutate == "flat_mismatch" and k == (101, 102)) else 0) for k in pairs]
    feather.write_feather(pa.table({"body_pre": pa.array([a for a, _ in pairs], pa.int64()),
                                    "body_post": pa.array([b for _, b in pairs], pa.int64()),
                                    "weight": pa.array(flat_w, pa.int64())}), p("flat_connectome_weights"))

    # ---- annotations ----
    ann_rows = []
    for b, (typ, sc, cls, ss, rs, sl, st, thl, ihl, neu, soma) in NEURON_ANN.items():
        ann_rows.append(dict(bodyId=b, type=typ, instance=f"{typ}_{ss or rs}", superclass=sc, **{"class": cls},
                             subclass=None, somaSide=ss, rootSide=rs, statusLabel=sl, status=st, trumanHl=thl,
                             itoleeHl=ihl, somaNeuromere=neu, somaLocation=soma, group=float(b), mancBodyid=float(b + 10000),
                             mancType=typ, flywireType=typ, hemibrainType=None, synonyms=None, dimorphism=None, fruDsx=None))
    ann_rows.append(dict(bodyId=900, type=None, instance=None, superclass=None, **{"class": None}, subclass=None,
                         somaSide=None, rootSide=None, statusLabel="Orphan", status="Orphan", trumanHl=None, itoleeHl=None,
                         somaNeuromere=None, somaLocation=None, group=None, mancBodyid=None, mancType=None,
                         flywireType=None, hemibrainType=None, synonyms=None, dimorphism=None, fruDsx=None))
    ann_rows.append(dict(bodyId=950, type=None, instance=None, superclass=None, **{"class": None}, subclass=None,
                         somaSide=None, rootSide=None, statusLabel="Glia", status="Glia", trumanHl=None, itoleeHl=None,
                         somaNeuromere=None, somaLocation=None, group=None, mancBodyid=None, mancType=None,
                         flywireType=None, hemibrainType=None, synonyms=None, dimorphism=None, fruDsx=None))
    if mutate == "annotation_duplicate":
        ann_rows.append(dict(ann_rows[0]))
    ann = pa.Table.from_pylist(ann_rows, schema=pa.schema([
        ("bodyId", pa.int64()), ("type", pa.string()), ("instance", pa.string()), ("superclass", pa.string()),
        ("class", pa.string()), ("subclass", pa.string()), ("somaSide", pa.string()), ("rootSide", pa.string()),
        ("statusLabel", pa.string()), ("status", pa.string()), ("trumanHl", pa.string()), ("itoleeHl", pa.string()),
        ("somaNeuromere", pa.string()), ("somaLocation", pa.list_(pa.int64())), ("group", pa.float64()),
        ("mancBodyid", pa.float64()), ("mancType", pa.string()), ("flywireType", pa.string()),
        ("hemibrainType", pa.string()), ("synonyms", pa.string()), ("dimorphism", pa.string()), ("fruDsx", pa.string())]))
    ann = ann.set_column(ann.schema.get_field_index("statusLabel"), "statusLabel",
                         ann.column("statusLabel").dictionary_encode().cast(pa.dictionary(pa.int8(), pa.string())))
    feather.write_feather(ann, p("body_annotations"))

    # ---- neurotransmitters ----
    nt_rows = []
    for b, (pn, pc_, n, cpn, cc, cn, gt, cons) in NT.items():
        typ = NEURON_ANN.get(b, (None,))[0]
        nt_rows.append(dict(body=b, cell_type=typ, total_nt_predictions=n, predicted_nt_confidence=pc_, predicted_nt=pn,
                            ground_truth=gt, celltype_total_nt_predictions=cn, celltype_predicted_nt=cpn,
                            celltype_predicted_nt_confidence=cc, consensus_nt=cons))
    if mutate == "nt_bad_vocab":
        nt_rows[0]["predicted_nt"] = "glycine"
    feather.write_feather(pa.Table.from_pylist(nt_rows, schema=pa.schema([
        ("body", pa.int64()), ("cell_type", pa.string()), ("total_nt_predictions", pa.int32()),
        ("predicted_nt_confidence", pa.float64()), ("predicted_nt", pa.string()), ("ground_truth", pa.string()),
        ("celltype_total_nt_predictions", pa.int32()), ("celltype_predicted_nt", pa.string()),
        ("celltype_predicted_nt_confidence", pa.float64()), ("consensus_nt", pa.string())])), p("body_neurotransmitters"))

    # ---- neuPrint neurons (segments) ----
    per = {b: Counter() for b in bodies}
    per_roi = {b: defaultdict(Counter) for b in bodies}
    seen_tbar = set()
    for s in syn:
        a, b = s["pre"], s["post"]
        per[a]["downstream"] += 1
        per[b]["upstream"] += 1
        per[b]["post"] += 1
        for r in roi_path(s["troi"]):
            per_roi[a][r]["downstream"] += 1
        for r in roi_path(s["proi"]):
            per_roi[b][r]["upstream"] += 1
            per_roi[b][r]["post"] += 1
        if s["tb"] not in seen_tbar:
            seen_tbar.add(s["tb"])
            per[a]["pre"] += 1
            for r in roi_path(s["troi"]):
                per_roi[a][r]["pre"] += 1
    nrows = []
    annd = {r["bodyId"]: r for r in ann_rows}
    for b in bodies:
        c = per[b]
        ri = {}
        for r, cc in sorted(per_roi[b].items()):
            d = {k: v for k, v in cc.items() if v}
            if d.get("downstream", 0) or d.get("upstream", 0):
                d["synweight"] = d.get("downstream", 0) + d.get("upstream", 0)
            ri[r] = d
        a = annd.get(b, {})
        nt = NT.get(b)
        label = "Segment;male-cns_Segment" + (";Neuron;male-cns_Neuron" if (a.get("superclass") or b == 900) else "")
        nrows.append({
            ":ID(Body-ID)": b, "bodyId:long": b, "pre:int": c["pre"], "post:int": c["post"],
            "downstream:int": c["downstream"], "upstream:int": c["upstream"],
            "synweight:int": c["downstream"] + c["upstream"], "size:long": float(1000 * b),
            ":LABEL": label, "roiInfo:string": json.dumps(ri),
            "type:string": a.get("type"), "instance:string": a.get("instance"), "superclass:string": a.get("superclass"),
            "class:string": a.get("class"), "subclass:string": a.get("subclass"), "somaSide:string": a.get("somaSide"),
            "rootSide:string": a.get("rootSide"), "status:string": a.get("status"), "statusLabel:string": a.get("statusLabel"),
            "group:long": a.get("group"), "flywireType:string": a.get("flywireType"), "mancType:string": a.get("mancType"),
            "hemibrainType:string": a.get("hemibrainType"), "synonyms:string": a.get("synonyms"),
            "predictedNt:string": nt[0] if nt else None, "consensusNt:string": nt[7] if nt else None,
            "celltypePredictedNt:string": nt[3] if nt else None,
            "predictedNtConfidence:float": nt[1] if nt else None, "celltypePredictedNtConfidence:float": nt[4] if nt else None,
            "totalNtPredictions:float": float(nt[2]) if nt else None,
        })
    ints = {"pre:int", "post:int", "downstream:int", "upstream:int", "synweight:int"}
    floats = {"size:long", "group:long", "predictedNtConfidence:float", "celltypePredictedNtConfidence:float",
              "totalNtPredictions:float"}
    schema = pa.schema([(k, pa.int64() if k in (":ID(Body-ID)", "bodyId:long") else pa.int32() if k in ints else
                         pa.float64() if k in floats else pa.string()) for k in nrows[0]])
    feather.write_feather(pa.Table.from_pylist(nrows, schema=schema), p("neuprint_neurons"))
    return raw_dir


def build_synthetic_dataset(root: Path, mutate: str | None = None) -> dict:
    """Write the fixture under root/raw and ingest it into root/out (test mode: no acquisition log)."""
    from ..ingest.malecns import IngestConfig, build

    root = Path(root)
    raw = write_malecns_fixture(root / "raw", mutate=mutate)
    cfg = IngestConfig(raw_dir=raw, out_dir=root / "out", verify_acquisition=False, threads=2,
                       duckdb_memory_limit="1GB", synapse_sample_neurons=50)
    return build(cfg)
