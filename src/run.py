"""Run the hub model and print GA-vs-optimal.
    python -m src.run --scenario current|expansion     the business scenarios (base results)
    python -m src.run --stress                          algorithm-validation instances (not a business recommendation)

Steps: build the instance (road times from the OSRM cache/API), solve it exactly with PuLP, run the GA with
roulette and with tournament selection over several seeds, and compare each GA result with the exact optimum.
"""
import argparse
import copy
import csv

import numpy as np

from src.config import ROOT, load_config
from src.data import SCENARIOS
from src.hub_exact import solve_exact
from src.hub_ga import SELECTION, run_ga
from src.hub_model import build_instance, describe, evaluate


def krw(x):
    return f"{x / 1e6:,.2f}M KRW"


def compare(inst, v2, title, csv_name):
    """Exact optimum, then GA (both selections, all seeds) against it. Prints everything and writes the per-seed CSV."""
    villas, hubs, stats = inst["villas"], inst["hubs"], inst["travel_stats"]
    print(f"== {title} ==")
    print(f"villas {len(villas['ids'])} ({int((villas['zone'] == 'jeju').sum())} on Jeju), "
          f"turnovers/week {villas['turnovers'].sum():.0f}, candidate hubs {len(hubs['ids'])}, "
          f"hub capacity {inst['capacity']:.0f} turnovers/week")
    print(f"travel data: {sum(stats.values())} villa-hub pairs: {stats['cache']} from cache, {stats['osrm']} fresh OSRM, "
          f"{stats['fallback']} HAVERSINE FALLBACK" + ("  <-- FLAGGED: these are not road times" if stats["fallback"] else ""))
    if stats["fallback"]:
        vi, hj = np.nonzero(inst["fallback"])
        print("  fallback pairs (villa->hub): " + ", ".join(f"{villas['ids'][i]}->{hubs['names'][j]}" for i, j in zip(vi[:8], hj[:8]))
              + (" ..." if len(vi) > 8 else ""))

    # ---- exact optimum
    ex = solve_exact(inst, v2["exact"]["time_limit_s"])
    facts = describe(inst, ex["assign"])
    parts = evaluate(inst, ex["open"])
    print(f"\nexact (PuLP/CBC): weekly cost {krw(ex['cost'])}, status {ex['status']}, runtime {ex['runtime_s']:.1f} s")
    print(f"  hubs opened ({len(facts['open_hubs'])}): {', '.join(facts['open_hubs']) or 'none (everything outsourced)'}")
    print("  share of turnovers outsourced to the vendor: " + ", ".join(f"{z} {s:.0%}" for z, s in facts["vendor_share"].items()))
    if "jeju" in facts["vendor_share"]:
        print("  Jeju: " + ("hub BUILT" if any(hubs["zone"][j] == "jeju" for j in ex["assign"][ex["assign"] >= 0]) else "OUTSOURCED (no Jeju hub)"))
    print("  cost breakdown (GA decoder on this hub set): " + ", ".join(f"{k} {krw(float(parts[k][0]))}" for k in ("transport", "drive", "vendor", "fixed", "capacity")))
    print(f"  violations: capacity overflow {facts['overflow_turnovers']:.0f} turnovers, villas beyond the {inst['max_drive_min']} min drive limit {facts['villas_over_drive_limit']}")
    print(f"  capacity binding? {'no' if abs(ex['decoder_cost'] - ex['cost']) < 1 else 'YES (GA decoder cost on the same hub set is ' + krw(ex['decoder_cost']) + ')'}")

    # ---- GA, both selection methods, same seeds
    seeds = range(v2["ga"]["n_seeds"])
    rows = []
    for method in SELECTION:
        for seed in seeds:
            r = run_ga(inst, method, seed, v2["ga"])
            describe(inst, r["assign"])  # asserts the Jeju constraint held
            rows.append({"seed": seed, "method": method, "cost": r["cost"], "gap_pct": max(0.0, round(100 * (r["cost"] / ex["cost"] - 1), 9)),  # rounds away float noise like -1e-13
                         "runtime_s": r["runtime_s"], "n_open": int(r["open"].sum()), "same_hubs_as_exact": bool((r["open"] == ex["open"]).all()),
                         "capacity_violated": bool(evaluate(inst, r["open"])["capacity"][0] > 0),
                         "open_hubs": ";".join(hubs["names"][j] for j in np.nonzero(r["open"])[0])})
    with open(ROOT / "outputs" / csv_name, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    g = v2["ga"]
    print(f"\nGA vs optimal ({len(seeds)} seeds, population {g['population']} x {g['generations']} generations, "
          f"{g['population'] * g['generations']:,} evaluations of 2^{len(hubs['ids'])} = {2 ** len(hubs['ids']):,} hub sets)")
    print(f"{'selection':<11}{'mean gap %':>11}{'worst gap %':>12}{'optimal cost':>14}{'same hubs':>11}{'runtime s':>10}{'hubs open':>10}{'violations':>11}")
    for method in SELECTION:
        m = [r for r in rows if r["method"] == method]
        print(f"{method:<11}{np.mean([r['gap_pct'] for r in m]):>11.3f}{max(r['gap_pct'] for r in m):>12.3f}"
              f"{sum(r['gap_pct'] < 1e-6 for r in m):>10}/{len(m):<3}{sum(r['same_hubs_as_exact'] for r in m):>7}/{len(m):<3}"
              f"{np.mean([r['runtime_s'] for r in m]):>10.2f}{np.mean([r['n_open'] for r in m]):>10.1f}{sum(r['capacity_violated'] for r in m):>11}")
    print(f"{'exact':<11}{'0':>11}{'0':>12}{'':>14}{'':>11}{ex['runtime_s']:>10.2f}{len(facts['open_hubs']):>10}{'':>11}")
    print("('optimal cost' column = seeds whose cost equals the exact optimum; 'same hubs' = seeds that opened the exact optimum's hub set)")
    print("Jeju hard constraint: checked on the exact solution and on every GA result: OK\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=SCENARIOS)
    parser.add_argument("--stress", action="store_true", help="algorithm-validation instances, not a business result")
    args = parser.parse_args()
    if bool(args.scenario) == args.stress:
        parser.error("give exactly one of --scenario or --stress")
    cfg = load_config()
    v2 = cfg["v2"]

    if not args.stress:
        title = f"scenario: {args.scenario}   (SIMULATED villas, PLACEHOLDER costs: not MOZAIQ data)"
        compare(build_instance(args.scenario, cfg), v2, title, f"v2_{args.scenario}_runs.csv")
        return
    for st in v2["stress_tests"]:
        c = copy.deepcopy(cfg)  # change only the two unsourced numbers; everything else is the base configuration
        c["v2"]["costs"]["van_round_trips_per_turnover"] = st["round_trips"]
        for zone in c["v2"]["vendor"]["cost_per_turnover_krw"]:
            c["v2"]["vendor"]["cost_per_turnover_krw"][zone] *= st["vendor_multiplier"]
        title = (f"ALGORITHM VALIDATION, NOT A BUSINESS RECOMMENDATION: {st['scenario']} instance '{st['name']}' "
                 f"(vendor fee x{st['vendor_multiplier']:g}, {st['round_trips']:g} van round trips per turnover)")
        compare(build_instance(st["scenario"], c), v2, title, f"v2_{st['scenario']}_stress_{st['name']}_runs.csv")


if __name__ == "__main__":
    main()
