"""Independent data-quality audit of the processed MaleCNS v1.0 build.

Deliberately uses code paths *different* from the ingestion pipeline (plain pyarrow filters on the raw Arrow IPC
files, no DuckDB) so that shared bugs cannot hide. Writes research/audit/data_quality_audit_male-cns_v1.0.md.

Run:  uv run python scripts/audit_data_quality.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as pads
import pyarrow.parquet as pq

from brainir import paths
from brainir.graph import Connectome
from brainir.sources.registry import MALECNS_V1_0 as SRC

SEED = 1234
RAW = paths.raw_dir("male-cns", "v1.0")
PROC = paths.processed_dir("male-cns", "v1.0")
OUT = paths.repo_root() / "research" / "audit" / "data_quality_audit_male-cns_v1.0.md"


def raw(key: str) -> Path:
    return RAW / SRC.local_relpath(SRC.file(key))


def ipc_filter(key: str, expr, columns=None) -> pd.DataFrame:
    """Scan a raw Arrow IPC file with a pyarrow compute filter (independent of DuckDB)."""
    return pads.dataset(str(raw(key)), format="ipc").to_table(filter=expr, columns=columns).to_pandas()


class Audit:
    def __init__(self):
        self.rows: list[tuple[str, bool, str]] = []
        self.sections: list[str] = []

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        self.rows.append((name, bool(ok), detail))
        print(("PASS " if ok else "FAIL ") + name + (f" :: {detail}" if detail else ""))

    def md(self, *lines: str) -> None:
        self.sections.extend(lines)


def main() -> int:
    rng = np.random.default_rng(SEED)
    A = Audit()
    cx = Connectome.open("male-cns", "v1.0")
    neu = cx.neurons

    # 1. IDs exist in every official source, exact set equality, int64 everywhere ------------------------------
    raw_ann = pads.dataset(str(raw("body_annotations")), format="ipc").to_table(columns=["bodyId", "superclass"]).to_pandas()
    A.check("neuron ID set == raw annotation bodies with superclass",
            set(neu.index) == set(raw_ann.loc[raw_ann.superclass.notna(), "bodyId"]), f"n={len(neu)}")
    sch = pq.read_schema(PROC / "neurons.parquet")
    int_cols = {f.name: str(f.type) for f in sch if f.name in ("source_id", "group_id", "manc_body_id", "n_pre", "n_post")}
    A.check("ID/count columns are integers in Parquet (no float round-trip)",
            all(t.startswith("int") for t in int_cols.values()), json.dumps(int_cols))
    sch_c = pq.read_schema(PROC / "connections.parquet")
    A.check("edge endpoint columns are int64", str(sch_c.field("pre_id").type) == "int64" and str(sch_c.field("post_id").type) == "int64")
    sample = np.sort(rng.choice(cx.ids, size=200, replace=False))
    seg = ipc_filter("neuprint_neurons", pc.field(":ID(Body-ID)").isin(pa.array(sample, pa.int64())),
                     columns=[":ID(Body-ID)", "type:string", "instance:string", "superclass:string", "status:string",
                              "consensusNt:string", "pre:int", "post:int", "downstream:int", "upstream:int", ":LABEL"])
    A.check("200 sampled neuron IDs all exist in the raw neuPrint segment table", len(seg) == 200, f"found {len(seg)}")
    seg = seg.set_index(":ID(Body-ID)").loc[sample]
    mism = {}
    for pc_col, raw_col in (("cell_type", "type:string"), ("instance", "instance:string"), ("super_class", "superclass:string"),
                            ("status", "status:string"), ("nt_consensus", "consensusNt:string"), ("n_pre", "pre:int"),
                            ("n_post", "post:int"), ("n_downstream", "downstream:int"), ("n_upstream", "upstream:int")):
        a = neu.loc[sample, pc_col].astype("string").fillna("<NA>").to_numpy()
        b = seg[raw_col].astype("string").fillna("<NA>").to_numpy()
        mism[pc_col] = int((a != b).sum())
    A.check("sampled neuron fields equal raw neuPrint values (no join misalignment / type corruption)",
            not any(mism.values()), json.dumps(mism))
    rawnt = ipc_filter("body_neurotransmitters", pc.field("body").isin(pa.array(sample, pa.int64())),
                       columns=["body", "consensus_nt", "predicted_nt_confidence"]).set_index("body")
    common = [i for i in sample if i in rawnt.index]
    a = neu.loc[common, "nt_consensus"].astype("string").fillna("<NA>").to_numpy()
    b = rawnt.loc[common, "consensus_nt"].astype("string").fillna("<NA>").to_numpy()
    A.check("sampled NT annotations joined to the right bodies", (a == b).all(), f"{len(common)} with NT rows")

    # 2. Edge counts vs official sources (pyarrow scans) -----------------------------------------------------------
    idx = rng.choice(cx.n_edges, size=300, replace=False)
    pre, post, w, whp = cx._pre[idx], cx._post[idx], cx._w[idx], cx._whp[idx]
    pres = pa.array(np.unique(pre), pa.int64())
    conn = ipc_filter("neuprint_connections", pc.field(":START_ID(Body-ID)").isin(pres),
                      columns=[":START_ID(Body-ID)", ":END_ID(Body-ID)", "weight:int", "weightHP:int"])
    ref = {(a_, b_): (x, y) for a_, b_, x, y in conn.itertuples(index=False)}
    bad = [(a_, b_) for a_, b_, x, y in zip(pre, post, w, whp) if ref.get((a_, b_)) != (x, y)]
    A.check("300 sampled edges: synapse_count and _hp equal raw neuPrint weight/weightHP", not bad, f"mismatches={bad[:5]}")
    rev_bad = []
    for a_, b_ in zip(pre[:100], post[:100]):
        raw_rev = ref.get((b_, a_))  # only available when b_ is also among sampled presynaptic IDs
        if b_ in set(pres.to_pylist()):
            proc_rev = cx.edge_count(int(b_), int(a_))
            if (raw_rev[0] if raw_rev else 0) != proc_rev:
                rev_bad.append((a_, b_))
    A.check("reverse-direction counts agree with raw (no pre/post swap)", not rev_bad, f"mismatches={rev_bad[:5]}")
    flat = ipc_filter("flat_connectome_weights", pc.field("body_pre").isin(pres), columns=["body_pre", "body_post", "weight"])
    fref = {(a_, b_): x for a_, b_, x in flat.itertuples(index=False)}
    fbad = [(a_, b_) for a_, b_, x in zip(pre, post, w) if fref.get((a_, b_)) != x]
    A.check("300 sampled edges equal the independent flat connectome-weights export", not fbad, f"mismatches={fbad[:5]}")
    sub = rng.choice(len(idx), size=25, replace=False)
    syn = ipc_filter("syn_partners", pc.field("body_pre").isin(pa.array(pre[sub], pa.int64())),
                     columns=["body_pre", "body_post", "conf_post"])
    sbad = []
    for j in sub:
        s_ = syn[(syn.body_pre == pre[j]) & (syn.body_post == post[j])]
        n_hp = int((s_.conf_post.astype("float64") >= 0.7).sum())
        if len(s_) != w[j] or n_hp != whp[j]:
            sbad.append((int(pre[j]), int(post[j]), len(s_), int(w[j]), n_hp, int(whp[j])))
    A.check("25 sampled edges recounted from individual synapses (pyarrow)", not sbad, f"mismatches={sbad[:5]}")

    # 3. Edge direction from known biology ---------------------------------------------------------------------
    def between(mask_a, mask_b) -> int:
        ia, ib = neu.index[mask_a].to_numpy(), neu.index[mask_b].to_numpy()
        return int(cx.edges_between(ia, ib, annotate=False).synapse_count.sum())
    t = neu.cell_type.astype("string").fillna("")
    kc, mbon = t.str.startswith("KC").to_numpy(), t.str.startswith("MBON").to_numpy()
    orn = t.str.startswith("ORN").to_numpy()
    pn = t.str.contains(r"_[a-z]*PN$|^M_.*PN", regex=True).to_numpy()
    kc_mbon, mbon_kc = between(kc, mbon), between(mbon, kc)
    A.check("Kenyon cells -> MBONs dominates MBONs -> KCs (MB output direction)", kc_mbon > 20 * max(1, mbon_kc),
            f"KC->MBON={kc_mbon}, MBON->KC={mbon_kc}")
    orn_pn, pn_orn = between(orn, pn), between(pn, orn)
    A.check("ORNs -> antennal-lobe PNs dominates the reverse (sensory input direction)", orn_pn > 5 * max(1, pn_orn),
            f"ORN->PN={orn_pn}, PN->ORN={pn_orn}")
    dn = (neu.super_class == "descending_neuron").to_numpy()
    mn = (neu.super_class == "vnc_motor").to_numpy()
    dn_mn, mn_dn = between(dn, mn), between(mn, dn)
    A.check("descending neurons -> VNC motor neurons dominates the reverse", dn_mn > 10 * max(1, mn_dn),
            f"DN->MN={dn_mn}, MN->DN={mn_dn}")
    gf = cx.ids_of_type("DNp01")
    A.check("Giant Fiber (DNp01) located: 2 neurons", len(gf) == 2, str(gf.tolist()))

    # 4. Cell-type label sanity ----------------------------------------------------------------------------------
    inst_ok = [(i, ty, ins) for i, ty, ins in zip(neu.index, neu.cell_type, neu.instance)
               if isinstance(ty, str) and isinstance(ins, str) and not ins.startswith(ty.split(",")[0])]
    A.check("instance begins with its type for (almost) all typed neurons", len(inst_ok) < 0.01 * neu.cell_type.notna().sum(),
            f"{len(inst_ok)} exceptions, e.g. {inst_ok[:3]}")
    prefix_rules = {"descending_neuron": r"^DN", "vnc_intrinsic": r"^IN", "ascending_neuron": r"^AN"}
    for sc, pat in prefix_rules.items():
        s_ = neu.loc[neu.super_class == sc, "cell_type"].dropna().astype(str)
        frac = float(s_.str.contains(pat, regex=True).mean())
        A.check(f"{sc}: fraction of types matching {pat!r}", frac > 0.8, f"{frac:.3f} of {len(s_)}")
    dn_types = neu.loc[neu.super_class == "descending_neuron"]
    A.check("DNg100 annotated with literature synonym BDN2 and matched to MANC",
            dn_types.loc[cx.ids_of_type("DNg100"), "synonyms"].astype(str).str.contains("BDN2").all())

    # 5. No cross-version mixing -----------------------------------------------------------------------------------
    A.check("every neuron row is male-cns:v1.0", (neu.dataset == "male-cns").all() and (neu.dataset_version == "v1.0").all())
    info = json.loads((PROC / "build_info.json").read_text())
    acq = json.loads((RAW / "_acquisition.json").read_text())
    urls = [f["remote_url"] for f in acq["files"]]
    A.check("all acquired files come from the v1.0 prefix of the official bucket",
            all(u.startswith("https://storage.googleapis.com/flyem-male-cns/v1.0/") for u in urls), f"{len(urls)} files")
    meta = info["neuprint_meta"]
    A.check("neuPrint meta snapshot recorded (uuid/lastDatabaseEdit)", bool(meta.get("uuid")), json.dumps(meta)[:200])
    pq_md = {k.decode(): v.decode() for k, v in (pq.read_schema(PROC / "connections.parquet").metadata or {}).items()}
    A.check("Parquet key-value metadata carries dataset + version", pq_md.get("brainir_dataset_version") == "v1.0", str(pq_md)[:200])

    # 6. Representative records printed for human inspection -------------------------------------------------------
    rep_ids = list(cx.ids_of_type("DNg100")) + list(gf) + list(rng.choice(cx.ids, size=3, replace=False))
    cols = ["cell_type", "instance", "super_class", "side", "status", "nt_consensus", "n_pre", "n_post",
            "n_downstream_to_neurons", "n_downstream"]
    A.md("## Representative records", "", neu.loc[rep_ids, cols].to_markdown(), "")
    d = cx.downstream(int(gf[0]), min_count=20)[["post_id", "post_type", "synapse_count", "synapse_count_hp"]].head(8)
    A.md(f"Top outputs of Giant Fiber `{gf[0]}` (>= 20 synapses):", "", d.to_markdown(index=False), "")

    n_fail = sum(1 for _, ok, _ in A.rows if not ok)
    lines = ["# Data-quality audit — MaleCNS v1.0 (independent of the ingestion code path)", "",
             "> Generated by `scripts/audit_data_quality.py` (seed 1234). Raw files are read with plain pyarrow "
             "filters, not DuckDB.", "",
             f"**Result: {len(A.rows) - n_fail} pass, {n_fail} fail.**", "", "| result | check | detail |", "|---|---|---|"]
    for name, ok, detail in A.rows:
        lines.append(f"| {'PASS' if ok else '**FAIL**'} | {name} | {detail.replace('|', '/')[:300]} |")
    lines += [""] + A.sections
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT}: {len(A.rows) - n_fail} pass, {n_fail} fail")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
