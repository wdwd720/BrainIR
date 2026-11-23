# Notes on the short list (forward ledger v2; orchestrator's notes, not labels)

From `SHORTLIST_LINES.csv` (kit v2's line records; availability checked 2026-11-23 from public catalogue pages):

- **DNp41:** both available lines name another DN type: SS67050 also labels **DNg100**, a known walking driver, so a "yes" with it would
  not separate DNp41 from DNg100; SS82242 also labels DNp51. A clean DNp41 line would make this test decisive.
- **DNa03:** its one available line (SS01592) names six other DN types (DNa06, DNa09, DNp18, DNp19, DNp20, DNp22).
- **DNp02:** 10 available lines, 2 of them clean (SS01053, SS01554).
- **DNp71:** SS90829 is clean; SS81847 also names DNp103.
- **DNa13, DNa07, DNg63, DNg13, DNg21, DNp07, DNg39, DNp26:** at least one clean available line each.
- The 14 split lines that are "available" only through Janelia FlyBank (not a Bloomington stock) are the weakest "yes" rows
  (`AVAILABILITY_NOTE.md`); ordering needs an account and was not tried.
- **Lines not looked up.** Availability was checked for every hit candidate's lines and for the lines of the seven stable non-drivers
  with the highest two-step counting scores (S2 down to 574). For the other stable non-drivers, "no line listed as available" in
  `CANDIDATES_WHY.csv` means "not looked up": they rank below every checked control by counting score, and controls are taken by that
  score among types with an available line, so none of them could have entered the list.
