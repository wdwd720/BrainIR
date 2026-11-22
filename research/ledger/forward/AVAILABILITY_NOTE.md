# Driver-line availability (PREREG v4 E6)

`AVAILABILITY.csv`: for each of the 59 driver lines of the 15 decisive types (`DECISIVE.csv`), whether the collection named by the line
lists it as available, with the URL and the date checked (2026-11-22). Looked up by a fresh agent from public catalogue pages only (no
logins, no orders): 34 listed as available, 24 not, 1 not found (R77F05: no GMR77F05-GAL4 at Bloomington, only the LexA line and split
halves).

How it was checked, and its limits (the agent's account): the FlyLight split-GAL4 pages do not state availability in their HTML; a script
on the page asks Janelia FlyBank for each line's status and shows "Order from Bloomington" (with a Bloomington stock number), "Add to
cart" (FlyBank) or "Out of Stock". The agent made the same status request without logging in and checked every Bloomington stock number
against Bloomington's own record (each names the SS line and matching AD/DBD halves). The ten "yes" rows that rest on FlyBank's status
alone ("Add to cart"; ordering needs an account and was not tried) are the weakest. GMR lines were checked by Bloomington's search
(only a GMR<id>-GAL4 match counted). The three VT lines are listed as deceased in VDRC's list of discarded VT stocks (discarded
2017-09-30); DBD hemidrivers of them exist at Bloomington.
