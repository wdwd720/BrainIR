"""The tables of RESULTS_5 generated from `thirdfly_v1/C_tests.json` (no hand-copied number): one row per test with its pre-registered
words and numbers, the three-animal table of hits, Part V and the forward list. Output: `thirdfly_v1/C_tables.md` (hashed by
LOCK_thirdfly_v1).

    uv run --project ledger --no-sync python ledger/scripts/posthoc/results5_tables.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from brainir_ledger import RESEARCH  # noqa: E402


def f(x, n=2):
    return "-" if x is None else (f"{x:.{n}f}" if isinstance(x, (int, float)) else str(x))


def ratio(d):
    iv = d["bootstrap"]["interval"]["ratio"]
    return f"{f(d['primary']['ratio'])} ({f(iv[0])}-{f(iv[1])})"


def main() -> None:
    C = json.loads((RESEARCH / "thirdfly_v1" / "C_tests.json").read_text())
    prim = C["primary_procedure"]
    v = C["B4_validity"]
    L = ["# Run 6: the third animal (BANC), tests C1-C8 and Part V (generated from `thirdfly_v1/C_tests.json`)", "",
         f"**Validity (B4):** tuned screen DNg100 >= 0.5 in {v['tuned']['dng100_seeds_ge_0_5']} of {v['tuned']['of']} seeds "
         f"({'valid' if v['tuned']['valid'] else 'NOT valid'}; bar 12); sweep {v['sweep']['dng100_seeds_ge_0_5']} of {v['sweep']['of']} "
         f"({'valid' if v['sweep']['valid'] else 'not valid'}; bar 6). **Primary procedure: {prim}.**", "",
         "## The tests (words are PREREG v6's; sets without DNg100)", "", "| test | pre-registered words | numbers |", "|---|---|---|"]
    c1 = C["C1"]
    if isinstance(c1, dict):
        b = c1["label_consistent_noDNg100"]
        L.append(f"| C1 left vs right in BANC ({c1['type_sets']['label_consistent_noDNg100']} types) | {c1['words']} | ratio {ratio(b)}; "
                 f"drivers L {b['drivers']['L']}, R {b['drivers']['R']}; MANC 0.59, MaleCNS 0.64 (locked) |")
    c2 = C["C2"]
    if isinstance(c2, dict):
        b = c2["label_consistent_noDNg100"]
        cc, ob = b["copy_vs_copy"], b["observed_left_right"]
        iv = cc["bootstrap"]["interval"]["rho_x"]
        L.append(f"| C2 count noise in BANC | {c2['words']} | copy vs copy rho_x {f(cc['primary']['rho_x'])} ({f(iv[0])}-{f(iv[1])}), ratio "
                 f"{ratio(cc)}; observed left-right rho_x {f(ob['primary']['rho_x'])}, ratio {ratio(ob)}; difference "
                 f"{f(b['difference_observed_minus_copy']['point'])} ({f(b['difference_observed_minus_copy']['interval'][0])}-"
                 f"{f(b['difference_observed_minus_copy']['interval'][1])}) |")
    c3 = C["C3"]
    r = c3.get("first_line_ratios") or {}
    L.append(f"| C3 across animals ({prim}; 181 types) | {c3['first_line_words']} | " + "; ".join(
        f"{k} {f(x['ratio'])} ({f(x['interval'][0])}-{f(x['interval'][1])})" for k, x in r.items()) +
        (f"; wiring check {json.dumps({k: round(x, 3) for k, x in C['C3_wiring']['spearman'].items()})}" if C.get("C3_wiring") else "") +
        (f"; CAVEAT: {c3.get('first_line_caveat')}" if c3.get("first_line_caveat") else "") + " |")
    c4 = C["C4"]
    if isinstance(c4, dict):
        for name, blocks in c4.items():
            if not isinstance(blocks, dict):
                continue
            key = [k for k in blocks if k.endswith("high_noDNg100")][0]
            b = blocks[key]
            p = b["cuts"]["0.5"]["overlap"]["point"]
            o = b["cuts"]["0.5"]["overlap"]["bootstrap_95"]["OC_ratio"]
            curve = ", ".join(f"{z}: {b['cuts'][z]['overlap']['point']['k']}/{b['cuts'][z]['overlap']['point']['n_x']} "
                              f"(chance {f(b['cuts'][z]['overlap']['point']['chance_expectation'], 1)})" for z in ("0.3", "0.4", "0.5", "0.6"))
            L.append(f"| C4 {name} ({key}, N {p['N']}) | {b['words_at_0.5']} | at 0.5: {p['k']} of {p['n_x']} recur (CP "
                     f"{f(p['rate_x_in_y_clopper_pearson'][0])}-{f(p['rate_x_in_y_clopper_pearson'][1])}); BANC drivers {p['n_y']}; chance "
                     f"{f(p['chance_expectation'])}; p {f(p['hypergeom_p'], 3)}; OC ratio {f(p['OC_ratio'])} ({f(o['lo'])}-{f(o['hi'])}); curve {curve}; "
                     f"AUROC {f(b['cuts']['0.5']['graded']['point']['auroc_y_for_x_drivers'])} |")
    c5 = C["C5"]
    if isinstance(c5, dict):
        d = c5["DNg100"]
        L.append(f"| C5 DNg100 (tuned) | {d['words']} | tuned type score {f(d['tuned_type_score'])}, {d['tuned_seeds_ge_0_5']} of 16 seeds >= 0.5; "
                 f"sweep {f(d['sweep_type_score_beside'])} |")
        w = c5["DNb08"]["whole_type"]
        sm = "; ".join(f"{k.split('#')[1]}: {f(x['score'])} ({x['seeds_ge_0_5']}/16)" for k, x in c5["DNb08"]["single_members"].items())
        L.append(f"| C5 DNb08 (no prediction) | - | whole type tuned {f(w.get('BANC_tuned'))}, sweep {f(w.get('BANC_sweep'))}; members alone: {sm}; "
                 f"authors' BANC run position {(c5['DNb08']['authors_banc_config'] or {}).get('stim_position')} at "
                 f"{(c5['DNb08']['authors_banc_config'] or {}).get('stim_current')}: 0.000 |")
    c6 = C["C6"]
    if isinstance(c6, dict):
        L.append(f"| C6 pooling ({c6['n_types']} types) | {c6['words']} | d_M {f(c6['d_M']['point'], 3)} ({f(c6['d_M']['interval'][0], 3)} to "
                 f"{f(c6['d_M']['interval'][1], 3)}); d_C {f(c6['d_C']['point'], 3)} ({f(c6['d_C']['interval'][0], 3)} to {f(c6['d_C']['interval'][1], 3)}); "
                 f"prompt's D (no words) {f(c6['prompt_D_without_words']['D'], 3)} |")
    c7 = C["C7"]
    if isinstance(c7, dict):
        L.append(f"| C7 how many connectomes | (an extrapolation; no words) | rbar {f(c7.get('rbar'))}; n* {f(c7.get('n_star'), 1)} (rounded up "
                 f"{c7.get('n_star_rounded_up')}), interval {f(c7['interval'][0], 1)} to {f(c7['interval'][1], 1)} |")
    c8 = C["C8"]
    if isinstance(c8, dict):
        p = c8["primary"]
        L.append(f"| C8 stability predicts BANC ({p['n']} types) | {p['words']} | Spearman {f(p['rho'])}, one-sided p "
                 f"{f(p.get('p_one_sided_permutation'), 3)}; with DNg100 {f(c8['with_DNg100']['rho'])}; without DNb08 {f(c8['without_DNb08']['rho'])}; "
                 f"stability fraction {f(c8['stability_fraction']['rho'])}; partial given MANC score {f(c8['partial_given_B1r_score']['rho_partial'])} |")
    V = C["V"]
    L += ["", "## Part V (descriptive; fixed words)", "", f"- **V1:** {V['V1']['words']} (mean {f(V['V1']['mean'])}, "
          f"{f(V['V1']['frac_ge_0_5'])} of 64 seeds >= 0.5; authors 0.985).",
          f"- **V2:** {V['V2']['authors_configuration_sentence']}.", f"- **V2 words:** {V['V2']['words']}."]
    L += ["", "## Hits in any animal (C5 table; scores)", "", "| type | MANC tuned | MaleCNS tuned | BANC tuned | MANC sweep | MaleCNS sweep | BANC sweep | "
          "authors (A1) | match MaleCNS / BANC |", "|---|---|---|---|---|---|---|---|---|"]
    for row in C["C5"]["driver_table"] if isinstance(C["C5"], dict) else []:
        L.append(f"| {row['manc_type']} | {f(row.get('B1r'))} | {f(row.get('B2r'))} | {f(row.get('BANC_tuned'))} | {f(row.get('MANC_sweep'))} | "
                 f"{f(row.get('MaleCNS_sweep'))} | {f(row.get('BANC_sweep'))} | {f(row.get('A1'))} | {row['malecns_match']} / {row['banc_match']} |")
    L += ["", "## The forward list with BANC scores (readings unchanged)", "", "| type | BANC tuned | BANC sweep | BANC match |", "|---|---|---|---|"]
    for row in C["F"]:
        L.append(f"| {row['manc_type']} | {f(row['banc_tuned'])} | {f(row['banc_sweep'])} | {row['banc_match']} |")
    (RESEARCH / "thirdfly_v1" / "C_tables.md").write_text("\n".join(L) + "\n")
    print("\n".join(L[:20]))


if __name__ == "__main__":
    main()
