# a5-adj-01 adjudication notes

Source: Braun et al. 2024, Nature, 10.1038/s41586-024-07523-9 (only assigned source). Read: text.txt (results, ED Fig. 4-8
legends, Methods: optogenetics, headless experiments, data exclusion, fly husbandry), Extended Data Fig. 5 image,
Supplementary Information (MOESM1: video legends, Supplementary Table 2 split lines, Supplementary Table 5 P values,
Supplementary Discussion), peer review file (MOESM3) passages on DNa01, Supplementary Table MOESM4 sheets mentioning DNa01.
The paper has no Pugliese-type simulation score, rank or driver call; its connectome analysis is DN-DN connectivity
counts, not a simulation. saw_simulation_score = false. No sightings.

## DNa01 (SS00731)

Experiments found: two (Extended Data Fig. 5c), same as both readers. No other DNa01 activation experiment exists in
the paper (DNa01 is otherwise mentioned only in connectivity analyses and the Discussion).

**Intact, tethered on ball (record 0001).** Readers agreed: turning, legs unclear. I agree. The paper reports only turn
velocity (~400 deg/s, "in place turning"). Pre-stimulus state was not restricted, and legs were not tracked or described,
so per-pair rhythm cannot be read. effect_on_walking = turns.

**Headless, on ball (record 0002). This is where the readers disagreed.** Reader A coded all legs `no` (low confidence) and
effect_on_walking `none`. Reader B coded `unclear` and `not_assessed`. Finding: only turn and side velocity are
quantified (no different from headless controls, P = 0.206 / 0.392). Forward velocity is not plotted for DNa01. Text,
legend and Supplementary Discussion only say that turning is lost. They never say the legs were still, and headless flies
were kept only if their legs moved spontaneously. Absence of turning is not evidence that the legs had no rhythm, so I
side with B: `unclear` for all three pairs. A's `no` goes further than the source. behaviour_category
`no_visible_effect` refers only to the measured ball parameters.

Also differing from both readers: `line_specificity` is `unknown` rather than `clean`, because this paper says nothing
about SS00731 specificity (the kit's Namiki 2018 row reports ~5 unnamed background off-target types). `expression` is
`unknown` because it is not stated.

Not recorded: Supplementary Video 4 Part 3 shows DNa01 headless flies hanging without ground contact. Videos were not
downloaded (meta.json "skipped") and no text, figure or table reports that condition. A session with the videos could
check whether rhythmic leg movement appears there.

Mapping uncertainty: the paper's FAFB equivalence sheet (MOESM4, "Equivalence DN names and rootid") lists four "DNa01"
neurons. Two have FlyWire cell type DNa01, and two have hemibrain type DNa01 with FlyWire type DNae003, which the kit's
type_list maps to DNxn123, not to DNxl022 (= DNae001). This is about the connectome neurons drawn in ED Fig. 5c, not the
driver line. I kept the kit's preferred mapping for SS00731 (DNa01, medium) and proposed no new synonym.

Files not written: sources.csv (PROTOCOL section 7) is not in this audit's required outputs.
