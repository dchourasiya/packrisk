# Assumptions

Everything operational in this project is **simulated**. This file lists every modeling choice so a reviewer can disagree with a specific assumption instead of the whole project. Parameter values live in `config/params.json` and `config/delay_params.json`.

## 1. Site, products, plan

- One hypothetical assembly site, weekly time buckets, 8-week horizon.
- Two pack variants: **SR** (LFP prismatic, 100 cells) and **LR** (NMC cylindrical, 4,400 cells). Quantities per pack are in `src/packrisk/master.py`.
- Weekly plan: SR 900, LR 600 (12,000 packs over 8 weeks). Line capacity 1,600 packs/week, so up to 100 packs/week of catch-up is possible.
- **Lost packs** = plan − built at the end of week 8.
- **Backlog pack-weeks** = sum over weeks of (cumulative plan − cumulative built). It measures how far and how long production runs behind, even if it catches up by week 8.
- Penalties (hypothetical): **$2,000 per lost pack** (contribution-margin proxy) and **$100 per backlog pack-week** (lateness cost). These two numbers set how much mitigation is "worth it"; results change if they change. `packrisk.sensitivity` re-plans every policy at $1,000 and $4,000 per lost pack (see "Penalty sensitivity" in RESULTS.md).

## 2. Supply

- 20 tier-1 suppliers, 6 tier-2 sources, 4 lanes, 50 components (`master.py`).
- Purchase orders are scheduled just-in-time: one lot per component per week equal to that week's base-plan requirement.
- Starting inventory: cells 4 weeks of cover, electronics boards (C11, C12) 2 weeks, all others 2–4 weeks (fixed seed).
- A lot can be **late**, **partial**, **held for quality**, or **reduced by a capacity cut / scrap**.

| Mechanism | Model |
|---|---|
| Background lateness | Per lane: probability late and log-normal days late (`delay_params.json`), scaled by a supplier reliability multiplier |
| Lane shocks (background) | 5% chance per lane-week of a shared shock, median 7 days |
| Partial shipments | 10% of lots; 50–90% arrives, remainder one week later |
| Quality holds (background) | 3% of lots of flagged components; held 1–2 weeks, 0–20% scrap |
| Capacity cuts / scrap | Lost permanently within the horizon (no backlog recovery) |
| Arrivals after week 8 | Ignored |

**Delay calibration:** the shipped values are **placeholders**. `python -m packrisk.calibrate` refits them from the USAID Supply Chain Shipment Pricing dataset: ocean shipments → L1 and L4, truck shipments → L2 and L3. That data is health-commodity freight, not battery parts. It gives realistic *shape* (how late, how often, how skewed), not battery-specific truth.

## 3. Disruptions

- **Prior** (what the planner believes): lane delay +14 ± 5 days for 2–4 weeks; capacity cut 40–80% for 1–3 weeks; tier-2 cut 20–60% for 4–8 weeks; quality hold 1–3 weeks, 10–40% scrap.
- **Truth** (how the world behaves): equal to the prior for development scenarios D1–D6, deliberately different for held-out scenarios H1–H5 (see `world.py`).
- At week 0 the planner knows *which* disruption was announced and which suppliers, lanes or parts it affects, but not its severity or duration.
- **Correlation:** by default one draw of a lane or tier-2 shock hits every exposed supplier (correlated). The correlation stress test redraws it independently per supplier with the same marginal distribution.

## 4. Mitigation actions

| Action | Availability | Effect | Cost counted against budget |
|---|---|---|---|
| Expedite | Lanes L1, L4 (air), L2 (team driver); any scheduled lot | Lot arrives on its scheduled week regardless of lateness and lane events; still subject to capacity cuts and quality holds | 15% (air) or 3% (team driver) of unit cost |
| Extra inventory | Arrives no earlier than one lead time out (L1: week 7, L4: week 6, L2/L3: week 2); up to 20% of weekly requirement per week | Extra lot exposed to the same delays as normal lots | 4.6% of unit cost (≈12 weeks of holding at 20%/year) |
| Approved alternate | Only components with an approved alternate; from week 5 (3-week ramp + 1-week fast transit); up to 30% of weekly requirement | Arrives on time, but exposed to the alternate's own capacity and tier-2 risks | 8% premium + freight share of unit cost |

Only the incremental cost of mitigation counts against the $250,000 budget, not the base purchase price.

## 5. Decisions and evaluation

- **Static two-stage:** all actions are decided once at week 0 for the 8-week horizon. Weekly rolling re-planning is **not** implemented yet.
- Planning LP objective: mitigation cost + $2,000 × lost packs + $100 × backlog pack-weeks, with the budget as a hard limit.
- Deterministic LP plans on the average of 200 prior samples. Stochastic LP uses 100 prior samples. The CVaR version weighs the mean and the worst 10% of scenarios 50/50.
- The **oracle** solves the same LP on the realized scenario: same constraints, perfect knowledge.
- **Execution:** given the actions and the realized supply, production is scheduled optimally against the same objective. This flatters every policy equally.
- **Gating part:** in a week where material limits production, the gating part for a variant is the component with the lowest end-of-week inventory relative to its quantity per pack.
- Planning samples (seed 42) and evaluation realizations (seed 2027) are independent; tests check that plans don't depend on the evaluation world.

## 6. Known limitations

1. Simulated operations; placeholder delays until calibrated, and the calibration source isn't battery parts.
2. Static week-0 decisions; no rolling re-planning.
3. No backlog recovery after capacity cuts.
4. No minimum order quantities or integer lot sizes (pure LP).
5. Heuristic baselines ignore the disruption announcement; a real planner would react. They represent rule-of-thumb prioritization, not a straw man of human planners.
6. The lost-pack and backlog penalties drive the cost/benefit trade-off and are hypothetical values.
