"""DNg100 walking-CPG benchmark — data verification in MaleCNS v1.0.

ANSWER-KEY CODE (reads answer_key.json). Not part of the BrainIR library and never
imported by it. Purpose: locate the benchmark's stimulus (DNg100), readout (leg
motor neurons) and published circuit neurons in MaleCNS v1.0; compare with the
paper's own MaleCNS extraction (authors' repository, pinned commit).

Run:  uv run python benchmarks/dng100_walking_cpg/investigate_malecns.py
Outputs (this directory): malecns_v1.0_findings.md, malecns_v1.0_mapping.json, tables/*.csv
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import urllib.parse
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from brainir import paths
from brainir.graph import Connectome

HERE = Path(__file__).resolve().parent
TABLES = HERE / "tables"
KEY = json.loads((HERE / "answer_key.json").read_text(encoding="utf-8"))

# Authors' repository files, pinned by commit and by SHA-256 of the canonical (LF) bytes served by
# raw.githubusercontent.com (a Windows checkout with core.autocrlf=true yields different CRLF bytes).
# Stored as external raw data (git-ignored).
REPO = "smpuglie/Pugliese_2026"
COMMIT = "10e7661bf414ba7b4c2edf795cd36d0f878c17c0"
EXTERNAL = {
    "mcns_wtable": ("data/imac t1 connectome data/wTable_20260210_vncRoisOnly.csv",
                    "593a75c53f1c69600cac747364b8b623655699b1b83e16b41eeef6fe93dd5b2d"),
    "mcns_W": ("data/imac t1 connectome data/W_20260210_vncRoisOnly.csv",
               "255236baca7a24ead7360636a4ee98fd54d5423026c6ec864bbd717b8d58d3b4"),
}
EXT_DIR = paths.data_root() / "raw" / "external" / "pugliese_2026" / COMMIT[:10]

LABELS = ["E1", "E2", "I1", "I2", "E3", "E4", "E5"]
LEGS = [f"LegNp(T{s})({h})" for s in (1, 2, 3) for h in ("L", "R")]
LEG_SHORT = {f"LegNp(T{s})({h})": f"T{s}{h}" for s in (1, 2, 3) for h in ("L", "R")}


def fetch_external() -> dict[str, Path]:
    EXT_DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    for key, (rel, sha) in EXTERNAL.items():
        dest = EXT_DIR / Path(rel).name
        if not dest.exists():
            url = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/{urllib.parse.quote(rel)}"
            r = requests.get(url, timeout=600)
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


def vnc_neuropils(cx: Connectome) -> set[str]:
    np_ = pd.read_parquet(cx.dir / "neuropils.parquet")
    return set(np_.loc[(np_.top_level_region == "VNC") & np_.is_primary, "name"])


def leg_profile(cx: Connectome, ids) -> pd.DataFrame:
    """Per neuron: synapses (pre+post) in each leg neuropil and the dominant leg."""
    nn = cx.neuron_neuropils(ids)
    nn = nn[nn.neuropil.isin(LEGS)].assign(tot=lambda d: d.n_pre + d.n_post)
    piv = nn.pivot_table(index="source_id", columns="neuropil", values="tot", aggfunc="sum", fill_value=0)
    piv = piv.reindex(columns=LEGS, fill_value=0)
    dom = piv.idxmax(axis=1).map(LEG_SHORT)
    frac = piv.max(axis=1) / piv.sum(axis=1).replace(0, np.nan)
    return pd.DataFrame({"dominant_leg": dom, "dominant_leg_fraction": frac.round(3)}).join(piv.rename(columns=LEG_SHORT))


def edge_counts(cx: Connectome, pre: int, post: int, vnc: set[str]) -> tuple[int, int]:
    cn = cx.connection_neuropils([pre], [post])
    if cn.empty:
        return 0, 0
    return int(cn.synapse_count.sum()), int(cn.loc[cn.neuropil.isin(vnc), "synapse_count"].sum())


def main() -> None:
    TABLES.mkdir(exist_ok=True)
    cx = Connectome.open("male-cns", "v1.0")
    vnc = vnc_neuropils(cx)
    ext = fetch_external()
    wt = pd.read_csv(ext["mcns_wtable"], index_col=0)
    W = pd.read_csv(ext["mcns_W"], index_col=0)
    W.columns = W.columns.astype(np.int64)
    md: list[str] = []
    mapping: dict = {"dataset": "male-cns:v1.0", "generated_by": "benchmarks/dng100_walking_cpg/investigate_malecns.py",
                     "external_reference": {"repo": REPO, "commit": COMMIT, "files": {k: v[0] for k, v in EXTERNAL.items()}}}

    # ---------------------------------------------------------------- A. stimulus: DNg100
    dn = cx.neurons_by_type("DNg100")
    dn_ids = dn.index.to_numpy()
    lp = leg_profile(cx, dn_ids)
    left_dn = int(lp.index[lp.dominant_leg.str.endswith("L")][0])  # innervates the left leg neuropils
    right_dn = int([i for i in dn_ids if i != left_dn][0])
    cols = ["instance", "soma_side", "status_label", "nt_consensus", "nt_type_confidence", "synonyms", "manc_type",
            "manc_body_id", "flywire_type", "group_id", "n_pre", "n_post", "n_downstream", "n_upstream",
            "n_downstream_to_neurons", "n_upstream_from_neurons"]
    ident = dn[cols].join(lp[["dominant_leg", "dominant_leg_fraction"]])
    ident.to_csv(TABLES / "dng100_identity.csv", lineterminator="\n")
    mapping["DNg100"] = {"ids": [int(i) for i in dn_ids], "innervates_left_legs": left_dn, "innervates_right_legs": right_dn,
                         "paper_left_vnc_id": KEY["ids_as_published"]["MaleCNS"]["DNg100_left_VNC"],
                         "paper_id_matches_v1.0": left_dn == KEY["ids_as_published"]["MaleCNS"]["DNg100_left_VNC"]}
    md += ["# DNg100 walking-CPG benchmark — MaleCNS v1.0 data verification", "",
           "> ANSWER-KEY MATERIAL (see README.md). Generated by `investigate_malecns.py`; do not edit by hand.", "",
           "## A. Stimulus neurons: DNg100 (a.k.a. BDN2)", "",
           f"MaleCNS v1.0 has **{len(dn_ids)} DNg100 neurons**. Each projects **contralaterally** to the leg neuropils: "
           f"`{left_dn}` (instance {dn.loc[left_dn, 'instance']}, soma {dn.loc[left_dn, 'soma_side']}) innervates the LEFT leg "
           f"neuropils and is the paper's stimulated 'left DNg100' (paper's MaleCNS ID {mapping['DNg100']['paper_left_vnc_id']}: "
           f"{'same ID in v1.0' if mapping['DNg100']['paper_id_matches_v1.0'] else 'DIFFERENT ID in v1.0'}); "
           f"`{right_dn}` innervates the right legs.", "",
           ident.T.to_markdown(), ""]
    nnp = cx.neuron_neuropils(dn_ids)
    for i in dn_ids:
        d = nnp[nnp.source_id == i].copy()
        d["frac_out"] = (d.n_pre / d.n_pre.sum()).round(3)
        d["frac_in"] = (d.n_post / d.n_post.sum()).round(3)
        md += [f"**{i}** — top output neuropils (T-bars) / input neuropils (PSDs):", "",
               d.sort_values("n_pre", ascending=False).head(8)[["neuropil", "n_pre", "frac_out"]].to_markdown(index=False), "",
               d.sort_values("n_post", ascending=False).head(6)[["neuropil", "n_post", "frac_in"]].to_markdown(index=False), ""]
    # partners of the left-VNC DNg100
    down = cx.downstream(left_dn)
    up = cx.upstream(left_dn)
    down.to_csv(TABLES / f"dng100_{left_dn}_downstream.csv", index=False, lineterminator="\n")
    up.to_csv(TABLES / f"dng100_{left_dn}_upstream.csv", index=False, lineterminator="\n")
    by_type_d = down.groupby("post_type", dropna=False).agg(n_neurons=("post_id", "size"), synapses=("synapse_count", "sum"))
    by_type_u = up.groupby("pre_type", dropna=False).agg(n_neurons=("pre_id", "size"), synapses=("synapse_count", "sum"))
    sc_d = cx.neurons.loc[down.post_id, "super_class"].value_counts()
    md += [f"### Partners of `{left_dn}` (left-VNC DNg100)", "",
           f"* downstream neurons: {len(down)} (>=5 synapses: {(down.synapse_count >= 5).sum()}), synapses to neurons: "
           f"{int(down.synapse_count.sum())} of {int(cx.neurons.loc[left_dn, 'n_downstream'])} total outgoing connections "
           f"({down.synapse_count.sum() / cx.neurons.loc[left_dn, 'n_downstream']:.1%} captured by neurons)",
           f"* upstream neurons: {len(up)} (>=5 synapses: {(up.synapse_count >= 5).sum()})",
           f"* downstream superclasses: {sc_d.head(8).to_dict()}", "",
           "Top downstream cell types (by synapses):", "",
           by_type_d.sort_values("synapses", ascending=False).head(15).to_markdown(), "",
           "Top upstream cell types (by synapses):", "",
           by_type_u.sort_values("synapses", ascending=False).head(12).to_markdown(), ""]

    # ---------------------------------------------------------------- B. readout: leg motor neurons
    leg_mn = cx.neurons[(cx.neurons.super_class == "vnc_motor") & cx.neurons.sub_class.isin(["fl", "ml", "hl"])]
    tab = pd.crosstab(leg_mn.sub_class, leg_mn.side)
    direct = down[down.post_id.isin(leg_mn.index)]
    direct_by_leg = cx.neurons.loc[direct.post_id].assign(syn=direct.synapse_count.to_numpy()).groupby(
        ["sub_class", "side"]).agg(n=("syn", "size"), synapses=("syn", "sum"))
    mapping["readout_leg_motor_neurons"] = {"definition": "super_class == vnc_motor and sub_class in {fl, ml, hl}",
                                            "counts": {f"{a}_{b}": int(v) for (a, b), v in tab.stack().items()}}
    md += ["## B. Readout population: leg motor neurons", "",
           "Definition (MANC convention, used by MaleCNS): `super_class == 'vnc_motor'` and `sub_class` in "
           "`fl` (front), `ml` (middle), `hl` (hind leg).", "", tab.to_markdown(), "",
           f"Direct `{left_dn}` -> leg MN connections: {len(direct)} MNs, {int(direct.synapse_count.sum())} synapses:", "",
           direct_by_leg.to_markdown(), ""]

    # ---------------------------------------------------------------- C. published circuit types in v1.0
    labels = KEY["labels"]
    pub = KEY["ids_as_published"]["MaleCNS"]
    rows = []
    for lab in LABELS:
        typ = labels[lab]["type"]
        ids = cx.ids_of_type(typ)
        prof = leg_profile(cx, ids)
        for i in ids:
            r = cx.neurons.loc[i]
            rows.append({"label": lab, "type": typ, "source_id": int(i), "instance": r.instance, "soma_side": r.soma_side,
                         "soma_neuromere": r.soma_neuromere, "group_id": r.group_id, "nt_consensus": r.nt_consensus,
                         "nt_type_confidence": r.nt_type_confidence, "manc_body_id": r.manc_body_id,
                         "hemilineage_truman": r.hemilineage_truman, "n_pre": r.n_pre, "n_post": r.n_post,
                         "dominant_leg": prof.loc[i, "dominant_leg"] if i in prof.index else None,
                         "dominant_leg_fraction": prof.loc[i, "dominant_leg_fraction"] if i in prof.index else None})
    circ = pd.DataFrame(rows)
    circ.to_csv(TABLES / "circuit_types_all_copies.csv", index=False, lineterminator="\n")
    t1l = circ[circ.dominant_leg == "T1L"].groupby("label").source_id.apply(list).to_dict()
    t1r = circ[circ.dominant_leg == "T1R"].groupby("label").source_id.apply(list).to_dict()
    id_check = []
    for lab in LABELS:
        p_id = pub.get(lab)
        in_v10 = cx.has(p_id) if p_id else False
        typ_v10 = cx.neurons.loc[p_id, "cell_type"] if in_v10 else None
        prow = wt[wt.bodyId == p_id]
        id_check.append({"label": lab, "published_type": labels[lab]["type"], "paper_T1L_id": p_id,
                         "paper_table_type": prow.type.iloc[0] if len(prow) else None,
                         "exists_in_v1.0": in_v10, "v1.0_type": typ_v10, "type_unchanged": typ_v10 == labels[lab]["type"],
                         "v1.0_T1L_copies": t1l.get(lab, []), "paper_T1R_id": pub["T1R_copies"].get(lab),
                         "v1.0_T1R_copies": t1r.get(lab, [])})
    idc = pd.DataFrame(id_check)
    mapping["circuit_neurons"] = idc.to_dict(orient="records")
    counts = circ.groupby(["label", "type"]).size().rename("n_copies").reset_index()
    md += ["## C. Published circuit cell types located in MaleCNS v1.0", "",
           "Types are MANC-style VNC names (IN + hemilineage + number; `XXX` = hemilineage undetermined). "
           "Leg assignment below = neuropil with most synapses (pre+post) among the six leg neuropils.", "",
           counts.to_markdown(index=False), "",
           "Copies per leg (dominant leg neuropil):", "",
           pd.crosstab(circ.label, circ.dominant_leg).to_markdown(), "",
           "Paper's MaleCNS IDs (authors' 2026-02-10 extraction, pre-v1.0) vs v1.0:", "",
           idc.to_markdown(index=False), ""]

    # ---------------------------------------------------------------- D. circuit connectivity (T1L)
    members = {"DNg100": left_dn, **{lab: (t1l.get(lab) or [None])[0] for lab in LABELS}}
    sign = {lab: (1 if labels[lab]["nt"] == "acetylcholine" else -1) for lab in LABELS} | {"DNg100": 1}
    pairs = [e.split("->") for e in KEY["signed_counts_as_published"]["edges"]]
    paper_vals = dict(zip(KEY["signed_counts_as_published"]["edges"], KEY["signed_counts_as_published"]["MaleCNS"]))
    rows = []
    for a, b in pairs:
        ia, ib = members.get(a), members.get(b)
        tot, vnc_c = edge_counts(cx, ia, ib, vnc) if ia and ib else (None, None)
        pa_, pb_ = (pub["DNg100_left_VNC"] if a == "DNg100" else pub.get(a)), pub.get(b)
        w_paper_matrix = float(W.loc[pa_, pb_]) if (pa_ in W.index and pb_ in W.columns) else None
        rows.append({"edge": f"{a}->{b}", "v1.0_pre": ia, "v1.0_post": ib, "v1.0_synapses_all": tot,
                     "v1.0_synapses_VNC": vnc_c, "v1.0_signed_VNC": None if vnc_c is None else sign[a] * vnc_c,
                     "paper_signed_(answer_key)": paper_vals[f"{a}->{b}"], "paper_matrix_value": w_paper_matrix})
    conn = pd.DataFrame(rows)
    conn["abs_diff_VNC_vs_paper"] = (conn["v1.0_signed_VNC"] - conn["paper_signed_(answer_key)"]).abs()
    conn.to_csv(TABLES / "t1l_circuit_connectivity.csv", index=False, lineterminator="\n")
    mapping["t1l_members_v1.0"] = {k: (int(v) if v else None) for k, v in members.items()}
    mapping["t1l_connectivity"] = conn.to_dict(orient="records")
    ids_all = [v for v in members.values() if v]
    sub = cx.subgraph(ids_all, min_count=1)
    lab_of = {v: k for k, v in members.items() if v}
    mat = pd.DataFrame(0, index=list(lab_of.values()), columns=list(lab_of.values()))
    for r in sub.edges.itertuples():
        mat.loc[lab_of[r.pre_id], lab_of[r.post_id]] = r.synapse_count
    mat.to_csv(TABLES / "t1l_circuit_matrix_all_rois.csv", lineterminator="\n")
    md += ["## D. Connectivity of the front-left (T1L) circuit copies in v1.0", "",
           f"Members (v1.0 IDs): {mapping['t1l_members_v1.0']}", "",
           "Synapse counts pre (row) -> post (column), all ROIs, v1.0:", "", mat.to_markdown(), "",
           "Comparison with the paper's MaleCNS numbers (their matrix: VNC ROIs only, >=5 floor, signed by predicted NT):",
           "", conn.to_markdown(index=False), ""]

    # ---------------------------------------------------------------- E. recurrence around the pathway
    ds5 = cx.downstream(left_dn, min_count=5)
    tgt = ds5.post_id.to_numpy()
    tgt_in = cx.neurons.loc[tgt]
    vnc_tgt = tgt[(tgt_in.super_class.isin(["vnc_intrinsic", "ascending_neuron", "vnc_motor"])).to_numpy()]
    e = cx.edges_between(vnc_tgt, vnc_tgt, min_count=5, annotate=False)
    pairs_set = set(zip(e.pre_id, e.post_id))
    recip = sum(1 for (a, b) in pairs_set if a != b and (b, a) in pairs_set) // 2
    rank = ds5.reset_index(drop=True)
    e1_rank = int(rank.index[rank.post_id == members["E1"]][0]) + 1 if members["E1"] in set(rank.post_id) else None
    in_e1 = cx.upstream(members["E1"]) if members["E1"] else pd.DataFrame()
    dn_share = (in_e1.loc[in_e1.pre_id == left_dn, "synapse_count"].sum() / in_e1.synapse_count.sum()) if len(in_e1) else None
    # greedy-difficulty ranks (how easily a strongest-edge heuristic would walk the published circuit)
    def rank_in(df: pd.DataFrame, col: str, target: int | None) -> int | None:
        if target is None or target not in set(df[col]):
            return None
        return int(df.reset_index(drop=True).index[df.reset_index(drop=True)[col] == target][0]) + 1

    e1_out = cx.downstream(members["E1"]) if members["E1"] else pd.DataFrame(columns=["post_id"])
    e2_in = cx.upstream(members["E2"]) if members["E2"] else pd.DataFrame(columns=["pre_id"])
    inh = in_e1[in_e1.pre_nt_consensus.isin(["gaba", "glutamate", "histamine"])] if len(in_e1) else in_e1
    ranks = {"E2_rank_among_E1_outputs": rank_in(e1_out, "post_id", members["E2"]),
             "I1_rank_among_E1_inputs": rank_in(in_e1, "pre_id", members["I1"]),
             "I2_rank_among_E1_inputs": rank_in(in_e1, "pre_id", members["I2"]),
             "I1_rank_among_E1_inhibitory_inputs": rank_in(inh, "pre_id", members["I1"]),
             "I2_rank_among_E1_inhibitory_inputs": rank_in(inh, "pre_id", members["I2"]),
             "E1_rank_among_E2_inputs": rank_in(e2_in, "pre_id", members["E1"])}
    mapping["recurrence"] = {"dng100_targets_ge5": int(len(ds5)), "vnc_targets_ge5": int(len(vnc_tgt)),
                             "edges_among_vnc_targets_ge5": int(len(e)), "reciprocal_pairs_among_targets": int(recip),
                             "E1_rank_among_DNg100_targets": e1_rank, "DNg100_share_of_E1_input": dn_share, **ranks}
    md += ["## E. Recurrent connectivity around the DNg100 pathway (v1.0)", "",
           f"* `{left_dn}` has {len(ds5)} targets with >= 5 synapses; {len(vnc_tgt)} are VNC intrinsic/ascending/motor.",
           f"* Among those VNC targets there are {len(e)} edges with >= 5 synapses and {recip} reciprocally connected pairs "
           f"(density {len(e) / max(1, len(vnc_tgt) * (len(vnc_tgt) - 1)):.3f}).",
           f"* E1 ({members['E1']}) ranks #{e1_rank} among `{left_dn}`'s targets by synapse count; DNg100 provides "
           f"{dn_share:.1%} of E1's input synapses from neurons." if dn_share is not None else "",
           f"* Greedy-walk ranks (1 = strongest): {ranks}", ""]

    # ---------------------------------------------------------------- F. DNg100 -> E1 copies across legs
    e1 = circ[circ.label == "E1"].set_index("source_id")
    rows = []
    for i, r in e1.iterrows():
        rows.append({"E1_copy": i, "leg": r.dominant_leg, f"from_{left_dn}": cx.edge_count(left_dn, i),
                     f"from_{right_dn}": cx.edge_count(right_dn, i)})
    six = pd.DataFrame(rows).sort_values("leg")
    six.to_csv(TABLES / "dng100_to_e1_all_legs.csv", index=False, lineterminator="\n")
    md += ["## F. DNg100 -> E1 (IN17A001) across all six legs", "", six.to_markdown(index=False), ""]

    # ---------------------------------------------------------------- G. DNb08 (second pathway in the paper)
    dnb = cx.neurons_by_type("DNb08")
    md += ["## G. DNb08 (the paper's second rhythm-driving DN type)", "",
           dnb[["instance", "soma_side", "nt_consensus", "manc_body_id", "synonyms"]].to_markdown(), ""]
    mapping["DNb08"] = [int(i) for i in dnb.index]

    (HERE / "malecns_v1.0_findings.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    (HERE / "malecns_v1.0_mapping.json").write_text(json.dumps(mapping, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
    print("wrote", HERE / "malecns_v1.0_findings.md")


if __name__ == "__main__":
    main()
