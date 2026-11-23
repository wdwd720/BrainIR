"""Check the numbers printed in PREPRINT_v1 against the locked files cited in CLAIMS_v1.md (one check per printed value).

Each check resolves a field path in a locked file, rounds it as printed, and compares it with the printed text. It also confirms that
each printed string occurs in the paper (or in the named section). Writes `research/ledger/paper/CLAIMS_CHECK_v1.json`; exits 1 on
any failure.

    uv run --project ledger --no-sync python ledger/scripts/posthoc/claims_check_v1.py
"""

from __future__ import annotations

import csv
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
R = ROOT / "research" / "ledger"
PAPER = (R / "paper" / "PREPRINT_v1.md").read_text(encoding="utf-8")
PAPER_FLAT = re.sub(r"\s+", " ", PAPER)
SUPP_FLAT = re.sub(r"\s+", " ", (R / "paper" / "SUPPLEMENT_v1.md").read_text(encoding="utf-8"))


def J(rel):
    return json.loads((R / rel).read_text(encoding="utf-8"))


def get(obj, path):
    for k in path:
        obj = obj[k]
    return obj


C, H, PP = J("thirdfly_v1/C_tests.json"), J("posthoc_v6/H_posthoc.json"), J("paper_posthoc_v1/PAPER_POSTHOC.json")
A0, A, N = J("reliability_v2/A0.json"), J("reliability_v2/A.json"), J("reliability_v2/NOISE.json")
S, P2, P3 = J("replication_v1/S_tests.json"), J("results/run2/P.json"), J("results/run3/primary.json")
EX2, ER, G = J("thirdfly_v1/POSTHOC_exam2_pairs.json"), J("labels_audit_v1/ERROR_RATES.json"), J("gates_v6/BANC_GATE.json")
AG = J("labels_h1/agreement.json")
k3 = "three_animal_noDNg100"
hp = lambda pair, s="high|without_DNg100", z="0.5": H["pairs"][pair][s]["cuts"][z]["overlap"]["point"]  # noqa: E731
c4 = lambda lst, s, z="0.5": C["C4"][lst][s]["cuts"][z]["overlap"]["point"]  # noqa: E731
A1K = "A1 (the authors' list; 16-replicate halves under either procedure)"


def ratio(d):
    return d["primary"]["ratio"], d["bootstrap"]["interval"]["ratio"]


def fmt_ri(d, n=2):
    v, (lo, hi) = ratio(d)
    return f"{v:.{n}f} ({lo:.{n}f}-{hi:.{n}f})"


checks: list[tuple[str, str, str]] = []   # (claim row, expected printed text, value as computed from the locked file)


def add(row, printed, computed):
    checks.append((row, printed, computed))


A0p = A0["A0"]["primary_one_member_each_side"]
add("1", "0.63 of the ceiling (95 % interval 0.53-0.72)", f"{ratio(A0p)[0]:.2f} of the ceiling (95 % interval {ratio(A0p)[1][0]:.2f}-{ratio(A0p)[1][1]:.2f})")
a0 = list(csv.DictReader(open(R / "pertype_v1" / "A0_copies.csv")))
w = {}
for r in a0:
    if str(r["type_one_each_side"]).lower() == "true":
        w.setdefault(r["manc_type"], {})[r["side"]] = float(r["score"])
w = {k: v for k, v in w.items() if "L" in v and "R" in v}
nl, nr = sum(v["L"] >= 0.5 for v in w.values()), sum(v["R"] >= 0.5 for v in w.values())
both = [k for k, v in w.items() if v["L"] >= 0.5 and v["R"] >= 0.5]
add("1", "For the 250 cell types", f"For the {len(w)} cell types")
add("1", "Seven types are hits on the left and 8 on the right; only DNg100 is a hit on both sides",
    f"{'Seven' if nl == 7 else nl} types are hits on the left and {nr} on the right; only {both[0] if len(both) == 1 else both} is a hit on both sides")
six = A["six_agreements_primary_homolog_consistent"]
add("2", "0.59 of the ceiling in MANC (0.48-0.68) and 0.64 in MaleCNS (0.53-0.74)",
    f"{fmt_ri(six['MANC-L vs MANC-R']).replace(' (', ' of the ceiling in MANC (', 1)} and {fmt_ri(six['MaleCNS-L vs MaleCNS-R']).replace(' (', ' in MaleCNS (', 1)}")
add("3", "gave 0.58 (0.38-0.77): again a real gap", f"gave {fmt_ri(C['C1']['label_consistent_noDNg100'])}: again {C['C1']['words']}")
add("3", "the median type scores 0 on each side",
    "the median type scores 0 on each side" if C["C1"]["label_consistent_noDNg100"]["median_score"] == {"L": 0.0, "R": 0.0} else "MEDIAN NOT 0")
sm = C["C5"]["DNg100_single_members"]
add("4", "reached 0.5 in 13 of 16 draws", "reached 0.5 in " + " and ".join(sorted({f"{v['seeds_ge_0_5']} of {v['of']}" for v in sm.values()})) + " draws")
pn = N["primary_homolog_consistent"]
add("5", "at 0.48 of the ceiling (0.36-0.60), against 0.47 (0.34-0.59)",
    f"at {fmt_ri(pn['poisson']['copy_vs_copy']).replace(' (', ' of the ceiling (', 1)}, against {fmt_ri(pn['observed_left_right_paired_design'])}")
c2 = C["C2"]["label_consistent_noDNg100"]
dd = c2["difference_observed_minus_copy"]
add("7", "agreed at 0.78 (0.64-0.89), well above BANC's left-right 0.58", f"agreed at {fmt_ri(c2['copy_vs_copy'])}, well above BANC's left-right {ratio(c2['observed_left_right'])[0]:.2f}")
add("7", "-0.21 (-0.37 to -0.05)", f"{dd['point']:.2f} ({dd['interval'][0]:.2f} to {dd['interval'][1]:.2f})")
add("7", "did not reproduce it", "did not reproduce it" if C["C2"]["words"] == "does not reproduce it" else C["C2"]["words"])
sw, tu = C["C3"]["sweep"], C["C3"]["tuned"]
REF = "MANC-MaleCNS (reference, post hoc)"
add("9", f"| MANC, MaleCNS (post hoc) | {fmt_ri(sw[REF][k3])} | {fmt_ri(tu[REF][k3])} |", f"| MANC, MaleCNS (post hoc) | {fmt_ri(sw[REF][k3])} | {fmt_ri(tu[REF][k3])} |")
add("9", "| MANC, MaleCNS (post hoc) | 0.31 (0.17-0.45) | 0.40 (0.25-0.54) |", f"| MANC, MaleCNS (post hoc) | {fmt_ri(sw[REF][k3])} | {fmt_ri(tu[REF][k3])} |")
add("9", "| MANC, BANC | 0.35 (0.20-0.49) | 0.32 (0.17-0.46) |", f"| MANC, BANC | {fmt_ri(sw['MANC-BANC'][k3])} | {fmt_ri(tu['MANC-BANC'][k3])} |")
add("9", "| MaleCNS, BANC | 0.50 (0.38-0.62) | 0.44 (0.30-0.57) |", f"| MaleCNS, BANC | {fmt_ri(sw['MaleCNS-BANC'][k3])} | {fmt_ri(tu['MaleCNS-BANC'][k3])} |")
sp, tp = hp("sweep_dx1_x_ms"), hp("tuned_B1r_x_B2r")
add("10", "14 of 18 (6.0 expected) | 1 of 10 (1.0) |", f"{sp['k']} of {sp['n_x']} ({sp['chance_expectation']:.1f} expected) | {tp['k']} of {tp['n_x']} ({tp['chance_expectation']:.1f}) |")
m, cc = c4("MANC sweep list", "manc_banc_high_noDNg100"), c4("MaleCNS sweep list", "mcns_banc_high_noDNg100")
add("10", "| 5 of 17 (1.7) |", f"| {m['k']} of {m['n_x']} ({m['chance_expectation']:.1f}) |")
add("10", "| 12 of 60 (6.3) |", f"| {cc['k']} of {cc['n_x']} ({cc['chance_expectation']:.1f}) |")
add("10", "(214, 202, 182)", f"({sp['N']}, {m['N']}, {cc['N']})")
add("11", f"\"{C['C3']['first_line_words']}\"", '"confirmed in the third animal"')
add("11", C["C3"]["first_line_caveat"], "BANC's wiring of these types agrees with the other animals' less than the first two animals' wiring agreed, so part of the gap may come from the build or the type match")
add("12", "the sweep gives 0.32 and 0.57", f"the sweep gives {ratio(sw['MANC-BANC']['three_animal_same_name_noDNg100'])[0]:.2f} and {ratio(sw['MaleCNS-BANC']['three_animal_same_name_noDNg100'])[0]:.2f}")
ws = C["C3_wiring"]["spearman"]
add("13", "counts agree at 0.82", f"counts agree at {ws['MANC-MaleCNS']:.2f}")
add("13", "at 0.61 and 0.63 (0.63 and 0.63 without it)", f"at {ws['MANC-BANC_floor5']:.2f} and {ws['MaleCNS-BANC_floor5']:.2f} ({ws['MANC-BANC']:.2f} and {ws['MaleCNS-BANC']:.2f} without it)")
add("13", "(0.71)", f"({C['C3_wiring']['floor']:.2f})")
swd = hp("sweep_dx1_x_ms", "high|with_DNg100")
add("16", "with DNg100, 15 of 19", f"with DNg100, {swd['k']} of {swd['n_x']}")
md, cd = c4("MANC sweep list", "manc_banc_high"), c4("MaleCNS sweep list", "mcns_banc_high")
add("16", f"(5 of 17, p = 0.016; with DNg100, 6 of", f"({m['k']} of {m['n_x']}, p = {m['hypergeom_p']:.3f}; with DNg100, {md['k']} of")
add("16", "(12 of 60, p = 0.004; with DNg100, 13 of 61)", f"({cc['k']} of {cc['n_x']}, p = {cc['hypergeom_p']:.3f}; with DNg100, {cd['k']} of {cd['n_x']})")
add("17", "29 % and 20 % recur", f"{round(100 * m['rate_x_in_y'])} % and {round(100 * cc['rate_x_in_y'])} % recur")
hpa = PP["sweep"]["with_DNg100"]["hits_per_animal"]["MaleCNS"]
hca = PP["current_setting"]["with_DNg100"]["hits_per_animal"]["MaleCNS"]
add("18", "61 of the 182 three-animal types in MaleCNS, against 18", f"{hpa} of the {PP['sweep']['with_DNg100']['n_types']} three-animal types in MaleCNS, against {hca}")
a1 = list(csv.DictReader(open(R / "pertype_v1" / "A1.csv")))
n_a1 = sum(float(r["score"]) >= 0.5 for r in a1)
add("19", "cut by us at 0.5, has 11 hits", f"cut by us at 0.5, has {n_a1} hits")
au, aud = c4(A1K, "manc_banc_high_noDNg100"), c4(A1K, "manc_banc_high")
add("19", "Six of the 11 have a high-confidence BANC match", f"{'Six' if au['n_x'] == 6 else au['n_x']} of the {n_a1} have a high-confidence BANC match")
add("19", "(0.6 expected; p = 0.47; with DNg100, 2 of 7)", f"({au['chance_expectation']:.1f} expected; p = {au['hypergeom_p']:.2f}; with DNg100, {aud['k']} of {aud['n_x']})")
add("19", "and 1 is a hit in BANC", f"and {au['k']} is a hit in BANC")
add("19", '"at chance at the authors\' cut"', f"\"{C['C4'][A1K]['manc_banc_high_noDNg100']['words_at_0.5']}\"")
sn = [c4(k, "three_animal_same_name_noDNg100") for k in ("MANC sweep list", "MaleCNS sweep list", A1K)]
add("22", "1 of 7 MANC hits, 7 of 30 MaleCNS hits and 0 of 3 of the authors' hits recur",
    f"{sn[0]['k']} of {sn[0]['n_x']} MANC hits, {sn[1]['k']} of {sn[1]['n_x']} MaleCNS hits and {sn[2]['k']} of {sn[2]['n_x']} of the authors' hits recur")
t3 = hp("tuned_B1r_x_B2r", z="0.3")
add("23", "14 shared hits where 6 are expected", f"{t3['k']} shared hits where {round(t3['chance_expectation'])} are expected")
add("23", "(0.31 against 0.40)", f"({ratio(sw[REF][k3])[0]:.2f} against {ratio(tu[REF][k3])[0]:.2f})")
k0 = list(csv.DictReader(open(R / "predictions" / "B2" / "types.csv")))
dng = [r for r in k0 if r.get("manc_type") == "DNg100"][0]
add("24", "(DNg100 0.06 in MaleCNS)", f"(DNg100 {float(dng['primary_score']):.2f} in MaleCNS)")
o, s14 = hp("original_K0_B1lo10_x_B2"), hp("sweep_dx1_x_ms")
add("25", "the only type that is a hit in both MANC and\nMaleCNS is DNb08".replace("\n", " "), "the only type that is a hit in both MANC and MaleCNS is " + ", ".join(o["types_in_both"]))
add("25", "Under the sweep, 14 types besides DNg100 are", f"Under the sweep, {len(s14['types_in_both'])} types besides DNg100 are")
v = C["B4_validity"]
add("26", "in only 11 of 16 draws, short of the pre-registered bar of 12", f"in only {v['tuned']['dng100_seeds_ge_0_5']} of {v['tuned']['of']} draws, short of the pre-registered bar of 12")
add("26", "(8 of 8)", f"({v['sweep']['dng100_seeds_ge_0_5']} of {v['sweep']['of']})")
t = {r["manc_type"]: r for r in csv.DictReader(open(R / "paper_posthoc_v1" / "THREE_ANIMAL_SCORES.csv"))}
add("27", "it was (0.64)", f"it was ({C['C5']['DNg100']['tuned_type_score']:.2f})")
add("27", "(0.81, 0.98, 0.92)", f"({float(t['DNg100']['MANC_sweep']):.2f}, {float(t['DNg100']['MaleCNS_sweep']):.2f}, {float(t['DNg100']['BANC_sweep']):.2f})")
db = C["C5"]["DNb08"]
add("28", "0.00 under the current-setting procedure and 0.25 under the sweep", f"{db['whole_type']['BANC_tuned']:.2f} under the current-setting procedure and {db['whole_type']['BANC_sweep']:.2f} under the sweep")
add("28", "in 0 of 16 draws", "in " + "/".join(sorted({f"{x['seeds_ge_0_5']} of {x['of']}" for x in db["single_members"].values()})) + " draws")
all3 = PP["sweep"]["with_DNg100"]["all_three_types"]
add("29", "DNg100, DNxl134, DNa13 and DNxl092", "DNg100, DNxl134, DNa13 and DNxl092" if sorted(all3) == sorted(["DNg100", "DNxl134", "DNa13", "DNxl092"]) else str(all3))
add("29", "only DNg100 is; DNa13 and DNxl092 score 0.00 in BANC",
    f"only {', '.join(PP['current_setting']['with_DNg100']['all_three_types'])} is; DNa13 and DNxl092 score {float(t['DNa13']['BANC_current_setting']):.2f} in BANC"
    if abs(float(t['DNa13']['BANC_current_setting']) - float(t['DNxl092']['BANC_current_setting'])) < 0.005 else "DIFFER")
add("30", "The 22 of the 182 types", f"The {PP['sweep']['with_DNg100']['hit_in_at_least_two']} of the 182 types")
add("30", "71 types are\nhits in at least one".replace("\n", " "), f"{PP['sweep']['with_DNg100']['hit_in_at_least_one']} types are hits in at least one")
V2 = C["V"]["V2"]["table"]["391"]["250"]
add("31", "15 of 16 draws reach 0.5 (mean 0.86; theirs 0.80", f"{round(V2['frac_ge_0_5'] * 16)} of 16 draws reach 0.5 (mean {V2['mean']:.2f}; theirs 0.80")
add("31", "(mean 0.985; theirs 0.985)", f"(mean {C['V']['V1']['mean']:.3f}; theirs {C['V']['V1']['authors']['mean']:.3f})")
ok_copies = all(max(c["frac_ge_0_5"] for c in tab.values()) >= 0.5 for tab in C["V"]["V2"]["table"].values())
add("31", "Each of the four copies reaches 0.5 in at least half the draws at some fixed current",
    "Each of the four copies reaches 0.5 in at least half the draws at some fixed current" if ok_copies else "NOT ALL")
tb = S["tests"]["b1r_drivers"]
add("32", "(p = 0.11)", f"(p = {tb['primary_stability']['p']:.2f})")
add("32", "(p = 0.035 and 0.033; the others 0.13 and 0.18)",
    f"(p = {tb['sensitivity_ii_mean_copy_score']['p']:.3f} and {tb['sensitivity_iii_mean_frac_rhythmic']['p']:.3f}; the others "
    f"{tb['sensitivity_i_high_confidence']['p']:.2f} and {tb['sensitivity_iv_without_low_usable']['p']:.2f})")
c8 = C["C8"]
add("33", "Spearman 0.57, one-sided p = 0.029", f"Spearman {c8['primary']['rho']:.2f}, one-sided p = {c8['primary']['p_one_sided_permutation']:.3f}")
add("33", "0.64 with\nDNg100, 0.54 without DNb08, 0.53 with".replace("\n", " "),
    f"{c8['with_DNg100']['rho']:.2f} with DNg100, {c8['without_DNb08']['rho']:.2f} without DNb08, {c8['stability_fraction']['rho']:.2f} with")
add("33", "partial correlation of 0.56", f"partial correlation of {c8['partial_given_B1r_score']['rho_partial']:.2f}")
dt = {r["manc_type"]: r for r in C["C5"]["driver_table"]}
low = sum(float(dt[x]["BANC_sweep"]) < 0.07 for x in c8["primary"]["types"])
add("33", "ten of the 12 BANC\nscores are below 0.07".replace("\n", " "), f"{'ten' if low == 10 else low} of the {c8['primary']['n']} BANC scores are below 0.07")
b1 = {r["manc_type"]: r for r in csv.DictReader(open(R / "pertype_v1" / "B1r.csv"))}
add("33", "rest on 1 and 6 usable draws of 16", f"rest on {int(float(b1['DNg63']['n_usable']))} and {int(float(b1['DNxl121']['n_usable']))} usable draws of 16")
c6 = C["C6"]
add("34", "(gain in correlation 0.20, 0.08 to 0.32)", f"(gain in correlation {c6['d_M']['point']:.2f}, {c6['d_M']['interval'][0]:.2f} to {c6['d_M']['interval'][1]:.2f})")
add("34", "MaleCNS's alone (0.02, -0.03 to 0.07)", f"MaleCNS's alone ({c6['d_C']['point']:.2f}, {c6['d_C']['interval'][0]:.2f} to {c6['d_C']['interval'][1]:.2f})")
c7 = C["C7"]
add("35", "average 0.39 of the ceiling", f"average {c7['rbar']:.2f} of the ceiling")
add("35", "about 7 animals (4.3 to 9.7)", f"about {c7['n_star_rounded_up']} animals ({c7['interval'][0]:.1f} to {c7['interval'][1]:.1f})")
rng = PP["C7_per_pair"]["range"]
add("36", "about 4 to 9 animals", f"about {round(rng[0])} to {round(rng[1])} animals")
hm = P3["H-M"]
ci3 = P3["ci"] if isinstance(P3["ci"], (list, tuple)) else [P3["ci"]["lo"], P3["ci"]["hi"]]
p3 = P3["p"] if not isinstance(P3["p"], dict) else P3["p"]["p"]
add("37", "(mean 0.633, 0.533-0.724, p = 0.008)", f"(mean {hm['mean_pr']:.3f}, {ci3[0]:.3f}-{ci3[1]:.3f}, p = {p3:.3f})")
add("37", "(0 of 27)", f"({round(hm['top1'] * hm['n'])} of {hm['n']})")
add("37", "scored 0.638 (difference -0.006, -0.172 to\n0.166)".replace("\n", " "),
    f"scored {(P3['H-S']['H-S-k2-signed']['mean_pr'] if isinstance(P3['H-S']['H-S-k2-signed'], dict) else P3['H-S']['H-S-k2-signed']):.3f} "
    f"(difference {P3['vs_best_H-S']['diff']:.3f}, {P3['vs_best_H-S']['lo']:.3f} to {P3['vs_best_H-S']['hi']:.3f})")
ca = sorted(b["difference"] for b in EX2["baselines"].values() if b["clearly_above"])
add("39", "clearly above four (post hoc: differences 0.14 to 0.21)", f"clearly above {'four' if len(ca) == 4 else len(ca)} (post hoc: differences {ca[0]:.2f} to {ca[-1]:.2f})")
kk = AG["between_sources"]["10.7554/elife.04493 vs 10.7554/elife.106042"]
add("40", "0.24 over the 33", f"{kk['kappa']:.2f} over the {kk['n']}")
pr = P2["primary"]["result"]
add("41", "(area under the curve 0.577, 0.417-0.724; signed two-step counting 0.669)",
    f"(area under the curve {pr['auroc']:.3f}, {pr['boot']['lo']:.3f}-{pr['boot']['hi']:.3f}; signed two-step counting {pr['baselines_auroc']['S2_twohop_signed']:.3f})")
add("44", "shares 10 of their 11 whole-type hits", f"shares {sum(float(b1.get(r['manc_type'], {}).get('score', 0) or 0) >= 0.5 for r in a1 if float(r['score']) >= 0.5)} of their {n_a1} whole-type hits")
g = G["conditions"]
add("46", "(mean\n0.994; theirs 0.984)".replace("\n", " "), f"(mean {g['intact']['mean']:.3f}; theirs 0.984)")
add("46", "(0.000 and 0.028; theirs 0.014 and 0.035)", f"({g['E1']['mean']:.3f} and {g['E2']['mean']:.3f}; theirs 0.014 and 0.035)")
sd = C["B2_sides"]
add("47", "S2: 62.7 % of 840 neurons", f"S2: {100 * sd['agreement']:.1f} % of {sd['n_defined']} neurons")
e = ER["census_39"]
add("51", "3 errors among\nthe 39 labels (7.7 %): none among the 21".replace("\n", " "),
    f"{e['all']['errors']} errors among the {e['all']['n']} labels ({100 * e['all']['rate']:.1f} %): {'none' if e['atlas_only']['errors'] == 0 else e['atlas_only']['errors']} among the {e['atlas_only']['n']}")
add("51", "3 among the 18 others (17 %", f"{e['other']['errors']} among the {e['other']['n']} others ({round(100 * e['other']['errors'] / e['other']['n'])} %")
add("51", "exclude 18 whose", f"exclude {P2['exposed_set']['n_types']} whose")
tg, d1, d2 = J("gates_v6/TRUST_GATE_v6.json"), J("gates_v6/DETERMINISM_v6_stage1.json"), J("gates_v6/DETERMINISM_v6_stage2.json")
add("52", "re-run of 100 locked simulations matched exactly", f"re-run of {tg['identical']} locked simulations matched exactly" if tg["identical"] == tg["n"] else "TRUST MISMATCH")
add("52", "(240 of 240 identical)", f"({d1['identical'] + d2['identical']} of {d1['n'] + d2['n']} identical)")

# The table's own File column: every cited path must exist (repository-relative, or relative to research/ledger/).
missing_paths = []
for line in (R / "paper" / "CLAIMS_v1.md").read_text(encoding="utf-8").splitlines():
    cells = [c.strip() for c in line.split("|")]
    if len(cells) < 8 or not cells[1].isdigit():
        continue
    for tok in re.findall(r"`([^`]+)`", cells[4]):
        tok = tok.strip()
        if "/" not in tok and not re.search(r"\.(json|csv|md|py|parquet)$", tok):
            continue
        cands = [R / tok, ROOT / tok, R / "paper" / tok, R / "forward_v2" / tok, R / "gates_v6" / tok, R / "labels_audit_v1" / tok]
        if not any(c.exists() for c in cands):
            missing_paths.append({"row": cells[1], "path": tok})

res = []
for row, printed, computed in checks:
    in_paper = (re.sub(r"\s+", " ", printed[4:]) in SUPP_FLAT) if printed.startswith("S2: ") else (re.sub(r"\s+", " ", printed) in PAPER_FLAT)
    res.append({"row": row, "printed": printed, "computed": computed, "matches_locked": printed == computed, "found_in_paper": in_paper})
bad = [r for r in res if not (r["matches_locked"] and r["found_in_paper"])]
out = {"n_checks": len(res), "n_failed": len(bad), "failed": bad, "claims_paths_missing": missing_paths, "checks": res}
(R / "paper" / "CLAIMS_CHECK_v1.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"{len(res)} checks, {len(bad)} failed; cited paths missing: {len(missing_paths)}")
for m in missing_paths:
    print("  MISSING PATH row", m["row"], m["path"])
for b in bad:
    print(" FAIL row", b["row"], "| printed:", b["printed"][:110], "| computed:", b["computed"][:110], "| in paper:", b["found_in_paper"])
sys.exit(1 if bad or missing_paths else 0)
