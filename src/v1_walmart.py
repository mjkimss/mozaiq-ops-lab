"""v1: faithful rebuild of the 2022 IB essay GA for Walmart Korea distribution-center (DC) locations.

What the paper describes, in order (section numbers refer to docs/walmart_paper.md):
  - 16 fixed stores, named a..p by descending longitude; 5 DCs named A..E          (3-3-1)
  - DCs A-C (durable goods) serve stores a-i; DCs D-E (non-durable) serve j-p       (Table 1)
  - a DC is two genes: (latitude, longitude), inside a fixed search box             (3-3-1)
  - fitness = 1 / total distance; roulette-wheel selection; crossover; mutation     (3-3-2, 3-3-3)
  - stage 2: add each DC's distance to its nearest port (Incheon, Busan)            (3-4)
Every place the paper is vague is a choice recorded in docs/decisions.md.

Run:  python -m src.v1_walmart
"""
import csv

import numpy as np

from src.config import ROOT, load_config
from src.geo import haversine_km


# ---------------------------------------------------------------- data

def load_stores(cfg):
    """Read the 16 stores, sort by descending longitude, name them a..p, split into durable / non-durable."""
    with open(ROOT / "data" / "walmart_stores.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: -float(r["lon"]))  # store "a" has the highest longitude (paper 3-3-1)
    names = [r["name"] for r in rows]
    coords = np.array([[float(r["lat"]), float(r["lon"])] for r in rows])
    letters = [chr(ord("a") + i) for i in range(len(rows))]
    k = cfg["v1"]["n_durable_stores"]
    return {
        "durable": {"names": names[:k], "letters": letters[:k], "coords": coords[:k]},
        "nondurable": {"names": names[k:], "letters": letters[k:], "coords": coords[k:]},
    }


# ---------------------------------------------------------------- distance and fitness

def store_km(pop, stores):
    """Total store distance for every individual. pop has shape (P, n_dcs, 2); stores has shape (S, 2).
    Each store is served by its nearest DC in the same group; returns shape (P,)."""
    d = haversine_km(stores[:, 0], stores[:, 1], pop[:, :, None, 0], pop[:, :, None, 1])  # (P, n_dcs, S)
    return d.min(axis=1).sum(axis=1)


def port_km(pop, ports):
    """Sum over DCs of the distance to that DC's nearest port. ports has shape (K, 2); returns shape (P,)."""
    d = haversine_km(ports[:, 0], ports[:, 1], pop[:, :, None, 0], pop[:, :, None, 1])  # (P, n_dcs, K)
    return d.min(axis=2).sum(axis=1)


def total_km(pop, stores, ports=None):
    """Stage 1: store distance only. Stage 2 (ports given): store distance + port distance."""
    total = store_km(pop, stores)
    return total if ports is None else total + port_km(pop, ports)


def assign(dcs, stores):
    """For one set of DCs (n_dcs, 2): index of the nearest DC for each store, and that distance in km."""
    d = haversine_km(stores[:, 0], stores[:, 1], dcs[:, None, 0], dcs[:, None, 1])  # (n_dcs, S)
    return d.argmin(axis=0), d.min(axis=0)


# ---------------------------------------------------------------- the GA

def run_ga(stores, n_dcs, cfg, rng, ports=None, init_pop=None):
    """One GA run. Returns (final population, best individual, best-total-distance per generation)."""
    ga, bounds = cfg["v1"]["ga"], cfg["v1"]["bounds"]
    n = ga["population"]
    lo, hi = np.array([bounds["lat"], bounds["lon"]]).T  # lower and upper corner of the search box: (lat, lon)

    # Initialization: random DC coordinates inside the box (or start from a given population)
    pop = init_pop.copy() if init_pop is not None else rng.uniform(lo, hi, size=(n, n_dcs, 2))
    history = []

    for _ in range(ga["generations"]):
        dist = total_km(pop, stores, ports)
        history.append(dist.min())
        elite = pop[np.argsort(dist)[: ga["elite"]]]

        # Selection: roulette wheel. Fitness = 1 / distance, so each individual's slice of the wheel
        # is proportional to 1 / distance. (Tiny floor avoids dividing by zero.)
        fitness = 1.0 / np.maximum(dist, 1e-9)
        parents = rng.choice(n, size=(n, 2), p=fitness / fitness.sum())
        mom, dad = pop[parents[:, 0]], pop[parents[:, 1]]

        # Crossover: each gene of the child comes from one parent or the other, by coin flip.
        # With probability 1 - crossover_prob the child is just a copy of the first parent.
        child = np.where(rng.random(mom.shape) < 0.5, dad, mom)
        crossed = rng.random(n) < ga["crossover_prob"]
        pop = np.where(crossed[:, None, None], child, mom)

        # Mutation: with small probability a gene is thrown away and replaced by a fresh random value
        # inside the box, so locations no parent carries can enter the population.
        mutate = rng.random(pop.shape) < ga["mutation_prob"]
        pop = np.where(mutate, rng.uniform(lo, hi, size=pop.shape), pop)

        pop[: ga["elite"]] = elite  # elitism (addition beyond the paper, see decisions.md)

    dist = total_km(pop, stores, ports)
    history.append(dist.min())
    return pop, pop[dist.argmin()], np.array(history)


def run(cfg):
    """Both groups x both stages, from one seeded random generator. Returns everything main() needs."""
    rng = np.random.default_rng(cfg["v1"]["seed"])
    stores = load_stores(cfg)
    ports = np.array(list(cfg["v1"]["ports"].values()))
    n_dcs = {"durable": cfg["v1"]["n_durable_dcs"], "nondurable": cfg["v1"]["n_nondurable_dcs"]}

    out = {"stores": stores, "ports": cfg["v1"]["ports"], "groups": {}}
    for group in ("durable", "nondurable"):  # part I, then part II
        s = stores[group]["coords"]
        pop1, best1, hist1 = run_ga(s, n_dcs[group], cfg, rng)
        pop2, best2, hist2 = run_ga(s, n_dcs[group], cfg, rng, ports=ports, init_pop=pop1)  # stage 2 starts from stage 1
        out["groups"][group] = {}
        for stage, best, hist in (("stage1", best1, hist1), ("stage2", best2, hist2)):
            best = best[np.argsort(-best[:, 1])]  # label DCs east -> west, just for display
            idx, km = assign(best, s)
            out["groups"][group][stage] = {
                "dcs": best, "history": hist, "assigned": idx, "km": km, "store_km": km.sum(),
                "port_km": port_km(best[None], ports)[0],
            }
    return out


# ---------------------------------------------------------------- reporting

def report(res, cfg):
    """Print the results as text (this text is what the 'same result twice' check compares)."""
    lines = [f"v1 Walmart GA, seed {cfg['v1']['seed']}", ""]
    dc_letter = iter("ABCDE")
    for group in ("durable", "nondurable"):
        s, g = res["stores"][group], res["groups"][group]
        letters = [next(dc_letter) for _ in g["stage1"]["dcs"]]
        lines.append(f"== {group} DCs {letters[0]}-{letters[-1]}, stores {s['letters'][0]}-{s['letters'][-1]} ==")
        for stage in ("stage1", "stage2"):
            r = g[stage]
            lines.append(f"{stage}: store distance {r['store_km']:.1f} km + port distance {r['port_km']:.1f} km"
                         f" = {r['store_km'] + r['port_km']:.1f} km")
            for L, (la, lo) in zip(letters, r["dcs"]):
                lines.append(f"  DC {L}: ({la:.4f}, {lo:.4f})")
        lines.append("stage 2 assignment (store -> DC, km):")
        km = g["stage2"]["km"]
        for i, (L, name) in enumerate(zip(s["letters"], s["names"])):
            lines.append(f"  {L} {name:<12} -> DC {letters[g['stage2']['assigned'][i]]}  {km[i]:6.1f}")
        lines.append("")
    print("\n".join(lines))


COLORS = {"durable": "#2a78d6", "nondurable": "#eb6834"}  # blue / orange; colour-blind safe (checked with the dataviz validator)


def plot_convergence(res):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ink, muted, surface = "#0b0b0b", "#52514e", "#fcfcfb"
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), facecolor=surface)
    titles = {"stage1": "Stage 1: distance to stores only", "stage2": "Stage 2: stores + nearest port"}
    labels = {"durable": "Part I: durable DCs A-C (stores a-i)", "nondurable": "Part II: non-durable DCs D-E (stores j-p)"}
    for ax, stage in zip(axes, ("stage1", "stage2")):
        ax.set_facecolor(surface)
        for group in ("durable", "nondurable"):
            h = res["groups"][group][stage]["history"]
            ax.plot(h, color=COLORS[group], lw=1.8, label=labels[group])
            ax.annotate(f"{h[-1]:.0f} km", (len(h) - 1, h[-1]), xytext=(5, 0), textcoords="offset points",
                        color=ink, fontsize=9, va="center")
        ax.set_title(titles[stage], color=ink, fontsize=11, loc="left")
        ax.set_xlabel("Generation", color=muted)
        ax.set_ylabel("Best total distance (km)", color=muted)
        ax.set_xlim(0, len(h) * 1.12)
        ax.grid(axis="y", color="#e4e3df", lw=0.7)
        ax.tick_params(colors=muted)
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["left", "bottom"]].set_color("#c9c8c2")
    axes[0].legend(frameon=False, labelcolor=ink, fontsize=9, loc="upper right")
    fig.suptitle("v1 (2022 GA rebuild): best distance per generation, roulette-wheel selection",
                 color=ink, fontsize=12, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(ROOT / "outputs" / "v1_convergence.png", dpi=150, facecolor=surface)


def make_map(res):
    import folium

    m = folium.Map(location=[36.3, 127.8], zoom_start=7, tiles="OpenStreetMap")
    stage_layers = {s: folium.FeatureGroup(name=f"{s}: DCs and assignments", show=(s == "stage2"))
                    for s in ("stage1", "stage2")}
    store_layer = folium.FeatureGroup(name="stores")
    for group in ("durable", "nondurable"):
        s, g = res["stores"][group], res["groups"][group]
        color = COLORS[group]
        letters = "ABC" if group == "durable" else "DE"
        for L, name, (la, lo) in zip(s["letters"], s["names"], s["coords"]):
            folium.CircleMarker([la, lo], radius=5, color=color, fill=True, fill_opacity=0.9,
                                tooltip=f"store {L}: {name} ({group} group)").add_to(store_layer)
        for stage, layer in stage_layers.items():
            r = g[stage]
            for i, (la, lo) in enumerate(s["coords"]):
                dla, dlo = r["dcs"][r["assigned"][i]]
                folium.PolyLine([[la, lo], [dla, dlo]], color=color, weight=1.5, opacity=0.6).add_to(layer)
            for L, (la, lo) in zip(letters, r["dcs"]):
                folium.Marker([la, lo], tooltip=f"DC {L} ({stage})",
                              icon=folium.Icon(color="blue" if group == "durable" else "orange", icon="home")).add_to(layer)
    port_layer = folium.FeatureGroup(name="ports")
    for name, (la, lo) in res["ports"].items():
        folium.Marker([la, lo], tooltip=f"{name} port (approximate)", icon=folium.Icon(color="black", icon="anchor", prefix="fa")).add_to(port_layer)
    for layer in (store_layer, *stage_layers.values(), port_layer):
        layer.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    m.save(ROOT / "outputs" / "v1_map.html")


def main():
    cfg = load_config()
    res = run(cfg)
    report(res, cfg)
    plot_convergence(res)
    make_map(res)


if __name__ == "__main__":
    main()
