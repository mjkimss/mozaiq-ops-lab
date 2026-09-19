import json

import numpy as np
import pytest
import requests

from src import travel
from src.geo import haversine_km

CFG = {
    "osrm": {"base_url": "http://osrm.test", "batch_size": 2, "min_interval_s": 0, "timeout_s": 1,
             "retries": 0, "user_agent": "test"},
    "fallback": {"detour_factor": 1.5, "speed_kmh": 60},
}
A, B, C = (37.5, 127.0), (37.6, 127.1), (37.7, 127.2)
HUB = (37.55, 127.05)


class FakeResponse:
    """Stands in for requests.Response: every source is 30 minutes and 20 km from the destination."""
    def __init__(self, url):
        self.n = url.split("?")[0].count(";")  # coordinates in the path are joined by ';': that many sources + 1 destination
    def raise_for_status(self):
        pass
    def json(self):
        return {"code": "Ok", "durations": [[1800.0]] * self.n, "distances": [[20000.0]] * self.n}


@pytest.fixture
def calls(monkeypatch):
    log = []
    def fake_get(url, **kw):
        log.append(url)
        return FakeResponse(url)
    monkeypatch.setattr(travel.requests, "get", fake_get)
    return log


def test_cache_hit_makes_no_request(tmp_path, monkeypatch):
    cache = tmp_path / "c.json"
    cache.write_text(json.dumps({travel._key(A, HUB): [12.5, 9.0]}))
    def boom(*a, **k):
        raise AssertionError("network was called on a cache hit")
    monkeypatch.setattr(travel.requests, "get", boom)
    minutes, km, fb, stats = travel.travel_matrix([A], [HUB], cache_path=cache, cfg=CFG)
    assert (minutes[0, 0], km[0, 0], fb[0, 0]) == (12.5, 9.0, False)
    assert stats == {"cache": 1, "osrm": 0, "fallback": 0}


def test_each_pair_is_requested_once(tmp_path, calls):
    cache = tmp_path / "c.json"
    travel.travel_matrix([A, B, C], [HUB], cache_path=cache, cfg=CFG)
    assert len(calls) == 2                      # batch_size 2 -> 3 origins need 2 requests
    _, km, fb, stats = travel.travel_matrix([A, B, C], [HUB], cache_path=cache, cfg=CFG)
    assert len(calls) == 2                      # second time: all from the cache
    assert stats == {"cache": 3, "osrm": 0, "fallback": 0} and km.max() == 20.0 and not fb.any()


def test_api_failure_falls_back_and_is_flagged_not_cached(tmp_path, monkeypatch):
    def down(*a, **k):
        raise requests.ConnectionError("no network")
    monkeypatch.setattr(travel.requests, "get", down)
    cache = tmp_path / "c.json"
    minutes, km, fb, stats = travel.travel_matrix([A], [HUB], cache_path=cache, cfg=CFG)
    assert fb[0, 0] and stats["fallback"] == 1
    assert km[0, 0] == pytest.approx(haversine_km(*A, *HUB) * 1.5)
    assert minutes[0, 0] == pytest.approx(km[0, 0] / 60 * 60)
    assert not cache.exists() or json.loads(cache.read_text()) == {}   # fallbacks are never cached


def test_infeasible_pairs_are_never_requested(tmp_path, calls):
    feasible = np.array([[True], [False]])       # second origin cannot reach this destination (e.g. sea)
    minutes, km, fb, stats = travel.travel_matrix([A, B], [HUB], feasible=feasible, cache_path=tmp_path / "c.json", cfg=CFG)
    assert np.isinf(minutes[1, 0]) and np.isinf(km[1, 0]) and not fb[1, 0]
    assert len(calls) == 1 and "127.10000,37.60000" not in calls[0]   # only A and the hub were sent, never B
