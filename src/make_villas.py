"""One-off generator for data/villas.csv (SIMULATED villas). Run:  python -m src.make_villas
Reads the region table in config.yaml (counts are PLACEHOLDERs), scatters villas around each region centre by
+-jitter_deg so no real address is implied, and draws weekly turnovers at random. Same seed -> same file.
"""
import csv

import numpy as np

from src.config import ROOT, load_config


def main():
    v = load_config()["v2"]["villas"]
    rng = np.random.default_rng(v["seed"])
    lo, hi = v["weekly_turnovers_range"]
    rows = []
    for r in v["regions"]:
        for k in range(r["n_current"] + r["n_added"]):
            rows.append({
                "villa_id": f"V{len(rows) + 1:03d}", "region": r["name"], "zone": r["zone"],
                "lat": round(r["lat"] + rng.uniform(-v["jitter_deg"], v["jitter_deg"]), 5),
                "lon": round(r["lon"] + rng.uniform(-v["jitter_deg"], v["jitter_deg"]), 5),
                "weekly_turnovers": int(rng.integers(lo, hi + 1)),
                "in_current": int(k < r["n_current"]),  # first n_current villas of each region are in "current"
            })
    with open(ROOT / "data" / "villas.csv", "w", newline="") as f:
        f.write("# SIMULATED DATA: region-level coordinates only, PLACEHOLDER counts and turnovers. Not MOZAIQ data.\n")
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} villas ({sum(r['in_current'] for r in rows)} in current)")


if __name__ == "__main__":
    main()
