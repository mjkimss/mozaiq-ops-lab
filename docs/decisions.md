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
independent k-median yardstick (gap 0.05% durable, 0.9% non-durable), so the settings are not hiding a bad result.

**D11. Port coordinates are approximate PLACEHOLDERs** (Incheon 37.4750, 126.6100; Busan 35.1000, 129.0400).
The paper names the ports but gives no coordinates. Verify before quoting any port-distance number.

**D12. Search box kept exactly as the paper states it (lat 34-38, lon 120-130).** It is a rectangle, so a DC can
land in the sea or in North Korea. No land constraint added in v1; it is listed as a limitation.

**D13. Determinism:** one seeded numpy random generator (seed 42) is passed through the whole run.
Running twice gives identical text, JSON and PNG. (The map HTML contains random element ids, so its bytes
differ between runs though its content does not.)

**D14. Store-to-DC split follows Table 1 even though the paper's text says "one store is supplied by two DCs".**
Table 1 gives each store to one DC group only. Both statements cannot hold; Table 1 (and the brief) wins.
