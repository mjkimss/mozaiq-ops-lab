import numpy as np

from src.config import load_config
from src.geo import haversine_km
from src.v1_walmart import load_stores, run, run_ga, store_km, total_km

CFG = load_config()
ONE_DEG = 111.195  # km per degree of longitude on the equator


def test_fitness_hand_case():
    # One DC at (0, 1); stores at (0, 0) and (0, 2): each is one degree away.
    pop = np.array([[[0.0, 1.0]]])
    stores = np.array([[0.0, 0.0], [0.0, 2.0]])
    assert abs(store_km(pop, stores)[0] - 2 * ONE_DEG) < 0.05
    # Stage 2 adds the DC's distance to its NEAREST port: ports at (0, 3) and (0, 1.5) -> 0.5 degrees
    ports = np.array([[0.0, 3.0], [0.0, 1.5]])
    assert abs(total_km(pop, stores, ports)[0] - 2.5 * ONE_DEG) < 0.05


def test_each_store_uses_its_nearest_dc():
    # Two DCs; the far one must be ignored.
    pop = np.array([[[0.0, 0.0], [0.0, 50.0]]])
    stores = np.array([[0.0, 1.0]])
    assert abs(store_km(pop, stores)[0] - ONE_DEG) < 0.05


def test_store_naming_and_split():
    s = load_stores(CFG)
    assert s["durable"]["letters"] == list("abcdefghi")
    assert s["nondurable"]["letters"] == list("jklmnop")
    assert s["durable"]["names"][0] == "Pohangidong"  # highest longitude is store a
    lons = np.concatenate([s["durable"]["coords"][:, 1], s["nondurable"]["coords"][:, 1]])
    assert (np.diff(lons) <= 0).all()  # descending longitude a..p


def test_masan_no_longer_duplicates_yeoksam():
    s = load_stores(CFG)
    names = s["durable"]["names"] + s["nondurable"]["names"]
    coords = np.vstack([s["durable"]["coords"], s["nondurable"]["coords"]])
    masan, yeoksam = coords[names.index("Masan")], coords[names.index("Yeoksam")]
    assert haversine_km(*masan, *yeoksam) > 200  # Masan is in the south-east, Yeoksam in Seoul


def test_genes_stay_inside_paper_bounds():
    res = run(CFG)
    (la0, la1), (lo0, lo1) = CFG["v1"]["bounds"]["lat"], CFG["v1"]["bounds"]["lon"]
    for g in res["groups"].values():
        for r in g.values():
            assert ((r["dcs"][:, 0] >= la0) & (r["dcs"][:, 0] <= la1)).all()
            assert ((r["dcs"][:, 1] >= lo0) & (r["dcs"][:, 1] <= lo1)).all()


def test_same_seed_same_result():
    a, b = run(CFG), run(CFG)
    for group in a["groups"]:
        for stage in ("stage1", "stage2"):
            assert np.array_equal(a["groups"][group][stage]["dcs"], b["groups"][group][stage]["dcs"])
            assert np.array_equal(a["groups"][group][stage]["history"], b["groups"][group][stage]["history"])


def test_elitism_makes_best_distance_never_worse():
    res = run(CFG)
    for g in res["groups"].values():
        for r in g.values():
            assert (np.diff(r["history"]) <= 1e-9).all()


def _kmedian_reference(stores, k, seed=0, restarts=40):
    """Independent yardstick: many random-restart k-median runs (assign to nearest, then move each centre
    to the geometric median of its stores via Weiszfeld). Not part of the GA. Uses flat km coordinates."""
    rng = np.random.default_rng(seed)
    kx = np.cos(np.radians(stores[:, 0].mean())) * 111.195  # km per degree of longitude at this latitude
    xy = np.column_stack([stores[:, 1] * kx, stores[:, 0] * 111.195])  # (x = east km, y = north km)
    best = np.inf
    for _ in range(restarts):
        c = xy[rng.choice(len(xy), k, replace=False)].astype(float)
        for _ in range(30):
            lab = np.linalg.norm(xy[:, None] - c[None], axis=2).argmin(axis=1)
            for j in range(k):
                pts = xy[lab == j]
                if len(pts) == 0:
                    continue
                m = pts.mean(axis=0)
                for _ in range(30):  # Weiszfeld
                    d = np.maximum(np.linalg.norm(pts - m, axis=1), 1e-9)
                    m = (pts / d[:, None]).sum(axis=0) / (1 / d).sum()
                c[j] = m
        back = np.column_stack([c[:, 1] / 111.195, c[:, 0] / kx])  # back to (lat, lon)
        best = min(best, store_km(back[None], stores)[0])
    return best


def test_stage1_ga_is_close_to_the_true_optimum():
    """How good is the 2022 GA? Compare its stage-1 total with the k-median yardstick."""
    res, s = run(CFG), load_stores(CFG)
    for group, k in (("durable", 3), ("nondurable", 2)):
        ga_km, ref_km = res["groups"][group]["stage1"]["store_km"], _kmedian_reference(s[group]["coords"], k)
        print(f"{group}: GA {ga_km:.1f} km vs reference {ref_km:.1f} km (gap {100 * (ga_km / ref_km - 1):.2f}%)")
        assert ga_km <= ref_km * 1.05
