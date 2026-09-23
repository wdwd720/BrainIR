"""Graph access layer over processed BrainIR tables.

    >>> from brainir.graph import Connectome
    >>> cx = Connectome.open("male-cns", "v1.0")
    >>> cx.neurons_by_type("DNg100")
    >>> cx.downstream(cx.ids_of_type("DNg100"), min_count=5)
    >>> sub = cx.subgraph(cx.k_hop(seeds, k=2, direction="out", min_count=5))

Conventions
-----------
* IDs are dataset-native ``source_id`` integers within one (dataset, version).
* ``synapse_count`` is anatomy (T-bar->PSD pairs), never a physiological weight.
* Signs are *hypotheses* computed on demand from predicted neurotransmitters
  under the versioned rule :data:`brainir.schema.vocab.SIGN_RULE_ID`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import duckdb
import networkx as nx
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import scipy.sparse as sp

from . import paths
from .schema.models import (
    DirectedConnection,
    MorphologyRef,
    Neuron,
    NeuropilCount,
    NeurotransmitterPrediction,
    Provenance,
    SignHypothesis,
)
from .schema.vocab import SIGN_RULE_ID, sign_for_nt
from .sources.registry import SOURCES

SEARCH_FIELDS = ("cell_type", "instance", "synonyms", "flywire_type", "manc_type", "hemibrain_type")
_NULLABLE_INT = ("n_pre", "n_post", "n_downstream", "n_upstream", "size_voxels", "group_id", "manc_body_id",
                 "soma_x", "soma_y", "soma_z", "nt_body_n_tbars", "nt_type_n_tbars")


def _ids(x: int | Iterable[int]) -> np.ndarray:
    if isinstance(x, (int, np.integer)):
        return np.array([int(x)], dtype=np.int64)
    return np.unique(np.asarray(list(x), dtype=np.int64))


@dataclass
class Subgraph:
    neurons: pd.DataFrame
    edges: pd.DataFrame

    def to_networkx(self) -> nx.DiGraph:
        g = nx.DiGraph()
        for nid, row in self.neurons.iterrows():
            g.add_node(int(nid), cell_type=row.get("cell_type"), instance=row.get("instance"),
                       nt_consensus=row.get("nt_consensus"))
        for r in self.edges.itertuples(index=False):
            g.add_edge(int(r.pre_id), int(r.post_id), synapse_count=int(r.synapse_count),
                       synapse_count_hp=int(r.synapse_count_hp))
        return g


class Connectome:
    """Read-only, in-memory view of one processed dataset version."""

    def __init__(self, processed_dir: Path | str, *, min_count: int = 1):
        self.dir = Path(processed_dir)
        info_path = self.dir / "build_info.json"
        self.build_info = json.loads(info_path.read_text()) if info_path.exists() else {}
        nt = pq.read_table(self.dir / "neurons.parquet").to_pandas()
        self.dataset = str(nt["dataset"].iloc[0]) if len(nt) else self.build_info.get("dataset")
        self.version = str(nt["dataset_version"].iloc[0]) if len(nt) else self.build_info.get("version")
        for c in nt.columns:
            if isinstance(nt[c].dtype, pd.CategoricalDtype):
                nt[c] = nt[c].astype(object).where(nt[c].notna(), None)
        self.neurons = nt.set_index("source_id", drop=False)
        self.ids = self.neurons.index.to_numpy(dtype=np.int64)  # sorted (written sorted)
        if not np.all(np.diff(self.ids) > 0):
            raise ValueError("neurons.parquet must be sorted and unique by source_id")
        e = pq.read_table(self.dir / "connections.parquet",
                          columns=["pre_id", "post_id", "synapse_count", "synapse_count_hp"]).to_pandas()
        if min_count > 1:
            e = e[e["synapse_count"] >= min_count]
        self.min_count_loaded = min_count
        self._pre = e["pre_id"].to_numpy(np.int64)
        self._post = e["post_id"].to_numpy(np.int64)
        self._w = e["synapse_count"].to_numpy(np.int64)
        self._whp = e["synapse_count_hp"].to_numpy(np.int64)
        n = len(self.ids)
        pi, qi = self._index(self._pre), self._index(self._post)
        self._A = sp.csr_matrix((self._w, (pi, qi)), shape=(n, n))       # A[i, j] = synapses i -> j
        self._AT = self._A.T.tocsr()                                      # AT[j, i] = synapses i -> j
        self._Ahp = sp.csr_matrix((self._whp, (pi, qi)), shape=(n, n))
        self._duck = duckdb.connect()

    # ------------------------------------------------------------------ opening
    @classmethod
    def open(cls, dataset: str = "male-cns", version: str = "v1.0", **kw) -> Connectome:
        return cls(paths.processed_dir(dataset, version), **kw)

    def _index(self, ids: np.ndarray) -> np.ndarray:
        idx = np.searchsorted(self.ids, ids)
        bad = (idx >= len(self.ids)) | (self.ids[np.minimum(idx, len(self.ids) - 1)] != ids)
        if bad.any():
            raise KeyError(f"unknown neuron id(s): {ids[bad][:10].tolist()}")
        return idx

    def has(self, source_id: int) -> bool:
        i = np.searchsorted(self.ids, source_id)
        return bool(i < len(self.ids) and self.ids[i] == source_id)

    @property
    def n_neurons(self) -> int:
        return len(self.ids)

    @property
    def n_edges(self) -> int:
        return int(self._A.nnz)

    # ------------------------------------------------------------------ neurons
    def neuron(self, source_id: int) -> dict:
        if not self.has(source_id):
            raise KeyError(f"neuron {source_id} not in {self.dataset}:{self.version}")
        return self._row(self.neurons.loc[int(source_id)])

    @staticmethod
    def _row(row: pd.Series) -> dict:
        out = {}
        for k, v in row.items():
            if v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NA:
                out[k] = None
            elif isinstance(v, np.generic):
                out[k] = v.item()
            else:
                out[k] = v
        return out

    def neurons_by_type(self, cell_type: str, *, regex: bool = False) -> pd.DataFrame:
        s = self.neurons["cell_type"].astype("string")
        m = s.str.fullmatch(cell_type, na=False) if regex else s.eq(cell_type).fillna(False)
        return self.neurons[m.to_numpy(bool)]

    def ids_of_type(self, cell_type: str, *, regex: bool = False) -> np.ndarray:
        return self.neurons_by_type(cell_type, regex=regex).index.to_numpy(np.int64)

    def search(self, pattern: str, fields: Iterable[str] = SEARCH_FIELDS, *, case: bool = False,
               regex: bool = True) -> pd.DataFrame:
        mask = np.zeros(len(self.neurons), dtype=bool)
        flags = 0 if case else re.IGNORECASE
        for f in fields:
            s = self.neurons[f].astype("string")
            mask |= s.str.contains(pattern, case=case, flags=flags, regex=regex, na=False).to_numpy(bool)
        return self.neurons[mask]

    # ------------------------------------------------------------------ connectivity
    def _edge_frame(self, pre_idx: np.ndarray, post_idx: np.ndarray, w: np.ndarray, whp: np.ndarray,
                    annotate: bool = True) -> pd.DataFrame:
        df = pd.DataFrame({"pre_id": self.ids[pre_idx], "post_id": self.ids[post_idx],
                           "synapse_count": w.astype(np.int64), "synapse_count_hp": whp.astype(np.int64)})
        if annotate and len(df):
            n = self.neurons
            for side, col in (("pre", "pre_id"), ("post", "post_id")):
                sub = n.loc[df[col].to_numpy(), ["cell_type", "instance", "nt_consensus"]]
                df[f"{side}_type"] = sub["cell_type"].to_numpy()
                df[f"{side}_instance"] = sub["instance"].to_numpy()
                if side == "pre":
                    df["pre_nt_consensus"] = sub["nt_consensus"].to_numpy()
        return df.sort_values(["synapse_count", "pre_id", "post_id"], ascending=[False, True, True], ignore_index=True)

    def downstream(self, ids: int | Iterable[int], *, min_count: int = 1, include_autapses: bool = True,
                   annotate: bool = True) -> pd.DataFrame:
        """Direct postsynaptic partners of ``ids`` (edges ids -> partner)."""
        rows = self._index(_ids(ids))
        sub = self._A[rows].tocoo()
        whp = np.asarray(self._Ahp[rows][sub.row, sub.col]).ravel()
        keep = sub.data >= min_count
        pre_idx, post_idx = rows[sub.row[keep]], sub.col[keep]
        df = self._edge_frame(pre_idx, post_idx, sub.data[keep], whp[keep], annotate)
        return df if include_autapses else df[df.pre_id != df.post_id].reset_index(drop=True)

    def upstream(self, ids: int | Iterable[int], *, min_count: int = 1, include_autapses: bool = True,
                 annotate: bool = True) -> pd.DataFrame:
        """Direct presynaptic partners of ``ids`` (edges partner -> ids)."""
        cols = self._index(_ids(ids))
        sub = self._AT[cols].tocoo()  # rows: targets (subset), cols: sources
        pre_idx, post_idx = sub.col, cols[sub.row]
        whp = np.asarray(self._Ahp[pre_idx, post_idx]).ravel()
        keep = sub.data >= min_count
        df = self._edge_frame(pre_idx[keep], post_idx[keep], sub.data[keep], whp[keep], annotate)
        return df if include_autapses else df[df.pre_id != df.post_id].reset_index(drop=True)

    def edge_count(self, pre: int, post: int) -> int:
        i, j = self._index(_ids(pre))[0], self._index(_ids(post))[0]
        return int(self._A[i, j])

    def edges_between(self, pre_ids: Iterable[int], post_ids: Iterable[int], *, min_count: int = 1,
                      annotate: bool = True) -> pd.DataFrame:
        pi, qi = self._index(_ids(pre_ids)), self._index(_ids(post_ids))
        sub = self._A[pi][:, qi].tocoo()
        whp = np.asarray(self._Ahp[pi][:, qi][sub.row, sub.col]).ravel()
        keep = sub.data >= min_count
        return self._edge_frame(pi[sub.row[keep]], qi[sub.col[keep]], sub.data[keep], whp[keep], annotate)

    def connection_neuropils(self, pre_ids: Iterable[int] | None = None, post_ids: Iterable[int] | None = None) -> pd.DataFrame:
        """Per-edge synapse counts by neuropil (postsynaptic location); pushdown-filtered Parquet scan."""
        where = []
        if pre_ids is not None:
            where.append(f"pre_id IN ({','.join(str(int(x)) for x in _ids(pre_ids))})")
        if post_ids is not None:
            where.append(f"post_id IN ({','.join(str(int(x)) for x in _ids(post_ids))})")
        q = "SELECT pre_id, post_id, CAST(neuropil AS VARCHAR) AS neuropil, synapse_count FROM read_parquet(?)"
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY pre_id, post_id, synapse_count DESC, neuropil"
        return self._duck.execute(q, [str(self.dir / "connection_neuropils.parquet")]).fetchdf()

    def neuron_neuropils(self, ids: Iterable[int]) -> pd.DataFrame:
        q = (f"SELECT source_id, CAST(neuropil AS VARCHAR) AS neuropil, n_pre, n_post FROM read_parquet(?) "
             f"WHERE source_id IN ({','.join(str(int(x)) for x in _ids(ids))}) ORDER BY source_id, n_pre + n_post DESC")
        return self._duck.execute(q, [str(self.dir / "neuron_neuropils.parquet")]).fetchdf()

    def neuropil_breakdown(self, pre: int, post: int) -> dict[str, int]:
        df = self.connection_neuropils([pre], [post])
        return dict(zip(df["neuropil"], df["synapse_count"].astype(int)))

    # ------------------------------------------------------------------ NT / sign
    def nt(self, ids: Iterable[int]) -> pd.DataFrame:
        cols = ["cell_type", "nt_consensus", "nt_body_prediction", "nt_body_confidence", "nt_body_n_tbars",
                "nt_type_prediction", "nt_type_confidence", "nt_type_n_tbars", "nt_literature_label"]
        return self.neurons.loc[_ids(ids), cols]

    def sign_hypothesis(self, source_id: int, basis: str = "nt_consensus") -> SignHypothesis | None:
        row = self.neuron(source_id)
        nt = row.get(basis)
        rule = sign_for_nt(nt)
        if rule is None:
            return None
        if basis == "nt_consensus":
            conf = None if row.get("nt_literature_label") else row.get("nt_type_confidence")
        elif basis == "nt_type_prediction":
            conf = row.get("nt_type_confidence")
        else:
            conf = row.get("nt_body_confidence")
        return SignHypothesis(sign=rule.sign, rule_id=SIGN_RULE_ID, rule_class=rule.rule_class, based_on_nt=nt,
                              based_on_field=basis, nt_confidence=None if conf is None else float(conf))

    def sign_table(self, ids: Iterable[int], basis: str = "nt_consensus") -> pd.DataFrame:
        rows = []
        for i in _ids(ids):
            h = self.sign_hypothesis(int(i), basis)
            rows.append({"source_id": int(i), "sign": None if h is None else h.sign,
                         "rule_class": None if h is None else h.rule_class,
                         "based_on_nt": None if h is None else h.based_on_nt,
                         "nt_confidence": None if h is None else h.nt_confidence, "rule_id": SIGN_RULE_ID})
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------ subgraphs & paths
    def k_hop(self, seeds: int | Iterable[int], k: int = 1, *, direction: str = "both", min_count: int = 1,
              max_nodes: int | None = None) -> pd.Series:
        """Neurons within k hops of the seeds. Returns Series source_id -> hop distance (seeds = 0)."""
        if direction not in ("out", "in", "both"):
            raise ValueError("direction must be 'out', 'in' or 'both'")
        start = self._index(_ids(seeds))
        dist = np.full(len(self.ids), -1, dtype=np.int64)
        dist[start] = 0
        frontier = start
        mats = [m for d, m in (("out", self._A), ("in", self._AT)) if direction in (d, "both")]
        for hop in range(1, k + 1):
            if len(frontier) == 0:
                break
            nxt = []
            for M in mats:
                sub = M[frontier]
                nxt.append(sub.indices[sub.data >= min_count])
            cand = np.unique(np.concatenate(nxt)) if nxt else np.array([], dtype=np.int64)
            cand = cand[dist[cand] < 0]
            dist[cand] = hop
            frontier = cand
            if max_nodes is not None and (dist >= 0).sum() > max_nodes:
                raise ValueError(f"k-hop neighbourhood exceeds max_nodes={max_nodes} at hop {hop}")
        sel = np.flatnonzero(dist >= 0)
        return pd.Series(dist[sel], index=pd.Index(self.ids[sel], name="source_id"), name="hop")

    def subgraph(self, ids: Iterable[int] | pd.Series, *, min_count: int = 1, annotate: bool = True) -> Subgraph:
        idx = ids.index.to_numpy() if isinstance(ids, pd.Series) else _ids(ids)
        edges = self.edges_between(idx, idx, min_count=min_count, annotate=annotate)
        return Subgraph(neurons=self.neurons.loc[_ids(idx)], edges=edges)

    def shortest_paths(self, source: int, target: int, *, max_hops: int = 4, min_count: int = 1,
                       limit: int = 100) -> list[list[int]]:
        """All shortest directed paths source -> target (<= max_hops) using edges with >= min_count synapses."""
        fwd = self.k_hop(source, max_hops, direction="out", min_count=min_count)
        if target not in fwd.index:
            return []
        bwd = self.k_hop(target, max_hops, direction="in", min_count=min_count)
        both = fwd.index.intersection(bwd.index)
        keep = both[(fwd.loc[both].to_numpy() + bwd.loc[both].to_numpy()) <= fwd.loc[target]]
        g = self.subgraph(keep, min_count=min_count, annotate=False).to_networkx()
        out = []
        for path in nx.all_shortest_paths(g, source, target):
            out.append([int(x) for x in path])
            if len(out) >= limit:
                break
        return out

    # ------------------------------------------------------------------ typed records
    def dataset_version(self):
        """DatasetVersion record from the committed manifest (data/manifests/<dataset>_<version>.manifest.json)."""
        from .manifest import dataset_version_record
        p = paths.manifests_dir() / f"{self.dataset}_{self.version}.manifest.json"
        return dataset_version_record(json.loads(p.read_text(encoding="utf-8")))

    def provenance(self) -> Provenance:
        bi = self.build_info
        return Provenance(source_dataset=self.dataset, source_version=self.version,
                          source_files=sorted(bi.get("inputs", {}).keys()), pipeline=bi.get("pipeline"),
                          pipeline_version=bi.get("pipeline_version"), git_commit=(bi.get("git") or {}).get("commit"))

    def neuron_model(self, source_id: int, *, with_neuropils: bool = True) -> Neuron:
        r = self.neuron(source_id)
        nps = []
        if with_neuropils:
            df = self.neuron_neuropils([source_id])
            nps = [NeuropilCount(neuropil=x.neuropil, n_pre=int(x.n_pre), n_post=int(x.n_post)) for x in df.itertuples()]
        src = SOURCES.get((self.dataset, self.version))
        morph = []
        if src is not None and self.dataset == "male-cns":
            morph.append(MorphologyRef(kind="skeleton_swc", coordinate_space="male-cns EM", units="8nm voxels",
                                       uri=f"gs://{src.bucket}/{self.version}/segmentation/skeletons-malecns/skeletons-swc/{source_id}.swc"))
        soma = (r["soma_x"], r["soma_y"], r["soma_z"])
        return Neuron(
            neuron_uid=r["neuron_uid"], dataset=r["dataset"], dataset_version=r["dataset_version"], source_id=r["source_id"],
            cell_type=r["cell_type"], instance=r["instance"], super_class=r["super_class"], cell_class=r["cell_class"],
            sub_class=r["sub_class"], hemilineage_ito_lee=r["hemilineage_ito_lee"], hemilineage_truman=r["hemilineage_truman"],
            animal_sex=r["animal_sex"], soma_side=r["soma_side"], root_side=r["root_side"], side=r["side"],
            soma_neuromere=r["soma_neuromere"], soma_location_voxels=None if None in soma else tuple(int(v) for v in soma),
            status=r["status"], status_label=r["status_label"], is_traced=bool(r["is_traced"]),
            neuprint_neuron_label=bool(r["neuprint_neuron_label"]), n_pre=r["n_pre"], n_post=r["n_post"],
            n_downstream=r["n_downstream"], n_upstream=r["n_upstream"],
            neurotransmitter=NeurotransmitterPrediction(
                consensus=r["nt_consensus"], body_prediction=r["nt_body_prediction"], body_confidence=r["nt_body_confidence"],
                body_n_tbars=r["nt_body_n_tbars"], type_prediction=r["nt_type_prediction"],
                type_confidence=r["nt_type_confidence"], type_n_tbars=r["nt_type_n_tbars"],
                literature_label=r["nt_literature_label"]),
            sign_hypothesis=self.sign_hypothesis(source_id), neuropils=nps, morphology=morph,
            annotations={k: r[k] for k in ("group_id", "synonyms", "flywire_type", "hemibrain_type", "manc_type",
                                           "manc_body_id", "dimorphism", "fru_dsx")},
            provenance=self.provenance())

    def connection_model(self, pre: int, post: int) -> DirectedConnection | None:
        i, j = self._index(_ids(pre))[0], self._index(_ids(post))[0]
        w = int(self._A[i, j])
        if w == 0:
            return None
        nps = [NeuropilCount(neuropil=k, n_post=v) for k, v in self.neuropil_breakdown(pre, post).items()]
        return DirectedConnection(dataset=self.dataset, dataset_version=self.version, pre_id=int(pre), post_id=int(post),
                                  synapse_count=w, synapse_count_hp=int(self._Ahp[i, j]), is_autapse=pre == post,
                                  neuropils=nps, predicted_sign=self.sign_hypothesis(pre), provenance=self.provenance())
