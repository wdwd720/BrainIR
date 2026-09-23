"""Deterministic table I/O and file fingerprints."""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.ipc as ipc
import pyarrow.parquet as pq

from . import paths
from .schema.tables import TableSpec, conform

PARQUET_OPTIONS = dict(
    compression="zstd",
    compression_level=3,
    use_dictionary=True,
    write_statistics=True,
    version="2.6",
    data_page_size=1 << 20,
)
ROW_GROUP_SIZE = 1_000_000


def sha256_file(path: Path, block: int = 8 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(block):
            h.update(chunk)
    return h.hexdigest()


def sort_table(table: pa.Table, keys: tuple[str, ...]) -> pa.Table:
    if not keys or table.num_rows == 0:
        return table
    # dictionary columns sort by index order, not value; sort on decoded values for determinism
    sort_cols = []
    t = table
    for k in keys:
        col = t.column(k)
        if pa.types.is_dictionary(col.type):
            tmp = f"__sort_{k}"
            t = t.append_column(tmp, col.cast(col.type.value_type))
            sort_cols.append((tmp, "ascending"))
        else:
            sort_cols.append((k, "ascending"))
    idx = pc.sort_indices(t, sort_keys=sort_cols)
    return table.take(idx)


def write_canonical(table: pa.Table, spec: TableSpec, path: Path, extra_metadata: dict[str, str] | None = None) -> dict:
    """Conform to spec, sort deterministically, write Parquet, return a file record."""
    table = conform(table, spec)
    table = sort_table(table, spec.sort_by)
    # normalise dictionaries so identical content -> identical bytes
    table = table.unify_dictionaries().combine_chunks()
    arrays = []
    for i, field in enumerate(table.schema):
        col = table.column(i)
        if pa.types.is_dictionary(field.type):
            col = col.cast(field.type.value_type).dictionary_encode().cast(field.type)
        arrays.append(col)
    md = dict(table.schema.metadata or {})
    for k, v in (extra_metadata or {}).items():
        md[k.encode()] = str(v).encode()
    table = pa.Table.from_arrays(arrays, schema=table.schema.with_metadata(md))
    return write_parquet(table, path, row_group_size=ROW_GROUP_SIZE)


def write_parquet(table: pa.Table, path: Path, row_group_size: int = ROW_GROUP_SIZE) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    pq.write_table(table, tmp, row_group_size=row_group_size, **PARQUET_OPTIONS)
    if path.exists():
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    os.replace(tmp, path)
    return file_record(path, rows=table.num_rows, schema=table.schema)


def file_record(path: Path, rows: int | None = None, schema: pa.Schema | None = None) -> dict:
    rec = {
        "path": paths.relpath_for_record(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    if rows is not None:
        rec["rows"] = int(rows)
    if schema is not None:
        rec["schema"] = schema_record(schema)
    return rec


def schema_record(schema: pa.Schema) -> list[dict]:
    out = []
    for f in schema:
        d = {"name": f.name, "type": str(f.type), "nullable": f.nullable}
        if f.metadata:
            d.update({k.decode(): v.decode() for k, v in f.metadata.items()})
        out.append(d)
    return out


def open_ipc(path: Path) -> ipc.RecordBatchFileReader:
    """Open an Arrow IPC (Feather v2) file memory-mapped (cheap, random access)."""
    return ipc.open_file(pa.memory_map(str(path), "r"))


def ipc_row_count(path: Path) -> int:
    reader = open_ipc(path)
    return sum(reader.get_batch(i).num_rows for i in range(reader.num_record_batches))


def iter_ipc_batches(path: Path, columns: list[str] | None = None):
    """Yield record batches (optionally a column subset) from a Feather v2 file."""
    reader = open_ipc(path)
    idx = None
    if columns is not None:
        names = reader.schema.names
        missing = [c for c in columns if c not in names]
        if missing:
            raise KeyError(f"{path.name}: missing columns {missing}")
        idx = [names.index(c) for c in columns]
    for i in range(reader.num_record_batches):
        b = reader.get_batch(i)
        yield b if idx is None else b.select(idx)
