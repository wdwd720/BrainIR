# Driver-line availability (forward v2)

`AVAILABILITY.csv` covers the 78 lines of `LINES_TO_CHECK.csv`. For each line it records whether the collection that holds the line
lists it as available today, with the URL used, the date checked (2026-11-23) and a short note. A fresh agent did the lookups from
public pages only: no login, no account, nothing added to a cart, no order, no form, no contact. Every line was looked up again today,
including those already checked on 2026-11-22.

## Result

| Collection | Lines | `yes` | `no` | `not_found` | `lookup_failed` |
|---|---|---|---|---|---|
| FlyLight split-GAL4 (SS) | 69 | 52 | 17 | 0 | 0 |
| Janelia GAL4 at Bloomington (R) | 7 | 5 | 0 | 2 | 0 |
| Vienna Tiles at VDRC (VT) | 2 | 1 | 1 | 0 | 0 |
| **Total** | **78** | **58** | **18** | **2** | **0** |

- **SS `yes`.** 38 rest on a Bloomington stock and 14 on Janelia FlyBank's status alone.
- **R `not_found`.** R87B09 and R50D07: BDSC holds only their lexA lines and split halves.
- **VT.** VT057342 is `yes` (VDRC 205093). VT038873 is `no` (VDRC 208139, deceased).

**Re-check of 2026-11-22.** Sixteen of today's lines are also in `research/ledger/forward/AVAILABILITY.csv`: 14 SS lines, R29G08 and
VT038873. All 16 got the same verdict and the same deciding stock numbers today. VT038873's note also lists an AD hemidriver at BDSC,
#601150; the hemidriver does not affect its verdict.

## How it was checked (same procedure as `research/ledger/forward/AVAILABILITY_NOTE.md`)

**SS lines.** The FlyLight line page (`splitgal4_summary.cgi?_gsearch=Search&line=<SS>`, which redirects to the line's
`view_splitgal4_imagery.cgi` page) gives the robot ID and the AD and DBD halves. Its HTML does not state availability. The page's
FlyBank script (`cart.js`) posts the robot ID to `https://flybank.janelia.org/status/lines` and receives `{status, alt}`. The agent made
that same request for each line, anonymously and with no cookies. It never called the script's `/cart/*` endpoints. The replies took
only three forms:
- `available`, 14 lines: the page renders "Add to cart". Recorded as `yes`.
- `unavailable` with `alt` = Bloomington #N, 38 lines: the script's list view links "Order from Bloomington". BDSC's own record was read (search
  row plus stock details). The row is `yes` only if all of these hold:
  - the record is listed;
  - its comment names the SS line;
  - its genotype has the same AD and DBD enhancer fragments as the FlyLight page.
- `unavailable` with no `alt`, 17 lines: the script's list view shows "Out of Stock". Recorded as `no`. A BDSC search for the SS name found no stock
  naming any of these lines.

Every SS line got that BDSC name search. One line needed reading by hand. For SS02292, FlyBank still points to BDSC #75879, and BDSC
answers that number with "This may be because the stock is unavailable". The name search finds BDSC #93171, whose record names SS02292
and says "Validated replacement for BDSC stock 75879", and whose halves match. So SS02292 is `yes` via #93171.

**R lines.** BDSC searches for `GMR<id>` and `R<id>`. Only a `GMR<id>-GAL4` stock counts; lexA lines and AD/DBD hemidrivers do not.

**VT lines.**
- VDRC store (`shop.vbc.ac.at/vdrc_store`): the product page, and searches by VDRC ID, VT name and tile number.
- VDRC's VT lists `VT_current_stocks.xlsx` and `VT_discarded_stocks_20191023.xlsx`. Both files were last modified 2023-07-21.

**Calibration.** On each site a true miss looks like this:
- FlyLight: "`<line>` is not a valid line";
- BDSC: `Total 0`;
- FlyBank: `"status": "not found"`.

A failed request would have been recorded as `lookup_failed`; none occurred.

## Limits

- **Listed is not the same as shippable.** No order was placed. A BDSC `yes` means the stock is in BDSC's current catalogue search,
  which offers "Add To Cart" on every row. None of the matched rows carried a notice or DOA flag. A FlyBank `yes` rests on FlyBank's
  anonymous status alone, because ordering there needs an account; these 14 rows are the weakest. VT057342's VDRC page shows "Status
  available" and "Add to Cart"; prices need a sign-in.
- **Status is the anonymous view.** FlyBank's status and `alt` are what its public endpoint returns without a login. As SS02292 shows,
  the `alt` stock number can be stale, so the BDSC record decides.
- **Where the button labels come from.** On a single-line page the script renders only "Add to cart". "Order from Bloomington" and "Out
  of Stock" are its renderings of the same status reply in the collection's list view. The verdicts use the reply itself.
- **BDSC reads are the page's own reads.** BDSC stock URLs (`bdsc.indiana.edu/stocks/<N>`) redirect to its search page, which loads
  results through `POST /Home/GetSearchResults` and `/Home/GetDetails/<id>`. The agent made those same read requests.
- **VDRC relies partly on a 2023 file.** The two lists date from 2023; the store pages were read today. The store's search finds VT
  lines by VDRC ID or tile number but not by VT name, so a VT-name miss proves nothing. VT038873's `no` rests on three things:
  - the 208139 ID search finds nothing;
  - its product page returns 404;
  - the discarded list marks it deceased.
- **The AD/DBD match is by enhancer fragment.** For example, R26E02 or VT017411. Insertion sites and balancers were not compared.
