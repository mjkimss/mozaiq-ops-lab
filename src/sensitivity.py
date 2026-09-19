"""Sweeps for the outputs: change one or two assumptions, re-solve the hub model EXACTLY (PuLP), report what comes out.
Exact, not the GA, so a sweep shows the true optimum for each setting."""
import copy

import numpy as np

from src.config import load_config
from src.hub_exact import solve_exact
from src.hub_model import build_instance, evaluate


def override(cfg, vendor_multiplier=1.0, round_trips=None, rent_multiplier=1.0, surcharge=None):
    """A copy of the config with some assumptions changed; everything else stays as in config.yaml."""
    c = copy.deepcopy(cfg)
    v2 = c["v2"]
    if round_trips is not None:
        v2["costs"]["van_round_trips_per_turnover"] = round_trips
    for zone in v2["vendor"]["cost_per_turnover_krw"]:
        v2["vendor"]["cost_per_turnover_krw"][zone] *= vendor_multiplier
    v2["hub"]["rent_gyeonggi_krw_per_m2_month"] *= rent_multiplier  # the other rent tiers are multiples of this one
    if surcharge is not None:
        v2["vendor"]["distance_surcharge_krw_per_turnover_km"] = surcharge
    return c


def solve_with(scenario, cfg=None, turnover_scale=1.0, **changes):
    """Exact optimum for one scenario under changed assumptions. Returns the facts a chart needs."""
    cfg = cfg or load_config()
    c = override(cfg, **changes)
    inst = build_instance(scenario, c, turnover_scale=turnover_scale)
    ex = solve_exact(inst, c["v2"]["exact"]["time_limit_s"])
    parts = evaluate(inst, ex["open"])
    all_out = float(evaluate(inst, np.zeros(len(inst["fixed"]), dtype=bool))["total"][0])  # no hubs: outsource everything
    return {"inst": inst, "exact": ex, "n_hubs": int(ex["open"].sum()), "cost": ex["cost"], "all_outsourced": all_out,
            "saving_pct": 100 * (1 - ex["cost"] / all_out), "parts": {k: float(parts[k][0]) for k in ("transport", "drive", "vendor", "fixed", "capacity")},
            "hub_names": [inst["hubs"]["names"][j] for j in np.nonzero(ex["open"])[0]]}
