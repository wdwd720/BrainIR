# Session a5-g19-A notes (audit, run 5)

Assigned types: DNfl028, DNg12, DNp01 (GF), MDN (DNp50).

## Sources
- **10.1371/journal.pbio.3003553** (Gaitanidis et al. 2025): I read the full text and Fig 4 image. 1 record: GF split-GAL4 (17A04-AD; 68A06-DBD) > CsChrimson in freely moving flies triggers escape (jump followed by flight). Under PROTOCOL section 3 a jump is a single movement, so all leg-rhythm fields are `no`. Electrical GF stimulation (SLR/LLR, TTM/DLM recordings) is not opto/thermogenetic activation and was not coded. LC4/LPLC2 activation is not DN activation. Uncertainties:
  - Stimulus: Results say a 50 ms flash; Methods say 2 s pulses.
  - Fig 4B: the legend gives n = 33, but the figure shows (23).
  - Sex: probably male. Methods say male flies were removed for testing.
  - The driver line was not in driver_lines.csv, so I proposed it in `proposed_driver_lines.csv`.
- **10.7554/elife.106446** (Syed et al. 2026): full text read. DNg12 appears only as a connectome partner of 13A neurons. No DN activation, so `no_qualifying_experiment`.
- **10.1038/nn.3741** (von Reyn et al. 2014): the cached copy is abstract only. Europe PMC REST shows inPMC = N and a subscription. The Nature article page (reached after its idp redirect) showed only a preview. That preview indicates GF CsChrimson activation experiments (Fig 2 title "The GFs are necessary and sufficient for eliciting short-mode escapes"; Supplementary Video 3 caption), but legends and methods are not visible. I gave it `unreachable` and wrote no record.
- **10.1126/science.1249964** (Bidaye et al. 2014): the cached copy is abstract only. Europe PMC shows no PMC copy, and science.org returned 403 (/doi/ and /doi/full/). The abstract says MDN activity "is sufficient to trigger backward walking under conditions in which flies would otherwise walk forward". It names no effector, line or preparation, and the required `effector_kind` cannot be filled from the source without using memory. So I gave it `unreachable` and wrote no record. A session with access should code it.

No simulation scores were seen for any assigned type.
