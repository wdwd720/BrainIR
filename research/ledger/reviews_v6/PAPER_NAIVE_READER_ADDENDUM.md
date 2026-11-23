# Addendum to the naive reader's review (PAPER_NAIVE_READER_REVIEW.md)

Written by the orchestrating session after the review was committed unchanged (7d85be3). Each decision was made before the revision and
recorded here first. The reader's "most confusing" items (10, 11, 3, 7, 12) shape the revision. Three things are new:

- a paragraph before Results 1, "How the screens work", which says how each screen sets its stimulus and names each procedure once;
- Table 1, which gives the status of every result: pre-registered in this analysis, pre-registered earlier, or post hoc;
- one word per concept throughout ("draws" for random repetitions, "hits" for scores of at least 0.5, "resampled networks" for
  count-noise copies, "copies" only for a neuron's left and right versions).

| # | Decision | Change |
|---|---|---|
| 1 | Accepted | Abstract: "a cell type's left and right copies agree at 0.63 of the screen's agreement with itself". The ceiling and the random draws are defined at first use in "How the screens work" and R1. |
| 2 | Accepted | The abstract no longer uses "current-setting procedure" or DNb08 without context. It says how the stimulus is set ("Hit-list overlap depends on how the stimulus current is set") and drops the "them" sentence. |
| 3 | Accepted | The abstract names the procedure behind each overlap (see the referee's objection 1). |
| 4 | Accepted | Abstract and R3: "agreement between animals was also below the ceiling in BANC", with the size and the caveat. |
| 5 | Accepted | The contrast with the authors' list leaves the abstract and the Discussion. R3 keeps it with the fixed power sentence. |
| 6 | Accepted | C8 leaves the abstract. R5 defines stability (the mean score over 16 MANC networks with resampled counts) and calls the result fragile. |
| 7 | Accepted | "How the screens work" defines the rhythm score: 0 to 1, high when the active motor neurons oscillate regularly; 0.5 is the authors' threshold for a hit. The Introduction says DNg100 is the authors' strongest driver, whose circuit they analysed; it is the positive control. |
| 8 | Accepted | <ul><li>"Copies" is now used only for a neuron's left and right versions (bilateral homologs), defined at first use.</li><li>Count-noise networks are "resampled networks".</li><li>The premise is stated: if a hit reflects what a cell type does, its two copies should score alike.</li><li>The "qualitatively similar" paragraph moves after the statement of what we test.</li></ul> |
| 9 | Accepted | "These results are the authors' ... and what we re-ran reproduces". FANC is introduced only as one of the authors' four datasets, which has no network of all descending neurons to screen. |
| 10 | Accepted (most confusing) | <ul><li>"How the screens work" comes before Results 1: the authors' automatic rule; our original procedure (a reimplementation of that rule); our current-setting procedure (one added requirement, chosen on DNg100); and the current sweep (fixed currents, no setting).</li><li>Every number names its procedure.</li><li>Fig. 3's "Tuned current" becomes "current-setting procedure".</li><li>DNb08's BANC score is given under both procedures.</li></ul> |
| 11 | Accepted | <ul><li>Table 1 gives each result's status.</li><li>R4 marks Part V as pre-registered (descriptive). R6 says when its tests were registered. R7 gives the forward list's real timing.</li><li>The Introduction now says "Every pre-registered test ...".</li></ul> |
| 12 | Accepted | "Our previous analysis" becomes "our earlier pre-registered analysis of the first two animals". The Methods say that the ledger's earlier rulebooks and results are in the repository, with their tags. |
| 13 | Accepted | <ul><li>R1 says what is random: the neuron parameters are drawn at random each run.</li><li>The Methods give the exact ratio (the mean cross-screen correlation of half-screens divided by the mean of the two self-agreements).</li><li>R1 notes that the median type scores 0 on each side, so the ratio rests on the types that respond.</li></ul> |
| 14 | Accepted | R2 explains resampling: each connection's count is redrawn from a Poisson distribution with the same mean. In BANC, with no threshold, this only removes weak connections; in MANC, with a threshold, it also creates them. MANC's 0.47 (paired design) is distinguished from 0.59 (one-sided screens). Jargon such as "paired draws" is removed from the main text. |
| 15 | Accepted | <ul><li>Table 1 lists the sets.</li><li>Each count names its set.</li><li>Values from different sets or procedures no longer sit side by side unlabelled.</li></ul> |
| 16 | Accepted | <ul><li>"Signed two-step path count" is defined in the Methods: the sum, over paths of two synapses from the type's neurons to the front-leg motor neurons, of the product of the two signed synapse counts. Direct connections are not included.</li><li>R3 names the BANC values and the threshold. "0.71" is explained.</li></ul> |
| 17 | Accepted | <ul><li>R3 says what "confirmed" means and what it does not: below the ceiling, not the size.</li><li>The Discussion no longer says that a type "disagrees more" across animals, since no test compared the two gaps.</li><li>The reversed ordering of wiring and screen agreement is stated plainly.</li></ul> |
| 18 | Accepted | <ul><li>R3 gives the recurrence rates and says that most hits do not recur.</li><li>The supplement defines the overlap ratio.</li><li>R3 says why the sweep calls more hits: it keeps the best of 19 currents.</li><li>The whole-ranking and hit-list results are no longer contrasted without numbers.</li></ul> |
| 19 | Accepted | "How the screens work" introduces the authors' whole-type screen (their Extended Data Fig. 1c). R3 explains 11 → 6 (matched with high confidence in BANC, DNg100 left out). S5's 5 is labelled (the MANC-MaleCNS set). |
| 20 | Accepted | <ul><li>R4 separates the two criteria for DNg100: its mean score (0.64, the prediction) and the share of draws (11 of 16, the validity bar).</li><li>The calibration sentence is corrected.</li><li>The 2-s runs of the DNb08 check are explained, and the cause is no longer asserted.</li><li>"The bar" is defined (at least 8 of 16 draws at 0.5).</li><li>The four three-animal types are labelled post hoc.</li></ul> |
| 21 | Accepted | <ul><li>R5 explains the graded versions (a mean score instead of a yes/no count) and the 12 types (hits of our MANC screen or the authors' list with a BANC match, DNg100 left out).</li><li>It calls the partial correlation secondary, without an interval, and says "about 7 animals in total".</li></ul> |
| 22 | Accepted | R6 gives three sentences on the design: the authors' full nerve-cord model; each hemilineage's neurons switched on; the predicted pattern of movements compared with the published phenotypes; the rank of the right hemilineage among all predictions. The baselines are named in S4. "Blind" becomes "labels frozen before the predictions were scored". The erratum sentence moves to the supplement. |
| 23 | Accepted | R7 says the three readings are predictions, and how a headless fly would be scored (rhythmic front-leg stepping, scored blind to genotype). It notes that only DNa13 and DNg13 are BANC hits. |
| 24 | Accepted | "BANC's names appear to come from the same ID match, so the 'no conflict' check cannot fail there." |
| 25 | Accepted in part | <ul><li>The Methods give the units (arbitrary current units, as the authors'), "active" (above a rate threshold, as the authors define it), the size scaling, the handling of draws without an accepted run, and that the sweep's best score is taken per draw.</li><li>Methods and Limitations state that the bounds, start current and run limit are fixed choices copied from the authors, not tuned.</li></ul> |
| 26 | Accepted | <ul><li>The main text drops "prediction ledger", "word-bearing set", "campaign", "trust gate", "isolated rooms" and "which test carries which words".</li><li>"Pre-registered words" becomes "the verdict fixed in advance".</li><li>The Methods say "a re-run of earlier simulations that must match exactly".</li></ul> |
| 27 | Accepted | Fig. 1 adds lines at 0.5, counts the types at (0, 0), and gives the ceiling in the caption. |
| 28 | Accepted | Fig. 2 is redrawn in three panels (see numbers review P14), each bar naming its procedure. |
| 29 | Accepted | Fig. 3 renames the procedure, adds the authors' list, and separates the chance lines by style. Intervals at 0.5 are in S3. |
| 30 | Accepted | Fig. 4 prints each score, marks hits, and states a take-home in its title. |
| 31 | Accepted | <ul><li>Fig. 5 shows the ranks (the statistic is a rank correlation) and names all 12 types.</li><li>The caption says the 12 types include matches of any confidence, which is why DNxl102 (a medium-confidence match) is not in Fig. 4.</li></ul> |
| 32 | Accepted in part | Fig. 6 labels the copies "copy 1-4" (positions in the supplement) and uses "draws". The current that our procedure accepted varies from draw to draw and is not marked. The caption says that our procedure starts at 128 and accepts the first current at which activity is within bounds. |
| 33 | Accepted | <ul><li>S1's third column stays, for readers of the repository, under the heading "name in the repository's files".</li><li>The main text uses one word per concept (above).</li><li>S1 gains a short glossary.</li></ul> |
| 34 | Accepted | <ul><li>S2 defines E1, E2 and I2. S3 defines AUROC, d_M and d_C, and prints no raw JSON.</li><li>S3 explains "16-replicate halves".</li><li>S6 explains "0.12 (mean 0.14)". S7 explains its group names.</li></ul> |
| 35 | Accepted | S3's departure list says, item by item, what each departure is and that each was fixed before the BANC data were seen. |
| 36 | Partly accepted | <ul><li>The title options move into a comment in the source, invisible in the built files.</li><li>The hand-check line stays, because the author must fill it. The build refuses final files until then.</li></ul> |

**What the reader took away** matches what we intended, with one exception. "Only DNg100, DNa13 and DNxl092 are hits in all three
animals" was our error: it is four types, with DNxl134 (numbers review P1). The reader's question, whether the lesson concerns such
screens in general or our procedure, is now answered in the Discussion. Part of the answer depends on the procedure, and we say which
part.
