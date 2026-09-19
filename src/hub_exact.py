"""Exact solution of the same hub model with PuLP + CBC, to check the GA against the true optimum.
Every term in the GA's cost is linear, so this minimizes the very same function (capacity overflow is a slack variable)."""
import time

import numpy as np
import pulp

from src.hub_model import evaluate


def solve_exact(inst, time_limit_s):
    pair, vendor, fixed = inst["pair"], inst["vendor"], inst["fixed"]
    turnovers = inst["villas"]["turnovers"]
    n_v, n_h = pair.shape
    feasible = [(i, j) for i in range(n_v) for j in range(n_h) if np.isfinite(pair[i, j])]  # same zone only

    prob = pulp.LpProblem("hubs", pulp.LpMinimize)
    y = [pulp.LpVariable(f"open_{j}", cat="Binary") for j in range(n_h)]
    x = {(i, j): pulp.LpVariable(f"x_{i}_{j}", cat="Binary") for i, j in feasible}   # villa i served by hub j
    v = [pulp.LpVariable(f"vendor_{i}", cat="Binary") for i in range(n_v)]           # villa i outsourced
    s = [pulp.LpVariable(f"over_{j}", lowBound=0) for j in range(n_h)]               # turnovers above capacity

    prob += (pulp.lpSum(pair[i, j] * x[i, j] for i, j in feasible) + pulp.lpSum(vendor[i] * v[i] for i in range(n_v))
             + pulp.lpSum(fixed[j] * y[j] for j in range(n_h)) + inst["cap_penalty"] * pulp.lpSum(s))
    for i in range(n_v):
        prob += v[i] + pulp.lpSum(x[i, j] for j in range(n_h) if (i, j) in x) == 1   # every villa is served once
    for i, j in feasible:
        prob += x[i, j] <= y[j]                                                       # only open hubs serve
    for j in range(n_h):
        prob += pulp.lpSum(turnovers[i] * x[i, j] for i in range(n_v) if (i, j) in x) - s[j] <= inst["capacity"]

    t0 = time.perf_counter()
    prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit_s, gapRel=0.0))
    runtime = time.perf_counter() - t0

    assign = np.array([next((j for j in range(n_h) if (i, j) in x and x[i, j].value() > 0.5), -1) for i in range(n_v)])
    open_ = np.array([y[j].value() > 0.5 for j in range(n_h)])
    return {"cost": pulp.value(prob.objective), "open": open_, "assign": assign, "runtime_s": runtime,
            "status": "Optimal" if prob.sol_status == pulp.LpSolutionOptimal else "NOT proven optimal (time limit)",
            # the GA's own assignment rule applied to the MIP's hub set: equal cost means capacity does not bind
            "decoder_cost": float(evaluate(inst, open_)["total"][0])}
