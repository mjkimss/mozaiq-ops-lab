"""Loaders for the shared villa and candidate-hub data (used by the hub model now, by prototypes 2 and 3 later)."""
import csv

import numpy as np

from src.config import ROOT

SCENARIOS = ("current", "expansion")


def _read(name):
    with open(ROOT / "data" / name, newline="") as f:
        return list(csv.DictReader(line for line in f if not line.startswith("#")))  # skip the SIMULATED banner


def load_villas(scenario):
    """Villas for a scenario: 'current' = in_current rows, 'expansion' = all rows (a superset of current)."""
    assert scenario in SCENARIOS, f"scenario must be one of {SCENARIOS}"
    rows = [r for r in _read("villas.csv") if scenario == "expansion" or r["in_current"] == "1"]
    return {
        "ids": [r["villa_id"] for r in rows], "regions": [r["region"] for r in rows],
        "zone": np.array([r["zone"] for r in rows]),
        "coords": np.array([[float(r["lat"]), float(r["lon"])] for r in rows]),
        "turnovers": np.array([int(r["weekly_turnovers"]) for r in rows], dtype=float),
    }


def load_hubs():
    rows = _read("candidate_hubs.csv")
    return {
        "ids": [r["hub_id"] for r in rows], "names": [r["name"] for r in rows],
        "zone": np.array([r["zone"] for r in rows]), "rent_tier": [r["rent_tier"] for r in rows],
        "coords": np.array([[float(r["lat"]), float(r["lon"])] for r in rows]),
    }
