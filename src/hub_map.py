"""Folium map of one hub-model solution: villas, open hubs, assignment lines, candidate towns. Popups give region and drive time."""
import json
import textwrap

import folium
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

from src.config import ROOT

HUB_COLOR, VENDOR_COLOR = "#2a78d6", "#7a7a7a"  # blue = served by a hub, grey = outsourced to the vendor


def hub_map(inst, assign, banner, path):
    v, h = inst["villas"], inst["hubs"]
    m = folium.Map(location=[36.3, 127.8], zoom_start=7, tiles="OpenStreetMap")  # tiles carry the OpenStreetMap credit
    layers = {k: folium.FeatureGroup(name=k) for k in ("candidate towns", "assignment lines", "villas served by a hub",
                                                        "villas outsourced to the vendor", "open hubs")}
    for j, name in enumerate(h["names"]):
        folium.CircleMarker(h["coords"][j].tolist(), radius=4, color="#b0b0b0", fill=True, fill_opacity=0.6,
                            tooltip=f"candidate town: {name} (rent {inst['fixed'][j]:,.0f} KRW/week)").add_to(layers["candidate towns"])
    load = np.bincount(assign[assign >= 0], weights=v["turnovers"][assign >= 0], minlength=len(h["ids"]))
    for i, vid in enumerate(v["ids"]):
        lat, lon = v["coords"][i].tolist()
        j = int(assign[i])
        if j >= 0:
            minutes, km = inst["minutes"][i, j], inst["km"][i, j]
            served = f"hub {h['names'][j]}: {minutes:.0f} min drive, {km:.1f} km"
            folium.PolyLine([[lat, lon], h["coords"][j].tolist()], color=HUB_COLOR, weight=1.5, opacity=0.6).add_to(layers["assignment lines"])
            target = layers["villas served by a hub"]
        else:
            served = f"outsourced to the {v['zone'][i]} vendor ({inst['vendor'][i]:,.0f} KRW/week)"
            target = layers["villas outsourced to the vendor"]
        folium.CircleMarker([lat, lon], radius=5, color=HUB_COLOR if j >= 0 else VENDOR_COLOR, fill=True, fill_opacity=0.9,
                            popup=folium.Popup(f"<b>{vid}</b> ({v['regions'][i]}, SIMULATED)<br>{v['turnovers'][i]:.0f} turnovers/week<br>served by {served}",
                                               max_width=280)).add_to(target)
    for j in np.nonzero(load > 0)[0]:
        n_served = int((assign == j).sum())
        folium.Marker(h["coords"][j].tolist(), icon=folium.Icon(color="blue", icon="home"),
                      popup=folium.Popup(f"<b>Hub {h['names'][j]}</b> ({h['zone'][j]})<br>rent {inst['fixed'][j]:,.0f} KRW/week"
                                         f"<br>serves {n_served} villas, {load[j]:.0f} of {inst['capacity']:.0f} turnovers/week", max_width=280),
                      tooltip=f"hub {h['names'][j]}").add_to(layers["open hubs"])
    for layer in layers.values():
        layer.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    pts = np.vstack([v["coords"], h["coords"]])
    m.fit_bounds([pts.min(axis=0).tolist(), pts.max(axis=0).tolist()])
    n_hubs = int((load > 0).sum())
    m.get_root().html.add_child(folium.Element(
        f'<div style="position:fixed;top:10px;left:50px;right:50px;z-index:9999;background:#fffbe6;border:1px solid #d4b106;'
        f'padding:8px 12px;font:14px sans-serif;border-radius:6px">{banner}</div>'
        f'<div style="position:fixed;bottom:24px;left:10px;z-index:9999;background:white;border:1px solid #ccc;padding:6px 10px;'
        f'font:12px sans-serif;border-radius:6px"><span style="color:{HUB_COLOR}">&#9679;</span> villa served by a hub &nbsp; '
        f'<span style="color:{VENDOR_COLOR}">&#9679;</span> villa outsourced &nbsp; <span style="color:#b0b0b0">&#9679;</span> candidate town'
        f' &nbsp; (open hubs: {n_hubs})<br>Road times: OSRM. Road data &copy; OpenStreetMap contributors (ODbL).</div>'))
    m.save(path)


# ---------------------------------------------------------------- static PNG map (landscape, 1600 x 900 px)

FIG_IN, DPI = (12.5, 7.0), 128                       # 12.5 in x 128 dpi = 1600 px wide
INK, MUTED, SEA, LAND, LAND_EDGE = "#0b0b0b", "#52514e", "#f3f6f9", "#ecebe5", "#c3c1b8"
BOXES = {"main": {"lon": (126.3, 129.25), "lat": (36.95, 38.5)},   # capital area + Gangwon
         "jeju": {"lon": (126.1, 127.0), "lat": (33.1, 33.65)},
         "busan": {"lon": (128.85, 129.35), "lat": (35.05, 35.35)}}
INSET_TITLES = {"jeju": "Jeju island", "busan": "Busan area"}
REGION_NAMES = {"Seoul-Gahoe": "Seoul", "Gapyeong": "Gapyeong", "Yangyang": "Yangyang", "Gangneung": "Gangneung", "Hongcheon": "Hongcheon"}
# where the label of an open hub goes in the main panel (lon, lat), joined to the hub by a thin line
HUB_LABEL_AT = {"Namyangju": (126.35, 38.28), "Hongcheon": (127.35, 38.32), "Yangyang": (128.25, 38.33)}
# inset hub labels: (dx, dy in points, horizontal alignment, vertical alignment); default is just above the hub
INSET_HUB_LABEL = {"Jeju City": (12, 0, "left", "center")}
REGION_LABEL_AT = {"Seoul-Gahoe": (-12, -20, "right"), "Gapyeong": (-16, 16, "right"), "Yangyang": (12, -4, "left"),
                   "Gangneung": (-14, -22, "right"), "Hongcheon": (10, -20, "left")}


def _coast():
    return json.loads((ROOT / "data" / "korea_coast.json").read_text())["polygons"]


def _in_box(coords, box):
    return (coords[:, 1] >= box["lon"][0]) & (coords[:, 1] <= box["lon"][1]) & (coords[:, 0] >= box["lat"][0]) & (coords[:, 0] <= box["lat"][1])


def _panel(ax, box, inst, assign, load, main):
    """One map panel: land, candidate towns, assignment lines, villas, open hubs. Only what falls inside `box` is drawn."""
    v, h = inst["villas"], inst["hubs"]
    ax.set_facecolor(SEA)
    ax.set_xlim(*box["lon"])
    ax.set_ylim(*box["lat"])
    ax.set_aspect(1 / np.cos(np.radians(np.mean(box["lat"]))), adjustable="box")  # a degree of longitude is shorter than one of latitude
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("#b9b8b0")
    for rings in _coast().values():
        for ring in rings:
            ax.add_patch(Polygon(ring, closed=True, fc=LAND, ec=LAND_EDGE, lw=0.8, zorder=1))
    inside = _in_box(h["coords"], box)
    ax.scatter(h["coords"][inside, 1], h["coords"][inside, 0], s=60 if main else 110, facecolor="none", edgecolor="#a8a8a2", lw=1.3, zorder=2)
    vs, vh = (70, 620) if main else (110, 620)
    for i in range(len(v["ids"])):
        j = int(assign[i])
        if j >= 0 and _in_box(v["coords"][i:i + 1], box)[0]:
            ax.plot([v["coords"][i, 1], h["coords"][j, 1]], [v["coords"][i, 0], h["coords"][j, 0]], color=HUB_COLOR, lw=2, alpha=0.55, zorder=3)
    served, vin = assign >= 0, _in_box(v["coords"], box)
    ax.scatter(v["coords"][served & vin, 1], v["coords"][served & vin, 0], s=vs, color=HUB_COLOR, edgecolor="white", lw=1.2, zorder=5)
    ax.scatter(v["coords"][~served & vin, 1], v["coords"][~served & vin, 0], s=vs, color=VENDOR_COLOR, edgecolor="white", lw=1.2, zorder=5)
    hubs_open = [j for j in np.nonzero(load > 0)[0] if inside[j]]
    for j in hubs_open:
        lat, lon = h["coords"][j]
        ax.scatter(lon, lat, s=vh, marker="s", color=HUB_COLOR, edgecolor="white", lw=1.8, zorder=4)
        far = main and h["names"][j] in HUB_LABEL_AT
        dx, dy, ha, va = INSET_HUB_LABEL.get(h["names"][j], (-10, 26, "left", "baseline"))
        ax.annotate(f"{h['names'][j]}\n{load[j]:.0f} turnovers/wk", (lon, lat), xytext=HUB_LABEL_AT[h["names"][j]] if far else (dx, dy),
                    textcoords="data" if far else "offset points", ha=ha if not far else "left", va=va if not far else "baseline",
                    fontsize=14 if main else 12, fontweight="bold", color=INK, zorder=6,
                    arrowprops=dict(arrowstyle="-", color="#7a7a74", lw=1.2) if far else None,
                    bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#c9c8c2", alpha=0.96))
    if main:
        open_names = {h["names"][j] for j in np.nonzero(load > 0)[0]}
        for region, label in REGION_NAMES.items():
            mask = np.array([r == region for r in v["regions"]])
            if mask.any() and region not in open_names:  # skip names an open-hub label already carries
                lat, lon = v["coords"][mask].mean(axis=0)
                dx, dy, ha = REGION_LABEL_AT[region]
                ax.annotate(label, (lon, lat), xytext=(dx, dy), textcoords="offset points", ha=ha, fontsize=12, style="italic", color="#5b5a55", zorder=6)
        km50 = 50 / (111.195 * np.cos(np.radians(37.7)))  # 50 km in degrees of longitude, so the scale bar is honest without tick labels
        x0, y0 = box["lon"][0] + 0.06, box["lat"][0] + 0.07
        ax.plot([x0, x0 + km50], [y0, y0], color=INK, lw=3.5, solid_capstyle="butt", zorder=6)
        ax.text(x0 + km50 / 2, y0 + 0.03, "50 km", ha="center", fontsize=12, color=INK, zorder=6)
        handles = [plt.Line2D([], [], marker="o", ls="", color=HUB_COLOR, ms=9, label="villa served by a hub"),
                   plt.Line2D([], [], marker="o", ls="", color=VENDOR_COLOR, ms=9, label="villa outsourced to the vendor"),
                   plt.Line2D([], [], marker="s", ls="", color=HUB_COLOR, ms=11, label="open hub"),
                   plt.Line2D([], [], marker="o", ls="", markerfacecolor="none", markeredgecolor="#a8a8a2", ms=9, label="candidate town")]
        ax.legend(handles=handles, loc="lower right", fontsize=12, framealpha=0.95, edgecolor="#c9c8c2")


def hub_map_png(inst, assign, title, subtitle, path, whatif=False):
    """Static version of hub_map (same solution data and colours), landscape 1600 x 900 px. The main panel shows the capital area and
    Gangwon; small insets show Jeju and Busan, drawn only when the scenario has villas there. The interactive .html has OSM tiles."""
    v, h = inst["villas"], inst["hubs"]
    load = np.bincount(assign[assign >= 0], weights=v["turnovers"][assign >= 0], minlength=len(h["ids"]))
    fig = plt.figure(figsize=FIG_IN, dpi=DPI, facecolor="#fcfcfb")
    insets = [k for k in ("jeju", "busan") if _in_box(v["coords"], BOXES[k]).any()]
    main_w = 0.69 if insets else 0.96
    _panel(fig.add_axes([0.02, 0.03, main_w, 0.79]), BOXES["main"], inst, assign, load, main=True)
    top, col_w = 0.80, 0.255
    for k in insets:  # right column, stacked from the top, each sized to its own aspect ratio
        box = BOXES[k]
        aspect = (np.diff(box["lon"])[0] * np.cos(np.radians(np.mean(box["lat"])))) / np.diff(box["lat"])[0]
        height = col_w * FIG_IN[0] / aspect / FIG_IN[1]
        _panel(fig.add_axes([0.725, top - height, col_w, height]), box, inst, assign, load, main=False)
        fig.text(0.725, top + 0.012, INSET_TITLES[k], fontsize=14, fontweight="bold", color=INK, va="bottom")
        top -= height + 0.085
    if whatif:
        fig.text(0.02, 0.975, title, fontsize=20, fontweight="bold", color=INK, va="top", bbox=dict(boxstyle="round,pad=0.3", fc="#fffbe6", ec="#d4b106"))
    else:
        fig.text(0.02, 0.975, title, fontsize=20, fontweight="bold", color=INK, va="top")
    fig.text(0.02, 0.895, textwrap.fill(subtitle, 125), fontsize=12.5, color=MUTED, va="top")
    fig.text(0.98, 0.975, "SIMULATED data", fontsize=12, fontweight="bold", color="#8a5a00", ha="right", va="top",
             bbox=dict(boxstyle="round,pad=0.3", fc="#fff4e5", ec="#e0a030"))
    fig.savefig(path, dpi=DPI, facecolor=fig.get_facecolor())
    plt.close(fig)
