# Decisions log

One entry per significant choice: what we chose, the alternatives, and why.

## Phase 1: faithful rebuild of the 2022 GA (v1)

**D1. Distance = haversine (great-circle) km.** Alternatives: Euclidean distance on raw degrees (what a quick
2022 script would likely do). Why: one degree of longitude is shorter than one degree of latitude in Korea, so
degrees are not a real distance. The paper only says "distance"; haversine is the simplest correct
straight-line version, and v2 reuses it as the fallback when the road-time API fails.

**D2. The chromosome is only DC coordinates; stores go to the nearest DC in their group.** Alternative: also
store the store-to-DC assignment as genes. Why: the paper's genotype is (lat, lon); once DC positions are fixed,
"nearest DC" is the best possible assignment anyway, so extra assignment genes would only add ways to be worse.

**D3. Two independent GA runs (part I: 3 durable DCs, stores a-i; part II: 2 non-durable DCs, stores j-p).**
Follows paper Table 1. Store letters come from sorting by descending longitude (store a = highest).

**D4. Masan coordinate corrected.** Paper Appendix 2 gives Masan (37.49914, 127.04832), a copy of Yeoksam in
Seoul. Replaced with approximate Masan city centre (35.20, 128.57), flagged "approximate" in the CSV. Effect:
uncorrected, a phantom second Seoul store would have entered the durable group (a-i) and the real Masan
in the south-east would be missing. Only the order among the southern stores depends on the exact value
(128.57 vs Bisan 128.556); the durable / non-durable split does not.

**D5. Stage 2 = re-run the GA seeded with stage 1's final population, fitness = 1 / (store distance + each DC's
distance to its nearest port).** Alternative (rejected by Minjoo): re-rank stage 1's population without further
evolution. Why: only re-running lets the ports move the DCs; the report shows stage 1 vs stage 2 side by side.

**D6. Selection is roulette wheel on fitness = 1 / distance, exactly as written.** Weakness noted in
paper_review.md (slices of the wheel are nearly equal when distances are similar, so selection pressure is weak).
v2 adds tournament selection and compares.

**D7. Crossover = each gene of the child (a latitude or a longitude value) is taken from parent 1 or parent 2 by
coin flip; with probability 1 - crossover_prob the child copies parent 1.** Alternatives: swap whole DCs, blend
(average) the parents. Why: paper says the inherited elements are "selected randomly since order is not
important"; coin-flip per gene is the simplest reading.

**D8. Mutation = random reset: a gene is replaced by a fresh uniform value inside the bounds (per-gene
probability 0.05).** Chosen by Minjoo over a small Gaussian nudge. Why: literal reading of "combinations excluded
have a chance to be included".

**D9. Elitism (copy the best individual unchanged into the next generation) is an addition beyond the paper.**
Alternative: no elitism, as described. Why: without it the best-so-far can be lost, so the convergence curve
would wander instead of showing the search's real progress. One line of code, flagged as not in the paper.

**D10. GA settings (population 100, 300 generations, crossover 0.9, mutation 0.05) are PLACEHOLDERs in
config.yaml.** The paper gives no values and no stopping rule. Not tuned. A test compares the result with an
independent k-median heuristic (Lloyd-style, 40 random restarts): the GA matches it within 1%. The heuristic was
slightly better in both groups (291.9 vs 292.0 km durable, 58.0 vs 58.6 km non-durable). This is a heuristic
check, not a proven optimum; the exact-optimum claim waits for PuLP in Phase 2.

**D11. Port coordinates are approximate PLACEHOLDERs** (Incheon 37.4750, 126.6100; Busan 35.1000, 129.0400).
The paper names the ports but gives no coordinates. Verify before quoting any port-distance number.

**D12. Search box kept exactly as the paper states it (lat 34-38, lon 120-130).** It is a rectangle, so a DC can
land in the sea or in North Korea. No land constraint added in v1; it is listed as a limitation.

**D13. Determinism:** one seeded numpy random generator (seed 42) is passed through the whole run.
Running twice gives identical text and PNG. (The map HTML contains random element ids, so its bytes
differ between runs though its content does not.)

**D14. Store-to-DC split follows Table 1 even though the paper's text says "one store is supplied by two DCs".**
Table 1 gives each store to one DC group only. Both statements cannot hold; Table 1 (and the brief) wins.

## Phase 2: MOZAIQ hub model (v2)

**D15. Cost = van transport + drive-time penalty + vendor fees + fixed hub cost + capacity penalty.** Transport is
turnovers x round trips x 2 x road km x cost per km. The drive-time penalty is constant per villa-hub pair, so it is
folded into the pair cost. Capacity overflow is penalized, not repaired (as specified). Alternative: hard capacity
and drive-time constraints. Why soft: every term is linear, so PuLP minimizes exactly the GA's function.

**D16. Jeju is a hard constraint through a `zone` (mainland | jeju) on villas, hubs and vendors.** A cross-zone pair is
never feasible: never assigned, never sent to OSRM. Alternative: a big penalty for crossing. Why hard: a van cannot
drive to Jeju; it mirrors the port logic of the 2022 paper. Tested end to end (a test fails if any cross-zone pair reaches the network).

**D17. Jeju villas are in "current" (3 of 30) and "expansion" (16 of 100).** MOZAIQ already has Jeju villas (press and
Minjoo's own research); the counts and the split between Jeju City and Seogwipo are simulated. Regions are labelled SIMULATED.

**D18. 21 candidate hub towns** (more than the 8 examples), so the search space is 2^21 = 2,097,152 hub sets and a GA is a
fair test. With about 10 candidates brute force is enough, and a test uses exactly that to cross-check PuLP.

**D19. Outsourced local vendor, one per zone: always available, no rent, no capacity limit, no bit in the chromosome.**
Flat fee per turnover. It removes the "unserved villa" case, so no unserved penalty exists. Reported per scenario: hub built or outsourced.

**D20. Rent lives in config.yaml by tier (rent per m2 x hub area), not in the CSV.** Small deviation from the brief, per the
rule that assumptions live in config.yaml with a source. `candidate_hubs.csv` carries a `rent_tier` column.

**D21. Shared objective for GA and exact solver.** PuLP/CBC (single sourcing: x_ij binary, overflow as a slack variable) minimizes
the same cost. Caveat shown in every run: the GA's assignment rule (cheapest open option, capacity penalized afterwards) is not
capacity-aware, the MIP's is; the run prints whether capacity binds by pricing the MIP's hub set with the GA's rule.

**D22. Travel-time module (shared with prototypes 2 and 3).** OSRM `table` endpoint, one destination per request with up to 50
origins, 1 request per second, one retry. Cache key = directional coordinate pair rounded to 5 decimals, so any prototype
or scenario reuses it. Only real answers are cached; fallbacks are flagged, counted, printed and never cached. Alternative: cache by
villa/hub id (breaks when data is regenerated). Public demo server is fine for a prototype; production would use self-hosted OSRM or Kakao Mobility.

**D23. The cache (`data/cache/osrm_pairs.json`, 92 KB, 1,628 pairs) is committed**, with `NOTICE.md`: "Road data (c) OpenStreetMap
contributors (ODbL)". Why: reproducible offline runs and no repeat load on the free server. It is a September 2026 snapshot.

**D24. Fallback settings are measured, not guessed:** median road/straight ratio 1.27 (p10 1.19, p90 1.50) and median implied
speed 68 km/h over the 1,628 pairs. The driver-cost speed (45 km/h, PLACEHOLDER) is deliberately lower than OSRM's 68 km/h because
OSRM's car profile is optimistic for a loaded van with stops. Direction of the bias: a lower speed raises driver cost per km (229 vs 152
KRW/km, van 489 vs 412), so this choice leans toward outsourcing. Not adjusted; see the check under D29.

**D25. Placeholders come from real-world references, not from a target hub count.** Sources actually opened are quoted in
config.yaml with URL and year: diesel/fuel economy (hi5-guide, April 2026), minimum wage (MOEL, 2025 announcement for 2026),
capital-area industrial rent (JLL via Real Estate Asia, Q2 2022), washer throughput (HOZO guide), linen per hotel room (BASE4, 2018).
Not found, so PLACEHOLDER with no source: vendor fee per kg or per turnover, regional rents outside the capital area, hub area, machines
per hub, linen kg per turnover, drive-time limit, villa turnovers. Nothing was adjusted after seeing results.

**D26. Fixed hub cost = rent only.** In-house labour, energy and machines are not modelled. This biases the model toward building
hubs, so an "outsource everything" answer is not caused by leaving hub costs out.

**D27. Van trips: one direct round trip per turnover (`van_round_trips_per_turnover` = 1.0).** Upper bound on van cost; real vans
batch several villas per run (prototype 2). Probably the most influential placeholder.

**D28. GA design.** One bit per hub, uniform crossover, bit-flip mutation, 1 elite, population 50 x 100 generations (5,000
evaluations, 0.24% of the space). Roulette keeps the paper's 1/cost fitness; tournament uses k=3. Both methods start from the same
initial population for a given seed (paired comparison), same 20 seeds in both scenarios. Settings are PLACEHOLDERs, not tuned.

**D29. Result with the sourced placeholders is (near) degenerate; reported, not tuned.** current: the optimum opens 0 hubs and
outsources everything, so the GA-vs-optimal comparison is trivial there. expansion: 2 hubs (Hongcheon, Jeju City), 90% of mainland
turnovers outsourced. An informational grid (not used for any setting) shows the answer hinges on two unsourced numbers, the vendor
fee and van batching: at 1.5x the vendor fee current opens 1 hub and expansion 7; at 2x, 3 and 8. The driver-speed choice (D24) does not matter: at 68 km/h (van 412 KRW/km) the counts stay 0 and 2. To be adjusted with Minjoo, with a stated reason.

**D30. Dependencies added: requests, pulp (pinned; PuLP 3.3.2 prints API-deprecation warnings for 4.0, filtered in pytest.ini).**
pandas skipped: csv + numpy cover loading and tables.

## Phase 2 addendum: GA validation, GA-vs-MIP rationale, limitation

**D31. GA stress tests: ALGORITHM VALIDATION, NOT A BUSINESS RECOMMENDATION.** The base results (0 and 2 hubs) make the GA-vs-optimal
test easy: "open nothing" or "open two" is found by almost any search. So `python -m src.run --stress` runs the expansion instance
with two unsourced numbers changed until 5-9 hubs open (settings from the informational grid in D29; `current` has no setting that opens
5+ hubs, so all three are expansion instances). Same 20 seeds, same GA budget (5,000 evaluations of 2^21), same PuLP check.
Results (per-seed CSVs in `outputs/v2_expansion_stress_*_runs.csv`); the exact solver proved optimality in about 0.1 s every time:

| instance | optimal hubs | roulette: mean / worst gap, optimum found | tournament: mean / worst gap, optimum found |
|---|---|---|---|
| vendor fee x2 | 8 | 0.64% / 2.52%, 13 of 20 | 0.00% / 0.00%, 20 of 20 |
| vendor fee x3 | 9 | 1.13% / 3.43%, 5 of 20 | 0.00% / 0.00%, 20 of 20 |
| 0.25 round trips, fee x1 | 5 | 1.17% / 4.14%, 10 of 20 | 0.00% / 0.00%, 20 of 20 |

Reading: on harder instances roulette (the paper's rule, weak pressure on 1/cost) degrades while tournament still finds the optimum in
every seed. Capacity never binds and the Jeju hard constraint held in every run. These instances say nothing about MOZAIQ; the
base results stay the business result: "outsource-first at these costs".

**D32. Why a GA if the MIP solves in 0.1 s?** At this scale (21 candidate hubs, 100 villas, linear costs) the exact solver is the better
tool: it is faster, proves optimality, and needs no tuning. The GA is kept for two reasons. (1) It is the bridge from the 2022 paper:
v1 to v2 shows the same method growing up, and roulette vs tournament is a direct answer to the paper's weak-selection limitation.
(2) A GA only needs a function that scores a hub set, so it can take costs a MIP cannot express directly, for example batched van
routing from prototype 2, where a hub's transport cost is the length of a real multi-stop route. If prototype 2 does not need that,
the honest recommendation is to use the exact solver. The MIP also earns its place as the validator of the GA.

**D33. Limitation: the vendor fee is flat regardless of distance, while in-house hubs pay per km.** A real local vendor would charge
more for a remote villa (longer pickup and delivery), and does not exist in every place. With a flat fee the model over-favours
outsourcing remote villas (e.g. Gangwon) relative to a distance-priced vendor. The model is NOT changed (base results stay as the
business result). Planned for Phase 3: a "vendor distance surcharge" (extra KRW per turnover per km from the nearest town) as one more
sensitivity line, alongside vendor fee, van batching, rent and turnovers.

## Phase 3: outputs and README

**D34. All sweeps and the heatmaps use the exact solver, not the GA.** A sweep should show the true optimum for each setting; the GA
only appears in the convergence and validation charts. Sweep ranges: vendor fee x0.5 to x4 by van round trips 1.0 to 0.1 (40 cells per
scenario); rent x0.1 to x4 by turnovers x0.5 to x3; surcharge 0 to 1,000 KRW per turnover per km. Ranges are wide on purpose so the
break-even edge is visible; the base cell is outlined in every grid.

**D35. Vendor distance surcharge (answers D33).** `vendor.distance_surcharge_krw_per_turnover_km` in config.yaml, default 0 (base results
unchanged). When set, vendor cost per turnover = flat fee + surcharge x road km from the villa to its nearest candidate hub town in its zone
(a stand-in for how remote the villa is). Result: at about the in-house van's cost per km (roughly 1,000 KRW) the 100-villa network opens 7 hubs
instead of 2; the 30-villa network still opens none. Also added `turnover_scale` to `build_instance` for the turnovers sensitivity.

**D36. What-if map is kept and clearly labelled.** `hubs_expansion_whatif_batched.html` (0.25 round trips per turnover, 5 hubs) carries a
banner "WHAT-IF, not a business recommendation", because the base business result has 0 and 2 hubs and a viewer should also see what a hub
network looks like. Base maps state the business result in their banner ("outsource-first at these costs").

**D37. README order and wording.** Korean summary first, then the break-even heatmap and one-paragraph key finding, then the GA-vs-exact
validation, then v1 vs v2, then the rest. The Korean draft was kept except: "공개 자료 기반 가정치" (assumptions based on public sources)
changed to "시뮬레이션 또는 가정치이며, 일부만 공개 자료를 참고" because several values (vendor fee, hub area, machines, linen kg, drive limit,
turnovers) have no source and the original would overclaim; two sentences were smoothed for grammar. Paper link points to
`docs/walmart_paper.md`; the file was scanned for a candidate number, session number, supervisor name and personal name and none was
present, so nothing was removed (the "Kim" hits are cited authors). Chart colours were checked with the dataviz validator; aqua is below 3:1
contrast on the light surface, so every aqua bar segment carries a visible value label and a legend entry.
