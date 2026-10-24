# Power BI build guide

Python precomputes every scenario. Power BI is a **scenario explorer**: it filters precomputed results, it doesn't run the optimizer. Describe it that way in the video and README.

Budget about 4–6 hours. All files are in `outputs/powerbi/`.

## 1. Load the data

**Get Data → Folder → `outputs/powerbi` → Combine & Transform** won't work (different schemas). Instead use **Get Data → Text/CSV** once per file and load all 20 files. In Power Query, check types:

- IDs (`*_id`, `variant`, `action`, `split`): Text
- `week`, `realization`, `sort`: Whole number
- Dates in `fact_receipts`: Date
- Everything else numeric: Decimal

## 2. Relationships (Model view)

Single direction, one-to-many, dimension → fact:

| From (1) | To (*) |
|---|---|
| `dim_scenario[scenario_id]` | `fact_policy_evaluation`, `fact_realization_results`, `fact_weekly_trace`, `fact_inventory_trace`, `fact_gating_frequency`, `fact_gating_component`, `fact_actions`, `fact_budget_curve` |
| `dim_policy[policy_id]` | `fact_policy_evaluation`, `fact_realization_results`, `fact_weekly_trace`, `fact_inventory_trace`, `fact_gating_frequency`, `fact_gating_component`, `fact_actions` |
| `dim_component[component_id]` | `fact_inventory_trace`, `fact_gating_frequency`, `fact_gating_component`, `fact_actions`, `fact_bom`, `fact_receipts`, `fact_component_exposure` |
| `dim_supplier[supplier_id]` | `fact_receipts`, `dim_component[primary_supplier_id]` |
| `dim_week[week]` | `fact_weekly_trace`, `fact_inventory_trace`, `fact_gating_frequency`, `fact_actions` |

`fact_actions` also contains policy IDs `P5-corr` and `P5-indep` from the correlation test. They won't match `dim_policy`, which is intended; show them only on the Assumptions page.

Sort `dim_policy[name]` by `dim_policy[sort]` and `dim_scenario[name]` by `dim_scenario[sort]` (Column tools → Sort by column).

## 3. Measures

Create a table `_Measures` (Enter data, one empty column) and add:

```DAX
Lost Packs (mean) = AVERAGE ( fact_realization_results[lost_packs] )

Lost Packs (P90) =
PERCENTILEX.INC ( fact_realization_results, fact_realization_results[lost_packs], 0.9 )

Plan Attainment =
DIVIDE ( SUM ( fact_realization_results[built_packs] ), SUM ( fact_realization_results[plan_packs] ) )

Backlog Pack-Weeks = AVERAGE ( fact_realization_results[backlog_pack_weeks] )

Mitigation Spend = AVERAGE ( fact_realization_results[mitigation_cost] )

Expected Total Cost = AVERAGE ( fact_realization_results[objective] )

Budget Used % = DIVIDE ( [Mitigation Spend], 250000 )

Packs Protected vs Do Nothing =
VAR base = CALCULATE ( [Lost Packs (mean)], dim_policy[policy_id] = "P1" )
RETURN base - [Lost Packs (mean)]

Oracle Capture =
VAR base   = CALCULATE ( [Lost Packs (mean)], dim_policy[policy_id] = "P1" )
VAR oracle = CALCULATE ( [Lost Packs (mean)], dim_policy[policy_id] = "P7" )
RETURN DIVIDE ( base - [Lost Packs (mean)], base - oracle )

VSS ($) =
CALCULATE ( [Expected Total Cost], dim_policy[policy_id] = "P4" )
    - CALCULATE ( [Expected Total Cost], dim_policy[policy_id] = "P5" )

Shortfall vs Plan =
SUM ( fact_weekly_trace[cum_built] ) - SUM ( fact_weekly_trace[cum_plan] )

Gated Share = MAX ( fact_gating_component[share_of_realizations_gated] )

Weeks of Cover = AVERAGE ( fact_inventory_trace[weeks_of_cover] )

Action Spend = SUM ( fact_actions[cost] )

OTIF = AVERAGE ( dim_supplier[otif_rate] )

Simulated Label = "Simulated data. Delay behavior calibrated to public shipment records."
```

Format: currency for spend and cost; percentage for Attainment, Budget Used, Oracle Capture, OTIF; whole numbers for packs.

If you haven't run calibration yet, change the label to "placeholder delay parameters." Don't claim calibration you haven't done.

## 4. Pages

Every page gets a footer text box bound to `[Simulated Label]`, plus a **scenario slicer** (single select, `dim_scenario[name]`) synced across pages (View → Sync slicers).

### Page 1: Executive Overview

- **Cards:** Lost Packs (mean) for Do nothing and for Stochastic LP (two cards, each with a visual-level filter on policy), Packs Protected vs Do Nothing, Mitigation Spend, Oracle Capture.
- **Clustered bar:** `dim_policy[name]` × `[Expected Total Cost]`, sorted by policy order.
- **Bar:** top 5 gating parts. `dim_component[name]` × `[Gated Share]`, filtered to policy P1, Top N = 5.
- **Text box:** one sentence on the scenario (use `dim_scenario[description]` in a card).

### Page 2: Supplier Performance

- **Table:** `dim_supplier` supplier_id, supplies, lane_id, tier2_id, otif_rate, late_rate, sd_lead_time_days, partial_rate. Conditional formatting on otif_rate.
- **Scatter:** x = late_rate, y = sd_lead_time_days, size = spend, legend = lane_id.
- **Table:** `fact_shared_dependency` (dependency, suppliers exposed, single-sourced components, weekly spend exposed).
- **Key insight table (scenario-aware):** parts that stop the line in the selected scenario, with their supplier's late rate and starting stock. Late rate alone is a poor guide; stock cover decides. Compare with Page 3.

### Page 3: Production Risk

- **Line chart:** `dim_week[week_label]` × `[Shortfall vs Plan]`, legend = policy (filter to P1, P2, P5, P7). Add a slicer on `fact_weekly_trace[realization_type]` (median / severe P90); default to severe, since in the median realization most policies show no shortfall.
- **Matrix heatmap:** rows `dim_component[name]`, columns `dim_week[week_label]`, values `SUM(fact_gating_frequency[share_of_realizations])`, filtered to P1. Background conditional formatting. Filter rows where total > 0.
- **Line chart:** weeks of cover for the top gating parts. `fact_inventory_trace`, policy P1, same `realization_type` slicer, components filtered by the Top N gated parts.

### Page 4: Scenario Explorer

- **Policy slicer** (multi-select).
- **Clustered bar:** policy × `[Lost Packs (mean)]` and `[Lost Packs (P90)]`.
- **Table:** `fact_actions` component name, action, week, quantity, cost, for the selected policies. This is "what the plan actually buys."
- **Line chart:** `fact_budget_curve`, budget on x, stochastic_mean_lost, stochastic_p90_lost, oracle_mean_lost, do_nothing_mean_lost. Every scenario has a curve (budgets $0 to $600K).
- **Card:** `[VSS ($)]`.
- **Drill-through:** optional; left out of the final dashboard to keep it simple.

### Page 5: Assumptions & Limitations

- Text boxes summarizing `ASSUMPTIONS.md` sections 1–6 (short bullets).
- **Table:** `fact_stress_tests`.
- **Image:** `outputs/figures/correlation_tests.png`.
- State plainly: static week-0 decisions; placeholder or calibrated delays (say which); hypothetical costs and penalty.

## 5. Export

- File → Export → PDF (for reviewers who don't use Power BI).
- Save the .pbix in `powerbi/` in the repo.
- Screenshot Page 4 with D1 selected for the README.
