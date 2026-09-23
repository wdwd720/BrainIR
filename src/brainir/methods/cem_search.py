"""cem_search: cross-entropy / estimation-of-distribution search over neuron inclusion.

The method keeps an independent-Bernoulli inclusion distribution q_i over candidate neurons, samples keep-only subsets
from it, scores them with the budgeted simulator and moves q toward the elite samples (cross-entropy update with
smoothing), with two additions that make the search affordable on graphs of thousands of nodes: a *group-testing
exoneration* step (a neuron absent from - or silent inside - a passing keep-only set is not needed for that set, so
its q is multiplied by a factor < 1; this is PBIL-style negative learning) and an adaptive *inclusion level* that
expands q when too few samples pass and shrinks it when almost all pass (an MDL-flavoured size pressure that never
assumes a mechanism size). Fitness = pass verdict + score - size penalty, one parameter seed per sample, seeds rotating
over a small ensemble so the elites are robust rather than tuned to one draw.

Zero-cost pre-screen (model deductions, no answer knowledge): a neuron can matter only if activation can reach it from
the stimulus through excitatory edges and if it can reach the readout through any signed path; and a neuron that is
silent in the intact network carries no signal, so the pool is reduced to the intact network's active set whenever the
keep-only of that set still passes (verified by simulation, with a fallback to the structural pool).

The search is followed by a discrete cleanup: the MAP set (q >= 0.5) - or the best passing sample - is minimised by
ddmin-style backward elimination in ascending-q order (chunks halve on failure, every survivor is tested individually),
then verified on the seed ensemble. Alternatives come from a complement test (keep-only of pool minus the core; if it
passes, the same minimisation yields a different sufficient set; repeated). Full-network context: every verified set is
silenced in the intact network - a set whose loss destroys the function is the one the intact network relies on (it becomes
the core; keep-only-only alternatives, which cannot stand in for it, are dropped), while sets that can each be silenced
alone but not together are redundant implementations; when the core is necessary, its most strongly connected neighbours
are silenced one by one and join the core if the function depends on them (e.g. an interneuron suppressing a competitor
that keep-only removes anyway). Essentiality = silencing each core member alone in the FULL network on several seeds.
Fidelity = keep-only of the core on fresh seeds and on a widened-parameter ensemble; optional (config, off by default)
add-backs of removed members that improve the robust pass fraction (flagged modulatory_supporting).
Inclusion probabilities blend the converged q (search evidence) with a mixture over the verified sufficient sets
(discrete evidence), so equally supported implementations share probability mass. Generic roles come from sign,
position in the core's cycle structure, readout/stimulus connectivity and the criterion type.
"""

from __future__ import annotations

import math
import time
from collections.abc import Iterable, Sequence

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components

from ..discovery.interface import GENERIC_ROLES, DiscoveryMethod, DiscoveryResult, MethodRegistry
from ..discovery.interventions import keep_only, silence
from ..discovery.problem import DiscoveryProblem
from ..discovery.simulator import BudgetedSimulator, BudgetExhausted, Outcome, SimQuery

# ------------------------------------------------------------------------------------------------ graph helpers


def hop_distances(adj: sp.spmatrix, sources: Iterable[int]) -> np.ndarray:
    """BFS hop distance along edges pre -> post of ``adj[post, pre] != 0`` starting at ``sources``; -1 = unreachable."""
    n = adj.shape[0]
    A = (adj != 0).astype(np.int8).tocsr()
    dist = np.full(n, -1, dtype=np.int64)
    front = np.zeros(n, dtype=bool)
    src = sorted({int(s) for s in sources})
    if not src:
        return dist
    front[src] = True
    dist[front] = 0
    d = 0
    while front.any():
        d += 1
        reached = np.asarray(A @ front.astype(np.int8)).ravel() > 0
        new = reached & (dist < 0)
        if not new.any():
            break
        dist[new] = d
        front = new
    return dist


def structural_pool(problem: DiscoveryProblem) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Candidates that can be activated by the stimulus (excitatory-edge reachability) AND can influence the readout
    (any-sign reachability to a readout neuron). Returns (pool positions, d_stim, d_readout) - a sound superset of any
    mechanism member under the rate model: silent neurons and neurons without a path to the readout cannot matter."""
    W = problem.W.tocsr()
    exc = W.multiply(W > 0).tocsr()
    d_s = hop_distances(exc, problem.stim_positions)
    d_r = hop_distances(W.T.tocsr(), problem.readout_positions)
    cand = problem.candidate_positions()
    mask = (d_s[cand] >= 0) & (d_r[cand] >= 0)
    return cand[mask], d_s, d_r


# ------------------------------------------------------------------------------------------------ budget-aware runner


class _Runner:
    """Submits batches only when they fit the simulator's remaining budget (cache hits are free) and a stage allowance."""

    def __init__(self, sim: BudgetedSimulator, problem: DiscoveryProblem):
        self.sim = sim
        self._hash = problem.network_hash()
        self._crit = dict(problem.criterion_spec)
        self.exhausted = False
        self.stage_calls: dict[str, int] = {}

    def n_new(self, queries: Sequence[SimQuery]) -> int:
        seen: set[str] = set()
        n = 0
        for q in queries:
            k = q.key(self._hash, self._crit)
            if k not in self.sim.cache and k not in seen:
                seen.add(k)
                n += 1
        return n

    def run(self, queries: Sequence[SimQuery], stage: str, allowance: int | None = None) -> list[Outcome] | None:
        n = self.n_new(queries)
        if n > self.sim.remaining or (allowance is not None and n > allowance):
            return None
        try:
            outs = self.sim.run_many(list(queries))
        except BudgetExhausted:
            self.exhausted = True
            return None
        self.stage_calls[stage] = self.stage_calls.get(stage, 0) + n
        return outs


def _pass_fraction(outs: Sequence[Outcome]) -> float:
    return float(np.mean([o.passed for o in outs])) if outs else 0.0


# ------------------------------------------------------------------------------------------------ the method


@MethodRegistry.register
class CemSearch(DiscoveryMethod):
    name = "cem_search"
    version = "1.0"
    default_config = {
        # ensemble / population
        "n_search_seeds": None,        # None: 3 if budget >= 400 else 2
        "population": None,            # None: clip(round(0.5 * budget / 25), 6, 24)
        "max_iterations": 60,
        "min_iterations": 3,
        # cross-entropy update
        "alpha": 0.5,                  # smoothing toward the elite frequencies
        "rho": 0.35,                   # elite fraction of the population (at least 2 elites)
        "gamma_exonerate": 0.6,        # q multiplier for neurons ABSENT from a passing sample
        "gamma_silent": 0.7,           # q multiplier for neurons kept but SILENT in a passing sample
        "q_init": 0.95, "q_min": 0.005, "q_max": 0.995,
        "q_inactive_prior": 0.5,       # prior for structurally admissible but intact-silent neurons (fallback pool only)
        # adaptive inclusion level
        "pass_lo": 0.2, "pass_hi": 0.8, "expand": 1.25, "shrink": 0.9,
        # fitness
        "score_weight": 0.5, "size_penalty": 0.25,
        # stopping
        "u_stop": 0.5,                 # uncertain mass sum(min(q, 1-q)) over q > 0.02 below which the search stops
        # pre-screen
        "activity_filter": True, "activity_aware": True,
        # budget split (fractions of the budget available at start); unspent budget flows to later stages
        "frac_cem": 0.5, "frac_cleanup": 0.25, "frac_alternatives": 0.1, "frac_final": 0.15,
        "frac_alternatives_max": 0.4,  # hard cap of the alternatives stage (it may inherit unspent budget up to this share)
        # cleanup / verification
        # add_backs (off by default): re-add removed members that raise the robust (sd x2) keep-only pass fraction; the evidence is one
        # widened-parameter seed of three and it grows the core with non-essential members, so compactness wins unless asked for
        "max_alternatives": 3, "n_essential_seeds": 2, "n_fidelity_seeds": 3, "add_backs": False, "max_add_backs": 3,
        "n_context": 4,                # strongest core neighbours tested for necessity in context (full-network silencing)
        "w_search": 0.3,               # weight of the converged q in the final inclusion probability (rest: verified sets)
        # optional external prior {position: p in [0, 1]} (absent = uniform); q0 = level * (1 - prior_strength + prior_strength * p)
        "prior": None, "prior_strength": 0.5,
    }

    # ------------------------------------------------------------------------------------------ entry point
    def discover(self, problem: DiscoveryProblem, sim: BudgetedSimulator, *, seed: int, config: dict | None = None) -> DiscoveryResult:
        cfg = {**self.default_config, **(config or {})}
        t0 = time.time()
        rng = np.random.default_rng(int(seed))
        runner = _Runner(sim, problem)
        B = int(sim.remaining)
        n_s = int(cfg["n_search_seeds"] or (3 if B >= 400 else 2))
        search_seeds = [int(seed) * 1000 + i for i in range(n_s)]
        diag: dict = {"budget_at_start": B, "stages": {}, "warnings": []}
        # stage reserves: a stage may spend down to sim.remaining - reserve_after[stage]
        reserve_after = {"cem": (cfg["frac_cleanup"] + cfg["frac_alternatives"] + cfg["frac_final"]) * B,
                         "cleanup": (cfg["frac_alternatives"] + cfg["frac_final"]) * B,
                         "alternatives": cfg["frac_final"] * B, "final": 0.0}

        def allowance(stage: str) -> int:
            return max(0, int(sim.remaining - math.ceil(reserve_after[stage])))

        # ---------------------------------------------------------------- stage 0: pre-screen (structure + intact activity)
        pool_struct, d_s, d_r = structural_pool(problem)
        cand = problem.candidate_positions()
        diag["n_candidates"] = int(len(cand))
        diag["n_structural_pool"] = int(len(pool_struct))
        intact = runner.run([SimQuery(None, s) for s in search_seeds], "prescreen") or []
        intact_pass = [o for o in intact if o.passed]
        if intact and not intact_pass:
            extra = runner.run([SimQuery(None, int(seed) * 1000 + n_s + i) for i in range(2)], "prescreen") or []
            for i, o in enumerate(extra):
                if o.passed:
                    search_seeds.append(int(seed) * 1000 + n_s + i)
                    intact_pass.append(o)
            intact = list(intact) + list(extra)
        if intact_pass:  # seeds whose intact network fails are uninformative for pass/fail search: drop them when possible
            good = [s for s, o in zip(search_seeds, intact) if o.passed]
            search_seeds = good if len(good) >= 1 else search_seeds
        soft_mode = not intact_pass
        diag["intact_pass_fraction"] = _pass_fraction(intact) if intact else None
        diag["search_seeds"] = list(search_seeds)
        n_s = len(search_seeds)
        pos_struct = set(int(p) for p in pool_struct)
        active_union: set[int] = set()
        for o in (intact_pass or intact):
            active_union.update(int(p) for p in o.active_positions)
        active_pool = np.array(sorted(active_union & pos_struct), dtype=np.int64)
        pool = pool_struct
        pool_kind = "structural"
        if cfg["activity_filter"] and intact_pass and len(active_pool) < len(pool_struct):
            test = runner.run([SimQuery(keep_only(problem, active_pool), s) for s in search_seeds], "prescreen")
            if test is not None and _pass_fraction(test) >= 0.5:
                pool = active_pool
                pool_kind = "active"
            elif test is not None:
                diag["warnings"].append("keep-only of the intact active set fails: transient or silent neurons matter; using the structural pool")
        diag["pool_kind"] = pool_kind
        diag["n_active_pool"] = int(len(active_pool))
        diag["n_pool"] = int(len(pool))
        N = len(pool)
        pos_to_pool = np.full(problem.n, -1, dtype=np.int64)
        pos_to_pool[pool] = np.arange(N)
        active_mask_pool = np.zeros(N, dtype=bool)
        if len(active_pool):
            active_mask_pool[pos_to_pool[active_pool]] = True
        # prior: the inclusion level (q_init; lower for intact-silent neurons of a fallback pool), optionally biased by an external
        # prior {position: p in [0, 1]} (config["prior"], e.g. a mechanism transported from another network) - never required
        q = np.full(N, float(cfg["q_init"]))
        if pool_kind == "structural":
            q[~active_mask_pool] = float(cfg["q_inactive_prior"])
        ext_prior = self._external_prior(cfg.get("prior"), pool)
        if ext_prior is not None:
            s = float(np.clip(cfg.get("prior_strength", 0.5), 0.0, 1.0))
            q = q * (1.0 - s + s * ext_prior)
            diag["external_prior"] = {"n_given_in_pool": int(np.sum(ext_prior != 0.5)), "strength": s}
        q = np.clip(q, cfg["q_min"], cfg["q_max"])
        diag["stages"]["prescreen"] = runner.stage_calls.get("prescreen", 0)

        # ---------------------------------------------------------------- stage 1: cross-entropy search
        history: list[dict] = []
        cem_trace: list[dict] = []
        if N > 0:
            q = self._cem(problem, runner, rng, pool, q, active_mask_pool, search_seeds, cfg, allowance, history, cem_trace, soft_mode)
        diag["cem_iterations"] = len(cem_trace)
        diag["cem_trace"] = cem_trace
        diag["stages"]["cem"] = runner.stage_calls.get("cem", 0)
        q_final = q.copy()

        # ---------------------------------------------------------------- stage 2: discrete cleanup of the MAP set
        map_set = [int(p) for p in pool[q >= 0.5]]
        start, start_pf, start_kind = self._pick_start(problem, runner, map_set, history, search_seeds, allowance)
        diag["cleanup_start"] = {"kind": start_kind, "size": len(start), "pass_fraction": start_pf}
        qmap = {int(p): float(q[i]) for i, p in enumerate(pool)}
        core, removed_single, removed_chunk, mtrace = self._minimize(problem, runner, start, qmap, search_seeds, "cleanup", allowance)
        diag["minimize"] = mtrace
        diag["stages"]["cleanup"] = runner.stage_calls.get("cleanup", 0)
        verified: list[dict] = []  # sufficient sets with their pass fraction on the search seeds
        # verification of the minimised set (a cache hit when the last accepted removal test used the same query)
        core_outs = runner.run([SimQuery(keep_only(problem, core), s) for s in search_seeds], "cleanup")
        core_pf = _pass_fraction(core_outs) if core_outs is not None else (start_pf if core == sorted(start) else None)
        if core_pf is not None and core_pf < 0.5 and (removed_single or removed_chunk):
            # fragile after elimination: re-add removed members (most believed first) until the ensemble passes
            for p in sorted(removed_single + removed_chunk, key=lambda x: (-qmap.get(x, 0.0), x)):
                trial = sorted(core + [p])
                outs = runner.run([SimQuery(keep_only(problem, trial), s) for s in search_seeds], "cleanup", allowance("cleanup"))
                if outs is None:
                    break
                core = trial
                if p in removed_single:
                    removed_single.remove(p)
                else:
                    removed_chunk.remove(p)
                core_pf = _pass_fraction(outs)
                if core_pf >= 0.5:
                    break
        verified.append({"members": sorted(core), "pass_fraction": core_pf if core_pf is not None else 0.0, "kind": "core"})

        # ---------------------------------------------------------------- stage 3: alternatives by complement tests
        # the stage may use unspent budget of earlier stages but at most frac_alternatives_max of the whole budget (diffuse functions
        # - many weak routes to the readout - make complement minimisation expensive), and an alternative is accepted only when its
        # minimisation completed: a truncated one is a superset of unknown size, not a mechanism
        alt_cap = int(math.floor(float(cfg["frac_alternatives_max"]) * B))

        def alt_allowance(stage: str) -> int:
            return max(0, min(allowance(stage), alt_cap - runner.stage_calls.get("alternatives", 0)))

        excluded = set(core)
        for _ in range(int(cfg["max_alternatives"])):
            rest = [int(p) for p in pool if int(p) not in excluded]
            if not rest or alt_allowance("alternatives") < n_s + 4:
                break
            outs = runner.run([SimQuery(keep_only(problem, rest), s) for s in search_seeds], "alternatives", alt_allowance("alternatives"))
            if outs is None or _pass_fraction(outs) < 0.5:
                break
            alt, _rs, _rc, atrace = self._minimize(problem, runner, rest, qmap, search_seeds, "alternatives", alt_allowance)
            if atrace.get("stopped"):
                diag["alternatives_truncated"] = {"remaining_size": len(alt), "untested": len(atrace.get("untested", []))}
                break
            aouts = runner.run([SimQuery(keep_only(problem, alt), s) for s in search_seeds], "alternatives", alt_allowance("alternatives"))
            apf = _pass_fraction(aouts) if aouts else None
            if apf is None or apf < 0.5 or not alt:
                break
            verified.append({"members": sorted(alt), "pass_fraction": apf, "kind": "alternative", "trace": atrace})
            excluded |= set(alt)
        diag["stages"]["alternatives"] = runner.stage_calls.get("alternatives", 0)

        # weights of the verified sufficient sets; the core is the most probable one
        k_min = min(len(v["members"]) for v in verified) if verified else 0
        for v in verified:
            v["weight"] = float(v["pass_fraction"]) * math.exp(-0.3 * (len(v["members"]) - k_min))
        tot = sum(v["weight"] for v in verified) or 1.0
        for v in verified:
            v["weight"] /= tot
        verified.sort(key=lambda v: (-v["weight"], len(v["members"]), v["members"]))

        # ---------------------------------------------------------------- stage 4: full-network context (silencing in the intact network)
        # keep-only sufficiency removes everything else, including competitors the intact network must actively suppress; silencing
        # tests in the intact network decide which sufficient set the intact network relies on, whether the others are real backups,
        # per-member essentiality, and whether strong neighbours of the core are necessary in context (then they join the core)
        n_ess = min(int(cfg["n_essential_seeds"]), n_s)
        ess_seeds = search_seeds[:n_ess]
        fidelity_reserve = 2 * int(cfg["n_fidelity_seeds"])

        def full_pass(positions: Sequence[int]) -> float | None:
            outs = runner.run([SimQuery(silence(positions), s) for s in ess_seeds], "context", sim.remaining - fidelity_reserve)
            return None if outs is None else _pass_fraction(outs)

        ctx, verified = self._context_sets(verified, full_pass)
        core = list(verified[0]["members"]) if verified else sorted(core)
        alternatives = [list(v["members"]) for v in verified[1:]]
        essential: dict[int, bool | None] = {p: None for p in core}
        for p in sorted(core, key=lambda x: (-qmap.get(x, 0.0), x)):
            f = full_pass([p])
            if f is None:
                break
            essential[p] = bool(f < 0.5)
        added: list[int] = []
        if ctx["core_necessary"] and core:
            tested = set(core) | {int(x) for v in verified for x in v["members"]} | {int(x) for a in ctx["dropped_alternatives"] for x in a}
            first = [int(x) for x in ctx["other_necessary_members"] if int(x) not in set(core)]
            neigh, strength = self._context_candidates(problem, core, tested | set(first), pool, int(cfg["n_context"]))
            for x in first + neigh:
                f = full_pass([x])
                rec = {"position": int(x), "strength": strength.get(x), "silenced_pass_fraction": f}
                ctx["scan"].append(rec)
                if f is None:
                    break
                if f < 0.5:
                    trial = sorted(set(core) | {int(x)})
                    outs = runner.run([SimQuery(keep_only(problem, trial), s) for s in search_seeds], "context", sim.remaining - fidelity_reserve)
                    rec["keep_only_pass_fraction"] = None if outs is None else _pass_fraction(outs)
                    if outs is not None and _pass_fraction(outs) >= 0.5:
                        core = trial
                        added.append(int(x))
                        essential[int(x)] = True
            if added:
                verified[0]["members"] = list(core)
        ctx["added"] = added
        diag["context"] = ctx
        diag["stages"]["context"] = runner.stage_calls.get("context", 0)

        # ---------------------------------------------------------------- stage 5: fidelity on fresh seeds (nominal + robust)
        n_f = int(cfg["n_fidelity_seeds"])
        fresh = [int(seed) * 1000 + 100 + i for i in range(n_f)]
        mc = problem.model_cfg
        wide = {"tau_sd": mc.tau_sd * 2, "a_sd": mc.a_sd * 2, "theta_sd": mc.theta_sd * 2, "r_max_sd": mc.r_max_sd * 2}
        fid: dict = {"keep_only_pass_fraction_search_seeds": verified[0]["pass_fraction"] if verified else None}
        nominal = runner.run([SimQuery(keep_only(problem, core), s) for s in fresh], "fidelity") if core else None
        robust = runner.run([SimQuery(keep_only(problem, core), s, cfg_override=wide) for s in fresh], "fidelity") if core else None
        if nominal:
            fid["keep_only_pass_fraction"] = _pass_fraction(nominal)
            fid["keep_only_score_mean"] = float(np.mean([o.score for o in nominal]))
        if robust:
            fid["robust_sd_x2_pass_fraction"] = _pass_fraction(robust)
        # add-backs: removed members that raise the robust pass fraction (flagged modulatory_supporting, never essential)
        add_backs: list[int] = []
        if cfg["add_backs"] and robust and fid["robust_sd_x2_pass_fraction"] < 1.0 and core:
            cands = sorted(set(removed_single + removed_chunk) - set(core), key=lambda x: (-qmap.get(x, 0.0), x))[: int(cfg["max_add_backs"])]
            best_rob = fid["robust_sd_x2_pass_fraction"]
            for j in cands:
                trial = sorted(core + add_backs + [j])
                r2 = runner.run([SimQuery(keep_only(problem, trial), s, cfg_override=wide) for s in fresh], "fidelity")
                if r2 is None:
                    break
                if _pass_fraction(r2) > best_rob + 1e-9:
                    n2 = runner.run([SimQuery(keep_only(problem, trial), s) for s in fresh], "fidelity")
                    if n2 is not None and _pass_fraction(n2) >= fid.get("keep_only_pass_fraction", 0.0):
                        add_backs.append(j)
                        best_rob = _pass_fraction(r2)
                        fid["robust_sd_x2_pass_fraction"] = best_rob
                        fid["keep_only_pass_fraction"] = _pass_fraction(n2)
                        nominal = n2
        if add_backs:
            core = sorted(core + add_backs)
            verified[0]["members"] = list(core)
            for j in add_backs:
                essential[j] = False
        diag["add_backs"] = add_backs
        diag["stages"]["fidelity"] = runner.stage_calls.get("fidelity", 0)

        # ---------------------------------------------------------------- stage 6: probabilities, roles, loop, predictions
        w_search = float(cfg["w_search"])
        incl: dict[int, float] = {}
        member_sets = [(set(v["members"]), v["weight"]) for v in verified]
        core_set = set(core)
        removed_s, removed_c = set(removed_single), set(removed_chunk)
        added_set = set(added)
        for i, p in enumerate(pool):
            p = int(p)
            base = float(q_final[i])
            if p in added_set:
                base = 0.95  # necessary in context by a direct silencing test
            elif p in removed_s:
                base = min(base, 0.1)
            elif p in removed_c:
                base = min(base, 0.2)
            m = sum(w for s, w in member_sets if p in s)
            if p in core_set and p not in add_backs:
                m = max(m, verified[0]["weight"] if verified else 1.0)
            incl[p] = float(np.clip(w_search * base + (1.0 - w_search) * m, 0.0, 1.0))
        for p in cand:
            p = int(p)
            if p not in incl:
                incl[p] = 0.02 if (p in pos_struct) else 0.0  # active-filtered (model deduction with a transient caveat) / structurally excluded
        for p in core_set:  # core members are always assessed
            incl.setdefault(p, 1.0)
        roles = self._roles(problem, core, [set(a) for a in alternatives], incl, add_backs)
        loop = self._loop(problem, core)
        motif = self._motif(problem, core, loop, roles)
        # dynamics claims describe the INTACT network under the stimulus (measured directly in stage 0, no extra calls); the keep-only
        # core's own dynamics go to the fidelity record (they can differ: the rest of the network may modulate the rhythm)
        passing_core = [o for o in (nominal or []) if o.passed] or [o for o in (core_outs or []) if o.passed]
        core_freqs = [o.frequency_hz for o in passing_core if o.frequency_hz is not None]
        if core_freqs:
            fid["core_frequency_hz"] = float(np.median(core_freqs))
        if passing_core:
            fid["core_n_active_readout"] = int(np.median([o.n_active_readout for o in passing_core]))
        dyn_src = list(intact_pass) or passing_core
        diag["dynamics_source"] = "intact" if intact_pass else ("keep_only_core" if passing_core else None)
        freqs = [o.frequency_hz for o in dyn_src if o.frequency_hz is not None]
        n_act = [o.n_active_readout for o in dyn_src]
        nominal_pf = _pass_fraction(intact) if intact else fid.get("keep_only_pass_fraction", verified[0]["pass_fraction"] if verified else 0.0)
        diag["verified_sets"] = [{k: v for k, v in s.items() if k != "trace"} for s in verified]
        diag["budget_exhausted"] = runner.exhausted
        diag["soft_mode"] = soft_mode
        diag["wall_s"] = round(time.time() - t0, 2)
        return DiscoveryResult(
            core=[int(p) for p in core], inclusion_probability=incl, roles=roles, essential={int(k): v for k, v in essential.items()},
            alternatives=[[int(p) for p in a] for a in alternatives], loop=[int(p) for p in loop],
            predicted_frequency_hz=float(np.median(freqs)) if freqs else None,
            predicted_n_active_readout=int(np.median(n_act)) if n_act else None,
            predicted_function_preserved=bool(nominal_pf >= 0.5) if nominal_pf is not None else None,
            fidelity=fid, budget={**sim.report(), "wall_s": round(time.time() - t0, 2), "stage_calls": dict(runner.stage_calls)},
            diagnostics=diag, motif=motif)

    @staticmethod
    def _context_sets(verified: list[dict], full_pass) -> tuple[dict, list[dict]]:
        """Silence each verified sufficient set in the intact network (``full_pass`` -> pass fraction or None when unaffordable).

        * Some set's silencing destroys the function: the intact network relies on it -> it is the core, and the other sets (sufficient
          only when everything else is removed) cannot stand in for it -> dropped from the alternatives (kept in the diagnostics); the
          members of further sets that are also necessary are handed to the context scan.
        * Every set can be silenced alone but silencing their union destroys the function -> redundant implementations (all kept).
        * Otherwise undetermined (recorded)."""
        ctx: dict = {"set_silenced_pass_fraction": [], "union_silenced_pass_fraction": None, "verdict": "untested", "core_necessary": False,
                     "dropped_alternatives": [], "other_necessary_members": [], "scan": []}
        if not verified or not verified[0]["members"]:
            return ctx, verified
        f_sets: list[float | None] = []
        for v in verified:
            f = full_pass(v["members"])
            f_sets.append(f)
            if f is None:
                break
        ctx["set_silenced_pass_fraction"] = f_sets
        nec = [i for i, f in enumerate(f_sets) if f is not None and f < 0.5]
        if nec:
            i0 = min(nec, key=lambda i: (f_sets[i], -verified[i]["weight"], len(verified[i]["members"]), verified[i]["members"]))
            core_v = {**verified[i0], "weight": 1.0}
            others = [v for j, v in enumerate(verified) if j != i0]
            ctx["dropped_alternatives"] = [list(v["members"]) for v in others]
            ctx["other_necessary_members"] = sorted({int(x) for j in nec if j != i0 for x in verified[j]["members"]})
            ctx["verdict"] = "core necessary in the intact network; keep-only alternatives are not backups in context"
            ctx["core_necessary"] = True
            return ctx, [core_v]
        if any(f is None for f in f_sets):
            ctx["verdict"] = "untested (budget)"
        elif len(verified) > 1:
            f_u = full_pass(sorted({int(x) for v in verified for x in v["members"]}))
            ctx["union_silenced_pass_fraction"] = f_u
            ctx["verdict"] = ("redundant implementations" if f_u is not None and f_u < 0.5
                              else "undetermined: the function survives silencing every verified set")
        else:
            ctx["verdict"] = "undetermined: the function survives silencing the core (unfound backup or keep-only-only mechanism)"
        return ctx, verified

    @staticmethod
    def _context_candidates(problem, core: list[int], exclude: set[int], pool: np.ndarray, k: int) -> tuple[list[int], dict[int, float]]:
        """The k pool neurons most strongly connected with the core (observed synapse counts, both directions)."""
        if k <= 0 or not core:
            return [], {}
        C = problem.C.tocsr()
        idx = [int(p) for p in core]
        from_core = np.asarray(C[:, idx].sum(axis=1)).ravel()   # x receives from the core
        to_core = np.asarray(C[idx, :].sum(axis=0)).ravel()     # x projects onto the core
        s = from_core + to_core
        cands = [int(p) for p in pool if int(p) not in exclude and s[int(p)] > 0]
        cands.sort(key=lambda p: (-s[p], p))
        return cands[:k], {p: float(s[p]) for p in cands[:k]}

    @staticmethod
    def _external_prior(prior, pool: np.ndarray) -> np.ndarray | None:
        """Map an optional {position: p} dict onto the pool (missing positions are neutral, 0.5); None when no prior is given."""
        if not prior:
            return None
        table: dict[int, float] = {}
        for k, v in dict(prior).items():
            try:
                table[int(k)] = float(np.clip(float(v), 0.0, 1.0))
            except (TypeError, ValueError):
                continue
        if not table:
            return None
        return np.array([table.get(int(p), 0.5) for p in pool], dtype=float)

    # ------------------------------------------------------------------------------------------ cross-entropy loop
    def _cem(self, problem, runner: _Runner, rng: np.random.Generator, pool: np.ndarray, q: np.ndarray, active_mask_pool: np.ndarray,
             seeds: list[int], cfg: dict, allowance, history: list[dict], trace: list[dict], soft_mode: bool) -> np.ndarray:
        N = len(pool)
        B0 = allowance("cem")
        M = int(cfg["population"] or int(np.clip(round(B0 / 25), 6, 24)))
        alpha, rho = float(cfg["alpha"]), float(cfg["rho"])
        g_ex, g_si = float(cfg["gamma_exonerate"]), float(cfg["gamma_silent"])
        q_min, q_max = float(cfg["q_min"]), float(cfg["q_max"])
        pos_to_pool = np.full(problem.n, -1, dtype=np.int64)
        pos_to_pool[pool] = np.arange(N)
        prev_map: list[frozenset] = []
        n_s = len(seeds)
        for it in range(int(cfg["max_iterations"])):
            allow = allowance("cem")
            M_t = min(M, allow)
            if M_t < 2:
                trace.append({"it": it, "stopped": "budget"})
                break
            masks = rng.random((M_t, N)) < q[None, :]
            sample_seeds = [seeds[(it * M + m) % n_s] for m in range(M_t)]
            queries = [SimQuery(keep_only(problem, pool[masks[m]]), sample_seeds[m]) for m in range(M_t)]
            outs = runner.run(queries, "cem", allow)
            if outs is None:
                trace.append({"it": it, "stopped": "budget"})
                break
            sizes = masks.sum(axis=1)
            passed = np.array([o.passed for o in outs], dtype=bool)
            scores = np.array([o.score for o in outs], dtype=float)
            fit = passed.astype(float) + float(cfg["score_weight"]) * scores - float(cfg["size_penalty"]) * sizes / max(N, 1)
            order = np.argsort(-fit, kind="stable")
            K = max(2, int(math.ceil(rho * M_t)))
            n_pass = int(passed.sum())
            if n_pass >= 2:
                elites = [int(m) for m in order if passed[m]][:K]
                weights = np.ones(len(elites))
            else:
                elites = [int(m) for m in order[:K]]
                weights = np.array([1.0 if passed[m] else 0.5 for m in elites])
            # effective presence: kept AND active in that sample (a silent kept neuron does nothing for the function)
            eff = masks.copy()
            if cfg["activity_aware"]:
                for m in range(M_t):
                    act = np.zeros(N, dtype=bool)
                    idx = pos_to_pool[outs[m].active_positions]
                    act[idx[idx >= 0]] = True
                    eff[m] &= act
            f = (weights[:, None] * eff[elites]).sum(axis=0) / weights.sum()
            q = (1.0 - alpha) * q + alpha * f
            # group-testing exoneration from every passing sample
            n_ex = 0
            for m in np.flatnonzero(passed):
                absent = ~masks[m]
                silent_kept = masks[m] & ~eff[m]
                q[absent] *= g_ex
                q[silent_kept] *= g_si
                n_ex += int(absent.sum() + silent_kept.sum())
            pr = n_pass / M_t
            level = "hold"
            if pr < float(cfg["pass_lo"]):
                q = np.minimum(q * float(cfg["expand"]), q_max)
                level = "expand"
            elif pr > float(cfg["pass_hi"]):
                q = q * float(cfg["shrink"])
                level = "shrink"
            q = np.clip(q, q_min, q_max)
            for m in range(M_t):
                history.append({"members": pool[masks[m]], "seed": sample_seeds[m], "passed": bool(passed[m]),
                                "score": float(scores[m]), "fit": float(fit[m]), "size": int(sizes[m]),
                                "active": eff[m].sum() if cfg["activity_aware"] else None})
            uncertain = q > 0.02
            U = float(np.minimum(q, 1.0 - q)[uncertain].sum())
            map_now = frozenset(int(p) for p in pool[q >= 0.5])
            trace.append({"it": it, "M": M_t, "pass_rate": round(pr, 3), "n_elites": len(elites), "level": level, "U": round(U, 3),
                          "expected_size": round(float(q.sum()), 1), "map_size": len(map_now), "mean_sample_size": round(float(sizes.mean()), 1),
                          "n_exonerations": n_ex})
            prev_map.append(map_now)
            if it + 1 >= int(cfg["min_iterations"]) and pr >= 0.5:
                if U < float(cfg["u_stop"]):
                    trace[-1]["stopped"] = "converged"
                    break
                if len(prev_map) >= 3 and prev_map[-1] == prev_map[-2] == prev_map[-3] and pr >= 0.6 and U < 2.0:
                    trace[-1]["stopped"] = "map_stable"
                    break
        return q

    # ------------------------------------------------------------------------------------------ cleanup helpers
    def _pick_start(self, problem, runner: _Runner, map_set: list[int], history: list[dict], seeds: list[int], allowance):
        """The set to minimise: the MAP set if it passes the seed ensemble, else the best passing sample of the search."""
        if map_set:
            outs = runner.run([SimQuery(keep_only(problem, map_set), s) for s in seeds], "cleanup", allowance("cleanup"))
            if outs is not None and _pass_fraction(outs) >= 0.5:
                return sorted(map_set), _pass_fraction(outs), "map"
        passing = sorted((h for h in history if h["passed"]), key=lambda h: (-h["fit"], h["size"]))
        best, best_pf = None, -1.0
        for h in passing[:3]:
            members = sorted(int(x) for x in h["members"])
            outs = runner.run([SimQuery(keep_only(problem, members), s) for s in seeds], "cleanup", allowance("cleanup"))
            if outs is None:
                break
            pf = _pass_fraction(outs)
            if pf > best_pf:
                best, best_pf = members, pf
            if pf >= 0.5:
                break
        if best is not None and best_pf >= 0.5:
            return best, best_pf, "best_sample"
        if best is not None and not map_set:
            return best, best_pf, "best_sample_fragile"
        if map_set:
            return sorted(map_set), 0.0, "map_fragile"
        return (best or []), max(best_pf, 0.0), "best_sample_fragile"

    def _minimize(self, problem, runner: _Runner, S: Sequence[int], qmap: dict[int, float], seeds: list[int], stage: str, allowance):
        """ddmin-style backward elimination in ascending-q order. Chunks halve on failure; a single element whose removal
        fails is necessary (within the current set). Every removal must pass on ALL test seeds."""
        pending = sorted((int(p) for p in S), key=lambda p: (qmap.get(p, 0.0), p))
        core = list(pending)
        necessary: list[int] = []
        removed_single: list[int] = []
        removed_chunk: list[int] = []
        n_tests = 0
        stopped = None
        c = max(1, len(pending) // 2)
        while pending:
            c = max(1, min(c, len(pending)))
            chunk = pending[:c]
            chunk_set = set(chunk)
            trial = [p for p in core if p not in chunk_set]
            allow = allowance(stage)
            if allow < len(seeds):
                stopped = "budget"
                break
            outs = runner.run([SimQuery(keep_only(problem, trial), s) for s in seeds], stage, allow)
            if outs is None:
                stopped = "budget"
                break
            n_tests += 1
            if all(o.passed for o in outs):
                core = trial
                pending = pending[c:]
                (removed_single if c == 1 else removed_chunk).extend(chunk)
                c = min(c * 2, max(1, len(pending)))
            elif c == 1:
                necessary.append(chunk[0])
                pending = pending[1:]
            else:
                c //= 2
        return sorted(core), removed_single, removed_chunk, {"n_tests": n_tests, "necessary": necessary, "untested": pending, "stopped": stopped,
                                                             "start_size": len(S), "final_size": len(core)}

    # ------------------------------------------------------------------------------------------ interpretation
    def _core_structure(self, problem, members: list[int]) -> dict:
        W = problem.W
        signs = problem.signs
        m = list(members)
        n_c = len(m)
        info: dict = {}
        if n_c == 0:
            return info
        sub = W[np.ix_(m, m)].toarray()
        adj = sp.csr_matrix((sub != 0).astype(np.int8))
        _, labels = connected_components(adj, directed=True, connection="strong")
        counts = np.bincount(labels)
        ro = problem.readout_positions
        n_ro = max(1, len(ro))
        crit = problem.criterion_spec
        ga = [int(p) for p in crit.get("group_a_positions", [])]
        gb = [int(p) for p in crit.get("group_b_positions", [])]
        Wro = W[ro, :][:, m].toarray() if len(ro) else np.zeros((0, n_c))
        Wa = W[ga, :][:, m].toarray() if ga else np.zeros((0, n_c))
        Wb = W[gb, :][:, m].toarray() if gb else np.zeros((0, n_c))
        Wst = W[m, :][:, list(problem.stim_positions)].toarray()
        for j, p in enumerate(m):
            comp_size = int(counts[labels[j]])
            self_loop = sub[j, j] != 0
            exc_targets_in_core = [m[i] for i in range(n_c) if i != j and sub[i, j] != 0]
            info[p] = {"sign": int(signs[p]), "self_loop": bool(self_loop), "on_cycle": bool(comp_size >= 2 or self_loop), "scc_size": comp_size,
                       "to_readout_frac": float((Wro[:, j] > 0).sum() / n_ro), "to_readout_inh_frac": float((Wro[:, j] < 0).sum() / n_ro),
                       "to_group_a": float((Wa[:, j] > 0).sum()) if ga else 0.0, "to_group_b": float((Wb[:, j] > 0).sum()) if gb else 0.0,
                       "from_stim": bool((Wst[j] > 0).any()), "to_core": [int(x) for x in exc_targets_in_core],
                       "to_core_exc": bool(any(signs[x] > 0 for x in exc_targets_in_core))}
        return info

    def _roles(self, problem, core: list[int], alternatives: list[set[int]], incl: dict[int, float], add_backs: list[int]) -> dict:
        crit = str(problem.criterion_spec.get("type", "rhythm"))
        roles: dict[int, tuple[str, float]] = {}
        info = self._core_structure(problem, core)
        for p in core:
            if p in add_backs:
                roles[p] = ("modulatory_supporting", 0.5)
                continue
            s = info[p]
            exc, inh = s["sign"] > 0, s["sign"] < 0
            clear = True
            if crit == "selectivity":
                if exc and (s["to_group_a"] > 0 or s["to_group_b"] > 0):
                    role = "output_driver" if s["to_group_a"] >= s["to_group_b"] else "competitor"
                elif inh:
                    role = "lateral_inhibition"
                else:
                    role, clear = "input_relay", False
            elif crit in ("persistence", "ramp"):
                if exc and s["on_cycle"]:
                    role = "state_memory"
                elif exc:
                    role = "output_driver" if s["to_readout_frac"] > 0 else "input_relay"
                else:
                    role, clear = "gain_control", inh
            elif crit == "activity_band":
                if inh:
                    role = "gain_control"
                elif exc and s["to_readout_frac"] > 0:
                    role = "output_driver"
                else:
                    role, clear = "input_relay", exc
            else:  # rhythm and anything else
                if inh and s["on_cycle"]:
                    role = "inhibitory_feedback"
                elif inh:
                    role, clear = ("gain_control" if s["to_readout_inh_frac"] > 0 else "inhibitory_feedback"), False
                elif exc and s["on_cycle"]:
                    role = "recurrent_excitatory_core" if (s["self_loop"] or s["to_readout_frac"] > 0 or s["from_stim"]) else "input_relay"
                elif exc and s["to_readout_frac"] > 0:
                    role = "output_driver"
                elif exc:
                    role = "input_relay"
                else:
                    role, clear = "unknown", False
            if role not in GENERIC_ROLES:
                role, clear = "unknown", False
            prob = (0.75 if clear else 0.55) * (0.6 + 0.4 * float(incl.get(p, 0.5)))
            roles[p] = (role, float(np.clip(prob, 0.05, 0.95)))
        for alt in alternatives:
            for p in sorted(alt):
                if p not in roles:
                    roles[p] = ("redundant_backup", 0.5)
        return roles

    def _loop(self, problem, core: list[int]) -> list[int]:
        if not core:
            return []
        m = list(core)
        sub = problem.W[np.ix_(m, m)].toarray()
        adj = sp.csr_matrix((sub != 0).astype(np.int8))
        _, labels = connected_components(adj, directed=True, connection="strong")
        counts = np.bincount(labels)
        big = int(np.argmax(counts))
        if counts[big] >= 2:
            return sorted(int(m[j]) for j in range(len(m)) if labels[j] == big)
        selfs = [int(m[j]) for j in range(len(m)) if sub[j, j] != 0]
        return selfs[:1]

    def _motif(self, problem, core: list[int], loop: list[int], roles: dict) -> str:
        if not core:
            return "no interneuron mechanism found (readout driven directly or search failed)"
        signs = problem.signs
        n_e = sum(1 for p in core if signs[p] > 0)
        n_i = sum(1 for p in core if signs[p] < 0)
        role_counts: dict[str, int] = {}
        for p in core:
            r = roles.get(p, ("unknown", 0.0))[0]
            role_counts[r] = role_counts.get(r, 0) + 1
        parts = [f"{len(core)} interneurons ({n_e}E/{n_i}I)"]
        parts.append(f"recurrent loop of {len(loop)}" if len(loop) >= 2 else ("self-excitatory unit" if len(loop) == 1 else "feedforward (no recurrence)"))
        parts.append("roles: " + ", ".join(f"{k} x{v}" for k, v in sorted(role_counts.items())))
        parts.append(f"criterion {problem.criterion_spec.get('type')}")
        return "; ".join(parts)
