"""Folium map of one hub-model solution: villas, open hubs, assignment lines, candidate towns. Popups give region and drive time."""
import folium
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

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


# label offsets (points) for candidate towns that would otherwise collide in the crowded Seoul area
LABEL_AT = {"Seoul": (-4, 5, "right"), "Goyang": (-4, 3, "right"), "Gimpo": (-4, -2, "right"), "Incheon": (-4, -8, "right"),
            "Suwon": (-4, -8, "right"), "Yongin": (4, -8, "left"), "Hanam": (4, -8, "left"), "Namyangju": (4, 3, "left"),
            "Sokcho": (4, 3, "left"), "Yangyang": (4, -8, "left"), "Gimhae": (-4, 3, "right")}

# where to put the label of an open hub (lon, lat in data coordinates), joined to it by a thin line; others get a small offset.
# The capital area and Gangwon are crowded, so those labels go into the empty band around them.
HUB_LABEL_AT = {"Namyangju": (126.15, 36.85), "Hongcheon": (127.15, 36.55), "Yangyang": (127.25, 38.33), "Busan": (127.9, 35.6),
                "Gapyeong": (126.15, 36.5), "Chuncheon": (127.15, 36.85), "Gangneung": (128.15, 37.0), "Seogwipo": (127.3, 33.05),
                "Seoul": (126.15, 37.3), "Hanam": (127.15, 36.25), "Incheon": (126.15, 36.1)}


def hub_map_png(inst, assign, title, subtitle, path, whatif=False):
    """Static version of hub_map (same data and colours): points only, no basemap tiles. The interactive .html has the tiles."""
    v, h = inst["villas"], inst["hubs"]
    load = np.bincount(assign[assign >= 0], weights=v["turnovers"][assign >= 0], minlength=len(h["ids"]))
    fig, ax = plt.subplots(figsize=(7.4, 10.6), facecolor="#fcfcfb")
    ax.set_facecolor("#f4f3ef")
    ax.set_aspect(1 / np.cos(np.radians(36)))  # a degree of longitude is shorter than a degree of latitude here
    ax.set_xlim(125.9, 129.7)
    ax.set_ylim(32.9, 38.5)
    ax.grid(color="#e2e0da", lw=0.6)
    ax.tick_params(colors="#52514e", labelsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#c9c8c2")
    ax.set_xlabel("longitude", color="#52514e", fontsize=8)
    ax.set_ylabel("latitude", color="#52514e", fontsize=8)
    for j, name in enumerate(h["names"]):
        lat, lon = h["coords"][j]
        ax.scatter(lon, lat, s=22, facecolor="none", edgecolor="#a8a8a2", lw=1, zorder=2)
        dx, dy, ha = LABEL_AT.get(name, (4, -3, "left"))
        ax.annotate(name, (lon, lat), xytext=(dx, dy), textcoords="offset points", ha=ha, fontsize=6.5, color="#8a8a84", zorder=2)
    for i in range(len(v["ids"])):
        j = int(assign[i])
        if j >= 0:
            ax.plot([v["coords"][i, 1], h["coords"][j, 1]], [v["coords"][i, 0], h["coords"][j, 0]], color=HUB_COLOR, lw=1, alpha=0.5, zorder=3)
    served = assign >= 0
    ax.scatter(v["coords"][served, 1], v["coords"][served, 0], s=30, color=HUB_COLOR, edgecolor="white", lw=0.6, zorder=4)
    ax.scatter(v["coords"][~served, 1], v["coords"][~served, 0], s=30, color=VENDOR_COLOR, edgecolor="white", lw=0.6, zorder=4)
    for j in np.nonzero(load > 0)[0]:
        lat, lon = h["coords"][j]
        ax.scatter(lon, lat, s=170, marker="s", color=HUB_COLOR, edgecolor="white", lw=1.5, zorder=5)
        far = h["names"][j] in HUB_LABEL_AT
        ax.annotate(f"Hub {h['names'][j]}\n{load[j]:.0f} of {inst['capacity']:.0f} turnovers/wk", (lon, lat),
                    xytext=HUB_LABEL_AT[h["names"][j]] if far else (10, 10), textcoords="data" if far else "offset points",
                    fontsize=8, fontweight="bold", color="#0b0b0b", zorder=6,
                    arrowprops=dict(arrowstyle="-", color="#7a7a74", lw=0.8) if far else None,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#c9c8c2", alpha=0.95))
    handles = [plt.Line2D([], [], marker="o", ls="", color=HUB_COLOR, label="villa served by a hub"),
               plt.Line2D([], [], marker="o", ls="", color=VENDOR_COLOR, label="villa outsourced to the vendor"),
               plt.Line2D([], [], marker="s", ls="", color=HUB_COLOR, ms=9, label="open hub"),
               plt.Line2D([], [], marker="o", ls="", markerfacecolor="none", markeredgecolor="#a8a8a2", label="candidate town")]
    ax.legend(handles=handles, loc="lower right", fontsize=8, frameon=True, framealpha=0.9, edgecolor="#c9c8c2")
    if whatif:
        fig.text(0.05, 0.965, title, fontsize=11.5, fontweight="bold", color="#0b0b0b", va="top",
                 bbox=dict(boxstyle="round,pad=0.4", fc="#fffbe6", ec="#d4b106"))
    else:
        fig.text(0.05, 0.965, title, fontsize=12, fontweight="bold", color="#0b0b0b", va="top")
    fig.text(0.05, 0.925, subtitle, fontsize=8.5, color="#52514e", va="top", wrap=True)
    fig.text(0.05, 0.010, "Points only, no basemap; the interactive .html has OpenStreetMap tiles.\nRoad times: OSRM. Road data \u00a9 OpenStreetMap contributors (ODbL).\n"
             "SIMULATED villas, PLACEHOLDER costs: not MOZAIQ data.", fontsize=7, color="#52514e", va="bottom")
    fig.subplots_adjust(left=0.1, right=0.96, top=0.89, bottom=0.085)
    fig.savefig(path, dpi=130, facecolor=fig.get_facecolor())
    plt.close(fig)
