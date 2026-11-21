#!/usr/bin/env python3
"""Independent recomputation of the BrainIR ledger primary AUROC (run P).

Definition: PREREG v1 section 7 as used by PREREG v2 S1 / S4 run P (labels v2, v2 exposed set of L6).
Standard library only. Reads the locked CSV files directly; never imports or runs any project code.

Usage:
  python3 -I recompute_auroc.py [--repo PATH] [--seed N] [--extra-seeds K] [--compare]

Without --compare the script only computes and never opens research/ledger/results/run2/P.json.
With --compare it computes everything first, then opens P.json and compares.

Pre-specified "close" criteria (fixed before P.json was opened):
  * AUROC agrees if |diff| <= 1e-12; n, n_yes, n_no must be equal.
  * p (one-sided, (1+count)/(N+1)) is close if |p - p_exact| <= 3*sqrt(p_exact(1-p_exact)/N) + 1/(N+1),
    where p_exact is the exact permutation p-value (all C(n, n_yes) label assignments, by dynamic programming).
  * each 95 % interval endpoint is close if it lies within max(3*SD, 1/(n_yes*n_no)) of the mean of my
    endpoints over K+1 seeds (SD = their standard deviation, i.e. the Monte Carlo SD of one 10,000-resample run).
"""
import argparse
import csv
import hashlib
import json
import math
import random
import statistics
import sys
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from math import comb
from pathlib import Path

A1_CSV = "research/ledger/predictions/A1/types.csv"
LABELS_CSV = "research/ledger/labels_v2/type_labels.csv"
KIT_EXPOSED = "research/ledger/kit_v2/exposed_types.csv"
EXPOSED_V2 = "research/ledger/labels_v2/exposed_v2.csv"
LOCK_PRED = "research/ledger/LOCK_predictions_v1.json"
LOCK_LAB = "research/ledger/LOCK_labels_v2.json"
P_JSON = "research/ledger/results/run2/P.json"
N_BOOT = 10_000
N_PERM = 10_000


# ---------------------------------------------------------------- helpers
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path):
    with open(path, "rb") as f:
        if f.read(3) == b"\xef\xbb\xbf":
            sys.exit(f"unexpected UTF-8 BOM in {path}")
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parse_bool(s):
    if s == "True":
        return True
    if s == "False":
        return False
    sys.exit(f"unparseable boolean {s!r}")


def two_u(yes_vals, no_vals):
    """2*U (integer): 2 per yes>no pair, 1 per tie. AUROC = two_u / (2*n_yes*n_no)."""
    num = 0
    for a in yes_vals:
        for b in no_vals:
            num += 2 if a > b else (1 if a == b else 0)
    return num


def midranks_x2(vals):
    """2 * ascending midrank (ties averaged) of each value, as integers."""
    n = len(vals)
    order = sorted(range(n), key=lambda i: vals[i])
    r2 = [0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        for k in range(i, j + 1):  # 0-based positions i..j hold ranks i+1..j+1; midrank*2 = i+j+2
            r2[order[k]] = i + j + 2
        i = j + 1
    return r2


def percentile_linear(sorted_x, q):
    """Linear-interpolation percentile (Hyndman-Fan type 7, numpy's default)."""
    h = (len(sorted_x) - 1) * q / 100.0
    lo = math.floor(h)
    hi = min(lo + 1, len(sorted_x) - 1)
    return sorted_x[lo] + (h - lo) * (sorted_x[hi] - sorted_x[lo])


def self_test():
    # hand-worked: yes {0.9, 0.5, 0.5}, no {0.5, 0.1}: pairs 2+2+1+2+1+2 = 10 of 12 -> 5/6
    y, n = [0.9, 0.5, 0.5], [0.5, 0.1]
    assert Fraction(two_u(y, n), 2 * 3 * 2) == Fraction(5, 6)
    r2 = midranks_x2(y + n)
    assert sum(r2[:3]) - 3 * 4 == 10
    assert two_u([0.1], [0.9]) == 0 and two_u([0.9], [0.1]) == 2  # direction: positive class = yes
    assert percentile_linear([0.0, 1.0, 2.0, 3.0, 4.0], 2.5) == 0.1


# ---------------------------------------------------------------- statistics
def bootstrap(cyn, n_yes, n_no, seed, n_boot=N_BOOT):
    """Stratified bootstrap: yes and no types resampled separately with replacement."""
    rng = random.Random(seed)
    den = 2 * n_yes * n_no
    out = []
    for _ in range(n_boot):
        my = [0] * n_yes
        for _ in range(n_yes):
            my[rng.randrange(n_yes)] += 1
        mn = [0] * n_no
        for _ in range(n_no):
            mn[rng.randrange(n_no)] += 1
        num = 0
        for a in range(n_yes):
            if my[a]:
                row = cyn[a]
                num += my[a] * sum(row[b] * mn[b] for b in range(n_no))
        out.append(num / den)
    out.sort()
    return percentile_linear(out, 2.5), percentile_linear(out, 97.5)


def permutation(r2_all, cfull, n_yes, obs_num, seed, n_perm=N_PERM):
    """Random label shuffles; 2U from doubled midranks (checked against the pair matrix on 200 shuffles)."""
    rng = random.Random(seed)
    n = len(r2_all)
    idx = list(range(n))
    base = n_yes * (n_yes + 1)
    count = 0
    for k in range(n_perm):
        rng.shuffle(idx)
        ys = idx[:n_yes]
        num = sum(r2_all[i] for i in ys) - base
        if k < 200:
            nos = idx[n_yes:]
            assert num == sum(cfull[i][j] for i in ys for j in nos)
        if num >= obs_num:
            count += 1
    return (1 + count) / (n_perm + 1), count


def exact_perm_p(r2_all, n_yes, obs_num):
    """Exact one-sided p over all C(n, n_yes) yes-sets: P(2U_perm >= 2U_obs)."""
    target = obs_num + n_yes * (n_yes + 1)
    dp = [dict() for _ in range(n_yes + 1)]
    dp[0][0] = 1
    for v in r2_all:
        for k in range(n_yes, 0, -1):
            prev, cur = dp[k - 1], dp[k]
            for s, c in prev.items():
                cur[s + v] = cur.get(s + v, 0) + c
    total = comb(len(r2_all), n_yes)
    assert sum(dp[n_yes].values()) == total
    ge = sum(c for s, c in dp[n_yes].items() if s >= target)
    return Fraction(ge, total)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="~/BrainIR")
    ap.add_argument("--seed", type=int, default=777)
    ap.add_argument("--extra-seeds", type=int, default=9)
    ap.add_argument("--compare", action="store_true")
    args = ap.parse_args()
    repo = Path(args.repo)
    self_test()

    # 1. locks
    pred_lock = json.loads((repo / LOCK_PRED).read_text(encoding="utf-8"))
    lab_lock = json.loads((repo / LOCK_LAB).read_text(encoding="utf-8"))
    checks = [
        (A1_CSV, pred_lock["arms_locked"]["A1"][A1_CSV], "LOCK_predictions_v1.json arms_locked.A1", True),
        (LABELS_CSV, lab_lock["labels"][LABELS_CSV], "LOCK_labels_v2.json labels", True),
        (KIT_EXPOSED, lab_lock["kit_v2"][KIT_EXPOSED], "LOCK_labels_v2.json kit_v2", False),
        (EXPOSED_V2, lab_lock["labels"][EXPOSED_V2], "LOCK_labels_v2.json labels", False),
    ]
    print("== locks")
    for rel, expected, where, required in checks:
        got = sha256(repo / rel)
        ok = got == expected
        print(f"  {rel}  sha256={got}  {'MATCH' if ok else 'MISMATCH'} ({where}){'' if required else ' [extra]'}")
        if not ok:
            sys.exit("lock mismatch: stopping")
    lock_shas = (sha256(repo / LOCK_PRED), sha256(repo / LOCK_LAB))
    for rel, h in zip((LOCK_PRED, LOCK_LAB), lock_shas):
        print(f"  (lock file) {rel}  sha256={h}")

    # 2. predictions (A1)
    a1_rows = read_csv(repo / A1_CSV)
    assert all(r["arm"] == "A1" for r in a1_rows)
    a1 = {}
    for r in a1_rows:
        t = r["manc_type"]
        assert t not in a1, f"duplicate A1 type {t}"
        a1[t] = r
    print(f"== A1: {len(a1)} types")

    # 3. labels v2
    lab_rows = read_csv(repo / LABELS_CSV)
    labels = {}
    for r in lab_rows:
        t = r["manc_type"]
        assert t not in labels, f"duplicate label type {t}"
        labels[t] = r
    fronts = {}
    for r in lab_rows:
        fronts[r["front"]] = fronts.get(r["front"], 0) + 1
    print(f"== labels v2: {len(labels)} types; front values {dict(sorted(fronts.items()))}")
    near = [v for v in fronts if v not in ("yes", "no") and v.strip().lower() in ("yes", "no")]
    print(f"  front values that are yes/no only after strip/lower: {near}")

    # 4. exposed set (L6)
    kit_rows = read_csv(repo / KIT_EXPOSED)
    unresolved = [r["name_as_given"] for r in kit_rows if r["resolved"] != "True"]
    kit_set = {t for r in kit_rows for t in r["manc_types"].split(";") if t != ""}
    v2_set = {r["manc_type"] for r in read_csv(repo / EXPOSED_V2)}
    exposed = kit_set | v2_set
    print(f"== exposed: kit_v2 {len(kit_set)} types ({len(kit_rows)} rows, unresolved {unresolved}), "
          f"exposed_v2 {len(v2_set)}, union {len(exposed)}")
    print(f"  union: {sorted(exposed)}")
    mism = [t for t, r in labels.items() if parse_bool(r["exposed"]) != (t in exposed)]
    absent = sorted(exposed - set(labels))
    n_col_true = sum(parse_bool(r["exposed"]) for r in labels.values())
    print(f"  'exposed' column True: {n_col_true}; disagreements with the union: {mism}; "
          f"union members absent from label table: {absent}")

    # whitespace check on join keys
    keys = list(a1) + list(labels) + list(exposed)
    ws = [k for k in keys if k != k.strip()]
    print(f"  join keys with leading/trailing whitespace: {ws}")
    if {k.strip() for k in a1} & {k.strip() for k in labels} != set(a1) & set(labels):
        print("  WARNING: stripping whitespace would change the A1/label join")

    # 5. primary-set funnel
    clear = sorted(t for t, r in labels.items() if r["front"] in ("yes", "no"))
    in_a1 = [t for t in clear if t in a1]
    not_exp = [t for t in in_a1 if t not in exposed]

    def finite(t):
        try:
            return math.isfinite(float(a1[t]["primary_score"]))
        except ValueError:
            return False

    prim = [t for t in not_exp if finite(t)]
    print("== primary-set funnel")
    print(f"  front in {{yes,no}}: {len(clear)}")
    print(f"  and among A1's types: {len(in_a1)} (dropped not in A1: {sorted(set(clear) - set(in_a1))})")
    print(f"  and not exposed: {len(not_exp)} (dropped exposed: {sorted(set(in_a1) - set(not_exp))})")
    print(f"  and finite A1 primary_score: {len(prim)} (dropped: {sorted(set(not_exp) - set(prim))})")
    yes_t = [t for t in prim if labels[t]["front"] == "yes"]
    no_t = [t for t in prim if labels[t]["front"] == "no"]
    n, n_yes, n_no = len(prim), len(yes_t), len(no_t)
    print(f"  n={n} n_yes={n_yes} n_no={n_no}")
    nu = [t for t in prim if a1[t]["status"] != "ok"]
    print(f"  never_usable types in set: {len(nu)}; their primary_score values: "
          f"{sorted({a1[t]['primary_score'] for t in nu})}")

    # 6. AUROC (exact integer form) + cross-checks
    sc = {t: float(a1[t]["primary_score"]) for t in prim}
    dec = {}
    for t in prim:
        try:
            dec[t] = Decimal(a1[t]["primary_score"])
        except InvalidOperation:
            sys.exit(f"bad decimal {t}")
    num = two_u([sc[t] for t in yes_t], [sc[t] for t in no_t])
    den = 2 * n_yes * n_no
    auc = Fraction(num, den)
    num_dec = two_u([dec[t] for t in yes_t], [dec[t] for t in no_t])
    allt = yes_t + no_t
    vals = [sc[t] for t in allt]
    r2_all = midranks_x2(vals)
    num_rank = sum(r2_all[:n_yes]) - n_yes * (n_yes + 1)
    cfull = [[2 if a > b else (1 if a == b else 0) for b in vals] for a in vals]
    dvals = [dec[t] for t in allt]
    cdec = [[2 if a > b else (1 if a == b else 0) for b in dvals] for a in dvals]
    ties = sum(1 for t in yes_t for u in no_t if sc[t] == sc[u])
    print("== AUROC")
    print(f"  2U pairwise(float)={num} pairwise(decimal)={num_dec} midrank={num_rank}; denominator 2*n_yes*n_no={den}")
    print(f"  float and exact-decimal pair orderings identical: {cfull == cdec}; yes-no tied pairs: {ties}")
    assert num == num_dec == num_rank and cfull == cdec
    print(f"  AUROC = {auc} = {float(auc)!r}")

    # 7. bootstrap + permutation, main seed and extra seeds
    cyn = [[cfull[i][n_yes + j] for j in range(n_no)] for i in range(n_yes)]
    p_exact = exact_perm_p(r2_all, n_yes, num)
    print(f"== exact permutation p (all {comb(n, n_yes)} yes-sets) = {float(p_exact)!r}")
    runs = []
    for k in range(args.extra_seeds + 1):
        s_boot = args.seed + 10 * k
        s_perm = args.seed + 10 * k + 1
        lo, hi = bootstrap(cyn, n_yes, n_no, s_boot)
        p, cnt = permutation(r2_all, cfull, n_yes, num, s_perm)
        runs.append((s_boot, s_perm, lo, hi, p, cnt))
        print(f"  seeds boot={s_boot} perm={s_perm}: 95% CI [{lo!r}, {hi!r}]  p={p!r} (count {cnt}/{N_PERM})")
    lo_m, hi_m, p_m = runs[0][2], runs[0][3], runs[0][4]
    los, his = [r[2] for r in runs], [r[3] for r in runs]
    print(f"== MAIN (seed {args.seed} bootstrap, {args.seed + 1} permutation): AUROC={float(auc)!r} n={n} "
          f"n_yes={n_yes} n_no={n_no} CI=[{lo_m!r}, {hi_m!r}] p={p_m!r}")
    print(f"  over {len(runs)} seeds: lower mean {statistics.mean(los):.6f} sd {statistics.stdev(los):.6f} "
          f"range [{min(los):.6f}, {max(los):.6f}]; upper mean {statistics.mean(his):.6f} "
          f"sd {statistics.stdev(his):.6f} range [{min(his):.6f}, {max(his):.6f}]")

    if not args.compare:
        return

    # 8. comparison with the project's result (opened only now)
    pj = json.loads((repo / P_JSON).read_text(encoding="utf-8"))
    print(f"== compare with {P_JSON} (sha256={sha256(repo / P_JSON)})")
    compare(pj, float(auc), n, n_yes, n_no, len(not_exp) - len(prim), lo_m, hi_m, p_m, los, his,
            float(p_exact), lock_shas, len(exposed))


def compare(pj, auc, n, n_yes, n_no, n_nonfinite, lo_m, hi_m, p_m, los, his, p_exact, lock_shas, n_exposed):
    r = pj["primary"]["result"]
    uf = pj["unblind_flag"]
    print(f"  run P names lock files with the hashes checked here: predictions "
          f"{uf['predictions_lock_sha256'] == lock_shas[0]}, labels {uf['labels_lock_sha256'] == lock_shas[1]}")
    print(f"  exposed-set size: project {pj['exposed_set']['n_types']}, mine {n_exposed}; "
          f"non-finite dropped: project {r['n_dropped_nonfinite']}, mine {n_nonfinite}")
    same = (r["n"], r["n_pos"], r["n_neg"]) == (n, n_yes, n_no)
    print(f"  counts: project n={r['n']} n_pos={r['n_pos']} n_neg={r['n_neg']}; mine n={n} n_yes={n_yes} "
          f"n_no={n_no} -> {'IDENTICAL' if same else 'DIFFERENT'}")
    for key, val in (("auroc", r["auroc"]), ("boot.auroc", r["boot"]["auroc"]), ("perm.auroc", r["perm"]["auroc"])):
        d = abs(val - auc)
        print(f"  {key}: project {val!r}, mine {auc!r}, |diff| = {d!r} -> {'AGREE' if d <= 1e-12 else 'DISAGREE'} (1e-12)")
    se = math.sqrt(p_exact * (1 - p_exact) / N_PERM)
    tol_p = 3 * se + 1 / (N_PERM + 1)
    print(f"  p_exact = {p_exact:.6f}; Monte Carlo SE at N={N_PERM}: {se:.6f}; tolerance 3*SE + 1/(N+1) = {tol_p:.6f}")
    for name, p in (("project (seed %d)" % r["perm"]["seed"], r["perm"]["p"]), ("mine", p_m)):
        d = abs(p - p_exact)
        print(f"    p {name} = {p:.6f}; |p - p_exact| = {d:.6f} = {d / se:.2f} SE -> {'close' if d <= tol_p else 'NOT close'}")
    print(f"    |p_project - p_mine| = {abs(r['perm']['p'] - p_m):.6f}")
    grid = 1 / (n_yes * n_no)
    for name, proj, mine_all, mine_main in (("lower", r["boot"]["lo"], los, lo_m), ("upper", r["boot"]["hi"], his, hi_m)):
        mu, sd = statistics.mean(mine_all), statistics.stdev(mine_all)
        tol = max(3 * sd, grid)
        d = abs(proj - mu)
        print(f"  CI {name}: project (seed {r['boot']['seed']}) {proj:.6f}; mine {mine_main:.6f} (|diff| "
              f"{abs(proj - mine_main):.6f}); my {len(mine_all)}-seed mean {mu:.6f} sd {sd:.6f} range "
              f"[{min(mine_all):.6f}, {max(mine_all):.6f}]; |project - mean| = {d:.6f} = {d / sd:.2f} sd, "
              f"tolerance {tol:.6f} -> {'close' if d <= tol else 'NOT close'}")
    dec = r["decision"]
    under = n < 20 or n_yes < 5 or n_no < 5
    print(f"  decision inputs: project underpowered={dec['underpowered']} model_predicts={dec['model_predicts']}; "
          f"mine underpowered={under}, lower bound > 0.5 in {sum(l > 0.5 for l in los)}/{len(los)} seeds")


if __name__ == "__main__":
    main()
