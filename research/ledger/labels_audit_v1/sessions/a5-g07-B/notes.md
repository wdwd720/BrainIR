# Session a5-g07-B — label audit (run 5), notes

Assigned types: DNa04, DNa05, DNa15, DNg100, DNg13, DNp01, DNp02, DNp03, DNp04, DNp06,
DNp07, DNp10, DNp11, DNp26, MDN.
Assigned sources: 3 (all present and readable in the room).

## What I read

- `10.1016/j.cub.2025.11.035` (Croke et al., DNp03 saccade hub): whole `text.txt` including
  STAR Methods, genotype table, figure legends and key resources table. The room has no
  `figures/`, `supp/` or `pages/` for this source (the folder manifest lists 0 images, 0 supp
  files, 0 page images), so I could only use the legends embedded in `text.txt`. The legends
  are complete enough to see what each activation panel measures.
- `10.1016/j.cub.2026.09.056` (Cao & Anderson, threat display): whole `text.txt` including
  STAR Methods and reference list. Again no figures/supp/pages in the room.
- `10.7554/elife.38554` (Carreira-Rosario et al., MDN): whole `text.txt` plus the Figure 8
  image (`figures/elife-38554-fig8.jpg`) to confirm panels 8D and 8H are adult backward-walking
  probability plots.

## Decisions

**DNp03 paper — no record.** DNp03 *is* activated optogenetically in adult flies, in three
preparations: unilateral stochastic CsChrimson in tethered flight (Fig. 4), bilateral CsChrimson
in tethered flight (Fig. 6B–D) and bilateral CsChrimson in free flight (Fig. 6E–M). But in every
case the measured and reported variables are wing beat amplitude / wing stroke amplitude, head
yaw, and body pitch/roll/yaw. The legs are never described under activation. The only leg
observation in the paper (leg extension, Fig. 7G–J) comes from *looming-stimulus* trials in
control and Kir2.1-silenced flies — a silencing experiment with a visual stimulus, not an
activation experiment. PROTOCOL section 3 says wing/flight behaviours give `not_assessed` legs
"unless the legs are described"; here they are not described at all under activation, and the
task says to write a record only for experiments that activate the type *and* report what the
legs do. Hence `no_qualifying_experiment`.

Note also: the T1 legs were amputated at the femur for the electrophysiology preparation only
(not the behaviour assays), which is another reason not to read anything about legs into the
flight data.

**Cao & Anderson — no record.** The activation targets are AIP (CL062), DNpe050, DNp60, AVLP491
and AVLP710m. None is an assigned type. AVLP491 activation produces increased forward and angular
locomotion (a leg result), but AVLP491 is an interneuron, not a DN, and is not an assigned type.
DNg100 is named once, as a connectome-level common downstream target of AVLP491 and AVLP710m
(Fig. S6H) — there is no activation of DNg100 in this paper, so no record.

**MDN paper — 2 records.** The paper is mostly larval, and larval experiments are excluded by
PROTOCOL section 1. Two adult experiments qualify:
1. Fig. 8C–F: Split3 (ss01613) ∩ VT044845-lexA drives ReaChR:citrine in the cells that were larval
   MDNs; 8/10 adults walked backward under 0.28 mW/mm², 617/red light in an agar ring arena.
2. Fig. 8G–I: RU486-induced FLP immortalisation of Split1 (R49F02-AD/R53F07-DBD) expression,
   giving lexAop-CsChrimson:mVenus in adult MDNs; all 20 adults walked backward under 617 nm,
   ~4.6 µW/mm² in a serological pipette.

Both are coded `backward_walking` with `yes` for all three leg pairs (PROTOCOL section 3,
"Walking, forward or backward: yes for all three leg pairs"). `labeler_confidence` is `medium`
for both: backward walking was scored by eye as a probability, with no leg tracking or stepping
quantification, and both lines carry a few unnamed off-target neurons (Fig. 8F green arbor;
Fig. 8I four blue-shaded neurons), so `line_specificity` = `minor_offtarget`.

For record 2 the penetrance is conditional: the adults assayed were pre-selected as larvae that
had crawled backward, so "20/20" is not an unconditional penetrance. That is stated in the record
notes.

`effect_on_walking`: the vocabulary (`stops`, `slows`, `speeds`, `turns`, `none`, `not_assessed`)
has no term for a reversal of walking direction, which is what MDN activation produces. I used
`not_assessed` for both records rather than force-fitting `turns`, and said so in the record notes.

## Mapping

`MDN` is a MANC type in `type_list.csv` (other name DNp50) and in `synonyms.csv`
(MDN → DNp50, literature, Carreira-Rosario 2018), so `mapping_confidence` = `high` for both
records. The paper itself identifies the adult cells as the moonwalker neurons of Bidaye et al.
2014 by morphology (Fig. 8E, F), which is the same identification the kit uses.

The two driver lines used in the adult MDN experiments (`ss01613` with `VT044845-lexA`, and
`R49F02-AD`/`R53F07-DBD`) are not listed in `driver_lines.csv`, which has MDN-1, MDN-2, SS03131
and a VT044845/VT050660 hemidriver pair. I did not add proposed driver-line rows: the Split lines
here were raised against *larval* MDN and carry off-targets, and the type assignment in my records
rests on the paper's own adult morphological match rather than on the line identity. So
`out/proposed_synonyms.csv` and `out/proposed_driver_lines.csv` were not written.

## Simulation scores

I saw no rhythm score, rank or driver/non-driver call from a connectome activation screen in any
of the three sources. `saw_simulation_score` is `false` on both records, and no
`out/sightings.csv` was written. (The DNp03 paper makes connectome-based *predictions* about
wing motor neurons, e.g. "we predict b3MN and i1MN decrease the contralateral WBA", but that is
the paper's own anatomical reasoning, not a simulation score, and it concerns wings, not legs.)

## Not accessible

Nothing was unreachable. The two Current Biology sources have no figure images, supplementary
files or page images in the room — only `text.txt` and `fulltext.xml`. For both, the embedded
figure legends were detailed enough to determine what was measured, so this did not change either
disposition; but if a later pass wants to check the DNp03 free-flight videos (Videos S1–S8, none
downloaded) for incidental leg movement, those are missing here.
