"""Folium map of one hub-model solution: villas, open hubs, assignment lines, candidate towns. Popups give region and drive time."""
import folium
import numpy as np

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
