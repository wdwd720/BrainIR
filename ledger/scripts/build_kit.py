"""Build the labeler kit's name files (LABEL SIDE: reads network tables and annotation files only, never predictions).

    uv run --project ledger --no-sync python ledger/scripts/build_kit.py

Inputs (all pinned):
* the authors' MANC front-leg table (wTable_20250813, = manc:v1.2.1 types) and full-cord table (wTable_20251006, v1.2.3);
* MaleCNS v1.0 curated body annotations (mancBodyid, mancType, type, flywireType, hemibrainType, synonyms).

Outputs (research/ledger/kit/):
* type_list.csv: every MANC DN type of the two networks, ALPHABETICAL, names and synonyms only;
* synonyms.csv: one row per (manc_type, name, kind, source) - kinds manc_v1.2.3, malecns, flywire, hemibrain, literature;
* exposed_types.csv: the exposed list (PREREG section 2) resolved to manc_type through the synonym map.
"""

from __future__ import annotations

import glob
import hashlib
import json
import re
import sys
from pathlib import Path

import pandas as pd
import pyarrow.feather as feather

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
from brainir import paths  # noqa: E402

KIT = REPO / "research" / "ledger" / "kit"
EXT = paths.data_root() / "raw" / "external"
EXPOSED_AS_GIVEN = ["DNg100", "DNb08", "DNg12", "DNg97", "MDN", "DNa01", "DNa02", "DNp09", "DNg13", "DNp01", "DNg16", "DNg55", "DNg75",
                    "DNg74", "DNg62"]
DN_CLASS = "descending neuron"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_inputs():
    front = EXT / "pugliese_2026" / "10e7661bf4" / "wTable_20250813_DNtoMN_unsorted_withModules.csv"
    full = EXT / "pugliese_2026" / "10e7661bf4" / "wTable_20251006.feather"
    ann = Path(glob.glob(str(EXT / "malecns_v1.0_body_annotations" / "*.feather"))[0])
    ft = pd.read_csv(front, index_col=0)
    fc = feather.read_table(full).to_pandas()
    an = feather.read_table(ann).to_pandas()
    prov = {str(p.relative_to(paths.data_root())): _sha(p) for p in (front, full, ann)}
    return ft, fc, an, prov


def canonical_types(ft: pd.DataFrame, fc: pd.DataFrame) -> tuple[dict[int, str], pd.DataFrame]:
    """body -> canonical manc_type (v1.2.1 name where the body is in the front-leg table, else the v1.2.3 name)."""
    body2type = {}
    rows = []
    for _, r in fc.loc[fc["class"] == DN_CLASS].iterrows():
        body2type[int(r["bodyId"])] = str(r["type"])
    renamed = []
    for _, r in ft.loc[ft["class"] == DN_CLASS].iterrows():
        b = int(r["bodyId"])
        if b in body2type and body2type[b] != str(r["type"]):
            renamed.append((str(r["type"]), body2type[b]))
        body2type[b] = str(r["type"])
    for old, new in sorted(set(renamed)):
        rows.append({"manc_type": old, "name": new, "kind": "manc_v1.2.3", "source": "same body, full-cord table (2025-10-06)"})
    return body2type, pd.DataFrame(rows)


def split_synonyms(s: str) -> list[tuple[str, str]]:
    """'Author 2018: GF; Other 2010: pIP-a' -> [('GF', 'Author 2018'), ('pIP-a', 'Other 2010')]"""
    out = []
    for part in re.split(r";", s or ""):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            src, names = part.split(":", 1)
            for n in re.split(r",", names):
                if n.strip():
                    out.append((n.strip(), src.strip()))
        else:
            out.append((part, ""))
    return out


def driver_lines(types: list[str], S: pd.DataFrame) -> pd.DataFrame | None:
    """Kit driver-line map from the anatomy-only extraction (copied to <data>/raw/external/driver_lines_extraction/); names are
    mapped to MANC types through the type list and the synonym map (exact, case-insensitive); unmapped names are kept."""
    src = EXT / "driver_lines_extraction" / "driver_lines_raw.csv"
    if not src.exists():
        return None
    raw = pd.read_csv(src, dtype=str).fillna("")
    cand: dict[str, set[str]] = {}
    for t in types:
        cand.setdefault(t.lower(), set()).add(t)
    for n, t in zip(S["name"], S["manc_type"]):
        cand.setdefault(str(n).lower(), set()).add(t)

    def candidates(x: str) -> list[str]:
        x = x.strip()
        c = cand.get(x.lower()) or cand.get(x.split("(")[0].strip().lower()) or set()
        return sorted(c)

    cands = raw["dn_type_as_written"].map(candidates)
    mapped = cands.map(lambda c: c[0] if len(c) == 1 else ("AMBIGUOUS" if len(c) > 1 else "UNMAPPED"))
    out = pd.DataFrame({"line_id": raw["line_id"], "manc_type": mapped, "candidate_types": cands.map(";".join),
                        "name_as_written": raw["dn_type_as_written"], "line_kind": raw["line_kind"],
                        "other_cells": raw["other_cells_as_written"], "expression_note": raw["expression_note"],
                        "source_doi": raw["source_doi"], "source_locator": raw["source_locator"]})
    return out.drop_duplicates().sort_values(["line_id", "manc_type", "source_doi"]).reset_index(drop=True)


def main() -> None:
    ft, fc, an, prov = load_inputs()
    body2type, ren = canonical_types(ft, fc)
    types = sorted(set(body2type.values()))
    syn = [ren] if len(ren) else []
    dn = an[an["superclass"].astype(str).str.contains("descending", na=False)].copy()
    rows = []
    for _, r in dn.iterrows():
        mt = None
        if pd.notna(r.get("mancBodyid")) and int(r["mancBodyid"]) in body2type:
            mt, basis = body2type[int(r["mancBodyid"])], "MaleCNS mancBodyid -> MANC body type"
        elif pd.notna(r.get("mancType")) and str(r["mancType"]) in types:
            mt, basis = str(r["mancType"]), "MaleCNS mancType"
        if mt is None:
            continue
        if pd.notna(r.get("type")) and str(r["type"]) != mt:
            rows.append({"manc_type": mt, "name": str(r["type"]), "kind": "malecns", "source": basis})
        if pd.notna(r.get("flywireType")) and str(r["flywireType"]) != mt:
            rows.append({"manc_type": mt, "name": str(r["flywireType"]), "kind": "flywire", "source": "MaleCNS flywireType"})
        if pd.notna(r.get("hemibrainType")) and str(r["hemibrainType"]) != mt:
            rows.append({"manc_type": mt, "name": str(r["hemibrainType"]), "kind": "hemibrain", "source": "MaleCNS hemibrainType"})
        if pd.notna(r.get("mancType")) and str(r["mancType"]) != mt:
            rows.append({"manc_type": mt, "name": str(r["mancType"]), "kind": "malecns_mancType_string", "source": basis})
        for name, src in split_synonyms(str(r["synonyms"]) if pd.notna(r.get("synonyms")) else ""):
            if name != mt:
                rows.append({"manc_type": mt, "name": name, "kind": "literature", "source": src or "MaleCNS synonyms"})
    syn.append(pd.DataFrame(rows))
    S = pd.concat(syn, ignore_index=True).drop_duplicates().sort_values(["manc_type", "kind", "name", "source"]).reset_index(drop=True)
    # ambiguity: how many MANC types a name can denote (as a synonym of several types, or as a type name used elsewhere)
    ntypes = {}
    for n in set(S["name"]):
        ts = set(S.loc[S["name"] == n, "manc_type"]) | ({n} if n in types else set())
        ntypes[n] = len(ts)
    S["n_types_for_name"] = S["name"].map(ntypes)
    S["ambiguous"] = S["n_types_for_name"] > 1
    S.loc[S["kind"] == "malecns_mancType_string", "kind"] = "malecns_mancType_string_conflict"
    KIT.mkdir(parents=True, exist_ok=True)
    S.to_csv(KIT / "synonyms.csv", index=False, lineterminator="\n")
    # alphabetical type list, names only
    tl = []
    for t in types:
        names = S.loc[S["manc_type"] == t]
        tl.append({"manc_type": t, "other_names": "; ".join(sorted({f"{n} ({k})" for n, k in zip(names["name"], names["kind"])}))})
    pd.DataFrame(tl).sort_values("manc_type", key=lambda s: s.str.lower()).to_csv(KIT / "type_list.csv", index=False, lineterminator="\n")
    # exposed list resolved to MANC types
    ex = []
    for name in EXPOSED_AS_GIVEN:  # PREREG section 2: a name that maps to several MANC types exposes all of them
        hits = sorted(({name} if name in types else set()) | set(S.loc[S["name"] == name, "manc_type"]))
        ex.append({"name_as_given": name, "manc_types": ";".join(hits), "resolved": bool(hits)})
    pd.DataFrame(ex).to_csv(KIT / "exposed_types.csv", index=False, lineterminator="\n")
    dl = driver_lines(types, S)
    if dl is not None:
        dl.to_csv(KIT / "driver_lines.csv", index=False, lineterminator="\n")
        src = EXT / "driver_lines_extraction" / "driver_lines_raw.csv"
        prov[str(src.relative_to(paths.data_root()))] = _sha(src)
        print(f"driver lines: {len(dl)} rows, {dl['line_id'].nunique()} lines; mapped {int((~dl['manc_type'].isin(['UNMAPPED', 'AMBIGUOUS'])).sum())}, "
              f"ambiguous {int((dl['manc_type'] == 'AMBIGUOUS').sum())}, unmapped {int((dl['manc_type'] == 'UNMAPPED').sum())}")
    (KIT / "kit_inputs.json").write_text(json.dumps({"inputs_sha256": prov, "n_types": len(types), "n_synonym_rows": int(len(S))},
                                                    indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"types {len(types)}, synonym rows {len(S)}; exposed: " + ", ".join(f"{e['name_as_given']}->{e['manc_types'] or '?'}" for e in ex))


if __name__ == "__main__":
    main()
