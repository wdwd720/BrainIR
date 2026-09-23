"""On-demand extraction of individual synapses (canonical ``synapses`` table).

The full synapse-partner table (312M rows) stays in raw/ as the official Arrow
IPC file; subsets are extracted by pyarrow predicate scans (~20-60 s for a
full scan on an SSD) and conformed to :data:`brainir.schema.tables.SYNAPSES`.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as pads

from . import paths
from .io import write_canonical
from .schema.tables import SYNAPSES
from .schema.vocab import UNASSIGNED_NEUROPIL
from .sources.registry import get_source


def _raw(dataset: str, version: str, raw_dir: Path | None) -> tuple[Path, list[str]]:
    src = get_source(dataset, version)
    root = Path(raw_dir) if raw_dir else paths.raw_dir(dataset, version)
    partners = root / src.local_relpath(src.file("syn_partners"))
    meta = json.loads((root / src.local_relpath(src.file("neuprint_meta_json"))).read_text(encoding="utf-8"))
    return partners, list(meta["primaryRois"])


def extract_synapses(pre_ids: Iterable[int] | None = None, post_ids: Iterable[int] | None = None, *,
                     mode: str = "and", dataset: str = "male-cns", version: str = "v1.0",
                     raw_dir: Path | None = None) -> pa.Table:
    """Synapses whose presynaptic body is in ``pre_ids`` and/or postsynaptic body is in ``post_ids``.

    mode='and': both constraints (a given side left as None is unconstrained); mode='or': either side matches.
    """
    if pre_ids is None and post_ids is None:
        raise ValueError("give pre_ids and/or post_ids (refusing to materialise all 312M synapses)")
    if mode not in ("and", "or"):
        raise ValueError("mode must be 'and' or 'or'")
    path, primary = _raw(dataset, version, raw_dir)
    conds = []
    if pre_ids is not None:
        conds.append(pc.field("body_pre").isin(pa.array(sorted({int(i) for i in pre_ids}), pa.int64())))
    if post_ids is not None:
        conds.append(pc.field("body_post").isin(pa.array(sorted({int(i) for i in post_ids}), pa.int64())))
    expr = conds[0]
    for c in conds[1:]:
        expr = (expr & c) if mode == "and" else (expr | c)
    t = pads.dataset(str(path), format="ipc").to_table(filter=expr)
    roi = t.column("primary_post")
    if pa.types.is_dictionary(roi.type):
        roi = roi.cast(roi.type.value_type)
    roi = pc.if_else(pc.is_in(roi, value_set=pa.array(primary, pa.string())), roi,
                     pa.scalar(UNASSIGNED_NEUROPIL, pa.string()))
    out = pa.table({
        "pre_id": t.column("body_pre"), "post_id": t.column("body_post"),
        "x_pre": t.column("x_pre"), "y_pre": t.column("y_pre"), "z_pre": t.column("z_pre"),
        "x_post": t.column("x_post"), "y_post": t.column("y_post"), "z_post": t.column("z_post"),
        "conf_pre": t.column("conf_pre"), "conf_post": t.column("conf_post"), "neuropil": roi,
    })
    return out


def write_synapse_subset(table: pa.Table, name: str, dataset: str = "male-cns", version: str = "v1.0",
                         out_dir: Path | None = None) -> dict:
    """Write a conformed, deterministically sorted synapse subset to processed/<ds>/<ver>/synapses/<name>.parquet."""
    out = Path(out_dir) if out_dir else paths.processed_dir(dataset, version) / "synapses"
    return write_canonical(table, SYNAPSES, out / f"{name}.parquet",
                           {"brainir_dataset": dataset, "brainir_dataset_version": version, "brainir_subset": name})
