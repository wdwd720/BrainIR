"""Graph access layer on the synthetic fixture (known answers)."""

from __future__ import annotations

import networkx as nx
import pytest

from brainir.schema.models import DirectedConnection, Neuron


def test_basic_sizes(cx):
    assert cx.n_neurons == 7 and cx.n_edges == 11
    assert cx.dataset == "male-cns" and cx.version == "v1.0"


def test_integer_columns_never_become_float(cx):
    # 105 has no soma location (null soma_x): the column must stay a nullable integer, not float64
    assert cx.neurons["soma_x"].dtype.name == "Int64" and cx.neurons["n_pre"].dtype.name == "Int32"
    r = cx.neuron(104)
    assert isinstance(r["n_pre"], int) and isinstance(r["source_id"], int) and cx.neuron(105)["soma_x"] is None


def test_fetch_neuron_by_id(cx):
    n = cx.neuron(101)
    assert n["cell_type"] == "DNtest" and n["super_class"] == "descending_neuron" and n["n_downstream"] == 10
    with pytest.raises(KeyError):
        cx.neuron(999999)
    assert cx.has(101) and not cx.has(900)  # fragment is not a neuron


def test_neurons_by_type_and_search(cx):
    assert cx.ids_of_type("INa").tolist() == [102]
    assert set(cx.ids_of_type("IN.", regex=True)) == {102, 103}
    assert set(cx.search("^in", fields=("cell_type",)).index) == {102, 103}  # case-insensitive by default
    assert cx.search("^in", fields=("cell_type",), case=True).empty


def test_downstream_upstream(cx):
    d = cx.downstream(101)
    assert dict(zip(d.post_id, d.synapse_count)) == {102: 6, 103: 3, 106: 1}
    assert d.iloc[0].post_id == 102 and d.iloc[0].post_type == "INa"  # sorted by strength
    assert dict(zip(d.post_id, d.synapse_count_hp)) == {102: 5, 103: 2, 106: 1}
    u = cx.upstream(102)
    assert dict(zip(u.pre_id, u.synapse_count)) == {101: 6, 102: 1, 103: 2, 105: 3}  # fragment 900 excluded
    assert 102 not in set(cx.upstream(102, include_autapses=False).pre_id)
    assert set(cx.downstream(101, min_count=3).post_id) == {102, 103}


def test_edge_strength_and_neuropils(cx):
    assert cx.edge_count(101, 102) == 6 and cx.edge_count(102, 101) == 0
    assert cx.neuropil_breakdown(101, 102) == {"LegNp(T1)(L)": 4, "<unassigned>": 2}
    eb = cx.edges_between([102, 103], [102, 103])
    assert {(r.pre_id, r.post_id): r.synapse_count for r in eb.itertuples()} == {(102, 102): 1, (102, 103): 1, (103, 102): 2}


def test_k_hop(cx):
    h = cx.k_hop(101, 1, direction="out")
    assert h.to_dict() == {101: 0, 102: 1, 103: 1, 106: 1}
    h2 = cx.k_hop(101, 2, direction="out")
    assert h2[104] == 2 and h2[107] == 2
    hin = cx.k_hop(101, 1, direction="in")
    assert set(hin.index) == {101, 106, 107}
    assert set(cx.k_hop(101, 1, direction="out", min_count=3).index) == {101, 102, 103}
    with pytest.raises(ValueError):
        cx.k_hop(101, 5, direction="out", max_nodes=3)


def test_subgraph_and_networkx(cx):
    sub = cx.subgraph(cx.k_hop(101, 1, direction="out"))
    g = sub.to_networkx()
    assert isinstance(g, nx.DiGraph) and set(g.nodes) == {101, 102, 103, 106}
    assert g[101][102]["synapse_count"] == 6 and g.has_edge(102, 102)


def test_shortest_paths(cx):
    assert cx.shortest_paths(105, 104) == [[105, 102, 104]]
    assert cx.shortest_paths(107, 104) == [[107, 101, 102, 104]]
    assert cx.shortest_paths(104, 101) == []
    assert cx.shortest_paths(107, 104, min_count=5) == []  # 102->104 (4) is below threshold


def test_nt_and_sign_hypotheses(cx):
    assert cx.sign_hypothesis(101).sign == 1
    s102 = cx.sign_hypothesis(102)
    assert s102.sign == -1 and s102.rule_class == "conventional_fast" and s102.nt_confidence == pytest.approx(0.8)
    s103 = cx.sign_hypothesis(103)  # consensus from literature label -> no model confidence
    assert s103.sign == -1 and s103.rule_class == "context_dependent" and s103.nt_confidence is None
    assert cx.sign_hypothesis(106).sign is None  # serotonin -> consensus unclear
    assert cx.sign_hypothesis(104) is None  # no NT prediction at all (no T-bars)
    tbl = cx.sign_table([101, 102, 104])
    assert tbl.set_index("source_id").loc[101, "sign"] == 1
    assert cx.nt([103]).loc[103, "nt_literature_label"] == "glutamate"


def test_typed_records(cx):
    n = cx.neuron_model(102)
    assert isinstance(n, Neuron) and n.neuron_uid == "male-cns:v1.0:102"
    assert sum(x.n_post for x in n.neuropils) == n.n_post
    assert n.morphology[0].uri.endswith("/102.swc")
    c = cx.connection_model(101, 102)
    assert isinstance(c, DirectedConnection) and c.synapse_count == 6 and c.predicted_sign.sign == 1
    assert cx.connection_model(102, 101) is None
    assert cx.connection_model(102, 102).is_autapse
