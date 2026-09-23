"""BrainIR command line interface.

Examples::

    brainir acquire --dataset male-cns --version v1.0 --tier metadata --tier core
    brainir acquire --tier synapses
"""

from __future__ import annotations

import argparse
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
    from .ingest.malecns import IngestAborted, IngestConfig, build
    from .manifest import write_manifest
    from .sources import get_source

    source = get_source(args.dataset, args.version)
    if source.dataset != "male-cns":
        raise SystemExit(f"no ingestion pipeline registered for {source.dataset}")
    cfg = IngestConfig(source=source, synapse_checks=not args.no_synapse_checks,
                       synapse_sample_neurons=args.sample, seed=args.seed, threads=args.threads,
                       duckdb_memory_limit=args.memory)
    try:
        res = build(cfg)
    except IngestAborted as exc:
        print(f"ABORTED: {exc}")
        return 2
    report = res["report"]
    if not args.no_manifest:
        path = write_manifest(source, res["build_info"], report.to_dict(), res["out_dir"])
        print(f"manifest: {path}")
    s = report.summary()
    print(f"validation: {s['pass']} pass, {s['fail']} fail, {s['warn']} warn, {s['info']} info")
    for c in report.checks:
        if c.status in ("fail", "warn"):
            print(f"  {c.status.upper():4s} {c.check_id}: observed={c.observed} expected={c.expected}")
    return 1 if s["fail"] else 0


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
    i.set_defaults(func=cmd_ingest)
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
