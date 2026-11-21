"""Pure functions of the exam 2 label side (PREREG v3 U5, V2, T3, T4, T8, S5.4). LABEL SIDE: no prediction is read here."""

from __future__ import annotations

import re
from collections import defaultdict

import numpy as np
import pandas as pd

D15 = [f"d{i}" for i in range(1, 16)]
PRIMARY = ["d1", "d2", "d3", "d4", "d5", "d6", "d7p", "d10", "d11", "d13", "d14", "d15"]
CELLS = ("yes", "no", "unclear", "not_assessed")
RECORD_TYPES = ("whole_two_sided", "clonal", "one_sided", "partial_or_mixed")
PREPS = ("decapitated", "intact", "other")
MERGED = {"20A": "20A.22A", "22A": "20A.22A", "20B": "20B.21B.22B", "21B": "20B.21B.22B", "22B": "20B.21B.22B", "24B": "24B.25B",
          "25B": "24B.25B"}
STR_FIELDS = ("record_id", "session", "doi", "hemilineage_as_named", "hemilineages_listed", "driver", "preparation_detail", "effector",
              "penetrance", "coverage_notes", "locator", "quote", "other_observation", "notes")
VERIFY_SEED, VERIFY_N = 20261313, 30
COIN_SEED = 20261306


# ------------------------------------------------------------------------------------------------ records
def validate(rec: dict) -> list[str]:
    """Problems of one record against kit v3's `record_schema.json` (empty list = valid)."""
    p = []
    need = set(STR_FIELDS) | set(D15) | {"record_type", "preparation", "saw_model_prediction"}
    missing, extra = need - set(rec), set(rec) - need
    if missing:
        p.append(f"missing fields {sorted(missing)}")
    if extra:
        p.append(f"unknown fields {sorted(extra)}")
    for f in STR_FIELDS:
        if f in rec and not isinstance(rec[f], str):
            p.append(f"{f} is not a string")
    for f in D15:
        if f in rec and rec[f] not in CELLS:
            p.append(f"{f}={rec[f]!r} not in the cell vocabulary")
    if rec.get("record_type") not in RECORD_TYPES:
        p.append(f"record_type={rec.get('record_type')!r}")
    if rec.get("preparation") not in PREPS:
        p.append(f"preparation={rec.get('preparation')!r}")
    if not isinstance(rec.get("saw_model_prediction"), bool):
        p.append("saw_model_prediction is not true/false")
    if isinstance(rec.get("record_id"), str) and not re.fullmatch(r"[A-Za-z0-9_.-]+-[0-9]{4}", rec["record_id"]):
        p.append("record_id pattern")
    for f in ("doi", "locator", "quote", "hemilineage_as_named"):
        if isinstance(rec.get(f), str) and len(rec[f].strip()) < 2:
            p.append(f"{f} empty")
    if isinstance(rec.get("quote"), str) and len(rec["quote"].split()) > 25:
        p.append("quote longer than 25 words")
    return p


def d7p(rec: dict) -> str:
    """PREREG v3 V2, per record before any consensus."""
    a, b = rec.get("d7"), rec.get("d8")
    if "yes" in (a, b):
        return "yes"
    if a == "no" and b == "no":
        return "no"
    if "unclear" in (a, b):
        return "unclear"
    return "not_assessed"


# ------------------------------------------------------------------------------------------------ names -> units (U5)
_NAME = re.compile(r"(?<![0-9])([0-9]{1,2})\s*([ABXabx])(?![A-Za-z])")


def norm_names(text: str) -> list[str]:
    """Hemilineage names in a string, normalised to two digits + upper-case letter ('9A', 'HL9a', 'lineage 9 A' -> '09A')."""
    t = re.sub(r"(?i)hemilineages?|lineages?|\bHL", " ", text or "")
    return [f"{int(n):02d}{l.upper()}" for n, l in _NAME.findall(t)]


def unit_of(rec: dict, units: list[str]) -> tuple[str | None, str]:
    """(unit or None, how): U5. Names come from `hemilineages_listed`, else from `hemilineage_as_named`."""
    names = norm_names(rec.get("hemilineages_listed") or "") or norm_names(rec.get("hemilineage_as_named") or "")
    if not names:
        return None, "no hemilineage name"
    us = set()
    for n in names:
        if n in units:
            us.add(n)
        elif n in MERGED and MERGED[n] in units:
            us.add(MERGED[n])
        else:
            return None, f"name {n} is not a unit"
    if len(us) != 1:
        return None, f"names span units {sorted(us)}"
    (u,) = us
    return u, ("exact" if set(names) == {u} else "merged-unit component(s)")


# ------------------------------------------------------------------------------------------------ pairing (T3)
def effector_class(e: str) -> str:
    s = (e or "").lower()
    if re.search(r"trpa|trp\b|heat|thermo|°c|deg c|\b[23][0-9] ?c\b", s):
        return "thermogenetic"
    if re.search(r"chrimson|chr2|channelrhodopsin|reachr|chronos|light|opto|csch", s):
        return "optogenetic"
    return "other"


def driver_norm(d: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (d or "").lower())


def pair_key(rec: dict, unit: str | None) -> tuple:
    return (rec["doi"].lower().strip(), unit or ("?" + "".join(norm_names(rec.get("hemilineage_as_named") or "")) or
                                                 rec.get("hemilineage_as_named", "")), rec["preparation"], effector_class(rec["effector"]))


def pair_readings(a: list[dict], b: list[dict], units: list[str]) -> tuple[list[tuple[dict, dict]], list[dict], list[dict]]:
    """Match reading 1 and reading 2 records on (source, unit, preparation, effector class); within a key, by normalised driver
    name (exact first, then by sorted order of the rest only when both sides have the same number left). Returns (pairs,
    unmatched in 1, unmatched in 2)."""
    ka, kb = defaultdict(list), defaultdict(list)
    for r in a:
        ka[pair_key(r, unit_of(r, units)[0])].append(r)
    for r in b:
        kb[pair_key(r, unit_of(r, units)[0])].append(r)
    pairs, ua, ub = [], [], []
    for k in sorted(set(ka) | set(kb), key=str):
        ra, rb = list(ka.get(k, [])), list(kb.get(k, []))
        for x in list(ra):
            m = [y for y in rb if driver_norm(y["driver"]) == driver_norm(x["driver"])]
            if m:
                pairs.append((x, m[0]))
                ra.remove(x)
                rb.remove(m[0])
        if ra and rb and len(ra) == len(rb) == 1:
            pairs.append((ra.pop(), rb.pop()))
        ua += ra
        ub += rb
    return pairs, ua, ub


def disputed_fields(x: dict, y: dict) -> list[str]:
    return [f for f in D15 + ["record_type"] if x[f] != y[f]]


def coin_order(dispute_ids: list[str]) -> dict[str, bool]:
    """Per disputed record, whether reading 2 is shown first (adjudication order; `default_rng(20261306)` over sorted ids)."""
    rng = np.random.default_rng(COIN_SEED)
    return {d: bool(rng.integers(0, 2)) for d in sorted(dispute_ids)}


def final_from_pair(x: dict, y: dict, adjudicated: dict | None) -> dict:
    """Agreed cells, adjudicated cells for the rest; locator/quote of reading 1; a sighting in either reading counts."""
    out = dict(x)
    for f in disputed_fields(x, y):
        if not adjudicated or f not in adjudicated:
            raise ValueError(f"{x['record_id']}/{y['record_id']}: disputed {f} not adjudicated")
        out[f] = adjudicated[f]
    out["saw_model_prediction"] = bool(x["saw_model_prediction"] or y["saw_model_prediction"])
    out["paired_with"] = y["record_id"]
    return out


# ------------------------------------------------------------------------------------------------ consensus (T4)
def _source_cell(vals: list[str]) -> str:
    if "yes" in vals and "no" in vals:
        return "conflicting"
    if "yes" in vals:
        return "yes"
    if "no" in vals:
        return "no"
    return "unclear" if "unclear" in vals else "not_assessed"


def consensus(final: pd.DataFrame, units: list[str], record_types=("whole_two_sided",)) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """T4 over any number of sources. `final`: final records with columns unit, doi, preparation, record_type, eligible (bool:
    non-breaching session, no sighting), d1..d15, d7p. Returns (consensus table, per-source tables), each indexed by unit with
    every unit that has an eligible record of these types."""
    f = final[final["eligible"] & final["record_type"].isin(record_types) & final["unit"].notna()]
    dims = D15 + ["d7p"]
    cons_rows, src_rows = {}, defaultdict(dict)
    for u, g in f.groupby("unit"):
        crow, srows = {}, defaultdict(dict)
        for d in dims:
            decap = g[(g["preparation"] == "decapitated") & g[d].isin(["yes", "no"])]
            use = g[g["preparation"] == "decapitated"] if len(decap) else g
            per = {s: _source_cell(list(h[d])) for s, h in use.groupby("doi")}
            for s, v in per.items():
                srows[s][d] = v
            yn = {v for v in per.values() if v in ("yes", "no")}
            if "conflicting" in per.values() or len(yn) > 1:
                crow[d] = "conflicting"
            elif yn:
                crow[d] = yn.pop()
            else:
                crow[d] = "unclear" if "unclear" in per.values() else "not_assessed"
        cons_rows[u] = crow
        for s, row in srows.items():
            # per-source table: the same preparation rule applied within the source alone
            gs = g[g["doi"] == s]
            src_rows[s][u] = {d: _source_cell(list((gs[gs["preparation"] == "decapitated"] if len(
                gs[(gs["preparation"] == "decapitated") & gs[d].isin(["yes", "no"])]) else gs)[d])) for d in dims}
    cons = pd.DataFrame.from_dict(cons_rows, orient="index").reindex(columns=dims)
    cons.index.name = "unit"
    bad = set(cons.index) - set(units)
    if bad:
        raise ValueError(f"units not in the unit list: {sorted(bad)}")
    per_src = {s: pd.DataFrame.from_dict(r, orient="index").reindex(columns=dims).rename_axis("unit") for s, r in src_rows.items()}
    return cons.sort_index(), per_src


def n_units_ge3(cons: pd.DataFrame) -> int:
    return int((cons[PRIMARY].isin(["yes", "no"]).sum(axis=1) >= 3).sum()) if len(cons) else 0


# ------------------------------------------------------------------------------------------------ agreement
def cohen_kappa(a: list[str], b: list[str]) -> dict:
    """Cohen's kappa over cells both code yes/no (S5.4)."""
    pairs = [(x, y) for x, y in zip(a, b) if x in ("yes", "no") and y in ("yes", "no")]
    n = len(pairs)
    if not n:
        return {"n": 0, "kappa": None}
    po = sum(x == y for x, y in pairs) / n
    pa, pb = sum(x == "yes" for x, _ in pairs) / n, sum(y == "yes" for _, y in pairs) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    k = 1.0 if pe == 1 else (po - pe) / (1 - pe)
    return {"n": n, "agreement": po, "kappa": k}


def readings_kappa(pairs: list[tuple[dict, dict]]) -> dict:
    a, b = [], []
    for x, y in pairs:
        x, y = {**x, "d7p": d7p(x)}, {**y, "d7p": d7p(y)}
        a += [x[d] for d in PRIMARY]
        b += [y[d] for d in PRIMARY]
    return cohen_kappa(a, b)


# ------------------------------------------------------------------------------------------------ verification (T8)
def verification_sample(final: pd.DataFrame, n: int = VERIFY_N, seed: int = VERIFY_SEED) -> list[str]:
    ids = sorted(final.loc[(final["record_type"] == "whole_two_sided") & final["eligible"], "record_id"])
    if len(ids) <= n:
        return ids
    return sorted(np.random.default_rng(seed).choice(ids, n, replace=False).tolist())


def verification_error(final: pd.DataFrame, verified: dict[str, dict]) -> dict:
    """Cells in error / cells the sampled records code yes/no, over the twelve primary dimensions (d7p from the verifier's d7, d8)."""
    err = tot = 0
    rows = []
    for rid, cells in verified.items():
        rec = final.set_index("record_id").loc[rid]
        v = dict(cells)
        if "d7p" not in v:
            v["d7p"] = d7p(v) if ("d7" in v or "d8" in v) else "cannot_verify"
        for d in PRIMARY:
            if rec[d] in ("yes", "no"):
                tot += 1
                bad = v.get(d) != rec[d]
                err += bad
                if bad:
                    rows.append({"record_id": rid, "dim": d, "recorded": rec[d], "verifier": v.get(d)})
    return {"cells_checked": tot, "cells_in_error": err, "error_rate": (err / tot) if tot else None, "errors": rows}
