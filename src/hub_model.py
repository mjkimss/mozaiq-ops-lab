"""Hub model: turns villas + candidate hubs + config into cost arrays, and scores sets of open hubs.

A solution is a yes/no per candidate hub. Every villa goes to its cheapest feasible option:
an open hub in its own zone, or the outsourced laundry vendor of its zone (always available).
Weekly cost (KRW) = van transport + drive-time penalty + vendor fees + fixed cost of open hubs + capacity penalty.
Jeju hard constraint: a villa and a hub/vendor in different zones (mainland vs jeju) are never paired.
"""
import numpy as np

from src.config import load_config
from src.data import load_hubs, load_villas
from src.travel import CACHE_PATH, travel_matrix


def build_instance(scenario, cfg=None, cache_path=CACHE_PATH, turnover_scale=1.0):
    v2 = (cfg or load_config())["v2"]
    villas, hubs = load_villas(scenario), load_hubs()
    villas = {**villas, "turnovers": villas["turnovers"] * turnover_scale}  # sensitivity hook; 1.0 = as in the data
    same_zone = villas["zone"][:, None] == hubs["zone"][None, :]  # the Jeju hard constraint
    minutes, km, fallback, stats = travel_matrix(villas["coords"], hubs["coords"], same_zone, cache_path, v2)

    c, h, pen = v2["costs"], v2["hub"], v2["penalties"]
    turnovers = villas["turnovers"][:, None]
    transport = turnovers * c["van_round_trips_per_turnover"] * 2 * km * c["van_cost_per_km_krw"]  # inf if infeasible
    drive = turnovers * pen["drive_krw_per_min_per_turnover"] * np.maximum(0, minutes - h["max_linen_drive_min"])
    rent = np.array([h["rent_gyeonggi_krw_per_m2_month"] * h["rent_tier_multiplier"][t] * h["area_m2"] for t in hubs["rent_tier"]])
    return {
        "scenario": scenario, "villas": villas, "hubs": hubs, "minutes": minutes, "km": km,
        "fallback": fallback, "travel_stats": stats,
        "transport": transport, "drive": drive, "pair": transport + drive,
        # flat fee per turnover, plus (default 0) a surcharge per km from the villa to its nearest candidate town
        "vendor": villas["turnovers"] * (np.where(villas["zone"] == "jeju", v2["vendor"]["cost_per_turnover_krw"]["jeju"],
                                                  v2["vendor"]["cost_per_turnover_krw"]["mainland"])
                                         + v2["vendor"]["distance_surcharge_krw_per_turnover_km"] * km.min(axis=1)),
        "fixed": rent * 12 / 52,  # monthly rent -> weekly
        "capacity": h["washer_kg_per_cycle"] * h["cycles_per_hour"] * h["hours_per_week"] * h["machines_per_hub"]
                    / h["linen_kg_per_turnover"],  # turnovers per week
        "cap_penalty": pen["capacity_krw_per_turnover"], "max_drive_min": h["max_linen_drive_min"],
    }


def evaluate(inst, open_):
    """Score sets of open hubs. open_: bool array (P, n_hubs) or (n_hubs,). Returns a dict of arrays of length P:
    total and its parts, plus assign (P, n_villas) = hub index, or -1 for the vendor."""
    open_ = np.atleast_2d(open_)
    n_hubs = open_.shape[1]
    pair = np.where(open_[:, None, :], inst["pair"][None], np.inf)          # closed or infeasible hubs cost inf
    best = pair.argmin(axis=2)                                               # (P, V) cheapest open hub per villa
    use_hub = pair.min(axis=2) < inst["vendor"][None]                        # hub only if strictly cheaper than the vendor
    assign = np.where(use_hub, best, -1)
    pick = lambda m: np.where(use_hub, np.take_along_axis(np.broadcast_to(m, pair.shape), best[..., None], 2)[..., 0], 0).sum(axis=1)
    load = ((assign[:, :, None] == np.arange(n_hubs)) * inst["villas"]["turnovers"][None, :, None]).sum(axis=1)  # (P, n_hubs)
    out = {
        "transport": pick(inst["transport"][None]), "drive": pick(inst["drive"][None]),
        "vendor": np.where(use_hub, 0, inst["vendor"][None]).sum(axis=1),
        "fixed": open_ @ inst["fixed"],
        "capacity": inst["cap_penalty"] * np.maximum(0, load - inst["capacity"]).sum(axis=1),  # penalty, not repair
        "assign": assign,
    }
    out["total"] = sum(out[k] for k in ("transport", "drive", "vendor", "fixed", "capacity"))
    return out


def describe(inst, assign):
    """Plain facts about one solution's assignment (assign: (n_villas,) hub index or -1 for vendor).
    Also asserts the Jeju hard constraint."""
    v, h = inst["villas"], inst["hubs"]
    used = assign >= 0
    assert (v["zone"][used] == h["zone"][assign[used]]).all(), "a villa was served across zones"
    load = np.bincount(assign[used], weights=v["turnovers"][used], minlength=len(h["ids"]))
    minutes = inst["minutes"][np.arange(len(assign))[used], assign[used]]
    return {
        "open_hubs": [h["names"][j] for j in np.unique(assign[used])],
        "vendor_share": {z: float(v["turnovers"][(~used) & (v["zone"] == z)].sum() / v["turnovers"][v["zone"] == z].sum())
                         for z in ("mainland", "jeju") if (v["zone"] == z).any()},
        "overflow_turnovers": float(np.maximum(0, load - inst["capacity"]).sum()),
        "villas_over_drive_limit": int((minutes > inst["max_drive_min"]).sum()),
    }
