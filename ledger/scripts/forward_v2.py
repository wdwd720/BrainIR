"""PREREG v5 Part F: forward ledger v2 (types, three readings, the short list, the decision rule and its power table).

    uv run --project ledger --no-sync python ledger/scripts/forward_v2.py candidates   # F1-F2 -> forward_v2/CANDIDATES.csv
    uv run --project ledger --no-sync python ledger/scripts/forward_v2.py shortlist    # F3-F5 (needs forward_v2/AVAILABILITY.csv) -> SHORTLIST.csv
    uv run --project ledger --no-sync python ledger/scripts/forward_v2.py lines-table  # F4 -> SHORTLIST_LINES.csv (per line: availability, other DN types)

Made after both exams were unblinded and after the replication pattern was seen; clean with respect to the experiments it predicts.
Inputs: the locked per-type tables (Part R categories), the audit's checked records (labels_audit_v1/) and exam 1's records (whether a
type was already tested in headless flies), kit v2's driver lines, A1's drivers, run 1's two-step signed counting (S2).
"""

from __future__ import annotations

import csv
import json
import re
import sys
from math import comb
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import forward_v1 as F1  # noqa: E402
import replication_v1 as R  # noqa: E402

from brainir_ledger import RESEARCH  # noqa: E402
from brainir_ledger.labels import aggregate as AGG  # noqa: E402

FWD2 = RESEARCH / "forward_v2"
KIT = RESEARCH / "kit_v2"
MAX_LIST, MAX_GROUP1, N_CONTROLS = 12, 9, 3
GROUP1 = ("replicated", "near_replicated")
HONESTY = ("Made after both exams were unblinded and after the replication pattern was seen (post hoc categories, PREREG v5 Part R). "
           "Clean with respect to the experiments it predicts, which have not been done.")


def category_of(T: dict | None = None) -> dict[str, str]:
    """F1: the B1r x B2r category; for a type that is 'neither' there, its A1 x B2r category."""
    T = T or R.tables()
    b = R.categories(T, "B1r").set_index("manc_type")["category"].to_dict()
    a = R.categories(T, "A1").set_index("manc_type")["category"].to_dict()
    return {t: (b.get(t) if b.get(t, "neither") != "neither" else a.get(t, "neither")) for t in sorted(set(a) | set(b))}


def kit_line_rows() -> pd.DataFrame:
    return pd.read_csv(KIT / "driver_lines.csv", dtype=str, keep_default_na=False)


def _dn_names() -> dict[str, re.Pattern]:
    names: dict[str, set[str]] = {}
    for r in csv.DictReader(open(KIT / "synonyms.csv", encoding="utf-8")):
        names.setdefault(r["manc_type"], set()).add(r["name"])
    for r in csv.DictReader(open(KIT / "type_list.csv", encoding="utf-8")):
        names.setdefault(r["manc_type"], set()).add(r["manc_type"])
    import audit5_rooms as AR  # noqa: PLC0415  (the same whole-word rule and common-word exclusions as the audit)

    return {t: re.compile("|".join(AR.pattern(n).pattern for n in sorted(v) if n not in AR.STOP_NAMES)) for t, v in names.items()}


def lines_for(t: str, dl: pd.DataFrame | None = None, pats: dict | None = None) -> list[dict]:
    """G6: kit lines of type t; `clean` = no kit record of the line names another DN type (in manc_type or other_cells)."""
    dl = kit_line_rows() if dl is None else dl
    pats = pats or _dn_names()
    out = []
    for line in sorted(set(dl.loc[dl["manc_type"] == t, "line_id"])):
        rows = dl[dl["line_id"] == line]
        others = sorted({m for m in rows["manc_type"] if m not in (t, "", "AMBIGUOUS", "UNMAPPED")})
        for _, r in rows[rows["manc_type"] == "AMBIGUOUS"].iterrows():
            others += [u.strip() for u in str(r["candidate_types"]).split(";") if u.strip() and u.strip() != t]
        for oc in rows["other_cells"]:
            others += [u for u, p in pats.items() if u != t and oc and p.pattern and p.search(oc)]
        others = [u for u in others if u in pats]  # DN types of kit_v2/type_list.csv
        out.append({"line": line, "collection": F1.collection_of(line), "other_dn_types": sorted(set(others)), "clean": not others})
    return out


def tested_headless() -> dict[str, str]:
    """F1: already tested in headless flies = a headless record with a yes/no front-leg value, eligible under the frozen rule with sightings
    allowed, among the audit's final records (`labels_audit_v1/final_records.jsonl`), or among exam 1's records of any eligibility (a
    mapped type and a verified quote)."""
    out = {}
    fin = RESEARCH / "labels_audit_v1" / "final_records.jsonl"
    for line in fin.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = dict(json.loads(line), quote_verified=True, saw_simulation_score=False)
        if AGG.eligible(r) and r.get("preparation") == "headless" and r.get("front_leg_rhythm") in ("yes", "no"):
            out.setdefault(r["manc_type"], "audit")
    for line in (RESEARCH / "labels_v2" / "records.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if (r.get("manc_type") not in (None, "", "UNMAPPED") and r.get("quote_verified") is True and r.get("preparation") == "headless"
                and r.get("front_leg_rhythm") in ("yes", "no")):
            out[r["manc_type"]] = "audit+exam1" if out.get(r["manc_type"]) == "audit" else out.get(r["manc_type"], "exam1")
    return out


def readings(t: str, cat: str, a1: pd.Series, terc: pd.Series) -> dict[str, str]:
    return {"replication_reading": "yes" if cat in GROUP1 else "no",
            "single_connectome_reading": "yes" if (t in a1.index and a1[t] >= R.DRIVER) else "no",
            "counting_reading": "yes" if (t in terc.index and int(terc[t]) == 2) else "no"}


def candidates() -> pd.DataFrame:
    T = R.tables()
    cat = category_of(T)
    a1 = T["A1"]["score"]
    s2 = F1.s2_scores()
    terc = F1._tercile(s2.reindex(a1.index))
    done = tested_headless()
    dl, pats = kit_line_rows(), _dn_names()
    rows = []
    for t, c in sorted(cat.items()):
        if c == "neither":
            continue
        ls = lines_for(t, dl, pats)
        rows.append({"manc_type": t, "category": c, **readings(t, c, a1, terc), "B1r": T["B1r"]["score"].get(t), "B2r": T["B2r"]["score"].get(t),
                     "A1": a1.get(t), "S2_twohop_signed": s2.get(t), "match_confidence": T["match_confidence"]["confidence"].get(t),
                     "n_lines": len(ls), "n_clean_lines": sum(x["clean"] for x in ls), "lines": ";".join(x["line"] for x in ls),
                     "already_tested_headless": done.get(t, ""), "eligible_F1": bool(ls) and t not in done})
    return pd.DataFrame(rows)


def q_of(n: int, alpha: float = 0.05) -> int | None:
    """F5: the smallest k with P(X >= k | n, 1/2) <= alpha (None if no k qualifies)."""
    for k in range(n + 1):
        if sum(comb(n, j) for j in range(k, n + 1)) / 2 ** n <= alpha:
            return k
    return None


def power(n: int, a: float) -> float:
    q = q_of(n)
    return 0.0 if q is None else sum(comb(n, j) * a ** j * (1 - a) ** (n - j) for j in range(q, n + 1))


def decide(n: int, k: int, x: str = "X", y: str = "Y") -> str:
    """F5 for one comparison: n = tested types with a yes/no outcome on which readings x and y disagree; k = how many of them x gets right."""
    q = q_of(n)
    if q is not None and k >= q:
        return f"supports the {x} reading over the {y} reading"
    if q is not None and n - k >= q:
        return f"supports the {y} reading over the {x} reading"
    return "inconclusive"


def shortlist(cand: pd.DataFrame, avail: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """F3: only F1 types with at least one line listed as available (`yes`). (1) replicated and near-replicated, at most 9, by the smaller
    of B1r and B2r (descending); (2) three stable non-drivers by S2 (descending), places reserved; (3) single-fly hits filling the rest:
    (3a) MANC hits that are A1 drivers, (3b) other MANC hits, (3c) MaleCNS hits. Ties: more available lines, more clean lines, the larger
    score (B1r for 3a/3b, B2r for 3c), name. Returns (short list, candidates with the reason a type is not on it)."""
    c = cand[cand["eligible_F1"]].copy()
    c["n_available"] = c["lines"].apply(lambda s: sum(avail.get(x) == "yes" for x in str(s).split(";") if x))
    c["min_score"] = c[["B1r", "B2r"]].min(axis=1)
    ok = c[c["n_available"] >= 1]

    def order(d: pd.DataFrame, score: str) -> pd.DataFrame:
        return d.assign(_s=-d[score].fillna(-1)).sort_values(["n_available", "n_clean_lines", "_s", "manc_type"],
                                                            ascending=[False, False, True, True]).drop(columns="_s")

    g1 = ok[ok["category"].isin(GROUP1)].assign(_m=lambda d: -d["min_score"]).sort_values(["_m", "n_available", "n_clean_lines", "manc_type"],
                                                                                        ascending=[True, False, False, True]).drop(columns="_m")
    g1 = g1.head(MAX_GROUP1).assign(group="1 replicated / near-replicated")
    ctl = ok[ok["category"] == "stable_non_driver"].assign(_s=lambda d: -d["S2_twohop_signed"]).sort_values(
        ["_s", "n_available", "n_clean_lines", "manc_type"], ascending=[True, False, False, True]).drop(columns="_s").head(N_CONTROLS)
    ctl = ctl.assign(group="2 control (stable non-driver, top counting)")
    room = MAX_LIST - len(g1) - len(ctl)
    sf = ok[ok["category"].isin(["single_fly_manc", "single_fly_malecns"])]
    g3a = order(sf[(sf["category"] == "single_fly_manc") & (sf["single_connectome_reading"] == "yes")], "B1r").assign(group="3a single-fly hit, MANC, A1 driver")
    g3b = order(sf[(sf["category"] == "single_fly_manc") & (sf["single_connectome_reading"] == "no")], "B1r").assign(group="3b single-fly hit, MANC")
    g3c = order(sf[sf["category"] == "single_fly_malecns"], "B2r").assign(group="3c single-fly hit, MaleCNS")
    g3 = pd.concat([g3a, g3b, g3c]).head(max(0, room))
    short = pd.concat([g1, g3, ctl]).reset_index(drop=True)
    why = cand.copy()
    why["not_listed_because"] = ""
    for i, r in why.iterrows():
        t = r["manc_type"]
        if t in set(short["manc_type"]):
            continue
        if not r["n_lines"]:
            why.at[i, "not_listed_because"] = "no kit line"
        elif r["already_tested_headless"]:
            why.at[i, "not_listed_because"] = f"already tested headless ({r['already_tested_headless']})"
        elif t not in set(ok["manc_type"]):
            why.at[i, "not_listed_because"] = "no line listed as available"
        else:
            why.at[i, "not_listed_because"] = "group full (F3 order)"
    return short, why


def comparisons(short: pd.DataFrame) -> dict:
    """F5: for each pair of readings, the short-listed types on which they disagree (the n if every type gives a clear outcome)."""
    pairs = {"A_replication_vs_single_connectome": ("replication_reading", "single_connectome_reading"),
             "B_replication_vs_counting": ("replication_reading", "counting_reading"),
             "C_single_connectome_vs_counting": ("single_connectome_reading", "counting_reading")}
    out = {}
    for k, (x, y) in pairs.items():
        d = short[short[x] != short[y]]
        n = len(d)
        out[k] = {"types": sorted(d["manc_type"]), "max_n": n, "q": q_of(n), "power_a0.8": round(power(n, 0.8), 3), "power_a0.9": round(power(n, 0.9), 3)}
    return out


def power_table() -> list[dict]:
    return [{"n_in_D": n, "q": q_of(n), "power_a0.8": round(power(n, 0.8), 3), "power_a0.9": round(power(n, 0.9), 3)} for n in range(1, 13)]


if __name__ == "__main__":
    cmd = sys.argv[1:2]
    if cmd == ["candidates"]:
        d = candidates()
        FWD2.mkdir(parents=True, exist_ok=True)
        with open(FWD2 / "CANDIDATES.csv", "x", encoding="utf-8", newline="\n") as fh:
            fh.write(d.to_csv(index=False, lineterminator="\n"))
        print(d[d["eligible_F1"]].to_string())
    elif cmd == ["shortlist"]:
        cand = pd.read_csv(FWD2 / "CANDIDATES.csv", dtype={"manc_type": str}, keep_default_na=False, na_values=[""])
        cand["already_tested_headless"] = cand["already_tested_headless"].fillna("")
        av = {r["line"]: r["listed_available"] for r in csv.DictReader(open(FWD2 / "AVAILABILITY.csv", encoding="utf-8"))}
        s, why = shortlist(cand, av)
        with open(FWD2 / "SHORTLIST.csv", "x", encoding="utf-8", newline="\n") as fh:
            fh.write(s.to_csv(index=False, lineterminator="\n"))
        with open(FWD2 / "CANDIDATES_WHY.csv", "x", encoding="utf-8", newline="\n") as fh:
            fh.write(why.to_csv(index=False, lineterminator="\n"))
        cmp_ = {"rule": "PREREG v5 F5", "comparisons": comparisons(s), "group_sizes": s["group"].value_counts().to_dict(),
                "power_table": power_table(), "protocol": F1.PROTOCOL, "honesty": HONESTY}
        with open(FWD2 / "DECISION_RULE.json", "x", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(cmp_, indent=1) + "\n")
        readme = ["# Forward ledger v2 (PREREG v5 Part F)", "", HONESTY, "",
                  "Forward ledger v1 (`research/ledger/forward/`) stays as locked; it is superseded for the ask by this list.", "",
                  "## Protocol (forward ledger v1's, unchanged)", ""] + [f"{i}. {x}" for i, x in enumerate(F1.PROTOCOL, 1)] + [
                  "", "## Decision rule (PREREG v5 F5)", "",
                  "Each tested type's outcome is the lab's own call (yes / no / no clear outcome), recorded verbatim before the readings are compared. "
                  "For readings X and Y: D = tested types with a yes/no outcome on which they disagree, n = |D|, k = the number X gets right, q(n) = the "
                  "smallest k with one-sided binomial P(K >= k | n, 1/2) <= 0.05. X is supported over Y if k >= q(n); Y over X if n - k >= q(n); otherwise "
                  "inconclusive (always when n <= 4). Comparisons: A replication vs single-connectome (inconclusive by construction with these lines), "
                  "B replication vs counting, C single-connectome vs counting. Expected n and power: `DECISION_RULE.json`.", "",
                  "Files: `CANDIDATES.csv` (F1-F2), `AVAILABILITY.csv` (F4), `SHORTLIST.csv` (F3), `CANDIDATES_WHY.csv` (why a candidate is not listed), "
                  "`DECISION_RULE.json` (F5)."]
        with open(FWD2 / "README.md", "x", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(readme) + "\n")
        print(s.to_string()); print(json.dumps(cmp_["comparisons"], indent=1))
    elif cmd == ["lines-table"]:
        # F4: one row per (short-listed type, kit line): collection, availability today, other DN types named by the line's kit rows
        short = pd.read_csv(FWD2 / "SHORTLIST.csv", dtype={"manc_type": str}, keep_default_na=False)
        av = {r["line"]: r for r in csv.DictReader(open(FWD2 / "AVAILABILITY.csv", encoding="utf-8"))}
        dl, pats = kit_line_rows(), _dn_names()
        out = []
        for t in short["manc_type"]:
            for x in lines_for(t, dl, pats):
                a = av.get(x["line"], {})
                out.append({"manc_type": t, "line": x["line"], "collection": x["collection"], "listed_available": a.get("listed_available", "not_checked"),
                            "url": a.get("url", ""), "date_checked": a.get("date_checked", ""), "other_dn_types": ";".join(x["other_dn_types"]),
                            "clean": x["clean"]})
        with open(FWD2 / "SHORTLIST_LINES.csv", "x", encoding="utf-8", newline="\n") as fh:
            fh.write(pd.DataFrame(out).to_csv(index=False, lineterminator="\n"))
        print(pd.DataFrame(out)[["manc_type", "line", "listed_available", "clean", "other_dn_types"]].to_string())
    elif cmd == ["power"]:
        print(json.dumps(power_table(), indent=1))
    else:
        raise SystemExit(__doc__)
