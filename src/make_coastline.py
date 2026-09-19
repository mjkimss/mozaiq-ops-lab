"""One-off: build data/korea_coast.json, a small simplified land outline for the static maps.   python -m src.make_coastline
Source: Natural Earth 1:10m Admin 0 - Countries (public domain), https://www.naturalearthdata.com/ , fetched as GeoJSON from
https://github.com/nvkelso/natural-earth-vector. Keeps South Korea (KOR) plus North Korea (PRK, so land above the DMZ is not drawn as sea),
only polygons that touch the map window, and thins each outline with Douglas-Peucker (numpy only, no new dependency)."""
import json

import numpy as np
import requests

from src.config import ROOT

URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_0_countries.geojson"
WINDOW = (125.5, 32.5, 130.5, 39.0)  # lon_min, lat_min, lon_max, lat_max: covers every map panel
TOLERANCE_DEG = 0.0015               # about 150 m; invisible at map scale


def douglas_peucker(pts, tol):
    """Drop points that lie within `tol` of the straight line between kept neighbours. pts: (n, 2) array."""
    keep = np.zeros(len(pts), dtype=bool)
    keep[[0, -1]] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        a, b, mid = pts[i], pts[j], pts[i + 1:j]
        d = b - a
        norm = np.hypot(*d)
        dist = np.hypot(*(mid - a).T) if norm == 0 else np.abs(d[0] * (mid[:, 1] - a[1]) - d[1] * (mid[:, 0] - a[0])) / norm
        k = int(dist.argmax())
        if dist[k] > tol:
            keep[i + 1 + k] = True
            stack += [(i, i + 1 + k), (i + 1 + k, j)]
    return pts[keep]


def main():
    data = requests.get(URL, timeout=120).json()
    out = {"source": "Natural Earth 1:10m Admin 0 - Countries, public domain, https://www.naturalearthdata.com/", "tolerance_deg": TOLERANCE_DEG, "polygons": {}}
    for f in data["features"]:
        code = f["properties"]["ADM0_A3"]
        if code not in ("KOR", "PRK"):
            continue
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        rings = []
        for poly in polys:
            ring = np.array(poly[0])  # outer ring only: (lon, lat)
            if ring[:, 0].max() < WINDOW[0] or ring[:, 0].min() > WINDOW[2] or ring[:, 1].max() < WINDOW[1] or ring[:, 1].min() > WINDOW[3]:
                continue
            rings.append(np.round(douglas_peucker(ring, TOLERANCE_DEG), 4).tolist())
        out["polygons"][code] = rings
    path = ROOT / "data" / "korea_coast.json"
    path.write_text(json.dumps(out, separators=(",", ":")))
    print({k: (len(v), sum(len(r) for r in v)) for k, v in out["polygons"].items()}, f"{path.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
