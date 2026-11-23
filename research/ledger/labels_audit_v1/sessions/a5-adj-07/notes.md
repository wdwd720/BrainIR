# a5-adj-07 audit notes

## Source read
- 10.1371/journal.pone.0267834 (Luo et al. 2022, PLoS ONE): read the full text in `text.txt`, Fig 3 (image), Table 1 and the
  supplement text files (camera mount, circuit diagram, materials list and Arduino code, none of which are behavioural). S1/S2 Movies
  were not downloaded. They were not needed because the result is stated in the text and Fig 3. The paper reports no simulations or model
  scores, so I saw no simulation score.

## DNp09
- **Experiment:** SS1540-split-Gal4 (= SS01540) > CsChrimson, 300 ms 627 nm light, flies tethered with no tarsal contact. About 62% of
  retinal-fed flies (n = 80) froze, compared with about 20% of non-retinal-fed flies (n = 79) and 0% of wild-type controls. Freezing is a
  complete stop of appendage movement during and after the light. Under PROTOCOL section 3 (stopping or freezing) all three leg-rhythm
  fields are `no`, with `behaviour_category` = `halting` and `effect_on_walking` = `stops`.
- **Where the readers agreed:** both readers wrote this single record with `no` for all leg pairs, `halting`/`stops`,
  `intact_tethered`, DNp09 mapped at medium confidence, and n = 80. I agree: the source shows no rhythmic leg movement. Leg movement
  (grooming or struggling) came *before* stimulation and stopped when the light came on. The authors say outright that they did not see
  the increase in locomotion reported for DNp09, and they attribute this to tethering without tarsal contact.
- **Where the readers differed:**
  - `line_specificity`: A put `minor_offtarget` and B put `multi_dn`. I chose **`minor_offtarget`**. The paper refers only to
    "other labeled neurons in SS1540-split-Gal4" and does not name or identify any other DN type. `multi_dn` would require other DN
    types to be named.
  - `expression`: A put `unknown` and B put `bilateral`. I chose **`bilateral`**. The paper describes the line's DN as "a bilateral
    pair of descending neurons, called DNp09", and nothing in it suggests unilateral or stochastic expression.
  - Wording only: the quote length, how the stimulation is described and the penetrance text. None of these changes the content.
- **Workshop:** high-school students also stimulated SS1540 flies in the same tethered preparation. The paper says only that freezing
  was "easily detected" and gives no separate data, so I folded this into the one record instead of writing a duplicate.
- **Caveat:** the authors suggest the freezing may come from non-DNp09 neurons in the line, which is why confidence is `medium`.
  Scoring was by eye and not blinded.

## No proposed synonyms or driver lines.
