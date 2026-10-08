"""Render the README figures (docs/figures/*.svg) from BrainIR's logged result records.

    python scripts/make_readme_figures.py

writes, in a light and a dark variant (the README picks one through `<picture>` / prefers-color-scheme):

    docs/figures/phase1_reproduction{,_dark}.svg   published model vs BrainIR: perturbation responses and the weight-noise curve
    docs/figures/phase2_reliability{,_dark}.svg    BrainIR v1.2 vs frozen simulation-guided pruning: keep-only validation per run
                                                   and simulator queries per run

Inputs (read only). Only aggregate rhythm scores, pass / fail outcomes and query counts are drawn; no neuron id, position, cell
type or core membership enters a figure.

    benchmarks/dng100_walking_cpg/results/interventions_{manc_v1.2.1,male-cns_v1.0}_nt-paper_n64.json
    benchmarks/dng100_walking_cpg/results/robust_weight_noise_manc_v1.2.1_nt-paper_n64.json
    research/phase2/reliability/{v12,greedy_frozen}_<network>.json    (keep-only fidelity on fresh draws and simulator calls)

Standard library only. The output is deterministic: a fixed bootstrap seed and no timestamps, so re-running reproduces the files
byte for byte.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from statistics import fmean
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "benchmarks" / "dng100_walking_cpg" / "results"
RELIABILITY = ROOT / "research" / "phase2" / "reliability"
OUT = ROOT / "docs" / "figures"

# Published intact-network means (Pugliese et al., bioRxiv 10.1101/2025.09.12.675944). The intervention records carry the published
# silencing means themselves; the intact means are the paper's stimulation statistics.
PUBLISHED_INTACT = {"manc_v1.2.1": 0.974, "male-cns_v1.0": 0.985}
NETWORKS = (("manc_v1.2.1", "MANC v1.2.1", ""),
            ("manc_v1.2.3", "MANC v1.2.3", "re-annotated snapshot of the same reconstruction"),
            ("male-cns_v1.0", "MaleCNS v1.0", "independent reconstruction, second animal"))
BOOT = 5000
SEED = 20261008

FONT = "system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
THEMES = {
    # chart tokens of the dataviz reference palette: surface, ink, secondary ink, gridline, axis, accent (series 1), de-emphasis gray
    "light": {"surface": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "grid": "#e1e0d9", "axis": "#c3c2b7", "accent": "#2a78d6",
              "gray": "#898781", "border": "#0b0b0b"},
    "dark": {"surface": "#1a1a19", "ink": "#ffffff", "ink2": "#c3c2b7", "grid": "#2c2c2a", "axis": "#383835", "accent": "#3987e5",
             "gray": "#898781", "border": "#ffffff"},
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _boot_ci(values: list[float], rng: random.Random) -> tuple[float, float]:
    """Percentile bootstrap 95 % interval of the mean."""
    n = len(values)
    means = sorted(fmean(rng.choices(values, k=n)) for _ in range(BOOT))
    return means[int(0.025 * BOOT)], means[int(0.975 * BOOT) - 1]


def _num(x: float, digits: int = 3) -> str:
    return f"{x:.{digits}f}"


class Svg:
    def __init__(self, width: int, height: int, theme: str, title: str, desc: str):
        self.w, self.h, self.c = width, height, THEMES[theme]
        self.title, self.desc = title, desc
        self.parts: list[str] = []

    def col(self, token: str) -> str:
        return self.c.get(token, token)

    def text(self, x: float, y: float, s: str, *, size: float = 12, fill: str = "ink", anchor: str = "start", weight: int = 400,
             tabular: bool = False) -> None:
        style = "font-variant-numeric:tabular-nums" if tabular else None
        attrs = f' style="{style}"' if style else ""
        self.parts.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" fill="{self.col(fill)}" '
                          f'text-anchor="{anchor}"{attrs}>{escape(s)}</text>')

    def line(self, x1: float, y1: float, x2: float, y2: float, *, stroke: str = "grid", width: float = 1, cap: str = "butt",
             opacity: float = 1.0) -> None:
        op = f' stroke-opacity="{opacity}"' if opacity < 1 else ""
        self.parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{self.col(stroke)}" '
                          f'stroke-width="{width}" stroke-linecap="{cap}"{op}/>')

    def dot(self, x: float, y: float, r: float, *, fill: str, ring: float = 2.0, opacity: float = 1.0) -> None:
        op = f' fill-opacity="{opacity}"' if opacity < 1 else ""
        self.parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{self.col(fill)}"{op} stroke="{self.col("surface")}" '
                          f'stroke-width="{ring}"/>')

    def ring(self, x: float, y: float, r: float, *, stroke: str = "gray", width: float = 2.0) -> None:
        self.parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="none" stroke="{self.col(stroke)}" stroke-width="{width}"/>')

    def square(self, x: float, y: float, size: float, *, fill: str | None, stroke: str | None = None, width: float = 1.5) -> None:
        if fill is not None:
            self.parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{size}" height="{size}" rx="2" fill="{self.col(fill)}"/>')
        else:
            inset = width / 2
            self.parts.append(f'<rect x="{x + inset:.1f}" y="{y + inset:.1f}" width="{size - width}" height="{size - width}" rx="2" '
                              f'fill="none" stroke="{self.col(stroke or "gray")}" stroke-width="{width}"/>')

    def polyline(self, pts: list[tuple[float, float]], *, stroke: str, width: float = 2.0) -> None:
        p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        self.parts.append(f'<polyline points="{p}" fill="none" stroke="{self.col(stroke)}" stroke-width="{width}" '
                          f'stroke-linejoin="round" stroke-linecap="round"/>')

    def polygon(self, pts: list[tuple[float, float]], *, fill: str, opacity: float) -> None:
        p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        self.parts.append(f'<polygon points="{p}" fill="{self.col(fill)}" fill-opacity="{opacity}" stroke="none"/>')

    def render(self) -> str:
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" '
                f'role="img" aria-labelledby="t d" font-family="{FONT}">\n'
                f'<title id="t">{escape(self.title)}</title>\n<desc id="d">{escape(self.desc)}</desc>\n'
                f'<rect x="0.5" y="0.5" width="{self.w - 1}" height="{self.h - 1}" rx="10" fill="{self.col("surface")}" '
                f'stroke="{self.col("border")}" stroke-opacity="0.10"/>\n')
        return head + "\n".join(self.parts) + "\n</svg>\n"


# ----------------------------------------------------------------------------------------------------------------- Phase 1
def phase1_data() -> dict:
    rng = random.Random(SEED)
    rows = []
    for net, name, slots in (("manc_v1.2.1", "MANC v1.2.1", ("E1", "E2", "I1")), ("male-cns_v1.0", "MaleCNS v1.0", ("E1", "E2", "I2"))):
        rec = _load(RESULTS / f"interventions_{net}_nt-paper_n64.json")
        published = rec["paper_reference"]["silencing"]
        group = []
        for label, key, ref in [("Intact network", "intact", PUBLISHED_INTACT[net])] + [
                (f"Silence {s}", f"silence_{s}", published[s]["mean_score"]) for s in slots]:
            scores = [float(v) for v in rec["conditions"][key]["scores"]]
            lo, hi = _boot_ci(scores, rng)
            group.append({"label": label, "brainir": fmean(scores), "lo": lo, "hi": hi, "published": float(ref), "n": len(scores)})
        rows.append((name, group))
    wn = _load(RESULTS / "robust_weight_noise_manc_v1.2.1_nt-paper_n64.json")
    curve = []
    for cond in wn["conditions"]:
        sigma = float(cond["weight_noise_sd"])
        scores = [float(r["score"]) for r in cond["replicates"]]
        lo, hi = _boot_ci(scores, rng)
        ref = wn["paper_reference"]["mean_score_by_sigma"][str(sigma)]
        curve.append({"sigma": sigma, "brainir": fmean(scores), "lo": lo, "hi": hi, "published": float(ref), "n": len(scores)})
    return {"rows": rows, "curve": curve}


def phase1_figure(data: dict, theme: str) -> str:
    max_dev = max(abs(r["brainir"] - r["published"]) for _, g in data["rows"] for r in g)
    s = Svg(960, 424, theme, "Phase 1: published walking-circuit model vs BrainIR's independent reproduction",
            "Panel a: mean rhythm score of the intact network and of single-neuron silencing in MANC v1.2.1 and MaleCNS v1.0, "
            f"BrainIR (mean with 95% bootstrap interval, 64 parameter draws) against the published model; largest deviation "
            f"{max_dev:.3f}. Panel b: mean rhythm score under multiplicative synapse-count noise, BrainIR (64 draws per level) "
            "against the published curve (512 draws per level).")
    s.text(24, 36, "Phase 1 · independent reproduction of the published walking-circuit model", size=15, weight=600)
    s.dot(664, 31, 4.5, fill="accent")
    s.text(675, 35, "BrainIR (mean, 95% CI)", size=12, fill="ink2")
    s.ring(830, 31, 4.5)
    s.text(841, 35, "published model", size=12, fill="ink2")

    # a: perturbation responses
    x0, x1, top, bottom = 200.0, 448.0, 118.0, 340.0

    def sx(v: float) -> float:
        return x0 + v * (x1 - x0)

    s.text(24, 70, "a", size=13, weight=700)
    s.text(40, 70, "Perturbation responses", size=13, weight=600)
    s.text(40, 88, "mean rhythm score · 64 parameter draws per condition", size=11.5, fill="ink2")
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        s.line(sx(t), top, sx(t), bottom, stroke="grid")
        s.text(sx(t), bottom + 18, f"{t:g}", size=11, fill="ink2", anchor="middle", tabular=True)
    s.line(x0, bottom, x1, bottom, stroke="axis")
    s.text((x0 + x1) / 2, bottom + 38, "mean rhythm score", size=11.5, fill="ink2", anchor="middle")
    s.text(506, 112, "BrainIR", size=11, fill="ink2", anchor="end", weight=600)
    s.text(580, 112, "published", size=11, fill="ink2", anchor="end", weight=600)
    y = 136.0
    for name, group in data["rows"]:
        s.text(24, y, name, size=12, weight=600)
        y += 22
        for r in group:
            s.text(40, y + 4, r["label"], size=12, fill="ink2")
            s.ring(sx(r["published"]), y, 4.5)
            s.line(sx(r["lo"]), y, sx(r["hi"]), y, stroke="accent", width=2, cap="round")
            s.dot(sx(r["brainir"]), y, 4.5, fill="accent")
            s.text(506, y + 4, _num(r["brainir"]), size=11.5, anchor="end", tabular=True)
            s.text(580, y + 4, _num(r["published"]), size=11.5, fill="ink2", anchor="end", tabular=True)
            y += 22
        y += 10

    # b: weight-noise dose-response
    bx0, bx1 = 682.0, 926.0

    def bx(sig: float) -> float:
        return bx0 + sig / 0.5 * (bx1 - bx0)

    def by(v: float) -> float:
        return bottom - v * (bottom - top)

    s.text(616, 70, "b", size=13, weight=700)
    s.text(632, 70, "Synapse-count noise (MANC v1.2.1)", size=13, weight=600)
    s.text(632, 88, "BrainIR 64 draws per level · published 512", size=11.5, fill="ink2")
    for v in (0.0, 0.25, 0.5, 0.75, 1.0):
        s.line(bx0, by(v), bx1, by(v), stroke="grid")
        s.text(bx0 - 10, by(v) + 4, f"{v:g}", size=11, fill="ink2", anchor="end", tabular=True)
    for sig in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5):
        s.text(bx(sig), bottom + 18, f"{sig:g}", size=11, fill="ink2", anchor="middle", tabular=True)
    s.line(bx0, bottom, bx1, bottom, stroke="axis")
    s.text((bx0 + bx1) / 2, bottom + 38, "multiplicative noise σ on synapse counts", size=11.5, fill="ink2", anchor="middle")
    curve = data["curve"]
    band = [(bx(c["sigma"]), by(c["hi"])) for c in curve] + [(bx(c["sigma"]), by(c["lo"])) for c in reversed(curve)]
    s.polygon(band, fill="accent", opacity=0.12)
    s.polyline([(bx(c["sigma"]), by(c["published"])) for c in curve], stroke="gray")
    s.polyline([(bx(c["sigma"]), by(c["brainir"])) for c in curve], stroke="accent")
    for c in curve:
        s.dot(bx(c["sigma"]), by(c["brainir"]), 4.5, fill="accent")
    for c in curve:
        s.ring(bx(c["sigma"]), by(c["published"]), 4.5)

    s.text(24, 410, "Generated by scripts/make_readme_figures.py from BrainIR's logged runs · published values: Pugliese et al. (2025)",
           size=10.5, fill="ink2")
    return s.render()


# ----------------------------------------------------------------------------------------------------------------- Phase 2
def phase2_data() -> list[dict]:
    blocks = []
    for net, name, note in NETWORKS:
        methods = {}
        for key, label in (("v12", "BrainIR v1.2"), ("greedy_frozen", "Frozen pruning")):
            rec = _load(RELIABILITY / f"{key}_{net}.json")
            runs = sorted(rec["runs"], key=lambda r: (int(str(r["variant"]).removeprefix("order")), int(r["seed"])))
            if len(runs) != 24:
                raise SystemExit(f"{key}_{net}: expected 24 runs, found {len(runs)}")
            methods[key] = {"label": label, "pass": [float(r["functional_fidelity"]) >= 0.5 for r in runs],
                            "calls": [int(r["calls"]) for r in runs]}
        blocks.append({"name": name, "note": note, "methods": methods})
    return blocks


def phase2_figure(blocks: list[dict], theme: str) -> str:
    tot = {k: sum(sum(b["methods"][k]["pass"]) for b in blocks) for k in ("v12", "greedy_frozen")}
    s = Svg(960, 382, theme, "Phase 2: BrainIR v1.2 vs frozen simulation-guided pruning on identical node orders and parameter seeds",
            f"Panel a: for each of 3 network builds and 24 runs (8 node orders x 3 seeds), whether the returned mechanism passes "
            f"keep-only validation on fresh parameter draws; BrainIR v1.2 {tot['v12']} of 72, frozen pruning {tot['greedy_frozen']} of 72. "
            "Panel b: simulator queries per run with the mean per method and build.")
    s.text(24, 36, "Phase 2 · BrainIR v1.2 vs frozen simulation-guided pruning", size=15, weight=600)
    s.square(686, 25, 11, fill="accent")
    s.text(702, 35, "pass", size=12, fill="ink2")
    s.square(744, 25, 11, fill=None, stroke="gray")
    s.text(760, 35, "fail", size=12, fill="ink2")
    s.text(796, 35, "(keep-only on fresh draws)", size=12, fill="ink2")

    cell, gap, ogap, gx0 = 11.0, 3.0, 7.0, 196.0

    def cx(i: int) -> float:
        return gx0 + i * (cell + gap) + (i // 3) * ogap

    gx1 = cx(23) + cell
    s.text(24, 70, "a", size=13, weight=700)
    s.text(40, 70, "Fresh keep-only validation, 72 paired runs", size=13, weight=600)
    s.text(40, 88, "identical node orders and seeds · pass = rhythmic on at least 4 of 8 fresh parameter draws", size=11.5, fill="ink2")

    px0, px1, pmax = 676.0, 896.0, 1100.0

    def px(v: float) -> float:
        return px0 + v / pmax * (px1 - px0)

    s.text(616, 70, "b", size=13, weight=700)
    s.text(632, 70, "Simulator queries per run", size=13, weight=600)
    s.text(632, 88, "dots: 24 runs · tick: mean", size=11.5, fill="ink2")
    s.text(940, 88, "mean", size=11, fill="ink2", anchor="end", weight=600)

    y = 118.0
    rows_top = y - 8
    row_ys = []
    for b in blocks:
        s.text(24, y, b["name"], size=12, weight=600)
        if b["note"]:
            s.text(24 + 8 * len(b["name"]) + 10, y, b["note"], size=11, fill="ink2")
        y += 8
        for key in ("v12", "greedy_frozen"):
            m = b["methods"][key]
            colour = "accent" if key == "v12" else "gray"
            s.text(40, y + cell - 1, m["label"], size=12, fill="ink" if key == "v12" else "ink2")
            for i, ok in enumerate(m["pass"]):
                s.square(cx(i), y, cell, fill=colour if ok else None, stroke=colour)
            s.text(gx1 + 14, y + cell - 1, f"{sum(m['pass'])} / 24", size=11.5, fill="ink" if key == "v12" else "ink2", tabular=True)
            row_ys.append((y + cell / 2, key, m))
            y += cell + 6
        y += 22
    rows_bottom = y - 22 + 4
    for o in range(8):
        s.text((cx(3 * o) + cx(3 * o + 2) + cell) / 2, rows_bottom + 14, str(o), size=11, fill="ink2", anchor="middle", tabular=True)
    s.text((gx0 + gx1) / 2, rows_bottom + 32, "node order (3 parameter seeds each)", size=11.5, fill="ink2", anchor="middle")
    s.line(gx1 + 12, rows_bottom + 6, gx1 + 66, rows_bottom + 6, stroke="axis")
    s.text(gx1 + 14, rows_bottom + 22, f"{tot['v12']} / 72", size=11.5, weight=600, tabular=True)
    s.text(gx1 + 14, rows_bottom + 38, f"{tot['greedy_frozen']} / 72", size=11.5, fill="ink2", tabular=True)

    for t in (0, 250, 500, 750, 1000):
        s.line(px(t), rows_top, px(t), rows_bottom, stroke="grid")
        s.text(px(t), rows_bottom + 14, f"{t:,}", size=11, fill="ink2", anchor="middle", tabular=True)
    s.line(px0, rows_bottom, px1, rows_bottom, stroke="axis")
    s.text((px0 + px1) / 2, rows_bottom + 32, "simulator queries", size=11.5, fill="ink2", anchor="middle")
    for yc, key, m in row_ys:
        colour = "accent" if key == "v12" else "gray"
        for c in m["calls"]:
            s.dot(px(c), yc, 3.5, fill=colour, ring=1.5, opacity=0.55)
        mean = fmean(m["calls"])
        s.line(px(mean), yc - 7, px(mean), yc + 7, stroke="ink", width=2, cap="round")
        s.text(940, yc + 4, f"{mean:,.0f}", size=11.5, fill="ink" if key == "v12" else "ink2", anchor="end", tabular=True)

    s.text(24, 368, "Generated by scripts/make_readme_figures.py from the logged reliability sweeps (keep-only checks on fresh draws, "
                    "simulator query counts)", size=10.5, fill="ink2")
    return s.render()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    p1, p2 = phase1_data(), phase2_data()
    for theme, suffix in (("light", ""), ("dark", "_dark")):
        (OUT / f"phase1_reproduction{suffix}.svg").write_text(phase1_figure(p1, theme), encoding="utf-8", newline="\n")
        (OUT / f"phase2_reliability{suffix}.svg").write_text(phase2_figure(p2, theme), encoding="utf-8", newline="\n")
    dev = max(abs(r["brainir"] - r["published"]) for _, g in p1["rows"] for r in g)
    print(f"phase 1: {sum(len(g) for _, g in p1['rows'])} perturbation conditions, largest |BrainIR - published| = {dev:.3f}; "
          f"{len(p1['curve'])} noise levels")
    for b in p2:
        v, g = b["methods"]["v12"], b["methods"]["greedy_frozen"]
        print(f"phase 2: {b['name']:13s} pass {sum(v['pass'])}/24 vs {sum(g['pass'])}/24; mean queries {fmean(v['calls']):.0f} vs "
              f"{fmean(g['calls']):.0f}")
    print(f"wrote {OUT.relative_to(ROOT)}/phase1_reproduction{{,_dark}}.svg and phase2_reliability{{,_dark}}.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
