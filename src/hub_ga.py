"""Binary genetic algorithm for the hub model: one bit per candidate hub (1 = open).
Two selection methods on the same budget: roulette wheel (as in the 2022 paper) and tournament."""
import time

import numpy as np

from src.hub_model import evaluate


def select_roulette(cost, rng, n, k=None):
    """Chance of being picked is proportional to fitness = 1 / cost (the paper's rule). Returns n pairs of parents."""
    fitness = 1.0 / cost
    return rng.choice(len(cost), size=(n, 2), p=fitness / fitness.sum())


def select_tournament(cost, rng, n, k):
    """For each parent: draw k random individuals, the cheapest one wins."""
    contenders = rng.integers(0, len(cost), size=(n, 2, k))
    winner = cost[contenders].argmin(axis=2)
    return np.take_along_axis(contenders, winner[..., None], axis=2)[..., 0]


SELECTION = {"roulette": select_roulette, "tournament": select_tournament}


def run_ga(inst, method, seed, ga):
    """One GA run. The seed fixes the initial population, so both methods start from the same one for a given seed."""
    t0 = time.perf_counter()
    rng = np.random.default_rng(seed)
    n, n_hubs = ga["population"], len(inst["fixed"])
    pop = rng.random((n, n_hubs)) < 0.5
    history = []
    for _ in range(ga["generations"]):
        cost = evaluate(inst, pop)["total"]
        history.append(cost.min())
        elite = pop[np.argsort(cost)[: ga["elite"]]]
        parents = SELECTION[method](cost, rng, n, ga["tournament_k"])
        mom, dad = pop[parents[:, 0]], pop[parents[:, 1]]
        child = np.where(rng.random(mom.shape) < 0.5, dad, mom)               # uniform crossover, bit by bit
        pop = np.where((rng.random(n) < ga["crossover_prob"])[:, None], child, mom)
        pop = pop ^ (rng.random(pop.shape) < ga["mutation_prob"])            # bit-flip mutation
        pop[: ga["elite"]] = elite
    res = evaluate(inst, pop)
    best = res["total"].argmin()
    history.append(res["total"][best])
    return {"open": pop[best], "cost": res["total"][best], "assign": res["assign"][best],
            "history": np.array(history), "runtime_s": time.perf_counter() - t0}
