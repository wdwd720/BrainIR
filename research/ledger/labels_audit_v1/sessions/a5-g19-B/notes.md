# Session a5-g19-B notes (audit, run 5)

Assigned types: DNfl028, DNg12, DNp01 (GF), MDN. Four assigned sources.

## Fetching
- Allowed to fetch 10.1038/nn.3741 and 10.1126/science.1249964. Europe PMC REST search: both have inPMC=N, isOpenAccess=N, full text "Subscription required".
- science.org/doi/10.1126/science.1249964 returned HTTP 403. nature.com/articles/nn.3741 redirected to the idp.nature.com login; I did not follow it. No bioRxiv version was tried because none is expected for these 2014 papers, and I searched for nothing beyond the assigned DOIs.

## Per source
- 10.1371/journal.pbio.3003553 (full text, all figure legends, Fig 4 image checked): one record, GF CsChrimson activation, free flies, escape jump (single movement, so leg rhythm 'no'). Results say 50 ms flash; Methods say 2 s 594 nm pulses. Sex coded male from the Methods wording, which is slightly ambiguous. Electrical GF stimulation (SLR/LLR EMG) is excluded because it is not opto/thermogenetic and gives no leg-movement read-out. Proposed driver-line row for the GF split (17A04-AD;68A06-DBD).
- 10.7554/elife.106446 (full text): DNg12 appears only in the Discussion as connectome input to 13A neurons. No activation of any assigned type. no_qualifying_experiment.
- 10.1126/science.1249964 (abstract only): one record, low confidence. The abstract gives no effector, line, stimulus or preparation. **effector_kind 'thermogenetic' is a schema-forced placeholder that no text I read supports**, and preparation is 'other'. Please re-code from full text if possible.
- 10.1038/nn.3741 (abstract only): the abstract describes GF intracellular recording and a model, with no activation experiment. Marked unreachable because the full text could not be read, so the absence of a qualifying experiment is unconfirmed.

## Simulation scores
I saw no Pugliese-type rhythm score, rank or driver call. The eLife paper has its own model of 13A circuits, and that does not count. saw_simulation_score is false on all records.
