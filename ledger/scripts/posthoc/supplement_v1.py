"""SUPPLEMENT_v1.md for PREPRINT_v1: written sections plus tables generated from locked files (no hand-copied number).
Inputs: `thirdfly_v1/C_tests.json` (LOCK_thirdfly_v1), `posthoc_v6/H_posthoc.json` (LOCK_posthoc_v6), `paper_posthoc_v1/`
(LOCK_paper_posthoc_v1), `gates_v6/` (prereg and third-fly locks), `pertype_v1/` (LOCK_pertype_v1), `labels_audit_v1/ERROR_RATES.json`,
`labels_audit_v1/RESCORE_exploratory.json` (LOCK_replication_v1), `results/run2/P.json` (tag ledger-scorecard-v1).
Output: `paper/SUPPLEMENT_v1.md`.

    uv run --project ledger --no-sync python ledger/scripts/posthoc/supplement_v1.py
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


def j(rel):
    return json.loads((RESEARCH / rel).read_text())


NAME_MAP = [
    ("first animal, MANC", "MANC v1.2.1 front-leg network (our rebuild, identical to the authors')", "`networks.front_leg()`"),
    ("second animal, MaleCNS", "the authors' MaleCNS front-leg network (`W_20260210_vncRoisOnly`)", "`arms.malecns_network()`"),
    ("third animal, BANC", "the authors' BANC front-leg network as released (`W_20260217.npz`)", "`banc.network()`"),
    ("the authors' single-neuron screen", "their 128-draw screen of single descending neurons in MANC", "A0"),
    ("the authors' whole-type screen", "their 16-draw screen of whole cell types in MANC (their Extended Data Fig. 1c), cut by us at 0.5", "A1"),
    ("our current-setting procedure", "the automatic current rule with one free setting: at least 1 active front-leg motor neuron", "tuner v2, K = 1; B1r / B2r / BT"),
    ("the original procedure", "our reimplementation of the authors' automatic current rule, without the motor-neuron requirement", "K = 0; B1-lo10 / B2"),
    ("the current sweep", "19 fixed currents 4-2,048; each draw's best in-bounds score", "rulebook v4 fix 1; dx-1 / ms / bs"),
    ("one-sided screens", "one side's copies stimulated, that side's motor neurons read out", "half-fly screens; BH"),
    ("resampled networks", "copies of a network with each synapse count redrawn from a Poisson distribution", "Poisson copies; B4.2 / C2; BN"),
    ("our earlier stability test", "stability under count noise in MANC, run 5", "Part S"),
    ("the first literature test", "front-leg rhythm when a type is switched on (39 types)", "exam 1"),
    ("the second literature test", "movement phenotypes of 27 hemilineages", "exam 2"),
    ("types excluded because their outcomes were known", "types whose model scores and fly outcomes we knew", "exposed set"),
    ("the procedure's one free setting", "the number of front-leg motor neurons that must be active", "K"),
    ("the rules", "the pre-registration rulebooks", "PREREG v1-v6"),
]

GLOSSARY = [
    ("draw", "one simulation with neuron parameters drawn at random (the ledger's files say seed or replicate)"),
    ("hit", "a cell type (or neuron) whose mean rhythm score is at least 0.5 (the files also say driver)"),
    ("copies", "a cell type's left and right neurons (bilateral homologs); the files say members or positions"),
    ("ceiling", "how well a screen agrees with itself across two halves of its draws"),
    ("agreement ratio", "cross-screen agreement of half-screens divided by the mean of the two ceilings; 1 = as close as a screen is to itself"),
    ("rho_x", "the cross-half rank correlation before division by the ceiling"),
    ("a real gap", "the ratio's 95 % interval lies below 1 (pre-registered words)"),
    ("overlap ratio (OC ratio)", "hits shared across two screens, relative to the share expected between two halves of the same screen"),
    ("graded overlap (AUROC)", "the probability that one screen's hit scores higher in the other screen than one of its non-hits; 0.5 = chance"),
    ("CP interval", "exact (Clopper-Pearson) 95 % interval for a share"),
    ("d_M, d_C", "pooling test: the pooled two-animal score's agreement with BANC minus MANC's alone (d_M) or MaleCNS's alone (d_C)"),
    ("E1, E2, I2", "the two excitatory and one inhibitory interneurons of the authors' rhythm circuit, as named in their paper"),
]


def r(d) -> str:
    v = d["primary"]["ratio"]
    lo, hi = d["bootstrap"]["interval"]["ratio"]
    return f"{f(v)} ({f(lo)}-{f(hi)})"


def ov(blk, z="0.5") -> str:
    p = blk["cuts"][z]["overlap"]["point"]
    pv = "<0.001" if p["hypergeom_p"] < 0.001 else f(p["hypergeom_p"], 3)
    ci = p["rate_x_in_y_clopper_pearson"]
    return f"{p['k']} of {p['n_x']} (CP {f(ci[0])}-{f(ci[1])}); chance {f(p['chance_expectation'])}; p {pv}; OC ratio {f(p['OC_ratio'])}"


def main() -> None:
    import csv  # noqa: PLC0415

    C = j("thirdfly_v1/C_tests.json")
    H = j("posthoc_v6/H_posthoc.json")
    PP = j("paper_posthoc_v1/PAPER_POSTHOC.json")
    gate = j("gates_v6/BANC_GATE.json")
    er = j("labels_audit_v1/ERROR_RATES.json")
    rs = j("labels_audit_v1/RESCORE_exploratory.json")
    title = (RESEARCH / "paper" / "PREPRINT_v1.md").read_text().splitlines()[0].lstrip("# ").strip()
    L = [f"# Supplement to: {title}", "",
         "Every number here comes from a locked file of the BrainIR prediction ledger (branch `ledger/v1`); this file is generated by",
         "`ledger/scripts/posthoc/supplement_v1.py`. \"Post hoc\" marks analyses decided after the data they concern were seen.", "",
         "## S1. Names and terms", "", "| In the paper | What it is | Name in the repository's files |", "|---|---|---|"]
    L += [f"| {a} | {b} | {c} |" for a, b, c in NAME_MAP]
    L += ["", "| Term | Meaning |", "|---|---|"] + [f"| {a} | {b} |" for a, b in GLOSSARY]
    nz = {}
    for arm in ("B1r", "B2r"):
        rows = list(csv.DictReader(open(RESEARCH / "pertype_v1" / f"{arm}.csv")))
        nz[arm] = (sum(float(x["n_usable"] or 0) == 0 for x in rows), len(rows))
    L += ["", f"A type with no usable draw scores 0 (the rule fixed in rulebook v2): {nz['B1r'][0]} of {nz['B1r'][1]} MANC types and "
          f"{nz['B2r'][0]} of {nz['B2r'][1]} MaleCNS types under the current-setting procedure (`pertype_v1/`)."]
    # S2 build and gate
    g = gate["conditions"]
    sd = C["B2_sides"]
    L += ["", "## S2. The third animal: build, check, type matching and sides", "",
          "- **Sources.** The authors' released BANC matrix (4,963 neurons, 496,041 signed connections, no synapse threshold) and table, at the",
          "  commit pinned in the ledger, checked by SHA-256; their run configurations read from their Zenodo record.",
          "- **Build.** The matrix as released; every row single-signed, agreeing with the transmitter rule (verified, else predicted) for all",
          "  4,863 rows the rule covers; sizes from surface area, as in the authors' code for BANC; excitatory descending neurons by the authors'",
          "  rule (922); read-out the 139 front-leg motor neurons (12 neck motor neurons left out, as in the other animals).",
          f"- **Build check** (fixed before it ran; DNg100 at the authors' current, 64 draws): intact mean {f(g['intact']['mean'], 3)} "
          f"({f(g['intact']['frac_ge_0_5'])} of draws >= 0.5; authors 0.984); E1 silenced {f(g['E1']['mean'], 3)}; E2 silenced "
          f"{f(g['E2']['mean'], 3)}; I2 silenced {f(g['I2']['mean'], 3)} (authors 0.014, 0.035, 0.993). Verdict: {gate['verdict']}. E1 and E2",
          "  are the circuit's two excitatory interneurons and I2 an inhibitory one (the authors' names). The check covers one neuron and its",
          "  circuit at one current; it cannot catch errors in other neurons' wiring, signs or sizes.",
          "- **Type matching.** 1,221 of 1,313 descending neurons carry a MANC match ID; 860 excitatory ones map to 309 MANC types; high",
          "  confidence 206, medium 103, low 0. The three-animal set: 182 types (181 without DNg100). BANC's type names appear to come from",
          "  the same ID match (no conflict in 1,221), so \"high\" adds little to the ID match; the same-name subset (96 types without DNg100)",
          "  is reported beside the tests without a verdict.",
          f"- **Sides.** BANC's side labels appear to follow the cell body, and many descending neurons send most of their output to the other",
          f"  side. Labels agree with each neuron's output side for {f(sd['agreement'] * 100, 1)} % of {sd['n_defined']} neurons (the rule's bar: 90 %),",
          f"  so each copy's side is its output side, as for MaleCNS. {sd['n_all_matched']} types have copies on both sides; "
          f"{sd['n_label_consistent']} of them have a single BANC label, and 180 without DNg100 form the left-right test's set."]
    # S3 the tests, from C_tests.json
    v = C["B4_validity"]
    c1, c2 = C["C1"], C["C2"]
    c3s, c3t, w = C["C3"]["sweep"], C["C3"]["tuned"], C["C3_wiring"]["spearman"]
    k3 = "three_animal_noDNg100"
    fixed = "'At chance' means the overlap could not be told apart from chance by this test, whose power is low; it does not show that the hits fail to recur."
    L += ["", "## S3. Every pre-registered test of the third animal", "",
          f"**Validity rule.** Our current-setting procedure gave DNg100 a score of at least 0.5 in {v['tuned']['dng100_seeds_ge_0_5']} of 16 draws "
          f"(bar 12), the current sweep in {v['sweep']['dng100_seeds_ge_0_5']} of 8 (bar 6), so the sweep is primary for the cross-animal tests "
          "(agreement, hit lists, pooling, number of animals, stability). The left-right and count-noise tests use one-sided screens run with",
          "the current-setting procedure, as pre-registered. Verdicts rest on the sets without DNg100; \"beside\" values carry no verdict.", "",
          "| Test | Verdict fixed in advance | On the verdict's set (DNg100 left out) | Beside the verdict |", "|---|---|---|---|",
          f"| Left vs right copies (one-sided screens, 180 types) | {c1['words']} | ratio {r(c1['label_consistent_noDNg100'])}; hits left "
          f"{c1['label_consistent_noDNg100']['drivers']['L']}, right {c1['label_consistent_noDNg100']['drivers']['R']}; median score 0 on each side | "
          f"with DNg100 {r(c1['label_consistent'])}; all matched types {r(c1['all_matched_noDNg100'])}; earlier: MANC "
          f"{f(c1['reference_locked']['MANC_L_vs_R'])}, MaleCNS {f(c1['reference_locked']['MaleCNS_L_vs_R'])} |",
          f"| Count noise (resampled networks, 180 types) | {c2['words']} | resampled vs resampled {r(c2['label_consistent_noDNg100']['copy_vs_copy'])}; "
          f"left vs right {r(c2['label_consistent_noDNg100']['observed_left_right'])}; difference in rho_x "
          f"{f(c2['label_consistent_noDNg100']['difference_observed_minus_copy']['point'])} "
          f"({f(c2['label_consistent_noDNg100']['difference_observed_minus_copy']['interval'][0])} to "
          f"{f(c2['label_consistent_noDNg100']['difference_observed_minus_copy']['interval'][1])}) | each resampled network vs the real "
          f"left screen {r(c2['label_consistent_noDNg100']['copy1_vs_L'])} and {r(c2['label_consistent_noDNg100']['copy2_vs_L'])}; with DNg100: "
          f"resampled {r(c2['label_consistent']['copy_vs_copy'])} |",
          f"| Agreement across animals (current sweep, 181 types) | {C['C3']['first_line_words']}, with the fixed caveat: \"{C['C3']['first_line_caveat']}.\" | "
          f"MANC-BANC {r(c3s['MANC-BANC'][k3])}; MaleCNS-BANC {r(c3s['MaleCNS-BANC'][k3])}; MANC-MaleCNS (post hoc) "
          f"{r(c3s['MANC-MaleCNS (reference, post hoc)'][k3])} | with DNg100: {r(c3s['MANC-BANC']['three_animal'])}, "
          f"{r(c3s['MaleCNS-BANC']['three_animal'])}; same-name (96): {r(c3s['MANC-BANC']['three_animal_same_name_noDNg100'])}, "
          f"{r(c3s['MaleCNS-BANC']['three_animal_same_name_noDNg100'])}; current-setting procedure: {r(c3t['MANC-BANC'][k3])}, "
          f"{r(c3t['MaleCNS-BANC'][k3])}, MANC-MaleCNS {r(c3t['MANC-MaleCNS (reference, post hoc)'][k3])}; wiring (two-step counts, Spearman): "
          f"MANC-MaleCNS {f(w['MANC-MaleCNS'])}, BANC at a 5-synapse threshold {f(w['MANC-BANC_floor5'])} and {f(w['MaleCNS-BANC_floor5'])}, "
          f"without it {f(w['MANC-BANC'])} and {f(w['MaleCNS-BANC'])}; caveat threshold 0.71 |"]
    lists = [("Our MANC hits in BANC (202 types)", "MANC sweep list", "manc_banc_high_noDNg100", "manc_banc_high", "manc_banc_all_noDNg100"),
             ("The authors' whole-type hits in BANC (202 types)", "A1 (the authors' list; 16-replicate halves under either procedure)",
              "manc_banc_high_noDNg100", "manc_banc_high", "manc_banc_all_noDNg100"),
             ("Our MaleCNS hits in BANC (182 types)", "MaleCNS sweep list", "mcns_banc_high_noDNg100", "mcns_banc_high", "mcns_banc_all_noDNg100")]
    for lab, key, sw, swd, sa in lists:
        B = C["C4"][key]
        words = B[sw]["words_at_0.5"] if "words_at_0.5" in B[sw] else B[sw].get("words", "")
        wtxt = words + (f" ({fixed})" if words.startswith("at chance") else "")
        curve = ", ".join(f"{z}: {B[sw]['cuts'][z]['overlap']['point']['k']} of {B[sw]['cuts'][z]['overlap']['point']['n_x']} "
                          f"(chance {f(B[sw]['cuts'][z]['overlap']['point']['chance_expectation'], 1)})" for z in ("0.3", "0.4", "0.6"))
        auc = B[sw]["cuts"]["0.5"]["graded"]["point"]["auroc_y_for_x_drivers"]
        L.append(f"| {lab} | {wtxt} | {ov(B[sw])} | with DNg100 {ov(B[swd])}; all matched {ov(B[sa])}; same-name (96) "
                 f"{ov(B['three_animal_same_name_noDNg100'])}; other thresholds {curve}; graded overlap at 0.5 {f(auc)} |")
    c5 = C["C5"]
    sm = c5["DNg100_single_members"]
    db = c5["DNb08"]
    L.append(f"| DNg100 in BANC (current-setting procedure; DNg100 itself) | {c5['DNg100']['words']} | score {f(c5['DNg100']['tuned_type_score'])}; "
             f"{c5['DNg100']['tuned_seeds_ge_0_5']} of 16 draws >= 0.5 | sweep {f(c5['DNg100']['sweep_type_score_beside'])}; each copy alone: "
             + ", ".join(f"{v_['seeds_ge_0_5']} of {v_['of']}" for v_ in sm.values()) + " |")
    L.append(f"| DNb08 in BANC | (no prediction) | current-setting {f(db['whole_type']['BANC_tuned'])}; sweep {f(db['whole_type']['BANC_sweep'])}; "
             "each copy alone (current-setting) " + ", ".join(f"{v_['seeds_ge_0_5']} of {v_['of']}" for v_ in db["single_members"].values())
             + " | the authors report a mean of 0.000 for their single DNb08 neuron in BANC; we did not run their configuration |")
    c6 = C["C6"]
    c6d = C["C6_with_DNg100"]
    L.append(f"| Pooling two animals (181 types) | {c6['words']} | d_M {f(c6['d_M']['point'])} ({f(c6['d_M']['interval'][0])} to "
             f"{f(c6['d_M']['interval'][1])}); d_C {f(c6['d_C']['point'])} ({f(c6['d_C']['interval'][0])} to {f(c6['d_C']['interval'][1])}) | "
             f"with DNg100: d_M {f(c6d['d_M']['point'])}, d_C {f(c6d['d_C']['point'])}; the instructions' average over three targets "
             f"{f(c6['prompt_D_without_words']['D'])} (positive by construction, so not used for the verdict) |")
    c7, c7d, pp = C["C7"], C["C7_with_DNg100"], PP["C7_per_pair"]["n_star"]
    L.append(f"| Animals needed for 0.8 (an extrapolation) | (an estimate, no verdict) | mean ratio {f(c7['rbar'])}; {f(c7['n_star'], 1)} animals, "
             f"about {c7['n_star_rounded_up']} ({f(c7['interval'][0], 1)} to {f(c7['interval'][1], 1)}; cell types resampled) | with DNg100 "
             f"{f(c7d['n_star'], 1)}; each pair alone (post hoc): MANC-BANC {f(pp['MB'], 1)}, MaleCNS-BANC {f(pp['CB'], 1)}, MANC-MaleCNS {f(pp['MC'], 1)} |")
    c8 = C["C8"]
    L.append(f"| Stability under count noise predicts BANC (12 types) | {c8['primary']['words']} | Spearman {f(c8['primary']['rho'])}; one-sided "
             f"permutation p {f(c8['primary']['p_one_sided_permutation'], 3)} | with DNg100 {f(c8['with_DNg100']['rho'])} (13 types); without DNb08 "
             f"{f(c8['without_DNb08']['rho'])}; the earlier count-of-networks measure {f(c8['stability_fraction']['rho'])}; partial given the MANC "
             f"score {f(c8['partial_given_B1r_score']['rho_partial'])}; disclosed in advance: {c8['disclosure']} |")
    L += ["", "**Departures from the run's instructions.** Each was written into the rulebook (`PREREG_v6.md`, Part D) before any BANC screen",
          "ran.", "",
          "1. The BANC table the authors' configuration names (same rows and match columns as the one the instructions named).",
          "2. The 139 front-leg motor neurons, the 12 neck motor neurons left out, as in the other animals.",
          "3. The left-right test uses types with a single BANC label on both sides, because BANC has no bilateral group annotation.",
          "4. The count-noise test uses the cross-half statistic, without a mirror network, which needs that annotation; BANC's resampled",
          "   networks have no threshold, as the authors' network has none.",
          "5. Exact (Clopper-Pearson) intervals for shares; resampling intervals for the overlap ratio and the graded version.",
          "6. Verdicts rest on the sets without DNg100; counts with DNg100 are reported beside them.",
          "7. The pooling verdict uses BANC as the only target, against each animal alone; the instructions' average over three targets is",
          "   positive by construction and is reported without a verdict.",
          "8. The stability test has 12 types, because 3 of the 16 earlier hits have no excitatory BANC group (and DNg100 is left out).",
          "9. The DNb08 check uses 2-s runs at every current, the authors' run length for that result.",
          "10. The DNb08 check reads out the 130 front-leg motor neurons of our MaleCNS screen.",
          "11. The original-procedure screens are the locked ones of rulebook v2.",
          "12. MANC's current sweep is the one stored from run 4, under no earlier lock, hashed by this rulebook's lock.",
          "13. A descriptive wiring check with a fixed caveat, because a broken build or type match would also give \"confirmed\".",
          "14. The same-name subset beside the high-confidence sets, without a verdict.",
          "15. DNg100's prediction is judged even if neither BANC procedure is valid.",
          "16. Campaigns were split into parts to respect the limit of 20 queued jobs; the analysis treats the parts as one campaign."]
    # S4 exam 1
    P = j("results/run2/P.json")["primary"]["result"]
    L += ["", "## S4. The literature tests in detail", "",
          "- **Second test (hemilineages; interpreted).** For each of 27 hemilineages with published activation phenotypes, the authors' model",
          "  of the whole nerve cord predicted which movements its activation should cause; the statistic is the percentile rank of the",
          "  hemilineage's own prediction among all 43 predictions, by fit to its observed movements. The eight wiring baselines, without fitted",
          "  parameters, score each leg's motor-neuron pool by the share of the pool inside the group (membership), by direct, two-step and",
          "  three-step synaptic paths from the group (each signed and unsigned), and by the steady state of the model's linearised form. The",
          "  best of them on these labels counted signed two-step paths. The comparisons with each baseline (post hoc) are in",
          "  `thirdfly_v1/POSTHOC_exam2_pairs.json`: the simulation is clearly above the membership, unsigned two-step, unsigned three-step",
          "  and linear baselines.",
          f"- **What it asked.** Whether the authors' whole-type score ranks types that drive rhythmic front-leg movement when switched on in flies "
          f"above types that do not. 39 labelled types ({P['n_pos']} yes, {P['n_neg']} no), labels frozen before scoring.",
          f"- **Verdict (locked).** Area under the curve {f(P['auroc'], 3)} ({f(P['boot']['lo'], 3)}-{f(P['boot']['hi'], 3)}): not better than chance "
          f"by the pre-registered rule. The best of the eight wiring baselines, picked on these labels, counted signed two-step paths "
          f"({f(P['baselines_auroc']['S2_twohop_signed'], 3)}). The eight baselines: direct synapses onto the front-leg motor neurons; signed "
          "and unsigned two-step path counts; total output synapses; number of output partners; synapses onto premotor neurons; number of neurons "
          "in the type; synapses onto the authors' circuit.",
          f"- **Why we do not interpret it.** All {er['census_39']['atlas_only']['n']} types whose labels rest on one optogenetic atlas of intact,",
          "  freely walking flies are \"yes\"; the \"no\" labels come from other kinds of experiment (takeoff, flight), and most were decided by the",
          "  consensus rule's tie-breaks between conflicting records, so a type's label is confounded with its source. Counting's higher value may",
          "  reflect neuron size. Both points are the first-round referee's findings, not locked analyses. The test also reads low scores as",
          "  predictions of no effect, which the authors explicitly do not do, and most labels describe intact flies, whereas the model is of the",
          "  nerve cord alone.",
          f"- **Audit.** Fresh readers re-read every source: {er['census_39']['all']['errors']} errors among the 39 types "
          f"({f(er['census_39']['all']['rate'] * 100, 1)} %), {er['census_39']['atlas_only']['errors']} among the {er['census_39']['atlas_only']['n']} atlas types and "
          f"{er['census_39']['other']['errors']} among the {er['census_39']['other']['n']} others (above the pre-registered 10 % if taken alone); overall below",
          "  10 %, so the test stands. An erratum corrected six types excluded because their outcomes were known (DNg100's label to yes).",
          f"- **Re-scored with audited labels (exploratory, once).** Simulation {f(rs['audited']['auroc'], 3)}; two-step counting "
          f"{f(rs['audited']['baselines_auroc']['S2_twohop_signed'], 3)}."]
    # S5 Part H
    L += ["", "## S5. The first two animals' hit lists by threshold (POST HOC)", "",
          "MANC-MaleCNS high-confidence types without DNg100 (214). k = hits in both; chance = expected k; p = hypergeometric; ratio = overlap",
          "relative to the within-animal overlap (95 % interval). \"Authors' screen vs ours\" compares the authors' whole-type screen of MANC",
          "with our MaleCNS screen.", "", "| procedure | threshold | MANC hits | MaleCNS hits | k | chance | p | ratio |",
          "|---|---|---|---|---|---|---|---|"]
    names = {"tuned_B1r_x_B2r": "current-setting", "authors_A1_x_B2r": "authors' screen vs ours", "original_K0_B1lo10_x_B2": "original",
             "sweep_dx1_x_ms": "current sweep"}
    for pair, lab in names.items():
        b = H["pairs"][pair]["high|without_DNg100"]
        for z in ("0.3", "0.4", "0.5", "0.6"):
            o = b["cuts"][z]["overlap"]
            p, bo = o["point"], o["bootstrap_95"]["OC_ratio"]
            pv = "<0.001" if p["hypergeom_p"] < 0.001 else f(p["hypergeom_p"], 3)
            L.append(f"| {lab} | {z} | {p['n_x']} | {p['n_y']} | {p['k']} | {f(p['chance_expectation'])} | {pv} | "
                     f"{f(p['OC_ratio'])} ({f(bo['lo'])}-{f(bo['hi'])}) |")
    L += ["", "With DNg100 (215 types), at 0.5: " + "; ".join(
        f"{names[pr]} {H['pairs'][pr]['high|with_DNg100']['cuts']['0.5']['overlap']['point']['k']} of "
        f"{H['pairs'][pr]['high|with_DNg100']['cuts']['0.5']['overlap']['point']['n_x']}" for pr in names) + ".",
          "", "Whole-ranking agreement (fraction of the ceiling, 214 types): " + "; ".join(
        f"{names[pr]} {f(H['pairs'][pr]['high|without_DNg100']['agreement']['primary']['ratio'])}" for pr in names) + " (post hoc).",
          "", f"Three-animal set (182 types with DNg100; `paper_posthoc_v1/`, post hoc): under the current sweep "
          f"{PP['sweep']['with_DNg100']['hit_in_at_least_one']} types are hits in at least one animal, "
          f"{PP['sweep']['with_DNg100']['hit_in_at_least_two']} in at least two and {PP['sweep']['with_DNg100']['hit_in_all_three']} in all three "
          f"({', '.join(PP['sweep']['with_DNg100']['all_three_types'])}); under the current-setting procedure "
          f"{PP['current_setting']['with_DNg100']['hit_in_at_least_one']}, {PP['current_setting']['with_DNg100']['hit_in_at_least_two']} and "
          f"{PP['current_setting']['with_DNg100']['hit_in_all_three']} ({', '.join(PP['current_setting']['with_DNg100']['all_three_types'])}). "
          f"Hits per animal under the sweep: MANC {PP['sweep']['with_DNg100']['hits_per_animal']['MANC']}, MaleCNS "
          f"{PP['sweep']['with_DNg100']['hits_per_animal']['MaleCNS']}, BANC {PP['sweep']['with_DNg100']['hits_per_animal']['BANC']}."]
    # S6 Part V
    V = C["V"]["V2"]["table"]
    pos = sorted(V, key=int)
    L += ["", "## S6. Single DNb08 neurons in our MaleCNS model (fixed currents, 2-s runs, 16 draws)", "",
          "Each cell: the share of the 16 draws with a score of at least 0.5, then the mean score. Copies 1-4 are the four DNb08 neurons at",
          f"positions {', '.join(pos)} of the network; copy 4 is the authors' neuron, and current 250 is the authors' configuration.", "",
          "| current | " + " | ".join(f"copy {i} ({p})" for i, p in enumerate(pos, 1)) + " |", "|---|" + "---|" * len(V)]
    curs = sorted({c for p_ in V.values() for c in p_}, key=float)
    for c in curs:
        L.append(f"| {c} | " + " | ".join(f"{f(V[p_][c]['frac_ge_0_5'])} (mean {f(V[p_][c]['mean'])})" if c in V[p_] else "-" for p_ in pos) + " |")
    L += ["", f"DNg100 at the authors' MaleCNS configuration: {C['V']['V1']['words']} (mean {f(C['V']['V1']['mean'], 3)}; theirs "
          f"{f(C['V']['V1']['authors']['mean'], 3)})."]
    # S7 forward list
    b1 = {x["manc_type"]: x for x in csv.DictReader(open(RESEARCH / "pertype_v1" / "B1r.csv"))}
    L += ["", "## S7. The twelve experiments, with the third animal's scores (readings unchanged)", "",
          "Groups: replicated or near-replicated between the first two animals; hits of a single connectome's screen (MANC, MaleCNS, or MANC",
          "and the authors' screen); controls that are stable non-hits but rank high in the two-step wiring count. Usable draws: draws with an",
          "accepted run in our MANC current-setting screen (of 16).", "",
          "| type | group | readings: replication / single connectome / counting | MANC usable draws | BANC score (current-setting) | "
          "BANC score (sweep) | BANC match |", "|---|---|---|---|---|---|---|"]
    for r_ in C["F"]:
        rd = f"{r_.get('replication_reading', '-')} / {r_.get('single_connectome_reading', '-')} / {r_.get('counting_reading', '-')}"
        nu = b1.get(r_["manc_type"], {}).get("n_usable", "-")
        nu = str(int(float(nu))) if nu not in ("-", "") else "-"
        L.append(f"| {r_['manc_type']} | {r_.get('group', r_.get('category', '-'))} | {rd} | {nu} | {f(r_['banc_tuned'])} | "
                 f"{f(r_['banc_sweep'])} | {r_['banc_match']} |")
    # S8 compute
    d1, d2 = j("gates_v6/DETERMINISM_v6_stage1.json"), j("gates_v6/DETERMINISM_v6_stage2.json")
    tg = j("gates_v6/TRUST_GATE_v6.json")
    L += ["", "## S8. Compute, determinism and review", "",
          f"- Trust gate: {tg['identical']} of {tg['n']} previously locked simulations reproduced exactly on GitHub Actions.",
          f"- Determinism re-runs: {d1['identical']} of {d1['n']} and {d2['identical']} of {d2['n']} identical.",
          "- The rules of this analysis were audited by a newly started agent session (14 findings, all applied) and re-checked by the same",
          "  session. A draft of this paper was reviewed by four newly started sessions (a hostile referee, numbers and references, a naive",
          "  reader, overclaim); the reviews and the answers to them are in `reviews_v6/`.",
          "- Post hoc numbers added after those reviews (the three-animal table, the per-pair arithmetic) are locked in",
          "  `LOCK_paper_posthoc_v1.json` (tag `ledger-paper-posthoc-v1`).", ""]
    (RESEARCH / "paper" / "SUPPLEMENT_v1.md").write_text("\n".join(L) + "\n")
    print("wrote SUPPLEMENT_v1.md", len(L), "lines")


if __name__ == "__main__":
    main()
