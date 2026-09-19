# Review of the 2022 essay GA, and how v2 answers it

Paper: *Application of Genetic Algorithms to Optimize Distribution Center Locations of Large Retail Businesses
Attempting Market Penetration to Foreign Markets* (IB extended essay, 2022; `docs/walmart_paper.md`).

## What the paper got right
- **Right problem shape.** Walmart used a hub-and-spoke network (few DCs feeding many stores). Choosing DC
  positions to shorten the hub-to-spoke legs is exactly the structure of a hub network for any store or villa
  network.
- **Right method family for the size of the problem.** The GA was a sensible fit: the search is over positions
  and combinations, and nobody had a formula for it.
- **Honest scoping.** It says which factors it left out (traffic, road type, rent, legal) and why (no 2005 data).
  Its section 4-2 lists most of the limitations below itself.
- **A real domain idea.** Fresh (non-durable) goods need shorter transport than durable goods, so the two
  categories get separate DCs. Ports as import gateways (stage 2) are the right anchor for an import-heavy retailer.
- **Simple, checkable objective.** Fitness = 1 / total distance can be recomputed by hand.

## Limitations, and how v2 addresses each

| # | Limitation in the 2022 GA | What v2 (MOZAIQ hubs) does |
|---|---|---|
| 1 | **Straight-line distance only.** Roads, rivers, mountains and traffic are ignored. In Korea the gap is large (Seoul-Busan is about 325 km straight, longer by road). | Real road driving time and distance from OSRM, cached, with a haversine-times-detour fallback that is flagged in the output. |
| 2 | **No fixed or rent cost.** Distance alone always favours more, closer DCs; there is no reason not to open one per store. The paper fixed the number at 5. | Cost = weekly transport + weekly hub rent (candidate hubs carry a rent); the chromosome chooses *which* hubs to open, so the number of hubs is an output. |
| 3 | **No capacity, no time windows.** A DC can serve any number of stores; no limit on how far goods can travel. | Hub capacity and maximum linen drive time enter the cost as penalties. |
| 4 | **Called "reinforcement learning"** (section 3-2). A GA is an evolutionary metaheuristic: it evolves a population by selection and variation, with no agent, reward signal or policy. | The README and code use the correct name. |
| 5 | **Arbitrary durable / non-durable split.** The roles of DCs and the stores they serve were assigned arbitrarily, by longitude. (See also findings 8-9.) | No arbitrary split. Demand comes from a weekly-turnovers figure per villa, and every villa is assigned to its cheapest feasible open hub. |
| 6 | **No results reported.** The paper describes a method and never says what it found, so its claim that the GA "would have lessened Walmart's problems" is untested. | v1 now reports final locations and convergence (this repo). v2 reports GA-versus-optimal: cost gap %, runtime, and 10+ seeds. |
| 7 | **No check against an exact answer.** Nothing says whether the GA found the best solution or merely a good one. | v2 solves the same instances exactly (PuLP with CBC) and reports the gap. (For v1 a k-median yardstick in `tests/test_v1.py` shows the GA is within 0.05% and 0.9%.) |
| 8 | **The longitude-based split contradicts the paper's own intent.** It wants non-durable DCs "in the north and south" because stores cluster there, but a longitude sort is east-west. With the corrected Masan the split is: a-i = Pohang, Hakseong, Seomyeon, Siji, Masan, Bisan, Gamsam, Wolpyeong, Guseong; j-p = the seven Seoul-metro stores. Both non-durable DCs therefore sit in the capital area and none serves the south. | The role of a hub is decided by the model (which hubs to open and where), not by sorting stores. |
| 9 | **Internal contradiction.** The text says one store is supplied by two DCs (one durable, one non-durable), but Table 1 gives each store to only one group. | v2 has one kind of hub and one assignment rule (cheapest feasible open hub). |
| 10 | **Islands and ports as a soft term.** Ports enter only as an added distance; nothing stops a DC from being placed in the sea (the search box is a rectangle covering sea and North Korea). | Jeju villas can only be served by a Jeju hub (a hard constraint that mirrors the paper's port logic); hubs are chosen from real candidate towns, so none can land in the sea. |
| 11 | **Missing settings.** Population size, generations, rates and the stopping condition are not stated, so the run cannot be reproduced from the essay. | Every parameter is in `config.yaml`, with a fixed seed. |
| 12 | **Roulette wheel on 1 / distance has weak selection pressure.** When all individuals have similar distances, all get almost equal slices, so selection barely favours the better ones. | v2 keeps roulette (for fidelity) and adds tournament selection, compared on the same seeds. |
| 13 | **Data error in Appendix 2.** Masan duplicates Yeoksam's coordinates (and the table is titled "DC locations" although it lists stores). | Corrected in `data/walmart_stores.csv` and logged (decision D4). |

## What v1 found (seed 42)
See the Phase 1 report and `outputs/v1_result.json`. In short: stage 1 places the three durable DCs near
Busan, Daegu and central Korea, and the two non-durable DCs inside the Seoul-metro cluster. Stage 2 (adding the port
term) moves the third durable DC north to Guseong, next to Incheon, cutting port distance by about 74 km while
adding about 4 km of store distance.
