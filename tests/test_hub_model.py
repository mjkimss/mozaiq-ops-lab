"""Tests for the hub cost function, the Jeju constraint, the capacity penalty, and PuLP vs brute force.
No test touches the network: travel times come from a pre-filled temporary cache."""
import itertools

import numpy as np
import pytest

from src import hub_model, travel
from src.hub_exact import solve_exact
from src.hub_ga import run_ga
from src.hub_model import build_instance, describe, evaluate

# Tiny world: villas A, B on the mainland, J on Jeju; hubs H1 (mainland) and H2 (Jeju).
VILLAS = {"ids": ["A", "B", "J"], "regions": ["a", "b", "j"], "zone": np.array(["mainland", "mainland", "jeju"]),
          "coords": np.array([[37.0, 127.0], [37.1, 127.1], [33.5, 126.5]]), "turnovers": np.array([2.0, 3.0, 1.0])}
HUBS = {"ids": ["H1", "H2"], "names": ["Hub1", "Hub2"], "zone": np.array(["mainland", "jeju"]),
        "rent_tier": ["gyeonggi", "jeju"], "coords": np.array([[37.05, 127.05], [33.4, 126.6]])}
# (villa, hub) -> (minutes, km). Cross-zone pairs (A-H2, B-H2, J-H1) are deliberately missing from the cache.
ROAD = {(0, 0): (30, 10), (1, 0): (60, 20), (2, 1): (10, 5)}


def cfg(vendor=30000, capacity_kg=10.0):
    return {"v2": {
        "osrm": {"base_url": "http://osrm.test", "batch_size": 50, "min_interval_s": 0, "timeout_s": 1, "retries": 0, "user_agent": "t"},
        "fallback": {"detour_factor": 1.3, "speed_kmh": 50},
        "costs": {"van_cost_per_km_krw": 1000, "van_round_trips_per_turnover": 1.0},
        "hub": {"area_m2": 1, "rent_gyeonggi_krw_per_m2_month": 26000, "rent_tier_multiplier": {"gyeonggi": 1.0, "jeju": 0.7},
                "washer_kg_per_cycle": capacity_kg, "cycles_per_hour": 1, "hours_per_week": 1, "machines_per_hub": 1,
                "linen_kg_per_turnover": 1, "max_linen_drive_min": 45},
        "vendor": {"cost_per_turnover_krw": {"mainland": vendor, "jeju": vendor + 10000}},
        "penalties": {"drive_krw_per_min_per_turnover": 100, "capacity_krw_per_turnover": 50000}}}


@pytest.fixture
def world(tmp_path, monkeypatch):
    """Instance builder wired to the tiny world and a temporary cache; any network call fails the test."""
    cache = tmp_path / "c.json"
    import json
    cache.write_text(json.dumps({travel._key(VILLAS["coords"][i], HUBS["coords"][j]): list(v) for (i, j), v in ROAD.items()}))
    def boom(*a, **k):
        raise AssertionError("network called: a cross-zone or uncached pair was requested")
    monkeypatch.setattr(travel.requests, "get", boom)
    monkeypatch.setattr(hub_model, "load_villas", lambda s: VILLAS)
    monkeypatch.setattr(hub_model, "load_hubs", lambda: HUBS)
    return lambda **kw: build_instance("current", cfg(**kw), cache_path=cache)


def test_cost_hand_computed(world):
    inst = world()
    # weekly rent: Hub1 = 26,000 x 12 / 52 = 6,000; Hub2 = 26,000 x 0.7 x 12 / 52 = 4,200
    assert inst["fixed"] == pytest.approx([6000, 4200])
    # Only Hub1 open. A -> hub: 2 turnovers x 2 x 10 km x 1000 = 40,000 (cheaper than vendor 2 x 30,000 = 60,000).
    # B -> hub would cost 3 x 2 x 20 x 1000 = 120,000 + drive penalty 3 x 100 x (60 - 45) = 4,500, so vendor 90,000 wins.
    # J has no open Jeju hub -> Jeju vendor 1 x 40,000.
    r = evaluate(inst, np.array([True, False]))
    assert [float(r[k][0]) for k in ("transport", "drive", "vendor", "fixed", "capacity")] == pytest.approx([40000, 0, 130000, 6000, 0])
    assert r["total"][0] == pytest.approx(176000) and list(r["assign"][0]) == [0, -1, -1]
    # Both open: J now uses the Jeju hub: 1 x 2 x 5 x 1000 = 10,000 < 40,000. total = 40,000 + 90,000 + 10,000 + 10,200
    assert evaluate(inst, np.array([True, True]))["total"][0] == pytest.approx(150200)


def test_drive_time_penalty_counts_when_the_hub_is_still_cheaper(world):
    inst = world(vendor=1e6)
    r = evaluate(inst, np.array([True, False]))          # B must use Hub1 (vendor is absurdly dear)
    assert r["drive"][0] == pytest.approx(4500)          # 3 turnovers x 100 KRW x 15 minutes over the 45-minute limit
    assert describe(inst, r["assign"][0])["villas_over_drive_limit"] == 1


def test_jeju_villa_never_uses_a_mainland_hub_and_vice_versa(world):
    inst = world()                                       # the fixture fails the test if any cross-zone pair was requested
    assert np.isinf(inst["pair"][2, 0]) and np.isinf(inst["pair"][0, 1]) and np.isinf(inst["pair"][1, 1])
    r = evaluate(inst, np.array([True, False]))          # no Jeju hub open -> the Jeju villa goes to the Jeju vendor
    assert r["assign"][0][2] == -1 and r["vendor"][0] == pytest.approx(90000 + 40000)
    for open_ in itertools.product([False, True], repeat=2):
        describe(inst, evaluate(inst, np.array(open_))["assign"][0])   # asserts no cross-zone service


def test_capacity_penalty(world):
    # capacity = 10 kg x 1 cycle x 1 h x 1 machine / 1 kg per turnover = 10 turnovers per week; A + B = 5 turnovers
    inst = world(vendor=1e9, capacity_kg=4.0)            # capacity 4: load 5 exceeds it by 1 -> 1 x 50,000
    assert evaluate(inst, np.array([True, False]))["capacity"][0] == pytest.approx(50000)
    inst = world(vendor=1e9, capacity_kg=5.0)            # load equal to capacity is fine
    assert evaluate(inst, np.array([True, False]))["capacity"][0] == 0


def _random_instance(seed, n_v=14, n_h=8, capacity=1e9):
    rng = np.random.default_rng(seed)
    pair = rng.uniform(5e4, 5e5, (n_v, n_h))
    pair[rng.random((n_v, n_h)) < 0.15] = np.inf         # some infeasible pairs (like cross-zone)
    return {"villas": {"turnovers": rng.integers(2, 6, n_v).astype(float)}, "pair": pair, "transport": pair, "drive": np.zeros_like(pair),
            "vendor": rng.uniform(2e5, 6e5, n_v), "fixed": rng.uniform(5e4, 4e5, n_h), "capacity": capacity, "cap_penalty": 5e4}


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_pulp_matches_brute_force(seed):
    inst = _random_instance(seed)                        # capacity never binds, so the GA's assignment rule is optimal too
    masks = np.array(list(itertools.product([False, True], repeat=8)))
    brute = evaluate(inst, masks)["total"].min()
    exact = solve_exact(inst, 60)
    assert exact["status"] == "Optimal" and exact["cost"] == pytest.approx(brute)


def test_pulp_is_a_lower_bound_when_capacity_binds():
    inst = _random_instance(3, capacity=6.0)
    brute = evaluate(inst, np.array(list(itertools.product([False, True], repeat=8))))["total"].min()
    assert solve_exact(inst, 60)["cost"] <= brute + 1e-6


def test_ga_is_deterministic_and_finds_the_optimum_on_a_small_instance():
    inst = _random_instance(0)
    ga = {"population": 30, "generations": 40, "crossover_prob": 0.9, "mutation_prob": 0.05, "elite": 1, "tournament_k": 3}
    a, b = run_ga(inst, "tournament", 5, ga), run_ga(inst, "tournament", 5, ga)
    assert np.array_equal(a["history"], b["history"]) and (np.diff(a["history"]) <= 1e-6).all()
    assert run_ga(inst, "roulette", 5, ga)["cost"] == pytest.approx(solve_exact(inst, 60)["cost"], rel=0.02)
