# Forensic task: DNg100's exam 1 label (label audit, BrainIR prediction ledger run 5)

You are a reader in a fresh session. This folder (your room) is all you may use; you have no shell, and no web unless the end of this task says otherwise.

**Background.** An earlier blind label collection (exam 1) recorded the descending-neuron type **DNg100** (also called BDN2) as "no" for
rhythmic front-leg stepping, best preparation **headless**, from 5 eligible records. Establish what the sources here report about
DNg100 activation and why the label came out as it did. The earlier collection's records of DNg100 are in `exam1_records_DNg100.jsonl`
(every field). How a type's label was made is in `CONSENSUS_RULE.md`, and the code that applies that rule is `aggregate.py.txt`; which
records were set aside, and why, is in `BLIND_RULE.md`. The sources are in `sources/<slug>/` (full text in `text.txt`, page images in
`pages/`, figures in `figures/`, supplements in `supp/`), listed in `assigned_sources.csv`; they include papers that report simulations,
which the earlier collection set aside.

**Your task.** Write `out/forensic.md` with:
1. The records behind the "no" (the eligible records at the best preparation), each with its source, locator and quote, and whether you
   agree with the recorded front-leg value after reading the source yourself.
2. Every source here that describes DNg100 activation in **headless** flies, with what it reports for the front legs (quotes, locators),
   and separately what sources report in intact flies.
3. The explanation of the label, as one or more of: (a) a mapping error (records of another neuron mapped to DNg100, or the reverse);
   (b) the consensus rule (how the rule combined the records); (c) sources set aside by the blind rule; (d) a correct reading of a narrower
   experiment (for example, a different stimulation, readout or leg); (e) other. Give the evidence for each part.
4. What a correct label for DNg100's front legs in headless flies would be, given every source here, and how sure you are.

Also write `out/explanations.csv` with the header `explanation,chosen` and exactly five rows, `a` to `e` (the explanations of point 3),
`chosen` being `yes` or `no`. Also write `out/records_reviewed.csv` with the header `record_id,doi,source_locator,recorded_front_leg,your_front_leg,agree,comment`, one
row per exam 1 record of DNg100. Cite only what the files say; never use your own memory of what a neuron does as evidence. Your session name is `{SESSION}`.
When done, write `out/DONE` (empty) and stop.
