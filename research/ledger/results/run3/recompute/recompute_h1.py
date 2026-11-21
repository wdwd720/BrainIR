#!/usr/bin/env python3
"""Independent recomputation of the PREREG v3 S1-S2 primary statistic for one arm.

Written from the text of research/ledger/PREREG_v3.md Parts S1-S2 only (no frozen scoring code read or imported).
Standard library only.

Usage:
    python3 -I recompute_h1.py PREDICTED_CSV CONSENSUS_CSV UNITS_CSV OUT_JSON

S1: P = predicted (43 units x 12 primary dims), each column standardised across the 43 units (mean 0, population sd 1;
    sd 0 -> column of zeros). O = consensus cells, yes = 1, no = 0, anything else missing; each column centred over the
    units where it is coded WITHIN the analysed set (units with >= 3 coded primary dims).
S2: for each analysed unit h, s_h(k) = sum over h's coded dims d of P[k,d] * O[h,d], k over all 43 units.
    pr(h) = (#{k != h: s_h(k) < s_h(h)} + 0.5 #{k != h: tied}) / 42; ties = scores within 1e-12.
    position(h) = 1 + #{k: s_h(k) > s_h(h)} + 0.5 #{k != h: tied}; top-1: position <= 1; top-3: position <= 3.
    Statistic = mean pr(h).
"""
import csv
import datetime
import hashlib
import json
import math
import sys

PRIMARY = ["d1", "d2", "d3", "d4", "d5", "d6", "d7p", "d10", "d11", "d13", "d14", "d15"]
CONSENSUS_COLS = ["d%d" % i for i in range(1, 16)] + ["d7p"]
VOCAB = {"yes", "no", "unclear", "not_assessed", "conflicting"}
CODED = {"yes": 1.0, "no": 0.0}
TIE_TOL = 1e-12
N_CAND_OTHER = 42


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames or [])
        rows = list(reader)
    return header, rows


def fail(msg):
    raise SystemExit("REFUSED: " + msg)


def main(pred_path, cons_path, units_path, out_path):
    # ---------- units ----------
    uh, urows = read_csv(units_path)
    if "unit" not in uh:
        fail("UNITS file has no 'unit' column")
    units = [r["unit"] for r in urows]
    if len(units) != 43 or len(set(units)) != 43 or any(not u for u in units):
        fail("UNITS file must hold 43 distinct non-empty units, got %d (%d distinct)" % (len(units), len(set(units))))

    # ---------- predicted ----------
    ph, prows = read_csv(pred_path)
    for d in ["unit"] + PRIMARY:
        if d not in ph:
            fail("predicted.csv lacks column %s" % d)
    pred_units = [r["unit"] for r in prows]
    if len(pred_units) != 43 or set(pred_units) != set(units) or len(set(pred_units)) != 43:
        fail("predicted.csv units differ from the 43-unit list")
    pred = {r["unit"]: r for r in prows}
    Praw = {}
    for k in units:
        row = []
        for d in PRIMARY:
            v = pred[k][d]
            if v is None or v.strip() == "":
                fail("missing predicted value %s/%s" % (k, d))
            x = float(v)
            if not math.isfinite(x):
                fail("non-finite predicted value %s/%s" % (k, d))
            row.append(x)
        Praw[k] = row

    # standardise each column across the 43 units, population sd
    Pz = {k: [0.0] * len(PRIMARY) for k in units}
    col_stats = {}
    for j, d in enumerate(PRIMARY):
        col = [Praw[k][j] for k in units]
        mean = math.fsum(col) / len(col)
        var = math.fsum((x - mean) ** 2 for x in col) / len(col)
        sd = math.sqrt(var)
        constant = len(set(col)) == 1
        col_stats[d] = {"mean": mean, "sd_pop": sd, "constant": constant}
        if sd == 0.0 or constant:
            for k in units:
                Pz[k][j] = 0.0
        else:
            for k in units:
                Pz[k][j] = (Praw[k][j] - mean) / sd

    # ---------- consensus ----------
    ch, crows = read_csv(cons_path)
    for d in ["unit"] + CONSENSUS_COLS:
        if d not in ch:
            fail("consensus.csv lacks column %s" % d)
    cons = {}
    for r in crows:
        u = r["unit"]
        if u in cons:
            fail("duplicate consensus unit %s" % u)
        if u not in set(units):
            fail("consensus unit %s not in the unit list" % u)
        for d in CONSENSUS_COLS:
            if r[d] not in VOCAB:
                fail("consensus value %r at %s/%s outside the vocabulary" % (r[d], u, d))
        cons[u] = r

    coded = {}
    for u in units:
        if u in cons:
            coded[u] = [d for d in PRIMARY if cons[u][d] in CODED]
        else:
            coded[u] = []
    analysed = [u for u in units if len(coded[u]) >= 3]  # order of the unit list
    n = len(analysed)

    # observed values and column centring over coded cells of the analysed set
    col_mean_O = {}
    for d in PRIMARY:
        cells = [CODED[cons[h][d]] for h in analysed if d in coded[h]]
        col_mean_O[d] = (math.fsum(cells) / len(cells)) if cells else None
        col_mean_O[d + "_n"] = len(cells)
    Oc = {}
    for h in analysed:
        Oc[h] = {d: CODED[cons[h][d]] - col_mean_O[d] for d in coded[h]}

    jidx = {d: j for j, d in enumerate(PRIMARY)}

    def scores(h, summer):
        return {k: summer([Pz[k][jidx[d]] * Oc[h][d] for d in coded[h]]) for k in units}

    def evaluate(summer):
        per = []
        min_untied_gap = math.inf
        max_tied_gap = 0.0
        for h in analysed:
            s = scores(h, summer)
            sh = s[h]
            higher = lower = ties = 0
            for k in units:
                if k == h:
                    continue
                diff = s[k] - sh
                if diff > TIE_TOL:
                    higher += 1
                    min_untied_gap = min(min_untied_gap, abs(diff))
                elif diff < -TIE_TOL:
                    lower += 1
                    min_untied_gap = min(min_untied_gap, abs(diff))
                else:
                    ties += 1
                    max_tied_gap = max(max_tied_gap, abs(diff))
            assert higher + lower + ties == N_CAND_OTHER
            pr = (lower + 0.5 * ties) / N_CAND_OTHER
            pos = 1 + higher + 0.5 * ties
            assert abs(pr - (43 - pos) / N_CAND_OTHER) < 1e-15
            per.append({"unit": h, "n_coded": len(coded[h]), "s_true": sh, "higher": higher, "tied": ties,
                        "lower": lower, "pr": pr, "position": pos, "top1": pos <= 1, "top3": pos <= 3})
        mean_pr = math.fsum(p["pr"] for p in per) / len(per)
        t1 = sum(1 for p in per if p["top1"])
        t3 = sum(1 for p in per if p["top3"])
        return per, mean_pr, t1, t3, min_untied_gap, max_tied_gap

    per, mean_pr, t1, t3, min_gap, max_tie = evaluate(math.fsum)
    # robustness: naive left-to-right summation must give the same tie decisions and numbers
    per2, mean_pr2, t1b, t3b, min_gap2, max_tie2 = evaluate(lambda xs: sum(xs, 0.0))
    same_decisions = all((a["higher"], a["tied"], a["lower"]) == (b["higher"], b["tied"], b["lower"])
                         for a, b in zip(per, per2))

    # identical raw P rows must be tied for every h
    groups = {}
    for k in units:
        groups.setdefault(tuple(Praw[k]), []).append(k)
    ident_groups = [g for g in groups.values() if len(g) > 1]
    for h in analysed:
        s = scores(h, math.fsum)
        for g in ident_groups:
            vals = [s[k] for k in g]
            assert max(vals) - min(vals) <= TIE_TOL, (h, g)

    all_zero_rows = [k for k in units if all(x == 0.0 for x in Praw[k])]

    rec = {
        "what": "independent recomputation, PREREG_v3 S1-S2 primary statistic",
        "recorded_utc": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n": n,
        "mean_pr": mean_pr,
        "mean_pr_12dp": "%.12f" % mean_pr,
        "top1": t1 / n,
        "top1_12dp": "%.12f" % (t1 / n),
        "top1_count": t1,
        "top3": t3 / n,
        "top3_12dp": "%.12f" % (t3 / n),
        "top3_count": t3,
        "analysed_units": analysed,
        "excluded_consensus_units": [u for u in units if u in cons and u not in analysed],
        "units_without_consensus_row": [u for u in units if u not in cons],
        "robustness": {
            "naive_sum_mean_pr": mean_pr2,
            "naive_sum_same_tie_decisions": same_decisions,
            "naive_sum_same_top": (t1b, t3b) == (t1, t3),
            "smallest_untied_gap": min_gap,
            "largest_tied_gap": max_tie,
            "identical_raw_P_row_groups": ident_groups,
            "all_zero_raw_P_rows": all_zero_rows,
            "constant_P_columns": [d for d in PRIMARY if col_stats[d]["constant"] or col_stats[d]["sd_pop"] == 0.0],
        },
        "O_column_means_over_analysed_coded": col_mean_O,
        "per_unit": per,
        "inputs_sha256": {"predicted": sha256(pred_path), "consensus": sha256(cons_path), "units": sha256(units_path)},
        "script_sha256": sha256(__file__),
    }
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, indent=1)
        f.write("\n")

    print("n (units with >= 3 coded primary dims) = %d" % n)
    print("mean_pr = %.12f" % mean_pr)
    print("top1    = %.12f  (%d/%d)" % (t1 / n, t1, n))
    print("top3    = %.12f  (%d/%d)" % (t3 / n, t3, n))
    print()
    print("excluded consensus units:", rec["excluded_consensus_units"])
    print("O column means (analysed, coded):",
          {d: (round(col_mean_O[d], 6) if col_mean_O[d] is not None else None, col_mean_O[d + "_n"]) for d in PRIMARY})
    print("constant P columns:", rec["robustness"]["constant_P_columns"])
    print("all-zero raw P rows (%d):" % len(all_zero_rows), all_zero_rows)
    print("identical raw-P groups:", ident_groups)
    print("smallest untied gap = %.3e ; largest tied gap = %.3e" % (min_gap, max_tie))
    print("naive-sum: same tie decisions=%s, mean_pr diff=%.3e, same top counts=%s"
          % (same_decisions, abs(mean_pr2 - mean_pr), (t1b, t3b) == (t1, t3)))
    print()
    print("%-9s %3s %12s %4s %4s %4s %9s %6s %3s %3s" % ("unit", "nd", "s_true", "hi", "tie", "lo", "pr", "pos", "t1", "t3"))
    for p in per:
        print("%-9s %3d %12.6f %4d %4d %4d %9.6f %6.1f %3d %3d" % (
            p["unit"], p["n_coded"], p["s_true"], p["higher"], p["tied"], p["lower"], p["pr"], p["position"],
            p["top1"], p["top3"]))


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
