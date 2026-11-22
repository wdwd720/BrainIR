Verdict: the headline survives with qualification: the reported 0.40 against 0.37 is the second-lowest of the six copy pairings that the four stored noise copies allow (0.38-0.54, mean 0.46, every one above 0.37), so Poisson count noise reproduces most of the left-right gap (about 86 %, 66-114 %) but not demonstrably all of it, and "agree no better than" should read "agree almost as poorly as".

# Adversarial review of RESULTS_3's headline (count noise, run 4)

Fresh reviewer, read-only. Read: `results/RESULTS_3.md` (commit 6f19b7f, unchanged at 52f99e6), `PREREG_v4.md` (G6-G10, B2-B4),
`reliability_v2/NOISE.json`, `B1_MANC.json`, `B2_MANC.json`, `B3_MANC.json`, `WIRING_A4.json`, `gates_v4/NB_DISPERSION.json`,
`gates_v4/DETERMINISM_stage3.json`, LOG L104-L151, and the code (`reliability_v2_bc.py` `_noise` / `_diff_interval`, `gha4.py`
`build_cn`, `fixes.py` `manc_raw_counts` / `poisson_copy` / `nb_copy` / `nb_inverse_k`). Every number below is recomputed from the
stored per-job results (`gha4.load_results` of `cn-run4`, `b2-manc-run4`, `b3-manc-run4`, `fl-1-run4`) or from wiring. Nothing was
simulated. My recomputation reproduces NOISE.json exactly (L vs R 0.372; Poisson 0.400; NB 0.448; copy 1 vs L on W 0.544; observed
minus Poisson -0.029, -0.162 to +0.102).

## 1. The strongest objection

The first line's equality ("two copies ... agree no better than the fly's left and right sides, 0.40 against 0.37") rests on one
pair of Poisson copies, P1 and P2. Its interval (-0.16 to +0.10) comes from a bootstrap over types that holds both copies fixed, so
it carries no between-copy (realisation) variance. A second pair drawn the same way could land anywhere in the real spread of
copy-to-copy agreement. If P1-P2 is a low draw, the true statement is "count noise reproduces most of the gap", not "all of it", and
the near-identity of 0.40 and 0.37 is partly luck. The spread can be measured without simulation. The run holds four independent noise
copies of the same network: P1 and P2 (Poisson) and N1 and N2 (negative binomial). All four were screened with the same seeds, paired
draws, types, runner and platform. The negative binomial differs from Poisson only on strong connections (1/k = 0.027: a count of 5 has
variance 5.7 instead of 5), so all six pairings among the four copies measure the same quantity.

## 2. The test and its exact result

All six copy pairs, each with its G6 cross-half rho_x and ceiling c. Observed (L on W vs R on W, paired design) minus the mean over
pairs. The share of the left-right gap that count noise reproduces, (c_model - rho_model) / (c_obs - rho_obs). All on one bootstrap
over the 261 primary types (10,000 resamples, `default_rng(20261401)`, as `_diff_interval`). **Exploratory, post hoc:** B4.2 fixes
P1-P2 and B4.3 fixes N1-N2. The four cross-model pairs are my addition, and four copies give six dependent pairs.

Run from the repository root with `uv run --project ledger --no-sync python - <<'EOF' ... EOF`:

```python
import sys, itertools; sys.path[:0] = ["ledger/scripts", "ledger/src"]
import numpy as np, reliability_v2_bc as BC
from brainir_ledger import agree as AG
ts, H = BC._types_for("MANC", True), BC.H8                      # 261 primary analysed types, seed halves 0-3 / 4-7
_, A = BC._b2_arms("MANC"); cn = BC._load("cn-run4")
arms = {"LW": A["LW"], "RW": A["RW"], **{k: BC._rep(cn, f"CN-{k}") for k in ("P1", "P2", "N1", "N2")}}
V = {k: [AG.type_scores(d, h, ts).to_numpy() for h in H] for k, d in arms.items()}
I = np.vstack([np.arange(len(ts)), np.random.default_rng(20261401).integers(0, len(ts), (10000, len(ts)))])
r = lambda a, b: BC._rho_rows(a[I], b[I])
rx = lambda x, y: (r(V[x][0], V[y][1]) + r(V[x][1], V[y][0])) / 2            # G6 cross-half agreement (row 0 = point)
cc = lambda x, y: (r(V[x][0], V[x][1]) + r(V[y][0], V[y][1])) / 2            # G6 matched ceiling
obs, cobs = rx("LW", "RW"), cc("LW", "RW")
pairs = list(itertools.combinations(["P1", "P2", "N1", "N2"], 2))
def pooled(ps, label):
    m, mc = np.mean([rx(*p) for p in ps], 0), np.mean([cc(*p) for p in ps], 0)
    d, s = obs - m, (mc - m) / (cobs - obs)
    q = lambda v: "%.3f (%.3f to %.3f)" % (v[0], *np.nanpercentile(v[1:], [2.5, 97.5]))
    print(f"{label:28s} rho_x {m[0]:.3f}  observed minus model {q(d)}  share of L-R gap {q(s)}")
print("observed L vs R: rho_x %.3f, c %.3f" % (obs[0], cobs[0]))
for p in pairs: print("  %s-%s rho_x %.3f  c %.3f" % (*p, rx(*p)[0], cc(*p)[0]))
pooled([("P1", "P2")], "P1-P2 (pre-registered)")
pooled([("P1", "P2"), ("N1", "N2")], "within-model mean (2 pairs)")
pooled(pairs, "all six pairs")
for drop in ("P1", "P2", "N1", "N2"):
    pooled([p for p in pairs if drop not in p], f"without {drop} (3 pairs)")
```

Output:

```
observed L vs R: rho_x 0.372, c 0.792
  P1-P2 rho_x 0.400  c 0.827
  P1-N1 rho_x 0.382  c 0.832
  P1-N2 rho_x 0.522  c 0.800
  P2-N1 rho_x 0.536  c 0.833
  P2-N2 rho_x 0.446  c 0.801
  N1-N2 rho_x 0.448  c 0.806
P1-P2 (pre-registered)       rho_x 0.400  observed minus model -0.029 (-0.162 to 0.102)  share of L-R gap 1.016 (0.734 to 1.409)
within-model mean (2 pairs)  rho_x 0.424  observed minus model -0.052 (-0.174 to 0.067)  share of L-R gap 0.933 (0.687 to 1.266)
all six pairs                rho_x 0.456  observed minus model -0.084 (-0.191 to 0.021)  share of L-R gap 0.858 (0.657 to 1.139)
without P1 (3 pairs)         rho_x 0.477  observed minus model -0.105 (-0.217 to 0.005)  share of L-R gap 0.800 (0.598 to 1.073)
without P2 (3 pairs)         rho_x 0.451  observed minus model -0.079 (-0.190 to 0.029)  share of L-R gap 0.861 (0.646 to 1.155)
without N1 (3 pairs)         rho_x 0.456  observed minus model -0.085 (-0.193 to 0.022)  share of L-R gap 0.841 (0.631 to 1.131)
without N2 (3 pairs)         rho_x 0.439  observed minus model -0.068 (-0.182 to 0.042)  share of L-R gap 0.931 (0.699 to 1.251)
```

On all 262 analysed types (secondary set) the six-pair result is the same: 0.455, -0.083 (-0.189 to +0.021).

**Reading.**
- **The reported pair is a low draw.** Copy pairs agree at 0.38, 0.40, 0.45, 0.45, 0.52 and 0.54 (SD 0.06). The pre-registered
  P1-P2 is the second lowest, and all six are above the observed 0.372.
- **Pooled, noise still reproduces most of the gap.** Over all six pairs, copies agree at 0.456. Observed minus model is -0.084
  (-0.191 to +0.021), and the share of the gap reproduced is 0.86 (0.66 to 1.14).
- **The pre-registered pairs alone.** P1-P2 with N1-N2 gives 0.424, with a share of 0.93 (0.69 to 1.27).
- **No single copy drives this.** Leaving out any one copy gives 0.44-0.48.
- **What survives.** B4.5's rule is met as locked, and every pooled interval includes 0. Poisson-level count noise produces most of
  the gap, against a ceiling of about 0.82.
- **What changes.** The point estimate of the share falls from 1.02 (the headline's pair) to 0.86. "Agree no better than" holds only
  for the lowest draws.

**Why the spread is realisation noise and not dose.** The copies were regenerated from `manc_raw_counts()` with the seeds of record.
They are bit-identical to the networks in the four `cn-run4` payloads (nnz 208,974 / 208,968 / 208,536 / 208,214; maximum absolute
difference 0). Their wiring distance was then measured with A4(b)'s statistics on matched-neuron entries:

```python
import sys, json, itertools; sys.path[:0] = ["ledger/scripts", "ledger/src"]
import numpy as np
from brainir_ledger import mirror as MR, fixes as FX
f = MR.fly("MANC"); mm = MR.mirror_map(f); n = f.n
ok = np.isin(mm.status[:n], MR.MATCHED); m = np.where(ok, mm.m[:n], np.arange(n))   # A4(b): matched neurons only
C1 = FX.manc_raw_counts(); W = FX.at_floor(C1, 5)
k = json.load(open("research/ledger/gates_v4/NB_DISPERSION.json"))["inv_k"]
cp = {"P1": FX.poisson_copy(C1, 20261411), "P2": FX.poisson_copy(C1, 20261412), "N1": FX.nb_copy(C1, k, 20261421), "N2": FX.nb_copy(C1, k, 20261422)}
cp = {a: FX.at_floor(v, 5) for a, v in cp.items()}
def dist(A, B):
    U = (A + B).tocoo(); s = ok[U.row] & ok[U.col]
    a = np.asarray(A[U.row[s], U.col[s]]).ravel(); b = np.asarray(B[U.row[s], U.col[s]]).ravel()
    both = (a > 0) & (b > 0)
    return ((a > 0) ^ (b > 0)).sum() / ((a > 0) | (b > 0)).sum(), np.corrcoef(np.log(a[both]), np.log(b[both]))[0, 1]
print("L vs R (W vs its mirror image): one-sided %.3f, Pearson log %.3f" % dist(W, W[m][:, m]))
for a in cp: print("W vs %s: one-sided %.3f, Pearson log %.3f" % (a, *dist(W, cp[a])))
for a, b in itertools.combinations(cp, 2): print("%s vs %s: one-sided %.3f, Pearson log %.3f" % (a, b, *dist(cp[a], cp[b])))
```

| comparison | share of connections present in one network only | Pearson of log counts, shared | screen rho_x |
|---|---|---|---|
| L on W vs L on relabelled W (B2.4) | 0 | 1 | 0.812 (= its ceiling) |
| W vs each copy (4) | 0.26-0.27 | 0.94-0.95 | 0.48-0.56 (mean 0.52) |
| copy vs copy (6) | 0.35-0.36 (P1-P2 0.349, the smallest) | 0.89-0.92 | 0.38-0.54 (mean 0.46; P1-P2 0.40) |
| L vs R on W (the real gap) | 0.51, plus 57,134 unmatched-neuron entries, 3,996 sizes, 108 signs | 0.78 | 0.372 |

The table reads as one curve: agreement falls as wiring distance grows. The copies sit between "W vs a copy" and "L vs R" in both
wiring distance and screen agreement, and their mean of 0.46 lies where the curve puts them. P1-P2 has the smallest wiring distance of
the six pairs but the second-lowest agreement. That is a property of the draw, not of the dose. The cross-model pairs differ slightly
more in wiring than P1-P2 (0.356-0.357 against 0.349 one-sided) and still agree more on the screen (mean 0.47). Pooling across the two
noise models is therefore conservative. The one-sided share is only a rough axis: floor 1 against floor 5 on the left network is 0.74
one-sided, but every added connection has 1-4 synapses, and the screens still agree at 0.58.

## 3. Other objections considered, and why they are weaker

1. **A construction bug in the copies.** Ruled out. The payloads equal the specification bit for bit (section 2), and B4.1's floor-5
   reproduction check is built into `_manc_raw_counts_cached`.
2. **Platform or numerics.** `cn-run4` and `b2-manc-run4` both ran on GitHub. The stage 3 determinism sample re-ran 20 of 20 `cn-run4`
   jobs identically. The relabelling control agrees with L on W at 0.812, its own ceiling. Floating-point noise is not the source.
3. **Copies are a denser network.** Poisson-then-floor pulls connections up from the 577,174 sub-floor counts: each copy has about 6 %
   more connections and 4 % more synapses than W. Both copies share this shift. Their usable shares (0.65-0.70 against 0.69 for L on W)
   and their own split-half ceilings (0.77-0.84 against 0.81) look like W's. A small change of regime cannot be excluded, but nothing
   points to one.
4. **Saturation: any change gives about 0.4, so the test cannot discriminate.** No. Block 3's hybrids against L on W, from the stored
   `b3-manc-run4` results with the same rx, are graded: sign of 108 slots 0.77; sizes 0.68; homologous weights 0.59; unmatched neurons
   0.59; one-sided connections 0.48; four classes together 0.39-0.49; full mirror (= R on W) 0.37 (ceilings 0.78-0.83). The statistic
   is not pegged. This objection would, if anything, strengthen "the model is very sensitive to count noise".
5. **Zero ties favour the copies.** They do, but that works against the headline. The copies have more types at zero in both screens
   (83 Poisson and 102 NB, against 69 for L vs R; full seeds, 261 types), and ties at zero inflate rho. On types non-zero in either
   screen, cross-half agreement is about 0.1 or less for all three: L vs R 0.099, Poisson 0.091, NB 0.007 (NOISE.json secondary).
6. **The NB copies are L-R-sized by construction, because 1/k is fitted on left-right pairs.** No. 1/k is small. The NB copies stay
   much closer in wiring than L and R (0.36 against 0.51 one-sided), and the headline rests on Poisson, which has no parameter.
7. **Choice of comparator.** The same left-right comparison on the same 261 types and seeds without paired draws (Block 1's tuned
   screen, `B1_MANC.json`) gives 0.403 instead of 0.372. The comparator moves by 0.03 with parameter draws alone. With 0.403 the
   six-pair difference would be about -0.05. This points the same way as the main objection and is smaller.
8. **"Counting noise" may suggest reconstruction error.** Poisson resampling changes 35 % of connections between copies, about
   two-thirds of the real left-right one-sided share. That is variability on the scale of biology, not of EM counting error.
   Independent detection with probability p gives binomial variance p(1-p)c, for example 0.09c at p = 0.9, against c for Poisson.
   Whether reconstruction-scale noise moves the screen was not tested. Block 3's grading (0.68-0.77 for the smallest perturbations)
   suggests a smaller change would leave agreement nearer the ceiling. The headline sentence itself defines the noise as Poisson
   noise in raw counts, so this is a matter of wording, not an artefact.
9. **"Cause found" claims more than sufficiency.** The test shows that noise on the Poisson scale is enough for most of a gap this
   large. It does not show that the real left-right differences act through count noise. No per-type check was made of whether the
   same types flip under noise as between the sides. RESULTS_3's caveat 1 says this explicitly, and so do BRIEF claim 3 and EVIDENCE_MAP
   row 10.
10. **Limits of my own test.** The pooled interval still omits between-copy variance, and four copies cannot estimate it well, so the
    honest interval on the share is wider than 0.66-1.14. I do not lean on the two cross-model pairs whose own intervals exclude 0
    (P1-N2 and P2-N1): that is selection among six.

The qualification below also applies to BRIEF.md claim 3 ("enough to produce the gap", 0.40 against 0.37) and EVIDENCE_MAP row 10.

## 4. Verdict

Verdict: the headline survives with qualification: the reported 0.40 against 0.37 is the second-lowest of the six copy pairings that the four stored noise copies allow (0.38-0.54, mean 0.46, every one above 0.37), so Poisson count noise reproduces most of the left-right gap (about 86 %, 66-114 %) but not demonstrably all of it, and "agree no better than" should read "agree almost as poorly as".
