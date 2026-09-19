"""Build every chart, map and table for the README.   python -m src.make_outputs   (about 1-2 minutes, offline)

All hub-model numbers come from the exact solver (PuLP) except the GA convergence and validation charts.
Every MOZAIQ number is simulated or a placeholder (config.yaml): these outputs are illustrative, not MOZAIQ data.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

from src.config import ROOT, load_config
from src.hub_ga import SELECTION, run_ga
from src.hub_map import hub_map
from src.hub_model import describe
from src.sensitivity import solve_with

OUT = ROOT / "outputs"
INK, MUTED, SURFACE, GRID, EDGE = "#0b0b0b", "#52514e", "#fcfcfb", "#e4e3df", "#c9c8c2"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"  # categorical slots 1-3 (colour-blind checked with the dataviz validator)
BLUE_RAMP = LinearSegmentedColormap.from_list("blue", ["#eef4fc", "#c5dbf5", "#8dbbec", "#4f93e0", "#2a78d6", "#1c5aa6", "#123e78"])
GREEN_RAMP = LinearSegmentedColormap.from_list("green", ["#eaf7f1", "#bfe9d9", "#84d3b8", "#3fba94", "#1b8f68", "#0f6248", "#0a4432"])
SCENARIOS = ("current", "expansion")
NOTE = "SIMULATED villas, PLACEHOLDER costs: not MOZAIQ data"


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.tick_params(colors=MUTED)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(EDGE)


def savefig(fig, path):
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def cell_text_color(cmap, value, vmax):
    r, g, b, _ = cmap(value / vmax if vmax else 0)
    return "white" if 0.299 * r + 0.587 * g + 0.114 * b < 0.55 else INK


# ---------------------------------------------------------------- heatmaps

def draw_grid(ax, values, texts, cmap, xlabels, ylabels, base=None, edge_of=None):
    """values: 2D array shaded with a one-hue ramp; texts: matching strings printed in the cells (never colour alone)."""
    vmax = np.nanmax(values)
    ax.imshow(values, cmap=cmap, vmin=0, vmax=vmax, aspect="auto")
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, texts[i][j], ha="center", va="center", fontsize=9, color=cell_text_color(cmap, values[i, j], vmax))
    ax.set_xticks(range(len(xlabels)), xlabels, fontsize=8)
    ax.set_yticks(range(len(ylabels)), ylabels, fontsize=9)
    ax.tick_params(length=0, colors=MUTED)
    for s in ax.spines.values():
        s.set_visible(False)
    if edge_of is not None:  # thick line between cells where "at least one hub is built" changes
        on = edge_of > 0
        for i in range(on.shape[0]):
            for j in range(on.shape[1]):
                if j + 1 < on.shape[1] and on[i, j] != on[i, j + 1]:
                    ax.plot([j + .5, j + .5], [i - .5, i + .5], color=INK, lw=2.5)
                if i + 1 < on.shape[0] and on[i, j] != on[i + 1, j]:
                    ax.plot([j - .5, j + .5], [i + .5, i + .5], color=INK, lw=2.5)
    if base is not None:
        ax.add_patch(plt.Rectangle((base[1] - .5, base[0] - .5), 1, 1, fill=False, ec=INK, lw=2, ls=(0, (3, 2))))


def heatmap_breakeven(vendor_mults, round_trips, path, cfg=None):
    cfg = cfg or load_config()
    fee = cfg["v2"]["vendor"]["cost_per_turnover_krw"]["mainland"]
    fig, axes = plt.subplots(2, 2, figsize=(13, 8.6), facecolor=SURFACE)
    grids = {}
    for row, sc in enumerate(SCENARIOS):
        res = [[solve_with(sc, cfg, vendor_multiplier=m, round_trips=rt) for m in vendor_mults] for rt in round_trips]
        hubs = np.array([[r["n_hubs"] for r in line] for line in res], dtype=float)
        cost = np.array([[r["cost"] / 1e6 for r in line] for line in res])
        grids[sc] = hubs
        base = (round_trips.index(cfg["v2"]["costs"]["van_round_trips_per_turnover"]), vendor_mults.index(1.0))
        xl = [f"x{m:g}\n{fee * m / 1000:.1f}k" for m in vendor_mults]
        yl = [f"{rt:g}" for rt in round_trips]
        draw_grid(axes[row, 0], hubs, [[f"{int(h)}" for h in line] for line in hubs], BLUE_RAMP, xl, yl, base, edge_of=hubs)
        draw_grid(axes[row, 1], cost, [[f"{r['cost'] / 1e6:.2f}" + (f"\n-{r['saving_pct']:.0f}%" if r["saving_pct"] >= 0.5 else "") for r in line]
                                       for line in res], GREEN_RAMP, xl, yl, base, edge_of=hubs)
        axes[row, 0].set_title(f"{sc}: hubs opened in the optimum", loc="left", color=INK, fontsize=11)
        axes[row, 1].set_title(f"{sc}: weekly cost, M KRW (and change vs outsourcing everything)", loc="left", color=INK, fontsize=11)
        for ax in axes[row]:
            ax.set_ylabel("van round trips per turnover\n(lower = more batching)", color=MUTED, fontsize=9)
        if row == 1:
            for ax in axes[row]:
                ax.set_xlabel("vendor fee multiplier (and mainland fee per turnover, KRW)", color=MUTED, fontsize=9)
    fig.suptitle("When does building hubs beat outsourcing?  Exact optimum for each pair of assumptions", color=INK, fontsize=13, x=0.01, ha="left")
    fig.text(0.01, 0.005, f"Dashed box = base assumptions. Thick line = edge of the region where at least one hub is built. {NOTE}.", color=MUTED, fontsize=9)
    fig.tight_layout(rect=(0, 0.02, 1, 0.96))
    savefig(fig, path)
    return grids


def heatmap_rent_turnovers(rents, scales, path, cfg=None):
    cfg = cfg or load_config()
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.6), facecolor=SURFACE)
    for ax, sc in zip(axes, SCENARIOS):
        hubs = np.array([[solve_with(sc, cfg, turnover_scale=s, rent_multiplier=r)["n_hubs"] for r in rents] for s in scales], dtype=float)
        draw_grid(ax, hubs, [[f"{int(h)}" for h in line] for line in hubs], BLUE_RAMP, [f"x{r:g}" for r in rents], [f"x{s:g}" for s in scales],
                  base=(scales.index(1.0), rents.index(1.0)), edge_of=hubs)
        ax.set_title(f"{sc}: hubs opened", loc="left", color=INK, fontsize=11)
        ax.set_xlabel("hub rent multiplier", color=MUTED, fontsize=9)
        ax.set_ylabel("turnovers per week multiplier", color=MUTED, fontsize=9)
    fig.suptitle("Sensitivity of the chosen network to rent and turnovers per week (exact optimum)", color=INK, fontsize=12, x=0.01, ha="left")
    fig.text(0.01, 0.005, f"Dashed box = base. Thick line = edge of the region where at least one hub is built. Turnovers x2 or more can exceed hub capacity. {NOTE}.",
             color=MUTED, fontsize=8.5)
    fig.tight_layout(rect=(0, 0.03, 1, 0.93))
    savefig(fig, path)


# ---------------------------------------------------------------- line and bar charts

def chart_surcharge(surcharges, path, cfg=None):
    cfg = cfg or load_config()
    van = 2 * cfg["v2"]["costs"]["van_cost_per_km_krw"] * cfg["v2"]["costs"]["van_round_trips_per_turnover"]  # in-house van, KRW per turnover per km
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.4), facecolor=SURFACE)
    for sc, color in zip(SCENARIOS, (BLUE, ORANGE)):
        res = [solve_with(sc, cfg, surcharge=s) for s in surcharges]
        for ax, key, scale in ((axes[0], "n_hubs", 1), (axes[1], "cost", 1e6)):
            ys = [r[key] / scale for r in res]
            ax.plot(surcharges, ys, color=color, lw=2, marker="o", ms=5, label=sc)
            ax.annotate(f"{sc} {ys[-1]:.0f}" if key == "n_hubs" else f"{sc} {ys[-1]:.1f}", (surcharges[-1], ys[-1]), xytext=(6, 0),
                        textcoords="offset points", color=INK, fontsize=9, va="center")
    for ax, title, yl, note_y in ((axes[0], "Hubs opened", "hubs", 0.04), (axes[1], "Weekly cost", "M KRW per week", 0.32)):  # note_y: empty band for the note
        style(ax)
        ax.axvline(van, color=MUTED, ls="--", lw=1)
        lo, hi = ax.get_ylim()
        ax.text(van - 15, lo + note_y * (hi - lo), "in-house van costs\nabout this per km", color=MUTED, fontsize=8, va="bottom", ha="right")
        ax.set_title(title, loc="left", color=INK, fontsize=11)
        ax.set_xlabel("vendor distance surcharge, KRW per turnover per km from the nearest town", color=MUTED, fontsize=9)
        ax.set_ylabel(yl, color=MUTED, fontsize=9)
        ax.set_xlim(right=surcharges[-1] * 1.3)
        ax.grid(axis="y", color=GRID, lw=0.7)
        ax.legend(frameon=False, labelcolor=INK, fontsize=9, loc="upper left")
    fig.suptitle("Does a distance-priced vendor pull remote villas in-house? (limitation D33, one assumption varied)", color=INK, fontsize=12, x=0.01, ha="left")
    fig.text(0.01, 0.005, NOTE + ".", color=MUTED, fontsize=8.5)
    fig.tight_layout(rect=(0, 0.03, 1, 0.93))
    savefig(fig, path)


def chart_cost_breakdown(base, path):
    parts = (("transport", "van transport", BLUE), ("vendor", "vendor fees", ORANGE), ("fixed", "hub rent", AQUA))
    bars = []  # (x position, label, dict of parts)
    for k, sc in enumerate(SCENARIOS):
        b = base[sc]
        bars.append((k * 3, f"{sc}\noutsource everything", {"transport": 0, "vendor": b["all_outsourced"], "fixed": 0}))
        bars.append((k * 3 + 1.1, f"{sc}\noptimal ({b['n_hubs']} hubs)", b["parts"]))
    fig, ax = plt.subplots(figsize=(10, 5.2), facecolor=SURFACE)
    style(ax)
    top = max(sum(p.values()) for _, _, p in bars) / 1e6
    for x, _, p in bars:
        bottom = 0
        for key, _, color in parts:
            v = p[key] / 1e6
            if v <= 0:
                continue
            ax.bar(x, v, bottom=bottom, width=0.9, color=color, edgecolor=SURFACE, linewidth=2)
            if v > 0.06 * top:
                ax.text(x, bottom + v / 2, f"{v:.2f}", ha="center", va="center", color="white" if color == BLUE else INK, fontsize=9)
            bottom += v
        ax.text(x, bottom + 0.01 * top, f"{bottom:.2f}", ha="center", va="bottom", color=INK, fontsize=10)
    ax.set_xticks([x for x, _, _ in bars], [lbl for _, lbl, _ in bars], fontsize=9)
    ax.set_ylabel("weekly cost, M KRW", color=MUTED)
    ax.set_ylim(0, top * 1.12)
    ax.grid(axis="y", color=GRID, lw=0.7)
    ax.set_axisbelow(True)
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=c) for _, _, c in parts], labels=[n for _, n, _ in parts], frameon=False, labelcolor=INK, loc="upper left")
    ax.set_title("Weekly cost: current vs expansion, outsource-everything vs the exact optimum", loc="left", color=INK, fontsize=12)
    fig.text(0.01, 0.005, NOTE + ". Penalties are zero in every bar.", color=MUTED, fontsize=8.5)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    savefig(fig, path)


def ga_runs(res, cfg):
    """All GA runs (both selections, all seeds) on one solved instance, with the gap to the exact optimum."""
    ga, opt = cfg["v2"]["ga"], res["cost"]
    out = {}
    for method in SELECTION:
        runs = [run_ga(res["inst"], method, seed, ga) for seed in range(ga["n_seeds"])]
        out[method] = {"gaps": np.array([max(0.0, 100 * (r["cost"] / opt - 1)) for r in runs]),
                       "history": np.array([100 * (r["history"] / opt - 1) for r in runs])}
    return out


def chart_convergence(cases, path):
    """cases: [(title, ga_runs result)]. Mean best cost across seeds (line) with the min-max band, as % above the exact optimum."""
    fig, axes = plt.subplots(1, len(cases), figsize=(6.2 * len(cases), 4.4), facecolor=SURFACE)
    for ax, (title, runs) in zip(np.atleast_1d(axes), cases):
        style(ax)
        for method, color in (("roulette", ORANGE), ("tournament", BLUE)):
            h = runs[method]["history"]
            ax.fill_between(range(h.shape[1]), h.min(axis=0), h.max(axis=0), color=color, alpha=0.15, lw=0)
            ax.plot(h.mean(axis=0), color=color, lw=2, label=method)
            end = max(0.0, h.mean(axis=0)[-1])  # clamp float noise so it never prints "-0.00%"
            ax.annotate(f"{method} {end:.2f}%", (h.shape[1] - 1, end), xytext=(5, 12 if method == "roulette" else 1),
                        textcoords="offset points", color=INK, fontsize=9)
        ax.set_title(title, loc="left", color=INK, fontsize=11)
        ax.set_xlabel("generation", color=MUTED, fontsize=9)
        ax.set_ylabel("best cost, % above the exact optimum", color=MUTED, fontsize=9)
        ax.set_xlim(0, h.shape[1] * 1.22)
        ax.set_ylim(bottom=-0.5)
        ax.grid(axis="y", color=GRID, lw=0.7)
        ax.legend(frameon=False, labelcolor=INK, fontsize=9, loc="upper right")
    fig.suptitle("GA convergence: roulette (2022 paper) vs tournament. Line = mean of 20 seeds, band = best and worst seed", color=INK, fontsize=11.5, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    savefig(fig, path)


def chart_validation(rows, path):
    """rows: [(label, ga_runs result)]: seeds that found the exact optimum, per selection method."""
    fig, ax = plt.subplots(figsize=(11, 4.8), facecolor=SURFACE)
    style(ax)
    w = 0.38
    for k, (method, color) in enumerate((("roulette", ORANGE), ("tournament", BLUE))):
        for i, (_, runs) in enumerate(rows):
            g = runs[method]["gaps"]
            found = int((g < 1e-6).sum())
            ax.bar(i + (k - 0.5) * w, found, width=w * 0.92, color=color, label=method if i == 0 else None)
            ax.text(i + (k - 0.5) * w, found + 0.3, f"{found}/{len(g)}\nworst {g.max():.1f}%", ha="center", va="bottom", color=INK, fontsize=8.5)
    ax.set_xticks(range(len(rows)), [lbl for lbl, _ in rows], fontsize=9)
    ax.set_ylabel("seeds (of 20) that found the exact optimum", color=MUTED)
    ax.set_ylim(0, 25)
    ax.grid(axis="y", color=GRID, lw=0.7)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, labelcolor=INK, loc="upper right", ncol=2)
    ax.set_title("GA vs exact solver: roulette degrades on harder instances, tournament does not", loc="left", color=INK, fontsize=12)
    fig.text(0.01, 0.005, "Left two groups: business scenarios. Right three: ALGORITHM VALIDATION instances, not a business recommendation. " + NOTE + ".", color=MUTED, fontsize=8)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    savefig(fig, path)


def stress_table(cases):
    """Markdown table generated from the GA runs, so README numbers cannot drift."""
    lines = ["| instance | hubs in the exact optimum | roulette: mean / worst gap, optimum found | tournament: mean / worst gap, optimum found |", "|---|---|---|---|"]
    for label, res, runs in cases:
        cells = [f"{runs[m]['gaps'].mean():.2f}% / {runs[m]['gaps'].max():.2f}%, {int((runs[m]['gaps'] < 1e-6).sum())} of {len(runs[m]['gaps'])}" for m in ("roulette", "tournament")]
        lines.append(f"| {label} | {res['n_hubs']} | {cells[0]} | {cells[1]} |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- orchestration

def main():
    cfg = load_config()
    v2 = cfg["v2"]
    print("solving base scenarios ...")
    base = {sc: solve_with(sc, cfg) for sc in SCENARIOS}
    for sc, r in base.items():
        facts = describe(r["inst"], r["exact"]["assign"])
        outsourced = ", ".join(f"{z} {s:.0%}" for z, s in facts["vendor_share"].items())
        banner = (f"<b>{sc}, base assumptions.</b> {NOTE}. Exact optimum: <b>{r['n_hubs']} hubs</b>"
                  f"{' (' + ', '.join(r['hub_names']) + ')' if r['n_hubs'] else ' (outsource-first at these costs)'}; turnovers outsourced: {outsourced}.")
        hub_map(r["inst"], r["exact"]["assign"], banner, OUT / f"hubs_{sc}.html")
    what = solve_with("expansion", cfg, round_trips=0.25)
    hub_map(what["inst"], what["exact"]["assign"],
            f"<b>WHAT-IF, not a business recommendation.</b> Expansion with 0.25 van round trips per turnover (heavy batching), which is not the base assumption. "
            f"{NOTE}. Exact optimum: <b>{what['n_hubs']} hubs</b> ({', '.join(what['hub_names'])}).", OUT / "hubs_expansion_whatif_batched.html")

    print("break-even heatmap ...")
    mults, trips = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0], [1.0, 0.75, 0.5, 0.25, 0.1]
    grids = heatmap_breakeven(mults, trips, OUT / "heatmap_breakeven.png", cfg)
    for sc, g in grids.items():
        print(f"  hubs opened, {sc} (rows = round trips {trips}, cols = vendor x {mults}):\n" + "\n".join("   " + " ".join(f"{int(v):2d}" for v in row) for row in g))
    print("cost breakdown, rent x turnovers, vendor surcharge ...")
    chart_cost_breakdown(base, OUT / "cost_breakdown.png")
    heatmap_rent_turnovers([0.1, 0.25, 0.5, 1.0, 2.0, 4.0], [0.5, 1.0, 1.5, 2.0, 3.0], OUT / "sensitivity_rent_turnovers.png", cfg)
    chart_surcharge([0, 100, 200, 400, 600, 800, 1000], OUT / "vendor_surcharge.png", cfg)

    print("GA runs (business scenarios and validation instances) ...")
    cases = [("current (business)", base["current"]), ("expansion (business)", base["expansion"])]
    for st in v2["stress_tests"]:
        cases.append((f"validation: {st['name']}", solve_with(st["scenario"], cfg, vendor_multiplier=st["vendor_multiplier"], round_trips=st["round_trips"])))
    runs = [ga_runs(res, cfg) for _, res in cases]
    (OUT / "stress_table.md").write_text(stress_table([(lbl, res, r) for (lbl, res), r in zip(cases, runs)]))
    chart_validation([(f"{lbl}\n{res['n_hubs']} hubs", r) for (lbl, res), r in zip(cases, runs)], OUT / "ga_validation.png")
    chart_convergence([("expansion, base assumptions (business)", runs[1]), ("validation instance vendor_x3 (not a business result)", runs[3])], OUT / "v2_convergence.png")
    print((OUT / "stress_table.md").read_text())


if __name__ == "__main__":
    main()
