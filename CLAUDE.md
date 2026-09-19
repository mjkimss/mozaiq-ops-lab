# CLAUDE.md: mozaiq-ops-lab

## Who and why
Minjoo Kim (UCSD Cognitive Science ML + Business Economics) is building a portfolio project for a
Product Owner application at MOZAIQ (Villa MOZAIQ), a Korean startup running a high-end private-villa
membership. Job post facts: 30+ standalone villas, mostly Seoul capital area, expanding to Jeju and
Busan toward 100+. The PO mandate is "villa operations efficiency 10x": daily cleaning-staff
allocation, laundry pickup/delivery routing, cleaning QA automation, facility issue detection,
consumables reorder automation. Known regions (press): Seoul (Gahoe hanok), Gapyeong, Cheongpyeong,
Hongcheon, Yangyang, Jeju.

## Repo = three prototypes sharing data
1. Ops-hub network optimizer (built now). Extends the 2022 IB essay `docs/walmart_paper.md`
   (GA for Walmart Korea DC locations).
2. Laundry pickup/delivery router (later).
3. Photo-based cleaning QA (later).
Shared pieces (villa data, travel-time matrix + cache, config) are designed for reuse by 2 and 3.
Do not build anything for 2 or 3 until asked.

## Working rules
- Work in phases. Stop at the end of each phase, show results (numbers, charts, maps), wait for OK.
- Minjoo is not a software engineer: explain each design choice in plain language; every line must
  be defensible in an interview.
- Keep `docs/decisions.md`: for each significant choice, what we chose, alternatives, why. Short.
- Commit after each phase with a clear message.
- Never invent facts about MOZAIQ. Anything not in the context above is an assumption that lives in
  `config.yaml` with a comment ("source: ..." or "PLACEHOLDER").
- Simulated data must be labelled as simulated.

## Ponytail stance
Minimalism applies to HOW (simplest code, stdlib/numpy first, no unrequested abstractions, flat
module layout), NOT to WHAT is delivered. Required on purpose: faithful paper rebuild, exact-solver
(PuLP/CBC) validation, tests, README. Readability for a reviewer beats brevity.

## Allowed dependencies
numpy, pandas, requests, pyyaml, matplotlib, folium, pulp, pytest. Ask before adding anything else.

## Environment
Python 3.13, `.venv` at repo root. Run modules from the repo root: `python -m src.v1_walmart`.

## Roadmap
- Phase 0 setup; Phase 1 faithful 2022 GA (v1); Phase 2 MOZAIQ hub model (v2: OSRM travel time,
  capacitated facility location GA, exact-solver validation, Jeju hard constraint);
  Phase 3 show-ready outputs (maps, charts, README with Korean summary).
