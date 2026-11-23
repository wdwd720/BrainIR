# Addendum to the hostile-referee review

The review (`PAPER_REFEREE_REVIEW.md`, 18 objections, 15 tested; scripts in `referee_tests/`) is unchanged. Responses, objection by
objection; "accepted" means the paper now says it. Numbers from the referee's tests are not locked, so the paper cites them only in words,
marked "not locked".

| # | Objection | Response |
|---|---|---|
| 1 | Exam 1's classes come from different kinds of experiment | **Accepted.** The abstract, Results 6, the Discussion and the Limitations now say that exam 1's labels are confounded with their sources (all 21 atlas-only types are "yes"; most labels from intact flies; most "no" labels from takeoff or flight experiments, a reviewer's finding, not locked) and that the exam cannot rank the model against counting firmly. The pre-registered verdict (not better than chance) stands as locked. |
| 2 | Counting's lead is a size effect | **Accepted in substance:** the paper no longer leans on counting's lead in exam 1, only on the pre-registered comparison ("no better than"), and says the labels are too confounded to rank the methods. The size analysis itself is the referee's (not locked) and is not quoted. |
| 3 | The draft tests a use the authors disclaimed and restates their own practice | **Accepted.** The Introduction says the authors present the screen as a discovery tool; Results 3 and the Discussion say the authors chose DNg100 and DNb08 to test, that our results support that choice, and that our recommended practices are ones their choice already follows. |
| 4 | The MaleCNS screen was calibrated on DNg100, so its replication is built in | **Accepted (major).** The abstract, Results 3, the Discussion and the Limitations now say DNg100's replication is guaranteed by our calibration (rulebook v2: the tuner's one setting chosen to make DNg100 a driver in both connectomes; under the original procedure DNg100 scored 0.059 in MaleCNS), that DNb08 is the informative case named in advance, and that DNit013 joins only under the calibrated procedure. |
| 5 | The audit "upheld" exam 1 mainly by re-running the same procedure | **Accepted.** Results 6 and the Limitations give the split: 0 of 21 atlas types (re-coded with exam 1's procedure) and 3 of 18 types read from papers. The consequence rule was pre-registered on the overall rate and is applied as written. |
| 6 | "Barely overlap" is a property of the 0.5 cut | **Accepted in part.** The thresholds are post hoc and were not varied; Results 2 says so and that the overlap rises at lower thresholds (a reviewer's finding, not locked). The half-screen comparison and the authors' own list are kept as checks at the same cut. |
| 7 | Exam 2: the model beat seven of eight baselines | **Accepted.** Results 6 says it scored above seven of eight baselines but no better than the best, which was picked on the same labels. |
| 8 | The title blames the connectome | **Accepted.** New title: "How far can a simulation of one connectome be trusted?" |
| 9 | DNit013's match was not rated "before looking" | **Accepted.** "a rule written after the replication pattern was known". |
| 10 | Left and right copies are two neurons; the ceiling assumes one | **Answered, not changed.** The ceiling is each screen's agreement with itself across replicates; the ratio asks how much of that reproducible variation the two copies share. The paper states the premise conditionally ("if the screen captures function shared by ... left and right copies"). |
| 11 | The 51 % is mostly the 5-synapse floor | **Accepted.** "pass the 5-synapse floor on one side only; two thirds of these have 1-4 synapses on the other side". |
| 12 | "Reproduces their published dynamics" needs a qualification | **Accepted.** The paper adds that our MANC screen shares 10 of the authors' 11 hits and adds 5. |
| 13 | Poisson resampling with the floor re-applied is a structural perturbation | **Accepted in words.** Results 4 says only that noise of this size can produce the gap; the Methods state that the floor is re-applied after resampling. |
| 14 | Part S takes abstract space while graded sensitivities point the other way | **Not changed.** The run prompt requires Part S in the abstract whatever it shows; the sensitivities were pre-specified without words and are reported as such. |
| 15 | The readers are language models of one family; the blind is procedural | **Already in the Limitations**; kept. |
| 16 | Read-outs differ | **Accepted.** The Limitations say which screens read one side and that the flies' front-leg motor-neuron sets differ (144 and 130). |
| 17 | "Your reimplementation is not our screen" | Refuted by the referee's own test (10 of 11 hits); now in the paper. |
| 18 | Matching, member counts, rarely accepted replicates, unequal list sizes | Refuted by the referee's own tests; the paper uses the size-robust overlap coefficient. |

**What survives**, in the referee's words and the paper's: the left-right gap in the authors' own screen, the reimplementation's
agreement with the authors in MANC, the chance-level overlap of the two flies' hit lists at the 0.5 cut, the count-noise result, and
wiring summaries replicating where simulated hits do not.
