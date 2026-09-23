"""BrainIR command line interface.

Examples::

    brainir acquire --tier metadata --tier core --tier synapses     # download + verify official files
    brainir ingest                                                  # rebuild processed tables + report + manifest
    brainir neuron 10056                                            # one neuron record (JSON)
    brainir type DNg100                                             # neurons of a cell type
    brainir search "BDN2"                                           # regex over type/instance/synonyms/...
    brainir down 10056 --min 5 --limit 20                           # strongest postsynaptic partners
    brainir up 10056 --min 5                                        # presynaptic partners
    brainir edge 10056 <post_id>                                    # counts, neuropils, sign hypothesis
    brainir khop 10056 -k 2 --direction out --min 10                # k-hop neighbourhood
    brainir paths 10056 12686 --max-hops 3 --min 5                  # shortest directed paths
    brainir synapses --pre 10056 --name dng100_out                  # extract individual synapses (Parquet)
    brainir mapping build --a male-cns:v1.0 --b manc:v1.2.1         # cross-connectome candidate table + summary
    brainir mapping lookup --a-id 10056                             # candidates of one A neuron (--b-id: reverse)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def cmd_acquire(args: argparse.Namespace) -> int:
    from .acquire import acquire_dataset
    from .sources import get_source

    source = get_source(args.dataset, args.version)
    tiers = set(args.tier) if args.tier else {"metadata", "core"}
    log_path = acquire_dataset(source, tiers, n_threads=args.threads,
                               allow_pin_mismatch=args.allow_pin_mismatch, docs=not args.no_docs)
    print(f"acquisition log: {log_path}")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    from .ingest import build_dataset
    from .ingest.common import IngestAborted, IngestConfig
    from .manifest import write_manifest
    from .sources.registry import resolve_build

    source, build_version = resolve_build(args.dataset, args.version)
    cfg = IngestConfig(source=source, build_version=build_version, synapse_checks=not args.no_synapse_checks,
                       synapse_sample_neurons=args.sample, seed=args.seed, threads=args.threads,
                       duckdb_memory_limit=args.memory, out_dir=args.out_dir)
    try:
        res = build_dataset(cfg)
    except IngestAborted as exc:
        print(f"ABORTED: {exc}")
        return 2
    report = res["report"]
    if not args.no_manifest and args.out_dir is None:
        path = write_manifest(source, res["build_info"], report.to_dict(), res["out_dir"])
        print(f"manifest: {path}")
    s = report.summary()
    print(f"validation: {s['pass']} pass, {s['fail']} fail, {s['warn']} warn, {s['info']} info")
    for c in report.checks:
        if c.status in ("fail", "warn"):
            print(f"  {c.status.upper():4s} {c.check_id}: observed={c.observed} expected={c.expected}")
    return 1 if s["fail"] else 0


# ----------------------------------------------------------------------------- queries
def _cx(args):
    from .graph import Connectome
    return Connectome.open(args.dataset, args.version)


def _emit(df, args, cols=None):
    df = df if cols is None else df[[c for c in cols if c in df.columns]]
    if args.limit:
        df = df.head(args.limit)
    if args.json:
        print(df.to_json(orient="records", indent=1))
    else:
        print(df.to_string(index=False) if len(df) else "(no rows)")


def cmd_neuron(args):
    cx = _cx(args)
    rec = cx.neuron_model(args.id).model_dump(mode="json")
    print(json.dumps(rec, indent=1))
    return 0


NEURON_COLS = ["source_id", "cell_type", "instance", "super_class", "side", "status", "nt_consensus", "n_pre", "n_post"]
EDGE_COLS = ["pre_id", "pre_type", "post_id", "post_type", "synapse_count", "synapse_count_hp", "pre_nt_consensus"]


def cmd_type(args):
    _emit(_cx(args).neurons_by_type(args.cell_type, regex=args.regex), args, NEURON_COLS)
    return 0


def cmd_search(args):
    _emit(_cx(args).search(args.pattern), args, NEURON_COLS)
    return 0


def cmd_down(args):
    _emit(_cx(args).downstream(args.ids, min_count=args.min), args, EDGE_COLS)
    return 0


def cmd_up(args):
    _emit(_cx(args).upstream(args.ids, min_count=args.min), args, EDGE_COLS)
    return 0


def cmd_edge(args):
    cx = _cx(args)
    m = cx.connection_model(args.pre, args.post)
    print(json.dumps(None if m is None else m.model_dump(mode="json"), indent=1))
    return 0


def cmd_khop(args):
    cx = _cx(args)
    hops = cx.k_hop(args.ids, args.k, direction=args.direction, min_count=args.min, max_nodes=args.max_nodes)
    df = cx.neurons.loc[hops.index, ["cell_type", "instance", "super_class"]].assign(hop=hops.to_numpy())
    df = df.reset_index().sort_values(["hop", "source_id"])
    _emit(df, args)
    return 0


def cmd_paths(args):
    cx = _cx(args)
    paths_ = cx.shortest_paths(args.src, args.dst, max_hops=args.max_hops, min_count=args.min)
    types = cx.neurons["cell_type"]
    out = [{"path": p, "types": [types.get(i) for i in p]} for p in paths_]
    print(json.dumps(out, indent=1) if args.json else "\n".join(" -> ".join(f"{i}[{t}]" for i, t in zip(o["path"], o["types"]))
                                                                  for o in out) or "(no path)")
    return 0


def cmd_synapses(args):
    from .synapses import extract_synapses, write_synapse_subset

    t = extract_synapses(args.pre, args.post, mode=args.mode, dataset=args.dataset, version=args.version)
    rec = write_synapse_subset(t, args.name, args.dataset, args.version)
    by_np = t.group_by("neuropil").aggregate([("pre_id", "count")]).sort_by([("pre_id_count", "descending")])
    print(f"{t.num_rows} synapses -> {rec['path']} (sha256 {rec['sha256'][:12]}...)")
    for r in by_np.to_pylist()[:15]:
        print(f"  {r['neuropil']:<24s} {r['pre_id_count']}")
    return 0


# ----------------------------------------------------------------------------- cross-connectome mapping
def cmd_mapping_build(args):
    import shutil

    from . import paths
    from .graph import Connectome
    from .mapping import MappingSpec, build_mapping, write_mapping

    spec = MappingSpec.parse(args.a, args.b)
    cx_a = Connectome.open(spec.a_dataset, spec.a_version)
    cx_b = Connectome.open(spec.b_dataset, spec.b_version)
    table, summary = build_mapping(cx_a, cx_b, spec=spec)
    rec = write_mapping(table, summary, out_dir=args.out_dir)
    if not args.no_manifest and args.out_dir is None:  # small committed copy next to the dataset manifests
        dst = paths.manifests_dir() / f"mapping_{spec.dir_name}.summary.json"
        shutil.copyfile(rec["out_dir"] / "summary.json", dst)
        print(f"summary copy: {dst}")
    print(f"table: {rec['table']['path']} ({rec['table']['rows']} rows, sha256 {rec['table']['sha256'][:12]}...)")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("a", "b")}, indent=1, default=str))
    return 0


def cmd_mapping_lookup(args):
    from .mapping import MappingSpec, forward_lookup, load_mapping, reverse_lookup

    spec = MappingSpec.parse(args.a, args.b)
    table = load_mapping((spec.a_dataset, spec.a_version), (spec.b_dataset, spec.b_version), out_dir=args.out_dir)
    if (args.a_id is None) == (args.b_id is None):
        raise SystemExit("give exactly one of --a-id / --b-id")
    df = forward_lookup(table, args.a_id) if args.a_id is not None else reverse_lookup(table, args.b_id)
    _emit(df, args, ["a_uid", "b_uid", "mapping_kind", "evidence_kind", "confidence", "ambiguity", "b_ambiguity", "a_cell_type",
                     "b_cell_type", "manc_type_consistent", "a_type_consistent", "side_consistent", "role_consistent", "nt_consistent",
                     "method", "notes"])
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="brainir", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("acquire", help="download + verify official raw files")
    a.add_argument("--dataset", default="male-cns")
    a.add_argument("--version", default="v1.0")
    a.add_argument("--tier", action="append", choices=["metadata", "core", "synapses", "optional"],
                   help="tiers to acquire (repeatable; default: metadata + core)")
    a.add_argument("--threads", type=int, default=4)
    a.add_argument("--allow-pin-mismatch", action="store_true",
                   help="accept remote objects that differ from registry pins (records the mismatch)")
    a.add_argument("--no-docs", action="store_true", help="skip snapshotting documentation pages")
    a.set_defaults(func=cmd_acquire)

    i = sub.add_parser("ingest", help="rebuild processed canonical tables + validation report + manifest")
    i.add_argument("--dataset", default="male-cns")
    i.add_argument("--version", default="v1.0")
    i.add_argument("--no-synapse-checks", action="store_true", help="skip synapse-level recomputation checks")
    i.add_argument("--sample", type=int, default=300, help="random neurons for synapse-level checks")
    i.add_argument("--seed", type=int, default=20260922)
    i.add_argument("--threads", type=int, default=8)
    i.add_argument("--memory", default="8GB", help="DuckDB memory limit (spills to data/cache beyond it)")
    i.add_argument("--no-manifest", action="store_true")
    i.add_argument("--out-dir", default=None,
                   help="write processed tables elsewhere (e.g. to verify byte-identical rebuilds); implies --no-manifest")
    i.set_defaults(func=cmd_ingest)

    def q(name, func, help_):
        s = sub.add_parser(name, help=help_)
        s.add_argument("--dataset", default="male-cns")
        s.add_argument("--version", default="v1.0")
        s.add_argument("--json", action="store_true", help="JSON output")
        s.add_argument("--limit", type=int, default=0, help="max rows (0 = all)")
        s.set_defaults(func=func)
        return s

    q("neuron", cmd_neuron, "neuron record by ID").add_argument("id", type=int)
    t = q("type", cmd_type, "neurons of a cell type")
    t.add_argument("cell_type")
    t.add_argument("--regex", action="store_true")
    q("search", cmd_search, "regex search over type/instance/synonyms/cross-dataset types").add_argument("pattern")
    for name, func, h in (("down", cmd_down, "downstream partners"), ("up", cmd_up, "upstream partners")):
        s = q(name, func, h)
        s.add_argument("ids", type=int, nargs="+")
        s.add_argument("--min", type=int, default=1, help="minimum synapse count")
    e = q("edge", cmd_edge, "connection record (counts, neuropils, sign hypothesis)")
    e.add_argument("pre", type=int)
    e.add_argument("post", type=int)
    k = q("khop", cmd_khop, "k-hop neighbourhood")
    k.add_argument("ids", type=int, nargs="+")
    k.add_argument("-k", type=int, default=1)
    k.add_argument("--direction", choices=["out", "in", "both"], default="both")
    k.add_argument("--min", type=int, default=1)
    k.add_argument("--max-nodes", type=int, default=None)
    pa_ = q("paths", cmd_paths, "shortest directed paths")
    pa_.add_argument("src", type=int)
    pa_.add_argument("dst", type=int)
    pa_.add_argument("--max-hops", type=int, default=4)
    pa_.add_argument("--min", type=int, default=1)
    sy = sub.add_parser("synapses", help="extract individual synapses for a neuron set -> processed/.../synapses/<name>.parquet")
    sy.add_argument("--dataset", default="male-cns")
    sy.add_argument("--version", default="v1.0")
    sy.add_argument("--pre", type=int, nargs="*", default=None, help="presynaptic body IDs")
    sy.add_argument("--post", type=int, nargs="*", default=None, help="postsynaptic body IDs")
    sy.add_argument("--mode", choices=["and", "or"], default="and")
    sy.add_argument("--name", required=True, help="subset name (file stem)")
    sy.set_defaults(func=cmd_synapses)

    m = sub.add_parser("mapping", help="cross-connectome neuron mapping (A neurons -> B candidates with evidence labels)")
    msub = m.add_subparsers(dest="mapping_command", required=True)
    mb = msub.add_parser("build", help="write data/processed/mappings/<a>__<b>/neuron_mapping.parquet + summary.json")
    mb.add_argument("--a", default="male-cns:v1.0", help="A build as dataset:version (the neurons being mapped)")
    mb.add_argument("--b", default="manc:v1.2.1", help="B build as dataset:version (where candidates are searched)")
    mb.add_argument("--out-dir", default=None, help="write elsewhere (implies --no-manifest)")
    mb.add_argument("--no-manifest", action="store_true", help="do not copy summary.json to data/manifests/")
    mb.set_defaults(func=cmd_mapping_build)
    ml = msub.add_parser("lookup", help="rows of one A neuron (--a-id) or all rows naming one B neuron (--b-id)")
    ml.add_argument("--a", default="male-cns:v1.0")
    ml.add_argument("--b", default="manc:v1.2.1")
    ml.add_argument("--out-dir", default=None)
    ml.add_argument("--a-id", type=int, default=None)
    ml.add_argument("--b-id", type=int, default=None)
    ml.add_argument("--json", action="store_true", help="JSON output")
    ml.add_argument("--limit", type=int, default=0, help="max rows (0 = all)")
    ml.set_defaults(func=cmd_mapping_lookup)
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    _setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
