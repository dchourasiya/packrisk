# PackRisk results

_All operational data is simulated. Results are "in simulation", never business savings._

- Delay parameters: PLACEHOLDER values. Replace by running: python -m packrisk.calibrate --usaid data/raw/<file>.csv
- 100 planning samples per scenario; 100 evaluation realizations per scenario
- Mitigation budget: $250,000 per 8-week horizon; runtime 1221.3s

## Mean lost packs (8-week horizon, plan = 12,000 packs)

| Scenario | Do nothing | Worst-supplier first | Lowest-cover first | Deterministic LP | Stochastic LP | Stochastic LP + CVaR | Oracle (perfect foresight) |
|---|---|---|---|---|---|---|---|
| D1 Asia ocean-lane port congestion (development) | 1,037 | 513 | 1,001 | 997 | 75 | 68 | 3 |
| D2 Semiconductor allocation (development) | 1,738 | 1,717 | 1,711 | 1,128 | 1,035 | 1,032 | 819 |
| D3 Enclosure plant outage (development) | 60 | 49 | 49 | 60 | 46 | 35 | 4 |
| D4 TIM quality hold (development) | 97 | 25 | 77 | 97 | 58 | 59 | 0 |
| D5 Demand mix shift (development) | 257 | 195 | 241 | 257 | 84 | 60 | 0 |
| D6 Port congestion + TIM hold (development) | 1,032 | 583 | 1,004 | 968 | 93 | 89 | 0 |
| H1 Europe ocean-lane disruption (held-out) | 1,674 | 1,674 | 1,674 | 1,674 | 218 | 126 | 0 |
| H2 Copper shortage (held-out) | 258 | 222 | 258 | 134 | 19 | 26 | 0 |
| H3 Long adhesive quality hold (held-out) | 52 | 12 | 52 | 52 | 37 | 36 | 0 |
| H4 Port congestion, 30% worse (held-out) | 2,024 | 1,300 | 1,975 | 1,968 | 368 | 323 | 0 |
| H5 Multi-event combination (held-out) | 295 | 275 | 295 | 295 | 83 | 74 | 0 |

## Mean total cost ($k) = $2,000 × lost packs + $100 × backlog pack-weeks + mitigation spend

| Scenario | Do nothing | Worst-supplier first | Lowest-cover first | Deterministic LP | Stochastic LP | Stochastic LP + CVaR | Oracle (perfect foresight) |
|---|---|---|---|---|---|---|---|
| D1 Asia ocean-lane port congestion (development) | 2,741 | 1,614 | 2,887 | 2,640 | 374 | 367 | 45 |
| D2 Semiconductor allocation (development) | 4,021 | 4,207 | 4,181 | 2,902 | 2,708 | 2,706 | 1,965 |
| D3 Enclosure plant outage (development) | 142 | 363 | 363 | 142 | 128 | 106 | 9 |
| D4 TIM quality hold (development) | 231 | 308 | 435 | 231 | 144 | 144 | 1 |
| D5 Demand mix shift (development) | 601 | 693 | 810 | 601 | 236 | 258 | 2 |
| D6 Port congestion + TIM hold (development) | 2,736 | 1,807 | 2,911 | 2,569 | 396 | 435 | 34 |
| H1 Europe ocean-lane disruption (held-out) | 4,401 | 4,651 | 4,651 | 4,401 | 627 | 431 | 22 |
| H2 Copper shortage (held-out) | 618 | 775 | 868 | 346 | 83 | 102 | 1 |
| H3 Long adhesive quality hold (held-out) | 125 | 282 | 375 | 125 | 94 | 97 | 0 |
| H4 Port congestion, 30% worse (held-out) | 5,247 | 3,629 | 5,359 | 5,108 | 1,080 | 985 | 80 |
| H5 Multi-event combination (held-out) | 786 | 987 | 1,036 | 786 | 223 | 210 | 1 |

![cost heatmap](outputs/figures/policy_cost_heatmap.png)

## Value of the stochastic solution and oracle capture

VSS = expected total cost of the deterministic LP minus the stochastic LP. Oracle capture = share of the do-nothing → oracle gap in lost packs that the policy closes.

| Scenario | Split | VSS ($k) | Stochastic LP oracle capture | CVaR oracle capture | Stochastic LP spend ($k) |
|---|---|---|---|---|---|
| D1 | development | 2,266 | 93% | 94% | 181 |
| D2 | development | 194 | 76% | 77% | 250 |
| D3 | development | 14 | 25% | 43% | 18 |
| D4 | development | 87 | 40% | 39% | 3 |
| D5 | development | 365 | 67% | 77% | 34 |
| D6 | development | 2,173 | 91% | 91% | 174 |
| H1 | held-out | 3,774 | 87% | 92% | 39 |
| H2 | held-out | 263 | 93% | 90% | 35 |
| H3 | held-out | 31 | 29% | 31% | 6 |
| H4 | held-out | 4,028 | 82% | 84% | 187 |
| H5 | held-out | 563 | 72% | 75% | 22 |

## Where the method fails or barely helps (auto-detected)

- **D2**: large remaining gap to the oracle (1,035 vs 819 lost packs); the budget was binding and some loss cannot be bought back.
- **D3 Enclosure plant outage**: best simple policy (Do nothing) costs $142k vs $128k for the stochastic LP (+10% advantage to the LP).
- **D4**: a heuristic protects more packs (25 lost vs 58) but spends $250k to do it; the LP judges the extra packs not worth that cost at the stated penalties.
- **H1**: large remaining gap to the oracle (218 vs 0 lost packs); the LP spent only $39k of $250k because its model judged more protection not worth the cost; the planner's prior underestimated this disruption (deliberate misspecification).
- **H3**: a heuristic protects more packs (12 lost vs 37) but spends $250k to do it; the LP judges the extra packs not worth that cost at the stated penalties.
- **H4**: large remaining gap to the oracle (368 vs 0 lost packs); the LP spent only $187k of $250k because its model judged more protection not worth the cost; the planner's prior underestimated this disruption (deliberate misspecification).

## Budget sweep (stochastic LP)

| scenario_id | budget | mitigation_cost | stochastic_mean_lost | stochastic_p90_lost | oracle_mean_lost | packs_protected |
|---|---|---|---|---|---|---|
| D1 | 0 | 0 | 1,037 | 2,600 | 1,037 | 0 |
| D1 | 50000 | 50,000 | 363 | 1,042 | 112 | 674 |
| D1 | 100000 | 100,000 | 171 | 680 | 27 | 866 |
| D1 | 150000 | 150,000 | 116 | 511 | 9 | 921 |
| D1 | 250000 | 181,246 | 75 | 106 | 3 | 963 |
| D1 | 400000 | 181,246 | 75 | 106 | 1 | 963 |
| D1 | 600000 | 181,246 | 75 | 106 | 0 | 963 |
| D2 | 0 | 0 | 1,738 | 3,474 | 1,738 | 0 |
| D2 | 50000 | 50,000 | 1,491 | 3,132 | 974 | 247 |
| D2 | 100000 | 100,000 | 1,350 | 2,979 | 839 | 388 |
| D2 | 150000 | 150,000 | 1,227 | 2,708 | 821 | 510 |
| D2 | 250000 | 250,000 | 1,035 | 2,549 | 819 | 702 |
| D2 | 400000 | 380,414 | 911 | 2,543 | 819 | 826 |
| D2 | 600000 | 380,414 | 911 | 2,543 | 819 | 826 |
| D3 | 0 | 0 | 60 | 4 | 60 | 0 |
| D3 | 50000 | 17,979 | 46 | 0 | 4 | 14 |
| D3 | 100000 | 17,979 | 46 | 0 | 4 | 14 |
| D3 | 150000 | 17,979 | 46 | 0 | 4 | 14 |
| D3 | 250000 | 17,979 | 46 | 0 | 4 | 14 |
| D3 | 400000 | 17,979 | 46 | 0 | 4 | 14 |
| D3 | 600000 | 17,979 | 46 | 0 | 4 | 14 |
| D4 | 0 | 0 | 97 | 0 | 97 | 0 |
| D4 | 50000 | 3,278 | 58 | 0 | 0 | 38 |
| D4 | 100000 | 3,278 | 58 | 0 | 0 | 38 |
| D4 | 150000 | 3,278 | 58 | 0 | 0 | 38 |
| D4 | 250000 | 3,278 | 58 | 0 | 0 | 38 |
| D4 | 400000 | 3,278 | 58 | 0 | 0 | 38 |
| D4 | 600000 | 3,278 | 58 | 0 | 0 | 38 |
| D5 | 0 | 0 | 257 | 540 | 257 | 0 |
| D5 | 50000 | 33,845 | 84 | 141 | 0 | 172 |
| D5 | 100000 | 33,845 | 84 | 141 | 0 | 172 |
| D5 | 150000 | 33,845 | 84 | 141 | 0 | 172 |
| D5 | 250000 | 33,845 | 84 | 141 | 0 | 172 |
| D5 | 400000 | 33,845 | 84 | 141 | 0 | 172 |
| D5 | 600000 | 33,845 | 84 | 141 | 0 | 172 |
| D6 | 0 | 0 | 1,032 | 2,600 | 1,032 | 0 |
| D6 | 50000 | 50,000 | 371 | 1,200 | 89 | 661 |
| D6 | 100000 | 100,000 | 158 | 864 | 12 | 874 |
| D6 | 150000 | 150,000 | 109 | 472 | 0 | 923 |
| D6 | 250000 | 173,816 | 93 | 28 | 0 | 938 |
| D6 | 400000 | 173,816 | 93 | 28 | 0 | 938 |
| D6 | 600000 | 173,816 | 93 | 28 | 0 | 938 |
| H1 | 0 | 0 | 1,674 | 2,610 | 1,674 | 0 |
| H1 | 50000 | 39,086 | 218 | 580 | 4 | 1,456 |
| H1 | 100000 | 39,086 | 218 | 580 | 0 | 1,456 |
| H1 | 150000 | 39,086 | 218 | 580 | 0 | 1,456 |
| H1 | 250000 | 39,086 | 218 | 580 | 0 | 1,456 |
| H1 | 400000 | 39,086 | 218 | 580 | 0 | 1,456 |
| H1 | 600000 | 39,086 | 218 | 580 | 0 | 1,456 |
| H2 | 0 | 0 | 258 | 724 | 258 | 0 |
| H2 | 50000 | 35,033 | 19 | 0 | 0 | 240 |
| H2 | 100000 | 35,033 | 19 | 0 | 0 | 240 |
| H2 | 150000 | 35,033 | 19 | 0 | 0 | 240 |
| H2 | 250000 | 35,033 | 19 | 0 | 0 | 240 |
| H2 | 400000 | 35,033 | 19 | 0 | 0 | 240 |
| H2 | 600000 | 35,033 | 19 | 0 | 0 | 240 |
| H3 | 0 | 0 | 52 | 0 | 52 | 0 |
| H3 | 50000 | 5,913 | 37 | 0 | 0 | 15 |
| H3 | 100000 | 5,913 | 37 | 0 | 0 | 15 |
| H3 | 150000 | 5,913 | 37 | 0 | 0 | 15 |
| H3 | 250000 | 5,913 | 37 | 0 | 0 | 15 |
| H3 | 400000 | 5,913 | 37 | 0 | 0 | 15 |
| H3 | 600000 | 5,913 | 37 | 0 | 0 | 15 |
| H4 | 0 | 0 | 2,024 | 2,981 | 2,024 | 0 |
| H4 | 50000 | 50,000 | 1,081 | 2,003 | 391 | 943 |
| H4 | 100000 | 100,000 | 688 | 1,500 | 106 | 1,336 |
| H4 | 150000 | 150,000 | 459 | 1,289 | 15 | 1,565 |
| H4 | 250000 | 187,021 | 368 | 1,049 | 0 | 1,655 |
| H4 | 400000 | 187,021 | 368 | 1,049 | 0 | 1,655 |
| H4 | 600000 | 187,021 | 368 | 1,049 | 0 | 1,655 |
| H5 | 0 | 0 | 295 | 1,100 | 295 | 0 |
| H5 | 50000 | 21,836 | 83 | 65 | 0 | 212 |
| H5 | 100000 | 21,836 | 83 | 65 | 0 | 212 |
| H5 | 150000 | 21,836 | 83 | 65 | 0 | 212 |
| H5 | 250000 | 21,836 | 83 | 65 | 0 | 212 |
| H5 | 400000 | 21,836 | 83 | 65 | 0 | 212 |
| H5 | 600000 | 21,836 | 83 | 65 | 0 | 212 |

![budget](outputs/figures/budget_curve.png)

## Penalty sensitivity (lost-pack penalty $1k / $2k / $4k)

Every policy except the oracle is re-planned with each penalty and evaluated on the same realizations; the backlog penalty stays at $100 per pack-week.

- The stochastic LP has lower expected total cost than doing nothing in **33 of 33** scenario-penalty combinations.
- It is the lowest-cost policy, or within 5% of it, in **22 of 33**.
- The lowest-cost policy is one of the two stochastic LPs (with or without CVaR) in **33 of 33**; no heuristic or deterministic plan is ever cheapest.

| Penalty | Scenario | Do nothing lost | Stochastic LP lost | Stochastic LP spend ($k) | Net saving vs do nothing ($k) | Lowest-cost policy |
|---|---|---|---|---|---|---|
| $1,000 | D1 Asia ocean-lane port congestion | 1,037 | 74 | 179 | 1,409 | Stochastic LP |
| $1,000 | D2 Semiconductor allocation | 1,738 | 1,038 | 250 | 610 | Stochastic LP |
| $1,000 | D3 Enclosure plant outage | 60 | 46 | 14 | 3 | Stochastic LP + CVaR |
| $1,000 | D4 TIM quality hold | 97 | 58 | 3 | 48 | Stochastic LP |
| $1,000 | D5 Demand mix shift | 257 | 85 | 29 | 195 | Stochastic LP |
| $1,000 | D6 Port congestion + TIM hold | 1,032 | 95 | 165 | 1,408 | Stochastic LP |
| $1,000 | H1 Europe ocean-lane disruption | 1,674 | 218 | 39 | 2,318 | Stochastic LP + CVaR |
| $1,000 | H2 Copper shortage | 258 | 19 | 35 | 295 | Stochastic LP |
| $1,000 | H3 Long adhesive quality hold | 52 | 37 | 6 | 16 | Stochastic LP |
| $1,000 | H4 Port congestion, 30% worse | 2,024 | 388 | 176 | 2,492 | Stochastic LP + CVaR |
| $1,000 | H5 Multi-event combination | 295 | 83 | 16 | 357 | Stochastic LP |
| $2,000 | D1 Asia ocean-lane port congestion | 1,037 | 75 | 181 | 2,367 | Stochastic LP + CVaR |
| $2,000 | D2 Semiconductor allocation | 1,738 | 1,035 | 250 | 1,313 | Stochastic LP + CVaR |
| $2,000 | D3 Enclosure plant outage | 60 | 46 | 18 | 14 | Stochastic LP + CVaR |
| $2,000 | D4 TIM quality hold | 97 | 58 | 3 | 87 | Stochastic LP |
| $2,000 | D5 Demand mix shift | 257 | 84 | 34 | 365 | Stochastic LP |
| $2,000 | D6 Port congestion + TIM hold | 1,032 | 93 | 174 | 2,340 | Stochastic LP |
| $2,000 | H1 Europe ocean-lane disruption | 1,674 | 218 | 39 | 3,774 | Stochastic LP + CVaR |
| $2,000 | H2 Copper shortage | 258 | 19 | 35 | 535 | Stochastic LP |
| $2,000 | H3 Long adhesive quality hold | 52 | 37 | 6 | 31 | Stochastic LP |
| $2,000 | H4 Port congestion, 30% worse | 2,024 | 368 | 187 | 4,167 | Stochastic LP + CVaR |
| $2,000 | H5 Multi-event combination | 295 | 83 | 22 | 563 | Stochastic LP + CVaR |
| $4,000 | D1 Asia ocean-lane port congestion | 1,037 | 75 | 181 | 4,292 | Stochastic LP + CVaR |
| $4,000 | D2 Semiconductor allocation | 1,738 | 1,035 | 250 | 2,718 | Stochastic LP + CVaR |
| $4,000 | D3 Enclosure plant outage | 60 | 46 | 18 | 42 | Stochastic LP + CVaR |
| $4,000 | D4 TIM quality hold | 97 | 58 | 3 | 164 | Stochastic LP |
| $4,000 | D5 Demand mix shift | 257 | 81 | 46 | 713 | Stochastic LP + CVaR |
| $4,000 | D6 Port congestion + TIM hold | 1,032 | 93 | 200 | 4,191 | Stochastic LP |
| $4,000 | H1 Europe ocean-lane disruption | 1,674 | 218 | 80 | 6,646 | Stochastic LP + CVaR |
| $4,000 | H2 Copper shortage | 258 | 19 | 35 | 1,014 | Stochastic LP |
| $4,000 | H3 Long adhesive quality hold | 52 | 37 | 6 | 61 | Stochastic LP |
| $4,000 | H4 Port congestion, 30% worse | 2,024 | 329 | 205 | 7,644 | Stochastic LP + CVaR |
| $4,000 | H5 Multi-event combination | 295 | 83 | 25 | 984 | Stochastic LP + CVaR |

## Correlation stress tests

| test | scenario_id | setting | metric | value |
|---|---|---|---|---|
| Correlation (do nothing) | D1 | correlated | mean_lost_packs | 1,033.63 |
| Correlation (do nothing) | D1 | correlated | p90_lost_packs | 2,600.00 |
| Correlation (do nothing) | D1 | correlated | p95_lost_packs | 2,700.00 |
| Correlation (do nothing) | D1 | correlated | prob_any_loss | 0.72 |
| Correlation (do nothing) | D1 | independent | mean_lost_packs | 1,294.56 |
| Correlation (do nothing) | D1 | independent | p90_lost_packs | 2,600.00 |
| Correlation (do nothing) | D1 | independent | p95_lost_packs | 2,700.00 |
| Correlation (do nothing) | D1 | independent | prob_any_loss | 0.86 |
| Planner correlation assumption | D1 | planner assumes correlation | mean_lost_packs | 74.52 |
| Planner correlation assumption | D1 | planner assumes correlation | p90_lost_packs | 105.62 |
| Planner correlation assumption | D1 | planner assumes correlation | mitigation_cost | 181,246.44 |
| Planner correlation assumption | D1 | planner assumes independence | mean_lost_packs | 103.14 |
| Planner correlation assumption | D1 | planner assumes independence | p90_lost_packs | 578.08 |
| Planner correlation assumption | D1 | planner assumes independence | mitigation_cost | 175,789.02 |
| Correlation (do nothing) | D2 | correlated | mean_lost_packs | 1,682.93 |
| Correlation (do nothing) | D2 | correlated | p90_lost_packs | 3,445.17 |
| Correlation (do nothing) | D2 | correlated | p95_lost_packs | 3,792.69 |
| Correlation (do nothing) | D2 | correlated | prob_any_loss | 0.91 |
| Correlation (do nothing) | D2 | independent | mean_lost_packs | 1,986.76 |
| Correlation (do nothing) | D2 | independent | p90_lost_packs | 3,636.28 |
| Correlation (do nothing) | D2 | independent | p95_lost_packs | 3,873.53 |
| Correlation (do nothing) | D2 | independent | prob_any_loss | 0.98 |
| Planner correlation assumption | D2 | planner assumes correlation | mean_lost_packs | 1,035.48 |
| Planner correlation assumption | D2 | planner assumes correlation | p90_lost_packs | 2,548.77 |
| Planner correlation assumption | D2 | planner assumes correlation | mitigation_cost | 250,000.00 |
| Planner correlation assumption | D2 | planner assumes independence | mean_lost_packs | 1,076.61 |
| Planner correlation assumption | D2 | planner assumes independence | p90_lost_packs | 2,616.56 |
| Planner correlation assumption | D2 | planner assumes independence | mitigation_cost | 250,000.00 |
| Correlation (do nothing) | D3 | correlated | mean_lost_packs | 105.28 |
| Correlation (do nothing) | D3 | correlated | p90_lost_packs | 314.39 |
| Correlation (do nothing) | D3 | correlated | p95_lost_packs | 1,058.71 |
| Correlation (do nothing) | D3 | correlated | prob_any_loss | 0.12 |
| Correlation (do nothing) | D3 | independent | mean_lost_packs | 53.25 |
| Correlation (do nothing) | D3 | independent | p90_lost_packs | 0.00 |
| Correlation (do nothing) | D3 | independent | p95_lost_packs | 287.69 |
| Correlation (do nothing) | D3 | independent | prob_any_loss | 0.07 |
| Planner correlation assumption | D3 | planner assumes correlation | mean_lost_packs | 45.64 |
| Planner correlation assumption | D3 | planner assumes correlation | p90_lost_packs | 0.00 |
| Planner correlation assumption | D3 | planner assumes correlation | mitigation_cost | 17,978.87 |
| Planner correlation assumption | D3 | planner assumes independence | mean_lost_packs | 23.36 |
| Planner correlation assumption | D3 | planner assumes independence | p90_lost_packs | 0.00 |
| Planner correlation assumption | D3 | planner assumes independence | mitigation_cost | 18,865.56 |
| Correlation (do nothing) | D4 | correlated | mean_lost_packs | 87.04 |
| Correlation (do nothing) | D4 | correlated | p90_lost_packs | 0.00 |
| Correlation (do nothing) | D4 | correlated | p95_lost_packs | 1,160.00 |
| Correlation (do nothing) | D4 | correlated | prob_any_loss | 0.08 |
| Correlation (do nothing) | D4 | independent | mean_lost_packs | 78.46 |
| Correlation (do nothing) | D4 | independent | p90_lost_packs | 0.00 |
| Correlation (do nothing) | D4 | independent | p95_lost_packs | 563.77 |
| Correlation (do nothing) | D4 | independent | prob_any_loss | 0.08 |
| Planner correlation assumption | D4 | planner assumes correlation | mean_lost_packs | 58.36 |
| Planner correlation assumption | D4 | planner assumes correlation | p90_lost_packs | 0.00 |
| Planner correlation assumption | D4 | planner assumes correlation | mitigation_cost | 3,277.79 |
| Planner correlation assumption | D4 | planner assumes independence | mean_lost_packs | 86.24 |
| Planner correlation assumption | D4 | planner assumes independence | p90_lost_packs | 0.00 |
| Planner correlation assumption | D4 | planner assumes independence | mitigation_cost | 3,838.80 |
| Correlation (do nothing) | D5 | correlated | mean_lost_packs | 221.30 |
| Correlation (do nothing) | D5 | correlated | p90_lost_packs | 361.07 |
| Correlation (do nothing) | D5 | correlated | p95_lost_packs | 1,240.00 |
| Correlation (do nothing) | D5 | correlated | prob_any_loss | 0.62 |
| Correlation (do nothing) | D5 | independent | mean_lost_packs | 196.58 |
| Correlation (do nothing) | D5 | independent | p90_lost_packs | 360.00 |
| Correlation (do nothing) | D5 | independent | p95_lost_packs | 1,012.00 |
| Correlation (do nothing) | D5 | independent | prob_any_loss | 0.64 |
| Planner correlation assumption | D5 | planner assumes correlation | mean_lost_packs | 84.37 |
| Planner correlation assumption | D5 | planner assumes correlation | p90_lost_packs | 141.00 |
| Planner correlation assumption | D5 | planner assumes correlation | mitigation_cost | 33,845.32 |
| Planner correlation assumption | D5 | planner assumes independence | mean_lost_packs | 108.82 |
| Planner correlation assumption | D5 | planner assumes independence | p90_lost_packs | 213.55 |
| Planner correlation assumption | D5 | planner assumes independence | mitigation_cost | 27,671.27 |
| Correlation (do nothing) | D6 | correlated | mean_lost_packs | 973.57 |
| Correlation (do nothing) | D6 | correlated | p90_lost_packs | 2,600.00 |
| Correlation (do nothing) | D6 | correlated | p95_lost_packs | 2,600.00 |
| Correlation (do nothing) | D6 | correlated | prob_any_loss | 0.70 |
| Correlation (do nothing) | D6 | independent | mean_lost_packs | 1,269.34 |
| Correlation (do nothing) | D6 | independent | p90_lost_packs | 2,600.00 |
| Correlation (do nothing) | D6 | independent | p95_lost_packs | 2,700.00 |
| Correlation (do nothing) | D6 | independent | prob_any_loss | 0.86 |
| Planner correlation assumption | D6 | planner assumes correlation | mean_lost_packs | 93.43 |
| Planner correlation assumption | D6 | planner assumes correlation | p90_lost_packs | 27.50 |
| Planner correlation assumption | D6 | planner assumes correlation | mitigation_cost | 173,815.54 |
| Planner correlation assumption | D6 | planner assumes independence | mean_lost_packs | 80.52 |
| Planner correlation assumption | D6 | planner assumes independence | p90_lost_packs | 0.00 |
| Planner correlation assumption | D6 | planner assumes independence | mitigation_cost | 198,533.42 |
| Correlation (do nothing) | H1 | correlated | mean_lost_packs | 1,680.87 |
| Correlation (do nothing) | H1 | correlated | p90_lost_packs | 2,700.00 |
| Correlation (do nothing) | H1 | correlated | p95_lost_packs | 2,700.00 |
| Correlation (do nothing) | H1 | correlated | prob_any_loss | 0.90 |
| Correlation (do nothing) | H1 | independent | mean_lost_packs | 1,740.35 |
| Correlation (do nothing) | H1 | independent | p90_lost_packs | 2,700.00 |
| Correlation (do nothing) | H1 | independent | p95_lost_packs | 2,700.00 |
| Correlation (do nothing) | H1 | independent | prob_any_loss | 0.96 |
| Planner correlation assumption | H1 | planner assumes correlation | mean_lost_packs | 218.24 |
| Planner correlation assumption | H1 | planner assumes correlation | p90_lost_packs | 580.26 |
| Planner correlation assumption | H1 | planner assumes correlation | mitigation_cost | 39,086.43 |
| Planner correlation assumption | H1 | planner assumes independence | mean_lost_packs | 160.13 |
| Planner correlation assumption | H1 | planner assumes independence | p90_lost_packs | 756.89 |
| Planner correlation assumption | H1 | planner assumes independence | mitigation_cost | 42,856.87 |
| Correlation (do nothing) | H2 | correlated | mean_lost_packs | 272.47 |
| Correlation (do nothing) | H2 | correlated | p90_lost_packs | 750.00 |
| Correlation (do nothing) | H2 | correlated | p95_lost_packs | 1,200.00 |
| Correlation (do nothing) | H2 | correlated | prob_any_loss | 0.52 |
| Correlation (do nothing) | H2 | independent | mean_lost_packs | 241.03 |
| Correlation (do nothing) | H2 | independent | p90_lost_packs | 660.00 |
| Correlation (do nothing) | H2 | independent | p95_lost_packs | 1,100.00 |
| Correlation (do nothing) | H2 | independent | prob_any_loss | 0.49 |
| Planner correlation assumption | H2 | planner assumes correlation | mean_lost_packs | 18.73 |
| Planner correlation assumption | H2 | planner assumes correlation | p90_lost_packs | 0.00 |
| Planner correlation assumption | H2 | planner assumes correlation | mitigation_cost | 35,032.73 |
| Planner correlation assumption | H2 | planner assumes independence | mean_lost_packs | 33.41 |
| Planner correlation assumption | H2 | planner assumes independence | p90_lost_packs | 0.00 |
| Planner correlation assumption | H2 | planner assumes independence | mitigation_cost | 35,475.47 |
| Correlation (do nothing) | H3 | correlated | mean_lost_packs | 59.49 |
| Correlation (do nothing) | H3 | correlated | p90_lost_packs | 0.00 |
| Correlation (do nothing) | H3 | correlated | p95_lost_packs | 431.55 |
| Correlation (do nothing) | H3 | correlated | prob_any_loss | 0.06 |
| Correlation (do nothing) | H3 | independent | mean_lost_packs | 39.80 |
| Correlation (do nothing) | H3 | independent | p90_lost_packs | 0.00 |
| Correlation (do nothing) | H3 | independent | p95_lost_packs | 0.00 |
| Correlation (do nothing) | H3 | independent | prob_any_loss | 0.03 |
| Planner correlation assumption | H3 | planner assumes correlation | mean_lost_packs | 37.22 |
| Planner correlation assumption | H3 | planner assumes correlation | p90_lost_packs | 0.00 |
| Planner correlation assumption | H3 | planner assumes correlation | mitigation_cost | 5,913.00 |
| Planner correlation assumption | H3 | planner assumes independence | mean_lost_packs | 36.22 |
| Planner correlation assumption | H3 | planner assumes independence | p90_lost_packs | 0.00 |
| Planner correlation assumption | H3 | planner assumes independence | mitigation_cost | 10,841.44 |
| Correlation (do nothing) | H4 | correlated | mean_lost_packs | 2,019.89 |
| Correlation (do nothing) | H4 | correlated | p90_lost_packs | 2,980.66 |
| Correlation (do nothing) | H4 | correlated | p95_lost_packs | 4,200.00 |
| Correlation (do nothing) | H4 | correlated | prob_any_loss | 0.94 |
| Correlation (do nothing) | H4 | independent | mean_lost_packs | 2,221.56 |
| Correlation (do nothing) | H4 | independent | p90_lost_packs | 3,303.50 |
| Correlation (do nothing) | H4 | independent | p95_lost_packs | 4,200.00 |
| Correlation (do nothing) | H4 | independent | prob_any_loss | 0.98 |
| Planner correlation assumption | H4 | planner assumes correlation | mean_lost_packs | 368.44 |
| Planner correlation assumption | H4 | planner assumes correlation | p90_lost_packs | 1,048.57 |
| Planner correlation assumption | H4 | planner assumes correlation | mitigation_cost | 187,020.83 |
| Planner correlation assumption | H4 | planner assumes independence | mean_lost_packs | 397.79 |
| Planner correlation assumption | H4 | planner assumes independence | p90_lost_packs | 1,300.00 |
| Planner correlation assumption | H4 | planner assumes independence | mitigation_cost | 201,142.82 |
| Correlation (do nothing) | H5 | correlated | mean_lost_packs | 280.22 |
| Correlation (do nothing) | H5 | correlated | p90_lost_packs | 1,064.00 |
| Correlation (do nothing) | H5 | correlated | p95_lost_packs | 1,203.00 |
| Correlation (do nothing) | H5 | correlated | prob_any_loss | 0.35 |
| Correlation (do nothing) | H5 | independent | mean_lost_packs | 297.44 |
| Correlation (do nothing) | H5 | independent | p90_lost_packs | 1,006.00 |
| Correlation (do nothing) | H5 | independent | p95_lost_packs | 1,200.00 |
| Correlation (do nothing) | H5 | independent | prob_any_loss | 0.39 |
| Planner correlation assumption | H5 | planner assumes correlation | mean_lost_packs | 83.16 |
| Planner correlation assumption | H5 | planner assumes correlation | p90_lost_packs | 65.30 |
| Planner correlation assumption | H5 | planner assumes correlation | mitigation_cost | 21,835.81 |
| Planner correlation assumption | H5 | planner assumes independence | mean_lost_packs | 70.67 |
| Planner correlation assumption | H5 | planner assumes independence | p90_lost_packs | 51.00 |
| Planner correlation assumption | H5 | planner assumes independence | mitigation_cost | 11,919.91 |

![correlation](outputs/figures/correlation_tests.png)

- D1: with no mitigation, mean loss is lower when delays are correlated (1,034 vs 1,295). A planner that assumes independence, evaluated in the correlated world, has P90 loss 578 vs 106 for the planner that models correlation.
- D2: with no mitigation, mean loss is lower when delays are correlated (1,683 vs 1,987). A planner that assumes independence, evaluated in the correlated world, has P90 loss 2,617 vs 2,549 for the planner that models correlation.
- D3: with no mitigation, mean loss is higher when delays are correlated (105 vs 53). A planner that assumes independence, evaluated in the correlated world, has P90 loss 0 vs 0 for the planner that models correlation.
- D4: with no mitigation, mean loss is higher when delays are correlated (87 vs 78). A planner that assumes independence, evaluated in the correlated world, has P90 loss 0 vs 0 for the planner that models correlation.
- D5: with no mitigation, mean loss is higher when delays are correlated (221 vs 197). A planner that assumes independence, evaluated in the correlated world, has P90 loss 214 vs 141 for the planner that models correlation.
- D6: with no mitigation, mean loss is lower when delays are correlated (974 vs 1,269). A planner that assumes independence, evaluated in the correlated world, has P90 loss 0 vs 28 for the planner that models correlation.
- H1: with no mitigation, mean loss is lower when delays are correlated (1,681 vs 1,740). A planner that assumes independence, evaluated in the correlated world, has P90 loss 757 vs 580 for the planner that models correlation.
- H2: with no mitigation, mean loss is higher when delays are correlated (272 vs 241). A planner that assumes independence, evaluated in the correlated world, has P90 loss 0 vs 0 for the planner that models correlation.
- H3: with no mitigation, mean loss is higher when delays are correlated (59 vs 40). A planner that assumes independence, evaluated in the correlated world, has P90 loss 0 vs 0 for the planner that models correlation.
- H4: with no mitigation, mean loss is lower when delays are correlated (2,020 vs 2,222). A planner that assumes independence, evaluated in the correlated world, has P90 loss 1,300 vs 1,049 for the planner that models correlation.
- H5: with no mitigation, mean loss is lower when delays are correlated (280 vs 297). A planner that assumes independence, evaluated in the correlated world, has P90 loss 51 vs 65 for the planner that models correlation.

## Gating parts and centerpiece

![gating](outputs/figures/gating_D1.png)

![centerpiece](outputs/figures/centerpiece_D1.png)

## Limitations

- All operations are simulated; delay distributions are placeholders until `calibrate.py` is run on real shipment data, and even then the source data is not battery parts.
- Decisions are made once at week 0 (static two-stage). Weekly rolling re-planning is a v2 item.
- Execution schedules production optimally against realized supply, which flatters every policy equally.
- Capacity lost to cuts and scrap is not recovered within the horizon; backlog recovery is not modeled.
- Costs, penalty per pack, BOM quantities and cover levels are hypothetical.
