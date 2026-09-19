"""Road travel time and distance between points, from the public OSRM API, cached on disk.

Shared by every prototype (hub model now, laundry router and photo QA later).
  - Only real OSRM answers are cached (data/cache/osrm_pairs.json). Each (origin, destination) pair is requested once.
  - Requests are batched (one destination, up to batch_size origins per call) and spaced out, out of politeness
    to the free demo server. A production version would use a self-hosted OSRM or the Kakao Mobility API.
  - If the API fails, the pair falls back to haversine km x detour factor. Fallback pairs are flagged and counted,
    never cached, so a later run can replace them with real answers.
  - Pairs the caller marks infeasible (e.g. mainland villa -> Jeju hub) are never requested: they come back as inf.
Road data (c) OpenStreetMap contributors (ODbL), served by OSRM.
"""
import json
import time

import numpy as np
import requests

from src.config import ROOT, load_config
from src.geo import haversine_km

CACHE_PATH = ROOT / "data" / "cache" / "osrm_pairs.json"
_last_request = [0.0]  # time of the previous request, for the 1-request-per-second limit


def _key(a, b):
    """Cache key: directional pair of coordinates rounded to 5 decimals (about 1 m)."""
    return f"{a[0]:.5f},{a[1]:.5f}|{b[0]:.5f},{b[1]:.5f}"


def _fetch(sources, dest, cfg):
    """One OSRM table call: many sources -> one destination. Returns [(seconds, metres), ...] or None on failure."""
    coords = ";".join(f"{lon:.5f},{lat:.5f}" for lat, lon in [*sources, dest])
    url = (f"{cfg['base_url']}/table/v1/driving/{coords}?sources={';'.join(map(str, range(len(sources))))}"
           f"&destinations={len(sources)}&annotations=duration,distance")
    for _ in range(cfg["retries"] + 1):
        wait = _last_request[0] + cfg["min_interval_s"] - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_request[0] = time.monotonic()
        try:
            r = requests.get(url, timeout=cfg["timeout_s"], headers={"User-Agent": cfg["user_agent"]})
            r.raise_for_status()
            data = r.json()
            if data.get("code") != "Ok":
                raise ValueError(data.get("code"))
            return [(d[0], m[0]) for d, m in zip(data["durations"], data["distances"])]
        except (requests.RequestException, ValueError, KeyError, IndexError):
            continue
    return None


def travel_matrix(origins, dests, feasible=None, cache_path=CACHE_PATH, cfg=None):
    """Road minutes and km from every origin to every destination (each row of `origins`/`dests` is (lat, lon)).

    feasible: optional boolean (n_origins, n_dests); False pairs are skipped and returned as inf.
    Returns (minutes, km, is_fallback, stats) where stats counts pairs from the cache, from fresh OSRM calls,
    and from the haversine fallback."""
    cfg = cfg or load_config()["v2"]
    osrm, fb = cfg["osrm"], cfg["fallback"]
    n_o, n_d = len(origins), len(dests)
    feasible = np.ones((n_o, n_d), dtype=bool) if feasible is None else feasible
    minutes, km = np.full((n_o, n_d), np.inf), np.full((n_o, n_d), np.inf)
    is_fallback = np.zeros((n_o, n_d), dtype=bool)
    stats = {"cache": 0, "osrm": 0, "fallback": 0}
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}

    missing = {j: [] for j in range(n_d)}  # destination -> origins not in the cache yet
    for i in range(n_o):
        for j in range(n_d):
            if not feasible[i, j]:
                continue
            hit = cache.get(_key(origins[i], dests[j]))
            if hit:
                minutes[i, j], km[i, j] = hit
                stats["cache"] += 1
            else:
                missing[j].append(i)

    for j, idx in missing.items():
        for start in range(0, len(idx), osrm["batch_size"]):
            chunk = idx[start:start + osrm["batch_size"]]
            res = _fetch([tuple(origins[i]) for i in chunk], tuple(dests[j]), osrm)
            for n, i in enumerate(chunk):
                if res is not None and None not in res[n]:
                    seconds, metres = res[n]
                    minutes[i, j], km[i, j] = round(seconds / 60, 3), round(metres / 1000, 3)
                    cache[_key(origins[i], dests[j])] = [minutes[i, j], km[i, j]]
                    stats["osrm"] += 1
                else:
                    straight = haversine_km(*origins[i], *dests[j])
                    km[i, j] = straight * fb["detour_factor"]
                    minutes[i, j] = km[i, j] / fb["speed_kmh"] * 60
                    is_fallback[i, j] = True
                    stats["fallback"] += 1
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache, sort_keys=True, separators=(",", ":")))  # save after every request
    return minutes, km, is_fallback, stats
