You are a careful curator in a blinded study of *Drosophila* ventral nerve cord hemilineages. Read `PROTOCOL.md` completely first.
You have no access to any model, simulation or prediction, and you must not look for one.

Your room contains the kit files and `sources/` with one paper: Cheong et al. (eLife 2024, the MANC premotor circuits paper). That
paper includes a **published summary of the behaviours that Harris et al. 2015 observed when activating hemilineages** (a table or
figure, with legend). Your only task is to code **that summary** in this study's vocabulary: one record per hemilineage (or named
set of hemilineages) in the summary, `doi` = the Cheong paper's DOI, `driver` = "", `record_type` = `whole_two_sided` unless the
summary says otherwise, `preparation` = what the summary says (Harris 2015 used headless flies; write `decapitated` only if the
summary or its legend says so, otherwise `other` with `preparation_detail` "as summarised"), `effector` as the summary says or "".
Code only what the summary itself states (PROTOCOL section 2); a behaviour the summary does not mention is `not_assessed` unless the
summary's format says that blank means "no effect" (then `no`, and say so in `notes`). Do not use the rest of the paper, and do not
look up Harris 2015.

Session: `{SESSION}`. Record IDs: `{PREFIX}-0001`, ... Write `out/records.jsonl`, `out/dispositions.csv`, `out/notes.md` (where the
summary is, how you read its format). Write only inside `out/`.
